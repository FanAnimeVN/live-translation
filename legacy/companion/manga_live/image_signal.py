"""Bounded weak-mark review hint, not text recognition or semantic filtering.

Only tiny, mostly flat light-paper crops with a few weak disconnected marks
qualify. A positive result must NEVER remove text or license erasing artwork.
Blank, dense, strong, reverse-print and unsupported crops are outside this
hint. Their OCR quality is not asserted by a negative result either.
"""
import math
import re
import unicodedata


def ellipsis_only(value):
    """A comparison only; never normalize/rewrite the OCR source."""
    if not isinstance(value,str):return False
    value=re.sub(r"\s+","",unicodedata.normalize("NFKC",value))
    value=value.replace("⋯","...")
    return len(value)>=2 and set(value)=={"."}


def edge_connected_punctuation_support(image,box):
    """Tiny dots-only OCR needs review when ink has no isolated dot support.

    This is not a non-text verdict: clipped dots/art/textured lettering may
    still be genuine. Preserve source/translation, require explicit reader
    role before storing it as story evidence, never authorize cleanup.
    Text gating occurs after OCR; normal words and other punctuation are not
    affected. Only small light-paper crops with substantial border-connected
    ink and no isolated components qualify. No raster leaves this function.
    """
    if not isinstance(box,(list,tuple)) or len(box)!=4:return False
    if any(type(v) not in (int,float) or not math.isfinite(v) or int(v)!=v for v in box):return False
    x,y,w,h=map(int,box)
    if (x<0 or y<0 or min(w,h)<8 or max(w,h)>48 or w*h>1024 or
            x+w>image.width or y+h>image.height):return False
    import cv2
    import numpy as np
    grey=np.asarray(image.crop((x,y,x+w,y+h)).convert("L"))
    paper=int(np.bincount(grey.reshape(-1),minlength=256).argmax())
    if paper<235:return False
    contrast=np.abs(grey.astype("int16")-paper)
    mask=(contrast>=30).astype("uint8")
    if float(mask.mean())<.22 or float((contrast<12).mean())>=.8:return False
    _,_,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
    support=[row for row in stats[1:] if row[cv2.CC_STAT_AREA]>=3]
    return bool(support and all(
        row[cv2.CC_STAT_LEFT]==0 or row[cv2.CC_STAT_TOP]==0 or
        row[cv2.CC_STAT_LEFT]+row[cv2.CC_STAT_WIDTH]==w or
        row[cv2.CC_STAT_TOP]+row[cv2.CC_STAT_HEIGHT]==h for row in support))


def weak_glyph_signal(image,box):
    if not isinstance(box,(list,tuple)) or len(box)!=4:return False
    if any(type(v) not in (int,float) or not math.isfinite(v) or int(v)!=v for v in box):return False
    x,y,w,h=map(int,box)
    if (x<0 or y<0 or min(w,h)<8 or max(w,h)>96 or w*h>4096 or
            x+w>image.width or y+h>image.height):return False
    import cv2
    import numpy as np
    grey=np.asarray(image.crop((x,y,x+w,y+h)).convert("L"))
    background=int(np.bincount(grey.reshape(-1),minlength=256).argmax())
    contrast=np.abs(grey.astype("int16")-background)
    # Do not mistake intentionally pale/reverse lettering or ordinary flat
    # paper for noise. This hint describes sparse support, not faintness alone.
    if background<235 or float((contrast<12).mean())<.8:return False
    mask=(contrast>=30).astype("uint8")
    pixels=int(mask.sum())
    if not 16<=pixels<=96 or int((contrast>=120).sum())>8:return False
    # Thresholding can break a genuine pale glyph into tiny pieces. Multiple
    # larger components at a softer threshold veto this sparse-mark hint;
    # do not isolate only dark cores and mislabel their disconnected remnants.
    _,_,softer,_=cv2.connectedComponentsWithStats((contrast>=20).astype("uint8"),connectivity=8)
    if sum(row[cv2.CC_STAT_AREA]>=18 and max(row[cv2.CC_STAT_WIDTH],row[cv2.CC_STAT_HEIGHT])>=9
           for row in softer[1:])>=2:return False
    _,_,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
    support=[row for row in stats[1:] if row[cv2.CC_STAT_AREA]>=3]
    return bool(3<=len(support)<=12 and all(
        row[cv2.CC_STAT_AREA]<=24 and max(row[cv2.CC_STAT_WIDTH],row[cv2.CC_STAT_HEIGHT])<=9
        for row in support))
