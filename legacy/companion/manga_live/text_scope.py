"""Conservative local routing, not a semantic-confidence model.

Geometry proposes groups; only a narrow visible editorial heading can defer
one automatically. Dense letters, signs and narration remain translatable.
No pixels are returned/persisted and a reader override always wins.
"""
import hashlib
import json
import re
import unicodedata
from .image_signal import weak_glyph_signal,edge_connected_punctuation_support,ellipsis_only

SCOPE_VERSION="text-scope-v5-unreadable-source-review"
# Reader choices bind source pixels/crop, not a changing routing policy. Keep
# the existing v3 namespace so this upgrade cannot discard saved exclusions
# or explicit roles. SCOPE_VERSION still invalidates automatic cache results.
SCOPE_KEY_VERSION="text-scope-v3-weak-mark-review"
VISUAL_REVIEW_REASONS={"visual_low_signal","visual_punctuation_support","ocr_crop_partition","cloud_ocr_uncertain","cloud_page_proposal","ocr_empty"}
ROLES={"dialogue","thought","narration","scene_text","editorial","sfx","unknown"}
ACTIONS={"translate","defer"}
STORY_ROLES={"dialogue","thought","narration","scene_text","unknown"}


def key_for(value):
    return "scope-"+hashlib.sha256(json.dumps(value,separators=(",",":"),sort_keys=True).encode()).hexdigest()[:32]


def story_regions(regions):
    # Legacy pages retain their old semantics. New scope must explicitly allow
    # story memory; on-demand translation of editorial text does not allow it.
    def allowed(region):
        scope=region.get("scope",{})
        if scope.get("reason")=="visual_review":return False
        if VISUAL_REVIEW_REASONS.intersection(region.get("reviewReasons",[])) and scope.get("reason")!="reader":return False
        return "scope" not in region or (scope.get("memory") is True and scope.get("action")=="translate")
    return [r for r in regions if allowed(r)]


