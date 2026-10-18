"""Small, conservative text-on-art cleanup. All raster data is transient.

This is classical local inpainting, not a generative model or exact recovery
of the author's hidden drawing. Uncertain/large/structural regions stay as
reversible annotations. No files, network, logging, or persistent image cache.
"""
import base64
import io
import math

CLEANUP_VERSION = "opencv-telea-v1"
MAX_PATCH_BYTES = 384 * 1024
MAX_JOB_PATCH_BYTES = 2 * 1024 * 1024


def continue_parallel_texture(rgb, mask, fallback):
    """Continue small, coherent line textures (e.g. rain), not semantic art.

    A Hough direction alone is insufficient: a projected color profile must
    also explain the unmasked pixels. Otherwise keep the standard inpainting.
    This bounded classical estimator never invents objects or edits unmasked
    pixels. It is deliberately unsuitable for faces or general backgrounds.
    """
    import cv2
    import numpy as np
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    safe = cv2.dilate(mask, np.ones((3, 3), "uint8")) == 0
    known = grey[safe]
    if known.size < 400 or not 3 < float(known.std()) < 35:
        return fallback
    edges = cv2.Canny(grey, 15, 45); edges[~safe] = 0
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 12, minLineLength=18, maxLineGap=2)
    if lines is None or len(lines) < 4:
        return fallback
    vectors = lines[:, 0, 2:].astype(float)-lines[:, 0, :2]
    vertical = np.abs(vectors[:, 1]) >= np.abs(vectors[:, 0])
    if max(vertical.mean(), 1-vertical.mean()) < 0.85:
        return fallback
    use_vertical = vertical.mean() > 0.5
    vectors = vectors[vertical if use_vertical else ~vertical]
    slopes = vectors[:, 0]/vectors[:, 1] if use_vertical else vectors[:, 1]/vectors[:, 0]
    slope = float(np.median(slopes))
    if float(np.percentile(np.abs(slopes-slope), 90)) > 0.10:
        return fallback
    yy, xx = np.indices(grey.shape)
    across, along = (xx, yy) if use_vertical else (yy, xx)
    values = grey[safe].astype(float)
    best = None
    # Quarter-pixel phases prevent a thin line from being split into two bins.
    # Fixed work bound: coarse/refine 7 slopes x 4 phases, not an unbounded
    # optimization. Sub-degree precision matters for one-pixel rain lines.
    for radius in (0.025,0.025/6):
        centre = best[3] if best else slope
        for candidate in np.linspace(centre-radius, centre+radius, 7):
            projected = across-candidate*along
            for phase in (0, 0.25, 0.5, 0.75):
                bins = np.floor(projected+phase).astype("int32")
                bins -= bins.min(); indexes = bins[safe]
                count = np.bincount(indexes)
                total = np.bincount(indexes, weights=values, minlength=len(count))
                squares = np.bincount(indexes, weights=values*values, minlength=len(count))
                mse = float((squares-total*total/np.maximum(1, count)).sum()/len(values))
                if best is None or mse < best[0]:best = (mse, bins, count, candidate)
    mse, bins, count, _ = best
    # One-pixel raster lines can cross projected bins even at the correct
    # sub-degree slope. Allow a small absolute quantization error while still
    # requiring the profile to explain at least 85% of known-pixel variance.
    # This does not accept arbitrary noisy artwork as a parallel texture.
    if mse > 12 or mse > float(values.var())*0.15:
        return fallback
    result = fallback.copy()
    flat_bins = bins[safe]; colors = rgb[safe]
    for index in np.unique(bins[mask > 0]):
        if index >= len(count) or count[index] < 8:
            continue
        source = colors[flat_bins == index]
        if len(source):result[(bins == index) & (mask > 0)] = np.median(source, axis=0).astype("uint8")
    return result


def lettering_box(image, box, source_size):
    x, y, w, h = box
    width, height = min(image.width,max(w,int(source_size*3))), min(image.height,max(h,int(source_size*3.5)))
    return [max(0,min(image.width-width,int(x+w/2-width/2))),
            max(0,min(image.height-height,int(y+h/2-height/2))),width,height]


