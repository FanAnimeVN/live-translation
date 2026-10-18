"""RAM-only, model-free reproduction of a real text crop's lettering decision.

Supply the detector's unpadded box, not a cleaned or altered image. This probe
does not grade OCR or write private pixels. --assert-integrated is a narrow
regression gate for a crop visually verified to be inside a closed balloon.
"""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from manga_live.ocr import decode_image, group_regions, polygon, LAYOUT_VERSION,PaddleDetector


def selected_geometry(image_path, box, replay=None, page_id=None,*,experimental_source_support=False,native_default=False):
    """Use exact full-page detector evidence, never an invented union box.

    The single authored-box path remains useful for synthetic probes. A real
    multi-column replay must bind its image and all raw PP lines to the audited
    dataset fingerprint, then select an unchanged production source bbox.
    """
    image_path = Path(image_path).resolve(strict=True)
    if experimental_source_support and native_default:
        raise ValueError("Choose the native default or an explicit experiment, not both")
    if replay is None:
        if experimental_source_support or native_default:
            raise ValueError("Source-support experiment requires retained real detector evidence")
        image = decode_image(image_path.read_bytes())
        return image, group_regions(image, [{"polygon": polygon(box), "score": .95}])
    from probe_balloon_footprints import read_report
    from benchmark import DirectoryDataset, audit, dataset_fingerprint
    evidence = read_report(replay)
    with DirectoryDataset(image_path.parent) as dataset:
        _, _, pages = audit(dataset)
        fingerprint = dataset_fingerprint(dataset)
    selected = [(meta, image) for meta, image, _ in pages if meta["page_id"] == page_id]
    rows = [row for row in evidence.get("pages", []) if row.get("page") == page_id]
    if (fingerprint != evidence.get("input_fingerprint_sha256") or len(selected) != 1 or len(rows) != 1
            or evidence.get("detector") != "PP-OCRv5_mobile_det"
            or image_path != (image_path.parent / selected[0][0]["image_file"]).resolve()):
        raise ValueError("Selected source image/page and recorded PP evidence differ")
    image = selected[0][1]
    raw = rows[0].get("detector_evidence", {}).get("raw_detections")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 512:
        raise ValueError("Missing bounded raw detector lines")
    if any("pass" in member for member in raw):
        from probe_tiled_detection import VERSION
        if evidence.get("experimental_detector",{}).get("kind")!=VERSION:
            raise ValueError("Unknown source plane; do not substitute tile candidates for production lines")
        raw=[member for member in raw if member.get("pass")=="full"]
        if not raw:raise ValueError("Missing unchanged full-page detector source")
    x,y,w,h=box
    x,y=max(0,x-3),max(0,y-3)
    expected=[x,y,min(image.width-x,w+6),min(image.height-y,h+6)]
    if native_default:
        # Retained upstream model output, real native detection/grouping path.
        # This is a geometry replay, not a fresh inference-quality claim.
        detector=PaddleDetector(ROOT/"models/detector")
        detector.model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(json={"res":{
            "dt_polys":[r["polygon"] for r in raw],"dt_scores":[r["score"] for r in raw]}})])
        grouped=detector.detect(image)
    else:
        grouped=group_regions(image,raw,experimental_source_support=experimental_source_support)
    regions = [r for r in grouped if r["bbox"] == expected]
    if len(regions) != 1:
        raise ValueError("Selection must match exactly one unchanged production OCR box")
    return image, regions


