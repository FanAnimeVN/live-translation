import io
import math
import os
import re
import time
from pathlib import Path
from .errors import AppError, require
from .expression import bind_expression

# Compatibility identity for source grouping/crops and accepted text caches.
# Presentation-only changes must not force paid OCR/translation regeneration.
LAYOUT_VERSION = "balloon-mask-v20-source-footprint-corners"
PRESENTATION_VERSION = "balloon-mask-v21-actual-source-support"
EXPERIMENTAL_LAYOUT_VERSION = "balloon-mask-v17-aligned-open-text-experiment"
PAIR_SCALE_GROUPING_VERSION = "pair-scale-v1-disjoint-parent-frame-experiment"
SOURCE_GROUPING_VERSION = "paddle-pair-scale-v1-disjoint-parent-frame"
OCR_PARTITION_VERSION = "ocr-crop-partition-v1"
OCR_COVERAGE_VERSION = "ocr-coverage-v4-retain-unreadable-source"


def decode_image(data):
    from PIL import Image
    require(isinstance(data, bytes) and 0 < len(data) <= 8 * 1024 * 1024, "IMAGE_SIZE")
    try:
        image = Image.open(io.BytesIO(data))
        require(image.format in ("PNG", "JPEG", "WEBP"), "IMAGE_FORMAT")
        require(image.width * image.height <= 12000000 and max(image.size) <= 8000, "IMAGE_SIZE")
        image.load()
        return image.convert("RGB")
    except AppError:
        raise
    except Exception:
        raise AppError("IMAGE_FORMAT", "Không đọc được ảnh.")


def blank_crop(image):
    import numpy as np
    pixels = np.asarray(image.convert("L"))
    return pixels.size == 0 or float(pixels.std()) < 3 or float((pixels < 180).mean()) < 0.001


def checked_ocr_results(values,count):
    # zip silently truncates missing/extra replies and accepts a bare string
    # as individual characters. Never declare such a batch source-complete.
    # Empty strings are valid blank/unrecognized results, not missing slots.
    require(isinstance(values,(list,tuple)) and len(values)==count and
            all(isinstance(value,str) for value in values),"OCR_RESULT",
            "OCR trả về thiếu hoặc sai cấu trúc. Thử lại; batch này chưa được đánh dấu hoàn tất.")
    return values


class MangaEngine:
    name = "manga-ocr/0.1.14-local-v3"
    def __init__(self, model_dir, threads=4):
        self.path, self.threads, self.model = Path(model_dir), threads, None

    def load(self):
        if self.model is None:
            require((self.path / "config.json").exists() and (self.path / "pytorch_model.bin").exists(),
                    "NO_MODEL", "Chưa tải manga-ocr. Chạy bộ cài model trước.")
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            import torch
            from loguru import logger
            logger.remove()  # Library logs must never include recognized text.
            from .ocr_backend import LocalMangaRecognizer
            torch.set_num_threads(self.threads)
            self.model = LocalMangaRecognizer(self.path)

    def recognize(self, image):
        if blank_crop(image):
            return ""
        self.load()
        return checked_ocr_results([self.model(image)],1)[0]

    def recognize_many(self,images):
        if not images:
            return []
        results=[""]*len(images)
        valid=[(i,image) for i,image in enumerate(images) if not blank_crop(image)]
        if valid:
            self.load()
            decoded=checked_ocr_results(self.model.recognize_many([image for _,image in valid]),len(valid))
            for (idx,_),value in zip(valid,decoded):
                results[idx]=value
        return results


def rect(poly):
    xs, ys = zip(*poly)
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def polygon(box):
    x, y, w, h = box
    return [[x, y], [x+w, y], [x+w, y+h], [x, y+h]]


class PaddleDetector:
    name = "PP-OCRv5_mobile_det"
    presentation_version = PRESENTATION_VERSION
    source_version = SOURCE_GROUPING_VERSION
    accepted_source_versions = (LAYOUT_VERSION,)
    def __init__(self, model_dir, threads=4):
        self.path, self.threads, self.model = Path(model_dir), threads, None

    def detect_raw(self,image,*,limit_side_len=None,limit_type=None,box_threshold=None):
        """Source line polygons before grouping; overrides are for probes.

        Runtime calls use the pinned model's defaults. Keeping raw geometry
        separate lets a benchmark distinguish detection misses from grouping.
        No source pixels or polygons are retained on this detector instance.
        """
        import numpy as np
        require(limit_side_len is None or (type(limit_side_len) is int and 64<=limit_side_len<=2048),"DETECTOR_SIZE")
        require(limit_type is None or (limit_side_len is not None and type(limit_type) is str and
                                      limit_type in ("max","resize_long")),"DETECTOR_SIZE")
        # DBPostProcess discards boxes before dt_scores is returned. Lowering
        # only our .35 guard cannot recover them. Probe the upstream box gate,
        # not the pixel-map threshold, and never mutate the resident model.
        require(box_threshold is None or
                (type(box_threshold) in (int,float) and 0.35<=float(box_threshold)<=0.8),
                "DETECTOR_THRESHOLD", "Ngưỡng detector ngoài phạm vi thử nghiệm.")
        require((self.path / "inference.pdiparams").exists(), "NO_MODEL", "Chưa tải detector chữ.")
        if self.model is None:
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            os.environ["PADDLE_PDX_CACHE_HOME"] = str(self.path.parent.parent/"runtime/paddlex")
            try:
                from paddleocr import TextDetection
                self.model = TextDetection(model_name=self.name, model_dir=str(self.path), device="cpu",
                                           cpu_threads=self.threads, enable_mkldnn=False)
            except ImportError:
                raise AppError("DEPENDENCY", "Chưa cài runtime PaddleOCR; có thể chọn vùng thủ công.")
        options={} if limit_side_len is None else {"limit_side_len":limit_side_len}
        if limit_type is not None:options["limit_type"]=limit_type
        if box_threshold is not None:options["box_thresh"]=float(box_threshold)
        outputs = self.model.predict(np.asarray(image)[:, :, ::-1], batch_size=1,**options)
        result = []
        for output in outputs:
            payload = output.json
            if callable(payload):
                payload = payload()
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            data = payload.get("res", payload)
            for poly, score in zip(data["dt_polys"], data["dt_scores"]):
                if float(score) >= 0.35:
                    result.append({"polygon": [[float(x), float(y)] for x, y in poly], "score": float(score)})
        return result

    def detect_plan(self,image):
        """One detector plane, explicit source grouping and inference plan.

        Retain diagnostic members only while proving parent lineage; never
        publish them to prompts, renderer, source keys or story memory.
        """
        raw=self.detect_raw(image)
        parents=group_regions(image,raw,include_source_members=True,experimental_source_support=True)
        regions=group_regions(image,raw,include_source_members=True,experimental_source_support=True,
                              experimental_pair_scale=True)
        # Preserve the pre-existing coverage bound; a split cannot displace
        # an otherwise retained source at the 64-region native boundary.
        if len(parents)>64 or len(regions)>64:
            regions=parents[:64];crops,evidence=partition_ocr_boxes(image,regions)
        else:crops,evidence=partition_ocr_boxes(image,regions,source_parents=parents)
        return [{k:v for k,v in region.items() if k!='sourceMembers'} for region in regions],crops,evidence

    def detect(self,image):
        return self.detect_plan(image)[0]