def render_patch(image, region, cancel=None, max_bytes=MAX_PATCH_BYTES):
    if cancel is not None and cancel.is_set():
        return None
    if (region.get("overlay") != "label" or region.get("balloon") or region.get("review") or
            region.get("type") == "sfx" or not region.get("ja") or region.get("score", 1) < 0.65):
        return None
    box = region.get("bbox")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in box):
        return None
    x, y, w, h = map(int, box)
    # A manual full-page selection must not be interpreted as a text mask.
    if (min(w, h) < 8 or max(w, h) > 900 or w*h > 90000 or w*h > image.width*image.height*0.28 or
            x < 0 or y < 0 or x+w > image.width or y+h > image.height):
        return None
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None  # Translation remains readable without optional cleanup.
    from PIL import Image

    pad = 12
    left, top = max(0, x-pad), max(0, y-pad)
    right, bottom = min(image.width, x+w+pad), min(image.height, y+h+pad)
    rgb = np.asarray(image.crop((left, top, right, bottom))).copy()
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    background = cv2.medianBlur(grey, 15).astype("int16")
    # Prefer saturated glyph ink over midtone rain/screentone. Components
    # crossing the evidence area are structural lines, not isolated letters.
    options = []
    for light_ink in (False, True):
        candidate = (((grey > 180) & (grey.astype("int16")-background > 35)) if light_ink else
                     ((grey < 85) & (background-grey.astype("int16") > 35))).astype("uint8")
        count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate)
        selected = np.zeros_like(candidate)
        sizes = []
        for idx in range(1, count):
            cx, cy, cw, ch, area = map(int, stats[idx])
            if (area < 3 or max(cw, ch) < 4 or max(cw, ch) > 64 or
                    max(cw/ch, ch/cw) > 12 or area/(cw*ch) < 0.08):
                continue
            if (cx < x-left-2 or cy < y-top-2 or cx+cw > x-left+w+2 or cy+ch > y-top+h+2):
                continue
            selected[labels == idx] = 1
            sizes.append(max(cw, ch))
        occupancy = int(selected.sum())/(w*h)
        if len(sizes) < 3 or not 0.015 <= occupancy <= 0.42:
            continue
        source_size = float(np.percentile(sizes, 80))
        if source_size < 8 or max(sizes) > source_size*2.4:
            continue
        priority = occupancy + (0.3 if light_ink == (float(np.median(grey)) < 128) else 0)
        options.append((priority, light_ink, selected, source_size))
    if not options:
        return None
    _, light_ink, selected, source_size = max(options, key=lambda item: item[0])
    # Both saturated colors can belong to the same outlined glyph. Selecting
    # only its black outline leaves the white centre visibly on the page.
    for _, _, other, _ in options:
        selected |= other
    # Remove antialiasing and the opposite-color outline only next to verified
    # ink. Do not flood-fill the white panel/surrounding rain as a text halo.
    near = cv2.dilate(selected, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    halo = (background-grey.astype("int16") > 12) if light_ink else (grey.astype("int16")-background > 12)
    mask = cv2.dilate(selected | (near & halo.astype("uint8")),
                      cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) * 255
    if int((mask > 0).sum()) > w*h*0.68:
        return None
    if cancel is not None and cancel.is_set():
        return None
    restored = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    restored = continue_parallel_texture(rgb, mask, restored)
    # Explicitly preserve every pixel outside the text mask, even if the
    # underlying implementation changes. The transparent patch reveals the
    # unchanged source, not a replacement rectangular crop of the artwork.
    restored[mask == 0] = rgb[mask == 0]
    rgba = np.dstack((restored, mask))
    rgba[mask == 0, :3] = 0
    buffer = io.BytesIO()
    Image.fromarray(rgba).save(buffer, format="PNG", compress_level=3)
    data = buffer.getvalue()
    if len(data) > min(MAX_PATCH_BYTES, max_bytes) or (cancel is not None and cancel.is_set()):
        return None
    return {"regionId": region["id"], "bbox": [left, top, right-left, bottom-top],
            "textBox": lettering_box(image, box, source_size),
            "dataUrl": "data:image/png;base64,"+base64.b64encode(data).decode("ascii"),
            "ink": "#ffffff" if light_ink else "#111111",
            "stroke": "#111111" if light_ink else "#ffffff",
            "sourceFontPx": round(source_size, 2), "method": CLEANUP_VERSION}