def _panels(image):
    import cv2
    import numpy as np
    grey=np.asarray(image.convert("L"))
    contours,_=cv2.findContours((grey<100).astype("uint8"),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    result=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if w<image.width*.12 or h<image.height*.12 or w*h>image.width*image.height*.85:continue
        perimeter=cv2.arcLength(contour,True)
        corners=cv2.approxPolyDP(contour,.015*perimeter,True)
        if len(corners)==4 and cv2.contourArea(contour)/(w*h)>.92:
            result.append((x,y,w,h))
    return result


def _inside(box,panel):
    x,y,w,h=box;px,py,pw,ph=panel
    return max(0,min(x+w,px+pw)-max(x,px))*max(0,min(y+h,py+ph)-max(y,py))/(w*h)>.8


def _adjacent(a,b):
    x,y,w,h=a;bx,by,bw,bh=b
    gx=max(0,max(x,bx)-min(x+w,bx+bw));gy=max(0,max(y,by)-min(y+h,by+bh))
    oy=max(0,min(y+h,by+bh)-max(y,by))/min(h,bh)
    ox=max(0,min(x+w,bx+bw)-max(x,bx))/min(w,bw)
    small=min(w,h,bw,bh)
    return (oy>.3 and gx<=small*1.5) or (ox>.3 and gy<=small*.8)


def make_plan(image,regions,image_hash):
    keys={r["id"]:key_for([SCOPE_KEY_VERSION,image_hash,r["bbox"]]) for r in regions}
    plan={"keys":keys,"groups":[],"seeds":[],
          "visual_review":{r["id"] for r in regions if weak_glyph_signal(image,r["bbox"])},
          "punctuation_review":{r["id"] for r in regions if edge_connected_punctuation_support(image,r["bbox"])}}
    if len(regions)<4:return plan
    panels=_panels(image)
    # Initial preview is limited to slender multi-column layouts. A row of
    # ordinary short dialogue crops must not reorder interactive OCR or force
    # an extra heading pass. This limits coverage, never justifies skipping.
    eligible=[r for r in regions if not r.get("balloon") and
              r["bbox"][3]>=r["bbox"][2]*3 and
              not any(_inside(r["bbox"],p) for p in panels)]
    remaining={r["id"]:r for r in eligible}
    while remaining:
        _,first=remaining.popitem();members=[first]
        for member in members:
            neighbors=[r for r in remaining.values() if _adjacent(member["bbox"],r["bbox"])]
            for r in neighbors:remaining.pop(r["id"]);members.append(r)
        if len(members)<4:continue
        left=min(r["bbox"][0] for r in members);top=min(r["bbox"][1] for r in members)
        right=max(r["bbox"][0]+r["bbox"][2] for r in members);bottom=max(r["bbox"][1]+r["bbox"][3] for r in members)
        if (right-left)*(bottom-top)>image.width*image.height*.28:continue
        group=key_for(sorted(keys[r["id"]] for r in members))
        members.sort(key=lambda r:r.get("order",0))
        # RTL and largest short-side are heading candidates, not role evidence.
        choices=[max(members,key=lambda r:r["bbox"][0]),max(members,key=lambda r:min(r["bbox"][2:]))]
        seeds=list(dict.fromkeys(r["id"] for r in choices))
        plan["groups"].append({"id":group,"ids":[r["id"] for r in members],"seeds":seeds})
    # A bounded preview avoids OCRing the whole page before the first bubble.
    plan["groups"].sort(key=lambda g:min(next(r.get("order",0) for r in regions if r["id"]==i) for i in g["ids"]))
    plan["groups"]=plan["groups"][:3]
    plan["seeds"]=list(dict.fromkeys(i for g in plan["groups"] for i in g["seeds"]))[:6]
    return plan


def _heading_role(value):
    value=re.sub(r"\s+","",unicodedata.normalize("NFKC",value)).strip("【】[]「」『』:：・")
    if re.fullmatch(r"(?:作者コメント|著者コメント|作者あとがき|著者あとがき|編集部からのお知らせ|読者の皆様へ)",value):
        return "editorial","editorial_marker"
    # A numbered external column may be supplementary, but not proven so.
    # Label it a candidate, never calibrated "AI confidence" or plot evidence.
    if re.fullmatch(r"[一-龥ぁ-ゖァ-ヺーA-Za-z・]{2,24}講座(?:第)?[0-9一二三四五六七八九十]{1,3}(?:回|章)?",value):
        return "unknown","editorial_candidate"
    return None


def route_regions(regions,plan,overrides,seed_evidence=None):
    evidence={r["id"]:r for r in (seed_evidence if seed_evidence is not None else regions)}
    decisions={}
    for group in plan["groups"]:
        role=next((_heading_role(evidence[i].get("ja","")) for i in group["seeds"]
                   if i in evidence and i not in plan.get("visual_review",set()) and
                   not evidence[i].get("review") and _heading_role(evidence[i].get("ja",""))),None)
        if role:
            # A lecture heading can be part of the story itself. Geometry
            # and a candidate label are not evidence to hide its translation.
            action="defer" if role[0]=="editorial" else "translate"
            for i in group["ids"]:decisions[i]=(role[0],action,role[1],group["id"])
    result=[]
    for r in regions:
        key=plan["keys"][r["id"]]
        role,action,reason,group=decisions.get(r["id"],("unknown","translate","unclassified",key))
        weak=r["id"] in plan.get("visual_review",set())
        uncertain="cloud_ocr_uncertain" in r.get("reviewReasons",[])
        unreadable="ocr_empty" in r.get("reviewReasons",[]) and not r.get("ja","").strip()
        punctuation=r["id"] in plan.get("punctuation_review",set()) and ellipsis_only(r.get("ja",""))
        # A dots-only crop whose ink is connected to surrounding artwork is
        # not safe to paint over automatically. Keep the source in the page
        # result and expose it through the reader's secondary-text affordance
        # instead. This is a reversible presentation choice, not a semantic
        # "irrelevant" verdict: an explicit reader action can recover it.
        # An empty authored/reader-provided string is not a semantic skip
        # signal.  Only an OCR adapter's explicit ``ocr_empty`` evidence (or
        # cloud uncertainty) may defer a source region for recovery.
        if punctuation or unreadable or (uncertain and not r.get("ja","").strip()):
            role,action,reason="unknown","defer","visual_review"
        elif weak or uncertain:
            role,action,reason="unknown","translate","visual_review"
        if key in overrides:
            role,action=overrides[key]["role"],overrides[key]["action"];reason="reader"
        if unreadable:
            # A saved role is not readable OCR. Retain that choice/anchor,
            # but wait for explicit source correction before translating.
            action,reason="defer","visual_review"
        scope={"v":1,"key":key,"group":group,"role":role,"action":action,"reason":reason,
               "memory":action=="translate" and role in STORY_ROLES and reason!="visual_review"}
        routed={**r,"type":r.get("type","unknown") if role=="unknown" else role,"scope":scope}
        reasons=[*r.get("reviewReasons",[])]
        if weak:reasons.append("visual_low_signal")
        if punctuation:reasons.append("visual_punctuation_support")
        if weak or punctuation or uncertain:
            routed.update(review=True,reviewReasons=list(dict.fromkeys(reasons)))
        result.append(routed)
    return result