class OpenCvDetector:
    """Explicit experimental fallback; never presented as the trained detector."""
    name = "opencv-experimental"
    def detect(self, image):
        import cv2
        import numpy as np
        grey = np.asarray(image.convert("L"))
        ink = cv2.threshold(grey, 170, 255, cv2.THRESH_BINARY_INV)[1]
        count, labels, stats, _ = cv2.connectedComponentsWithStats(ink)
        glyphs = np.zeros_like(ink)
        for x, y, w, h, area in stats[1:]:
            if 2 <= w <= 55 and 3 <= h <= 65 and 4 <= area <= 1800 and area/(w*h) > 0.08:
                glyphs[y:y+h, x:x+w] |= ink[y:y+h, x:x+w]
        connected = cv2.dilate(glyphs, np.ones((9, 5), np.uint8))
        contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if 10 <= w <= image.width*0.4 and 16 <= h <= image.height*0.4:
                found.append({"polygon": polygon([x,y,w,h]), "score": 0.4})
        return group_regions(image, found)[:80]


def balloon_lettering(image, labels, stats, label, box, *, source_boxes=None,source_support_boxes=None):
    """Conservative empty-space geometry, not segmentation or inpainting.

    Return only coordinates/color, never pixels. Source OCR crop is unchanged.
    A local filled outer contour is used to check safety, not painted wholesale.
    Unequal-column recovery additionally requires actual source footprints;
    it cannot erase nearby unaccounted ink to make an empty union corner fit.
    """
    import cv2
    import numpy as np
    bx,by,bw,bh,_=map(int,stats[label])
    if bx<=1 or by<=1 or bx+bw>=image.width-1 or by+bh>=image.height-1:
        return None
    # Read a narrow ring OUTSIDE the background component so detector padding
    # on a source outline can be proved/rejected by actual pixels. This is
    # analysis-only: the filled contour and protected erosion still define
    # every writable pixel, and outline_only_overhang keeps its 8px/10% gate.
    right,bottom=min(image.width,bx+bw+8),min(image.height,by+bh+8)
    bx,by=max(0,bx-8),max(0,by-8)
    bw,bh=right-bx,bottom-by
    component=(labels[by:by+bh,bx:bx+bw]==label).astype("uint8")
    contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not contours:return None
    contour=max(contours,key=cv2.contourArea)
    interior=np.zeros_like(component)
    cv2.drawContours(interior,[contour],-1,1,cv2.FILLED)
    enclosed=interior.copy()
    # This is a LOCAL array cropped to the background component. OpenCV's
    # neutral erosion border treats pixels beyond that array as foreground,
    # so a rectangular narration border's JPEG fringe can survive at x=0.
    # The outside is unknown, not safe balloon interior.
    interior=cv2.erode(interior,np.ones((3,3),np.uint8),iterations=2,
                       borderType=cv2.BORDER_CONSTANT,borderValue=0)
    # A union of line boxes can have empty corners very close to the curved
    # outline. Judge those corners by pixels, not the rectangular enclosure:
    # actual ink/art outside the safe interior must still reject integration.
    x,y,w,h=map(int,box)
    if x<bx or y<by or x+w>bx+bw or y+h>by+bh:
        return None
    rgb=np.asarray(image)[by:by+bh,bx:bx+bw]
    # JPEG ringing/antialiasing belongs to the glyph/outline edge, not the
    # paper. Scanned glyph ringing can extend four source pixels, matching
    # the bounded erasure halo. Exclude only that narrow edge neighbourhood,
    # never search for an arbitrary bright patch. Each candidate must retain
    # >=20% of the SAME component and meet the same six-level p95 tolerance.
    # Real gradients/textures away from glyphs must still reject integration.
    for radius in (2,3,4):
        stable=cv2.erode(component,np.ones((3,3),np.uint8),iterations=radius,
                         borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
        if int(stable.sum())<max(64,int(component.sum()*0.2)):
            return None
        paper=rgb[stable].astype(float)
        background=np.median(paper,axis=0).astype(int)
        if float(np.percentile(np.abs(paper-background),95))<=6:
            break
    else:
        return None
    footprint_constrained=False
    roi=interior[y-by:y-by+h,x-bx:x-bx+w]
    if not roi.all():
        outside=roi==0
        same_component=component[y-by:y-by+h,x-bx:x-bx+w]
        corner_pixels=rgb[y-by:y-by+h,x-bx:x-bx+w][outside].astype(float)
        flat=same_component[outside].astype(bool)&(np.abs(corner_pixels-background).max(axis=1)<=6)
        footprints=([[sx-bx,sy-by,sw,sh] for sx,sy,sw,sh in source_boxes]
                    if source_boxes and len(source_boxes)>1 else None)
        supports=([[sx-bx,sy-by,sw,sh] for sx,sy,sw,sh in source_support_boxes]
                  if source_support_boxes and len(source_support_boxes)>1 else None)
        if not flat.all():
            local_box=[x-bx,y-by,w,h]
            if not outline_only_overhang(rgb,component,enclosed,interior,background,local_box):
                if not footprints or not outline_only_overhang(rgb,component,enclosed,interior,background,
                        local_box,source_boxes=footprints):
                    # Actual source detector support is distinct from
                    # the extra 3px inference padding. Keep the SAME 8px/10%
                    # predicate and full-union foreign-ink proof; no rectangle
                    # becomes writable and no single-column exception is added.
                    if not supports or not outline_only_overhang(rgb,component,enclosed,interior,background,
                            local_box,source_boxes=supports):
                        return None
                    source_boxes=source_support_boxes
                footprint_constrained=True
    moments=cv2.moments(interior)
    if not moments["m00"]:return None
    cx,cy=moments["m10"]/moments["m00"],moments["m01"]/moments["m00"]
    integral=cv2.integral(interior)
    best=None;best_area=0
    # A centred, fully inscribed rectangle avoids outlines and concave tails.
    for wf in (0.9,0.85,0.8,0.75,0.7,0.65,0.6,0.55,0.5):
        for hf in (0.85,0.8,0.75,0.7,0.65,0.6,0.55,0.5,0.45,0.4):
            tw,th=max(1,int(bw*wf)),max(1,int(bh*hf))
            tx,ty=int(cx-tw/2),int(cy-th/2)
            if tx<0 or ty<0 or tx+tw>bw or ty+th>bh:continue
            area=int(integral[ty+th,tx+tw]-integral[ty,tx+tw]-integral[ty+th,tx]+integral[ty,tx])
            if area==tw*th and area>best_area:
                best=[bx+tx,by+ty,tw,th];best_area=area
    if best is None:return None
    grey=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    dark_background=float(background.mean())<128
    ink=((grey>max(35,float(background.mean())+15)) if dark_background else
         (grey<min(220,float(background.mean())-15)))& (interior>0)
    _,ink_labels,ink_stats,_=cv2.connectedComponentsWithStats(ink.astype("uint8"))
    sizes=[max(cw,ch) for ix,iy,cw,ch,area in ink_stats[1:] if area>=4 and
           4<=max(cw,ch)<=min(bw,bh)*0.4]
    source_size=float(np.percentile(sizes,80)) if sizes else min(w,h,32)
    source_size=max(8,min(160,source_size))
    pad=max(8,int(source_size*2))
    zone=[max(0,x-bx-pad),max(0,y-by-pad),min(bw,x-bx+w+pad),min(bh,y-by+h+pad)]
    footprints=np.zeros_like(interior)
    for sx,sy,sw,sh in source_boxes or [box]:
        footprints[sy-by:sy-by+sh,sx-bx:sx-bx+sw]=1
    selected=np.zeros_like(interior)
    for idx,(ix,iy,cw,ch,area) in enumerate(ink_stats[1:],1):
        if area<1:continue
        overlaps=ix+cw>zone[0] and iy+ch>zone[1] and ix<zone[2] and iy<zone[3]
        if not overlaps:continue
        # Large islands can be art, not missed punctuation. Leave source visible
        # in uncertain regions rather than erasing it without OCR evidence.
        if max(cw,ch)>source_size*3 or area>source_size*source_size*3:return None
        island=ink_labels==idx
        if footprint_constrained and not (island & (footprints>0)).any():
            # A nearby sweat mark/decorative stroke is not a detected glyph.
            # Preserve it. If it occupies the proposed typesetting rectangle,
            # annotation is safer than laying translated text over unknown art.
            tx,ty,tw,th=best
            if island[ty-by:ty-by+th,tx-bx:tx-bx+tw].any():return None
            continue
        selected[island]=1
    # Source downsampling and SVG edge antialiasing are separate operations.
    # A two-pixel margin erased all native-size glyphs yet leaked pale traces
    # at 351/800 scale. Four source pixels cover that observed kernel halo.
    # Remain clipped to the same safe interior: never enlarge a text card or
    # repaint a balloon outline/tail to conceal residuals.
    cores=selected.copy()
    selected=cv2.dilate(selected,np.ones((9,9),np.uint8)) & interior
    if footprint_constrained:
        protected=cv2.dilate((ink & (cores==0)).astype("uint8"),np.ones((9,9),np.uint8))
        selected &= 1-protected
        if (cores & (selected==0)).any():return None
    contours,_=cv2.findContours(selected,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if len(contours)>128:return None
    masks=[]
    for item in contours:
        refined=cv2.approxPolyDP(item,0.55,True).reshape(-1,2)
        if not 3<=len(refined)<=64:
            ix,iy,cw,ch=cv2.boundingRect(item);refined=np.asarray(polygon([ix,iy,cw,ch]))
        masks.append([[int(px+bx),int(py+by)] for px,py in refined])
    # Sample the solid core rather than all antialiased edge pixels; otherwise
    # nominal white lettering becomes grey and loses its original contrast.
    ink_core=ink.copy()
    if ink.any():
        threshold=np.percentile(grey[ink],85 if dark_background else 15)
        ink_core &= (grey>=threshold) if dark_background else (grey<=threshold)
    ink_rgb=rgb[ink_core]
    foreground=np.median(ink_rgb,axis=0).astype(int) if ink_rgb.size else np.array([255,255,255] if dark_background else [17,17,17])
    return {"textBox":best,"background":"#"+"".join(f"{v:02x}" for v in background),
            "ink":"#"+"".join(f"{v:02x}" for v in foreground),"sourceFontPx":round(source_size,2),"erasePolygons":masks}


def outline_only_overhang(rgb,component,enclosed,interior,background,box,*,source_boxes=None):
    """Permit a small detector corner on a continuous EXTERNAL outline.

    This is not an erasure mask. All erasure stays inside the eroded enclosed
    surface. An isolated missed glyph or ink within its two-pixel safety band
    still rejects integration. No open/whole-page component can reach here.

    With unequal columns, the union rectangle invents empty outside corners.
    Apply the SAME 8px/10% limit to every original padded source footprint,
    not that invented corner. ALL foreign ink in the union must still be
    proved external-outline/halo; footprints are never writable glyph masks.
    """
    import cv2
    import numpy as np
    x,y,w,h=box
    outside=interior[y:y+h,x:x+w]==0
    difference=np.abs(rgb.astype(float)-background).max(axis=2)
    contrast=difference>15
    distances=cv2.distanceTransform(1-enclosed,cv2.DIST_L2,5)
    if source_boxes is not None and (not isinstance(source_boxes,list) or not 2<=len(source_boxes)<=64):
        return False
    for sx,sy,sw,sh in source_boxes if source_boxes is not None else [box]:
        if (min(sw,sh)<=0 or sx<x or sy<y or sx+sw>x+w or sy+sh>y+h):
            return False
        unsupported=interior[sy:sy+sh,sx:sx+sw]==0
        if int(unsupported.sum())>unsupported.size*.1:
            return False
        if unsupported.any() and float(distances[sy:sy+sh,sx:sx+sw][unsupported].max())>8:
            return False
    _,ink_labels,ink_stats,_=cv2.connectedComponentsWithStats(contrast.astype("uint8"))
    perimeter=cv2.dilate(enclosed,np.ones((5,5),np.uint8)) & (1-enclosed)
    minimum=max(24,min(enclosed.shape)*.5)
    outline_labels=[]
    for idx,(_,_,_,_,area) in enumerate(ink_stats[1:],1):
        if area<minimum:
            continue
        island=ink_labels==idx
        if int((island&(enclosed==0)).sum())>=area*.6 and int((island&(perimeter>0)).sum())>=minimum:
            outline_labels.append(idx)
    foreign=outside&contrast[y:y+h,x:x+w]
    linked=np.isin(ink_labels,outline_labels)
    # JPEG can leave detached pale pixels next to a continuous stroke. Only
    # its two-pixel halo in THIS flat background component is exempt; a dark
    # point or a separate glyph is not. The protected band is still unpainted.
    halo=(cv2.dilate(linked.astype("uint8"),np.ones((5,5),np.uint8))>0)&(component>0)&(difference<=35)
    if source_boxes is not None:
        footprint=np.zeros_like(interior)
        for sx,sy,sw,sh in source_boxes:footprint[sy:sy+sh,sx:sx+sw]=1
        # A pale JPEG speck just OUTSIDE the outline belongs to the exterior
        # paper component. Only an invented union corner may use this halo;
        # retain the stricter same-component test at every source footprint.
        # This exterior is protected and never part of the writable interior.
        halo|=(cv2.dilate(linked.astype("uint8"),np.ones((5,5),np.uint8))>0)&(enclosed==0)&(footprint==0)&(difference<=35)
    supported=linked|halo
    # Includes antialias ringing just INSIDE the contour: it must connect to
    # a substantial external outline, not an isolated point/missed glyph.
    # Regardless of its label, nothing in this safety band is ever erased.
    return bool(supported[y:y+h,x:x+w][foreign].all())


def aligned_open_starts(a,b):
    """Candidate-only shared start band; not balloon or speaker evidence.

    Open paper can connect unrelated lettering. Require similarly oriented
    columns/lines and aligned leading edges before considering adjacency.
    A whole cluster checks this pairwise so local edges cannot drift across
    successively staggered blocks. Coordinates are the only input.
    """
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    if ah>=aw*1.25 and bh>=bw*1.25:
        return abs(ay-by)<=max(2,min(aw,bw)*.35)
    if aw>=ah*1.25 and bw>=bh*1.25:
        return abs(ax-bx)<=max(2,min(ah,bh)*.35)
    return False


def nearby_text_boxes(a,b,*,open_surface=False,open_overlap=False,minimum_open_overlap=.3,pair_scale=False):
    """Local line/column adjacency, not evidence of one speaker or balloon.

    Compare gaps with the transverse text scale, not page size or the length
    of a vertical utterance. Contained/overlapping detector boxes stay together.
    Keep distant blocks separate even when their surrounding paper connects.
    """
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    if open_surface and not aligned_open_starts(a,b):return False
    overlap_x=max(0,min(ax+aw,bx+bw)-max(ax,bx))
    overlap_y=max(0,min(ay+ah,by+bh)-max(ay,by))
    gap_x=max(0,max(ax,bx)-min(ax+aw,bx+bw))
    gap_y=max(0,max(ay,by)-min(ay+ah,by+bh))
    vertical=ah>=aw*1.25 and bh>=bw*1.25
    horizontal=aw>=ah*1.25 and bw>=bh*1.25
    # Containment is not permission to join a tiny side annotation to a large
    # open column. Leave the historical/default adjacency behavior unchanged.
    if open_overlap:
        scale=min(aw,bw) if vertical else min(ah,bh) if horizontal else 0
        largest=max(aw,bw) if vertical else max(ah,bh)
        if not scale or largest>scale*1.75:return False
    if overlap_x*overlap_y>=min(aw*ah,bw*bh)*.5:return True
    if open_surface:
        # Page paper does not supply the ownership evidence of a bounded
        # surface. Require compatible text scale and a genuinely narrow gap;
        # otherwise a caption, side mark and logo can bridge transitively.
        # No OCR text, dataset IDs or reference labels enter this decision.
        if vertical:
            scale=min(aw,bw)
            if max(aw,bw)>scale*1.75:return False
            if open_overlap and overlap_x<scale*minimum_open_overlap:return False
            return ((overlap_y>=max(min(ah,bh)*.65,max(ah,bh)*.35) and gap_x<=scale*.5) or
                    (overlap_x>=scale*.8 and gap_y<=scale*.5))
        if horizontal:
            scale=min(ah,bh)
            if max(ah,bh)>scale*1.75:return False
            if open_overlap and overlap_y<scale*minimum_open_overlap:return False
            return ((overlap_x>=max(min(aw,bw)*.65,max(aw,bw)*.35) and gap_y<=scale*.75) or
                    (overlap_y>=scale*.8 and gap_x<=scale*.5))
        return False
    if vertical:
        scale=min(aw,bw) if pair_scale else max(aw,bw)
        return ((overlap_y>=min(ah,bh)*.35 and gap_x<=scale) or
                (overlap_x>=min(aw,bw)*.65 and gap_y<=max(aw,bw)*.65))
    if horizontal:
        scale=min(ah,bh) if pair_scale else max(ah,bh)
        return ((overlap_x>=min(aw,bw)*.35 and gap_y<=scale*1.5) or
                (overlap_y>=min(ah,bh)*.65 and gap_x<=max(ah,bh)*.65))
    return False


def text_border_between(grey,a,b,kind):
    """Substantial source ink between adjacent lines is a merge veto.

    Connected PAPER can span two touching balloons or an open panel boundary.
    Inspect only the narrow separator corridor, never interpret ink as a
    speaker/semantic boundary or grant artwork erasure from this heuristic.
    False vetoes keep source crops separate instead of deleting source text.
    """
    import cv2
    import numpy as np
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    lateral=abs(ax+aw/2-bx-bw/2)/max(1,min(aw,bw))>=abs(ay+ah/2-by-bh/2)/max(1,min(ah,bh))
    if lateral:
        left,right=sorted((a,b),key=lambda box:box[0]+box[2]/2)
        first,last=max(ay,by),min(ay+ah,by+bh)
        start,stop=left[0]+left[2],right[0]
        if stop<=start:
            return False  # Overlapping detector ink is not a separate corridor.
        x0,x1=max(0,math.floor(start)),min(grey.shape[1],math.ceil(stop))
        y0,y1=max(0,math.floor(first)),min(grey.shape[0],math.ceil(last))
        length=y1-y0
    else:
        upper,lower=sorted((a,b),key=lambda box:box[1]+box[3]/2)
        first,last=max(ax,bx),min(ax+aw,bx+bw)
        start,stop=upper[1]+upper[3],lower[1]
        if stop<=start:
            return False
        x0,x1=max(0,math.floor(first)),min(grey.shape[1],math.ceil(last))
        y0,y1=max(0,math.floor(start)),min(grey.shape[0],math.ceil(stop))
        length=x1-x0
    if x1<=x0 or y1<=y0 or length<14:return False
    pixels=grey[y0:y1,x0:x1]
    ink=(pixels>135 if kind=="dark_balloon" else pixels<120).astype("uint8")
    _,_,stats,_=cv2.connectedComponentsWithStats(ink)
    minimum=max(14,length*.55)
    for _,_,width,height,area in stats[1:]:
        extent=height if lateral else width
        if extent>=minimum and area>=extent*.75:return True
    return False


def local_text_clusters(members,separated=None,*,open_surface=False,open_overlap=False,minimum_open_overlap=.3,pair_scale=False):
    """Deterministic connected groups of nearby detections; no OCR/gold input."""
    boxes=[rect(member["polygon"]) for member in members]
    remaining=set(range(len(members)));clusters=[]
    while remaining:
        first=min(remaining);remaining.remove(first);cluster={first};pending=[first]
        while pending:
            current=pending.pop()
            for idx in sorted(remaining):
                if not nearby_text_boxes(boxes[current],boxes[idx],open_surface=open_surface,open_overlap=open_overlap,minimum_open_overlap=minimum_open_overlap,pair_scale=pair_scale):continue
                if open_surface and not all(aligned_open_starts(boxes[member],boxes[idx]) for member in cluster):continue
                if separated is not None and separated(boxes[current],boxes[idx]):continue
                # Update immediately: two neighbours can each agree with the
                # old anchor but disagree with one another's leading edge.
                remaining.remove(idx);cluster.add(idx);pending.append(idx)
        clusters.append([members[idx] for idx in sorted(cluster)])
    return clusters


def group_regions(image, detections, *, experimental_open_text=False, experimental_open_overlap=False,minimum_open_overlap=.3,
                  include_source_members=False,experimental_source_support=False,experimental_pair_scale=False):
    """Cluster source lines; the default remains the frozen v20 comparator.

    Native PaddleDetector explicitly selects its source recipe and v21 presentation.
    OpenCV, cloud proposals and unrelated diagnostic candidates do not inherit
    it implicitly. The legacy flag spelling is retained for replay provenance.
    """
    import cv2
    import numpy as np
    from .layout_geometry import paper_notch_cuts,crosses_paper_cut
    if type(include_source_members) is not bool:
        raise ValueError("Source evidence retention must be explicit")
    if type(experimental_source_support) is not bool:
        raise ValueError("Source-support comparator must be explicit")
    if type(experimental_pair_scale) is not bool:
        raise ValueError("Pair-scale comparator must be explicit")
    if experimental_pair_scale and (experimental_open_text or experimental_open_overlap):
        raise ValueError("Compare pair-scale grouping without changing another policy")
    if experimental_source_support and (experimental_open_text or experimental_open_overlap):
        raise ValueError("Compare source-support lettering without changing grouping")
    if experimental_open_text and experimental_open_overlap:
        raise ValueError("Compare exactly one open-grouping candidate")
    if (type(minimum_open_overlap) not in (int,float) or not math.isfinite(minimum_open_overlap) or
            minimum_open_overlap not in (.2,.3) or (minimum_open_overlap!=.3 and not experimental_open_overlap)):
        raise ValueError("Overlap fraction is a bounded experimental comparator only")
    grey = np.asarray(image.convert("L"))
    # Closing the WHITE mask can bridge a thin dark balloon outline into the
    # page background, splitting its dialogue into separate line requests.
    # Keep dark boundaries intact; white space around glyphs stays connected.
    white = (grey > 175).astype("uint8")
    _, labels, stats, _ = cv2.connectedComponentsWithStats(white)
    _, dark_labels, dark_stats, _=cv2.connectedComponentsWithStats((grey<80).astype("uint8"))
    surfaces={"balloon":(labels,stats),"dark_balloon":(dark_labels,dark_stats)}
    groups = {}
    for idx, detection in enumerate(detections):
        box = rect(detection["polygon"])
        x,y,w,h = map(int, box)
        if w < 4 or h < 4:
            continue
        key=("region",idx)
        for kind,(surface,surface_stats) in surfaces.items():
            patch=surface[max(0,y):min(image.height,y+h),max(0,x):min(image.width,x+w)]
            candidates=patch[patch>0]
            votes=np.bincount(candidates) if candidates.size else []
            label=int(np.argmax(votes)) if len(votes) else 0
            area=int(surface_stats[label,4]) if label else 0
            # Paper in OTHER components cannot authorize ownership by this
            # one. A detection spanning two captions may be mostly white
            # overall yet belong to neither; keep that crop independent.
            if label and area>40 and votes[label]>patch.size*0.55:
                # A large paper component can still contain one bare dialogue
                # block. It may organize OCR, never authorize balloon erasure.
                if area<image.width*image.height*.12:
                    key=(kind,label)
                elif experimental_open_text or experimental_open_overlap:
                    key=("open_"+kind,label)
                break
        groups.setdefault(key, []).append(detection)
    work=[]
    for key,members in groups.items():
        kind=key[0].removeprefix("open_")
        cuts=(paper_notch_cuts(*surfaces[key[0]],key[1],[rect(d["polygon"]) for d in members])
              if key[0] in surfaces else [])
        border_probe=experimental_open_text or (experimental_open_overlap and key[0].startswith("open_"))
        separator=(lambda a,b:crosses_paper_cut(a,b,cuts) or
                   (border_probe and text_border_between(grey,a,b,kind))) if cuts or border_probe else None
        clusters=(local_text_clusters(members,separator,
                                      open_surface=key[0].startswith("open_"),
                                      open_overlap=experimental_open_overlap and key[0].startswith("open_"),minimum_open_overlap=minimum_open_overlap)
                  if kind in surfaces and len(members)>1 else [members])
        if experimental_pair_scale and kind in surfaces and len(members)>1:
            proposed=[]
            for parent in clusters:
                children=local_text_clusters(parent,separator,pair_scale=True)
                boxes=[rect([p for m in child for p in m['polygon']]) for child in children]
                padded=[]
                for x,y,w,h in boxes:
                    x,y=max(0,int(x)-3),max(0,int(y)-3)
                    padded.append([x,y,min(image.width-x,int(w)+6),min(image.height-y,int(h)+6)])
                # A narrower adjacency edge must not turn overlapping source
                # or padded inference envelopes into two active OCR units.
                # Preserve this parent only; never undo a prior notch split.
                overlap=any(min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and
                            min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
                            for i,a in enumerate(padded) for b in padded[i+1:])
                proposed.extend([parent] if overlap else children)
            clusters=proposed
        for index,cluster in enumerate(clusters):
            _,_,w,h=rect([point for member in cluster for point in member["polygon"]])
            if len(cluster)>1 and (int(w)+6)*(int(h)+6)>image.width*image.height*.16:
                work.extend((("fragment",idx),[member]) for idx,member in enumerate(cluster))
            elif key[0] in surfaces and len(clusters)>1:
                # A local separation veto does not prove independent balloon
                # ownership or permission to erase the entire paper component.
                work.append((("fragment",index),cluster))
            else:
                work.append((key,cluster))
    regions = []
    for key, members in work:
        coords = [point for d in members for point in d["polygon"]]
        x,y,w,h = rect(coords)
        x,y = max(0,int(x)-3), max(0,int(y)-3)
        w,h = min(image.width-x,int(w)+6), min(image.height-y,int(h)+6)
        if w*h > image.width*image.height*0.16:
            continue
        crop = grey[y:y+h,x:x+w]
        safe=key[0] in surfaces and float(((crop>175) if key[0]=="balloon" else (crop<80)).mean())>0.68
        surface,surface_stats=surfaces.get(key[0],(None,None))
        source_boxes=[];source_support_boxes=[]
        for member in members:
            sx,sy,sw,sh=rect(member["polygon"])
            ux,uy=max(0,math.floor(sx)),max(0,math.floor(sy))
            source_support_boxes.append([ux,uy,min(image.width,math.ceil(sx+sw))-ux,
                                         min(image.height,math.ceil(sy+sh))-uy])
            sx,sy=max(0,int(sx)-3),max(0,int(sy)-3)
            source_boxes.append([sx,sy,min(image.width-sx,int(sw)+6),min(image.height-sy,int(sh)+6)])
        support_options={"source_support_boxes":source_support_boxes} if experimental_source_support else {}
        balloon=(balloon_lettering(image,surface,surface_stats,key[1],[x,y,w,h],source_boxes=source_boxes,**support_options)
                 if safe else None)
        region={"bbox":[x,y,w,h], "polygon":polygon([x,y,w,h]), "score":min(m["score"] for m in members),
                "overlay":"white" if balloon else "label"}
        if include_source_members:
            # Private diagnostic opt-in only: exact detector input, not glyph
            # masks, source-key replacement or new artwork-erasure authority.
            region["sourceMembers"]=[{"polygon":[list(point) for point in member["polygon"]],
                                       "score":member["score"]} for member in members]
        if key[0]=="fragment":
            region.update(review=True,reviewReasons=["layout_fragment"])
        elif key[0].startswith("open_") and len(members)>1:
            region.update(review=True,reviewReasons=["layout_cluster"])
        if balloon:region["balloon"]=balloon
        regions.append(region)
    # Simple RTL row ordering. Complex panels still require review/selection mode.
    rows = []
    for region in sorted(regions, key=lambda r:r["bbox"][1]):
        box = region["bbox"]
        for row in rows:
            top = min(r["bbox"][1] for r in row)
            bottom = max(r["bbox"][1]+r["bbox"][3] for r in row)
            if min(bottom,box[1]+box[3])-max(top,box[1]) > min(box[3],bottom-top)*0.45:
                row.append(region)
                break
        else:
            rows.append([region])
    ordered = [r for row in rows for r in sorted(row, key=lambda r:-r["bbox"][0])]
    for idx,r in enumerate(ordered):
        r.update(id=f"r{idx:03}", order=idx, type="dialogue", speaker="unknown", listener="unknown")
    return ordered


def review_reasons(ja,score=1):
    """Heuristics, not calibrated OCR confidence. Never rewrite the evidence.

    A quote can legitimately span bubbles, so imbalance requests a human check
    instead of discarding the region or 'correcting' a possibly real quotation.
    """
    reasons=[]
    if re.search(r"(.{2,8})\1{3}",ja):reasons.append("repetition")
    if len(ja)>290:reasons.append("length")
    if score<0.6:reasons.append("detector_low_score")
    if any(ja.count(left)!=ja.count(right) for left,right in (("「","」"),("『","』"),("“","”"))) or ja.count('"')%2:
        reasons.append("quote_balance")
    return reasons


def _partition_reader_owned(region):
    scope = region.get("scope", {})
    return (scope.get("reason") == "reader" or scope.get("action") == "defer"
            or any(region.get(field, "unknown") != "unknown" for field in ("speaker", "listener")))


def _partition_aligned(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    if ah >= aw * 1.25 and bh >= bw * 1.25:
        return abs(ay - by) <= max(2, min(aw, bw) * .35)
    if aw >= ah * 1.25 and bw >= bh * 1.25:
        return abs(ax - bx) <= max(2, min(ah, bh) * .35)
    return False


def _inherit_parent_ocr_frames(image,regions,crops,evidence,parents):
    """An explicit regrouping experiment, never a provider crop hint.

    Recompute the original partition from source geometry/pixels. A split may
    retain its parent's longitudinal inference frame, but never its transverse
    neighbours, reader-owned source, balloon masks or artwork-erasure rights.
    """
    from collections import Counter
    parent_crops,_=partition_ocr_boxes(image,parents)

    def members(region):
        values=region.get('sourceMembers')
        require(isinstance(values,list) and 0<len(values)<=512,'OCR_PARTITION',
                'Exact source members required for inherited inference framing.')
        keys=[]
        x,y,w,h=region['bbox']
        for member in values:
            require(isinstance(member,dict),'OCR_PARTITION')
            points,score=member.get('polygon'),member.get('score')
            require(isinstance(points,list) and 3<=len(points)<=32 and
                    all(isinstance(p,list) and len(p)==2 and
                        all(type(v) in (int,float) and math.isfinite(v) for v in p) for p in points) and
                    type(score) in (int,float) and math.isfinite(score) and 0<=score<=1,'OCR_PARTITION')
            require(all(x<=px<=x+w and y<=py<=y+h for px,py in points),'OCR_PARTITION',
                    'Source member outside its source geometry.')
            keys.append((tuple(tuple(p) for p in points),score))
        return keys

    parent_keys=[members(parent) for parent in parents]
    child_keys=[members(child) for child in regions]
    old=Counter(key for keys in parent_keys for key in keys)
    new=Counter(key for keys in child_keys for key in keys)
    require(old==new and all(count==1 for count in old.values()),'OCR_PARTITION',
            'Missing, duplicate or ambiguous source membership.')
    owners=[]
    for keys in child_keys:
        matches=[i for i,parent in enumerate(parent_keys) if set(keys).issubset(parent)]
        require(len(matches)==1,'OCR_PARTITION','A child must have one original source parent.')
        owners.append(matches[0])
    output={key:list(value) for key,value in crops.items()};records=list(evidence)
    for index,parent in enumerate(parents):
        children=[r for r,owner in zip(regions,owners) if owner==index]
        if (len(children)<2 or parent.get('overlay')!='label' or parent.get('balloon') or
                'layout_fragment' in parent.get('reviewReasons',[]) or _partition_reader_owned(parent) or
                any(_partition_reader_owned(child) or child.get('balloon') or
                    child.get('overlay')!='label' for child in children)):continue
        member_boxes=[rect(member['polygon']) for member in parent['sourceMembers']]
        if all(b[3]>=b[2]*1.25 for b in member_boxes):axis,extent,long_axis,long_extent=0,2,1,3
        elif all(b[2]>=b[3]*1.25 for b in member_boxes):axis,extent,long_axis,long_extent=1,3,0,2
        else:continue
        boxes=[list(output.get(child['id'],child['bbox'])) for child in children]
        # Longitudinal fragments must not become two overlapping full strips.
        if any(min(a[axis]+a[extent],b[axis]+b[extent])>max(a[axis],b[axis])
               for i,a in enumerate(boxes) for b in boxes[i+1:]):continue
        original=parent_crops.get(parent['id'],parent['bbox'])
        for box in boxes:box[long_axis],box[long_extent]=original[long_axis],original[long_extent]
        if any(b[0]<original[0] or b[1]<original[1] or b[0]+b[2]>original[0]+original[2] or
               b[1]+b[3]>original[1]+original[3] for b in boxes):continue
        changed=False
        for child,box in zip(children,boxes):
            if box!=list(output.get(child['id'],child['bbox'])):
                output[child['id']]=box;changed=True
        if changed:
            records.append({'source_ids':[child['id'] for child in children],
                'reason':'group_parent_longitudinal_frame','orientation':'vertical' if axis==0 else 'horizontal',
                'parent_source_bbox':list(parent['bbox']),'parent_inference_crop':list(original),
                'source_members_preserved':True,'erasure_permitted':False})
    return output,records


def partition_ocr_boxes(image, regions, *, source_parents=None):
    """Bounded inference-only crops; parent framing is an explicit experiment.

    Parent regions must retain the exact original detector members. No model
    crop hints are consumed. The default/native recipe remains unchanged.
    """
    import numpy as np
    require(isinstance(regions, list) and len(regions) <= 64, "OCR_PARTITION")
    boxes=[]
    for region in regions:
        box=region.get("bbox") if isinstance(region,dict) else None
        require(isinstance(box,list) and len(box)==4 and all(type(v) is int for v in box),
                "OCR_PARTITION", "Invalid source geometry.")
        x,y,w,h=box
        require(min(x,y)>=0 and min(w,h)>=1 and x+w<=image.width and y+h<=image.height,
                "OCR_PARTITION", "Invalid source geometry.")
        boxes.append(list(box))
    ids=[region.get("id") for region in regions]
    require(all(isinstance(value,str) and value for value in ids) and len(set(ids))==len(ids),
            "OCR_PARTITION", "Unique source geometry identities required.")
    eligible=[index for index,region in enumerate(regions) if region.get("overlay")=="label" and
              not region.get("balloon") and "layout_fragment" not in region.get("reviewReasons",[]) and
              not _partition_reader_owned(region)]
    if len(eligible)<2:
        return ({},[]) if source_parents is None else _inherit_parent_ocr_frames(image,regions,{},[],source_parents)
    grey=np.asarray(image.convert("L"));source_ink=np.zeros(grey.shape,dtype=bool)
    for x,y,w,h in boxes:source_ink[y:y+h,x:x+w]|=grey[y:y+h,x:x+w]<220
    evidence=[]
    for offset,a_index in enumerate(eligible):
        for b_index in eligible[offset+1:]:
            a,b=regions[a_index]["bbox"],regions[b_index]["bbox"]
            if not _partition_aligned(a,b):continue
            vertical=a[3]>=a[2]*1.25 and b[3]>=b[2]*1.25
            axis,extent=(0,2) if vertical else (1,3); longitudinal,long_extent=(1,3) if vertical else (0,2)
            centres=[box[axis]+box[extent]/2 for box in (a,b)];scale=min(a[extent],b[extent]);pitch=abs(centres[0]-centres[1])
            if not scale*.5<=pitch<=scale*1.75:continue
            start,end=max(a[axis],b[axis]),min(a[axis]+a[extent],b[axis]+b[extent])
            top=min(a[longitudinal],b[longitudinal]);bottom=max(a[longitudinal]+a[long_extent],b[longitudinal]+b[long_extent])
            overlap=min(a[longitudinal]+a[long_extent],b[longitudinal]+b[long_extent])-max(a[longitudinal],b[longitudinal])
            if end-start<3 or overlap<min(a[long_extent],b[long_extent])*.65:continue
            patch=grey[top:bottom,start:end] if vertical else grey[start:end,top:bottom].T
            blank=np.flatnonzero((patch>=220).all(axis=0))
            runs=[run for run in np.split(blank,np.flatnonzero(np.diff(blank)>1)+1) if len(run)>=2] if len(blank) else []
            if not runs:continue
            target=sum(centres)/2;run=min(runs,key=lambda band:(abs(start+(band[0]+band[-1]+1)/2-target),-len(band)))
            seam=int(round(start+(int(run[0])+int(run[-1])+1)/2))
            before,after=sorted((a_index,b_index),key=lambda index:regions[index]["bbox"][axis])
            left,right=list(boxes[before]),list(boxes[after])
            if left[axis]>=seam or right[axis]+right[extent]<=seam:continue
            left[extent]=min(left[axis]+left[extent],seam)-left[axis];boundary=right[axis]+right[extent]
            right[axis]=max(right[axis],seam);right[extent]=boundary-right[axis]
            if min(left[extent],right[extent])<4:continue
            coverage=np.zeros(grey.shape,dtype=bool)
            for candidate in boxes:
                x,y,w,h=candidate;coverage[y:y+h,x:x+w]|=True
            coverage[regions[before]["bbox"][1]:regions[before]["bbox"][1]+regions[before]["bbox"][3],regions[before]["bbox"][0]:regions[before]["bbox"][0]+regions[before]["bbox"][2]]=False
            coverage[regions[after]["bbox"][1]:regions[after]["bbox"][1]+regions[after]["bbox"][3],regions[after]["bbox"][0]:regions[after]["bbox"][0]+regions[after]["bbox"][2]]=False
            for candidate in (left,right):
                x,y,w,h=candidate;coverage[y:y+h,x:x+w]|=True
            if (source_ink&~coverage).any():continue
            if left==boxes[before] and right==boxes[after]:continue
            evidence.append({"source_ids":[ids[before],ids[after]],"orientation":"vertical" if vertical else "horizontal",
                             "seam":seam,"blank_band":[start+int(run[0]),start+int(run[-1])+1],
                             "source_ink_coverage_preserved":True,"erasure_permitted":False})
            boxes[before],boxes[after]=left,right
    crops={ids[index]:boxes[index] for index in range(len(boxes)) if boxes[index]!=regions[index]["bbox"]}
    return (crops,evidence) if source_parents is None else _inherit_parent_ocr_frames(image,regions,crops,evidence,source_parents)


def recognize_regions(image, regions, engine, cancel, progress=None, batch_size=2,
                      crop_boxes=None, partition_evidence=None):
    output = []
    for start in range(0,len(regions),batch_size):
        require(not cancel.is_set(), "CANCELED", "Đã hủy tác vụ.")
        batch=regions[start:start+batch_size]
        crops=[]
        for r in batch:
            box=(crop_boxes or {}).get(r["id"],r["bbox"])
            crops.append(image.crop((box[0],box[1],box[0]+box[2],box[1]+box[3])))
        results=checked_ocr_results(engine.recognize_many(crops) if batch_size>1 else
                                   [engine.recognize(crop) for crop in crops],len(batch))
        for index,(region,ja) in enumerate(zip(batch,results)):
            # A detector region is source evidence even when the recognizer
            # cannot read it.  Dropping an empty result used to make the
            # source disappear from the page/cache, which prevented a reader
            # retry and made a detector miss indistinguishable from "no text".
            # Keep it review-only and let text_scope defer it; no translation,
            # memory entry, cleanup mask or erasure authority is granted.
            reasons=list(dict.fromkeys([*region.get("reviewReasons",[]),*review_reasons(ja,region.get("score",1))]))
            if not ja.strip(): reasons.append("ocr_empty")
            if index in getattr(engine,"uncertain_indices",set()): reasons.append("cloud_ocr_uncertain")
            cropped=(crop_boxes or {}).get(region["id"])
            if cropped is not None and list(cropped)!=list(region["bbox"]):
                reasons.append("ocr_crop_partition")
            result={**region,"ja":ja,"review":bool(reasons),
                    "reviewReasons":list(dict.fromkeys(reasons))}
            if cropped is not None and list(cropped)!=list(region["bbox"]):
                result["ocrCropBox"]=list(cropped)
                if partition_evidence:
                    related=[item for item in partition_evidence if region["id"] in item.get("source_ids",[])]
                    if related:result["ocrPartition"]=related[:2]
            output.append(bind_expression(result))
        if progress:
            progress(len(output), len(regions))
    return output