def trace_decisions(evidence):
    """Only bounded numeric diagnostics, never pixel arrays or source text."""
    def trace(frame, event, result):
        if frame.f_code.co_name not in ("group_regions", "balloon_lettering", "outline_only_overhang"):
            return
        # sys.settrace's global call hook must install a per-frame callback.
        # Returning None on "call" silently disables all subsequent returns.
        if event != "return":return trace
        values = frame.f_locals
        if frame.f_code.co_name == "outline_only_overhang":
            import numpy as np
            x, y, w, h = values["box"]
            outside = values["outside"]
            enclosed = values["enclosed"][y:y+h, x:x+w]
            row = {"seam": "outline_only_overhang", "return_line": frame.f_lineno,
                "accepted": bool(result), "outside_fraction": float(outside.mean()),
                "outline_label_count": len(values.get("outline_labels", []))}
            if "difference" in values:
                difference = values["difference"][y:y+h, x:x+w]
                row["inner_band_contrast_counts"] = {threshold: int((outside & (enclosed > 0) & (difference > threshold)).sum()) for threshold in (15, 35, 80)}
            if "outline_labels" in values:
                import cv2
                foreign = values["foreign"]
                linked = np.isin(values["ink_labels"], values["outline_labels"])
                unsupported = foreign & ~linked[y:y+h, x:x+w]
                row["unlinked_pixel_count"] = int(unsupported.sum())
                if unsupported.any():
                    distances = cv2.distanceTransform((~linked).astype("uint8"), cv2.DIST_L2, 5)
                    row["unlinked_max_contrast"] = float(difference[unsupported].max())
                    row["unlinked_max_distance_to_outline"] = float(distances[y:y+h, x:x+w][unsupported].max())
            evidence.append(row)
            return
        if frame.f_code.co_name == "group_regions":
            evidence.append({"seam": "group_regions", "groups":
                [{"surface": key[0], "lines": len(items)}
                 for key, items in values.get("groups", {}).items()], "safe": values.get("safe")})
            return
        row = {"seam": "balloon_lettering", "return_line": frame.f_lineno,
            "accepted": result is not None,
            "component_box": [values.get(k) for k in ("bx", "by", "bw", "bh")]}
        if "ink_stats" in values:
            row["ink_components"] = [{"box": [int(ix), int(iy), int(cw), int(ch)], "area": int(area)}
                for ix, iy, cw, ch, area in values["ink_stats"][1:]]
            row["selected_zone"] = values.get("zone")
        if "background" in values:
            import numpy as np
            rgb, component, background = (values[k] for k in ("rgb", "component", "background"))
            row["background"] = background.tolist()
            row["flatness_p95"] = float(np.percentile(np.abs(rgb[component > 0].astype(float) - background), 95))
            import cv2
            row["flatness_away_from_edges"] = []
            for radius in (1, 2, 3, 4):
                stable = cv2.erode(component, np.ones((3, 3), np.uint8), iterations=radius) > 0
                sample = rgb[stable].astype(float)
                row["flatness_away_from_edges"].append({"radius": radius,
                    "samples": int(stable.sum()),
                    "p95": float(np.percentile(np.abs(sample - background), 95)) if sample.size else None})
        if "roi" in values:
            row["crop_outside_safe_pixels"] = int((values["roi"] == 0).sum())
            if (values["roi"] == 0).any():
                import numpy as np
                x, y, w, h = (values[k] for k in ("x", "y", "w", "h"))
                bx, by = values["bx"], values["by"]
                outside = values["roi"] == 0
                crop_component = values["component"][y-by:y-by+h, x-bx:x-bx+w]
                pixels = values["rgb"][y-by:y-by+h, x-bx:x-bx+w][outside]
                row["outside_not_background_component"] = int((crop_component[outside] == 0).sum())
                row["outside_rgb_range"] = [int(pixels.min()), int(pixels.max())]
                row["outside_dark_pixels"] = int((pixels.mean(axis=1) < 175).sum())
                import cv2
                filled = np.zeros_like(values["component"])
                cv2.drawContours(filled, [values["contour"]], -1, 1, cv2.FILLED)
                filled_crop = filled[y-by:y-by+h, x-bx:x-bx+w]
                row["outside_dark_inside_filled_contour"] = int(((filled_crop[outside] > 0) & (pixels.mean(axis=1) < 175)).sum())
                distances = cv2.distanceTransform(1-filled, cv2.DIST_L2, 5)
                row["max_outside_distance_to_contour"] = float(distances[y-by:y-by+h, x-bx:x-bx+w][outside].max())
        if "source_size" in values:
            row["source_size"] = float(values["source_size"])
        evidence.append(row)
    return trace


def run(args):
    evidence = []
    if args.diagnose:
        sys.setprofile(trace_decisions(evidence))
    try:
        image, regions = selected_geometry(args.image,args.box,args.detector_replay,args.page)
    finally:
        sys.setprofile(None)
    region = regions[0] if len(regions) == 1 else {}
    balloon = region.get("balloon", {})
    integrated = bool(balloon.get("erasePolygons")) and region.get("overlay") == "white"
    print(json.dumps({"layout_version": LAYOUT_VERSION, "image_size": image.size,
        "detector_box": args.box, "region_count": len(regions),
        "ocr_box": region.get("bbox"), "integrated": integrated,
        "text_box": balloon.get("textBox"), "background": balloon.get("background"),
        "erase_polygon_count": len(balloon.get("erasePolygons", [])), "decisions": evidence}))
    if args.assert_integrated and not integrated:
        raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--box", required=True, type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--assert-integrated", action="store_true")
    parser.add_argument("--detector-replay",help="Exact raw PP lines from a fingerprint-bound private comparator")
    parser.add_argument("--page",help="Required page ID for --detector-replay")
    parser.add_argument("--diagnose", action="store_true")
    run(parser.parse_args())
