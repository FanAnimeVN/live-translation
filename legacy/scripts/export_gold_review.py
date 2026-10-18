"""Create a private text-only review draft, never a human-review attestation."""
import argparse
import json
from pathlib import Path
from benchmark import ROOT,audit,dataset_fingerprint,dataset_source


def make_review_pack(source,*,blind=False):
    if type(blind) is not bool:raise ValueError("Explicit pixels-first mode required")
    fingerprint=dataset_fingerprint(source)
    counts,issues,pages=audit(source)
    rows=[]
    for page,_image,bubbles in pages:
        for bubble in bubbles:
            rows.append({"page_id":page["page_id"],"bubble_id":bubble["bubble_id"],
                "image_file":page["image_file"],"source_bbox":dict(bubble["bbox"]),
                "source_ja_candidate":bubble["ja_ocr_truth"],
                "source_vi_candidate":bubble.get("vi_gold_trans") or None,
                "reviewed_ja":None,"vi_reference":None,"reviewed_bbox":None,
                "review_state":"unreviewed","reviewed_by":[],"evidence":[],
                "difficulty":"unclassified","role":"unknown","group_members":[],
                "reading_order":None,"meaning_notes":"","pronoun_notes":"",
                "term_notes":"","expression_notes":"","protected_art_review":"unreviewed",
                "clean_background_gold":None})
    if blind:
        # Freeze a pixel reading BEFORE revealing either the supplied label or
        # the prediction being graded. Geometry is a region to inspect, not a
        # guarantee that its contents/boundary/reading order are correct.
        for row in rows:
            row.pop("source_ja_candidate");row.pop("source_vi_candidate")
    return {"schema":1,"kind":"independent-reference-review-draft",
        "review_mode":"pixels-first-candidates-hidden" if blind else "candidate-assisted-draft",
        "dataset_fingerprint_sha256":fingerprint,"split":"development",
        "review_state":"unreviewed","independent_human_review":False,"reviewed_by":[],
        "quality_accepted":False,"counts":counts,"audit":issues,"rows":rows,
        "instructions":["Draft only: source labels are candidates, not independently validated gold.",
            "Freeze a pixels-first reading before unblinding source labels/predictions; retain uncertainty and incomplete crop coverage.",
            "Review Japanese and create Vietnamese references before viewing the predictions to be graded.",
            "Record uncertain, missing, split and merged labels; never modify the source dataset to match output.",
            "Use label IDs for this benchmark only, not reader speaker/source-key bindings.",
            "Reviewing this repeatedly used development set does not make it held-out.",
            "Unknown background under text stays unknown; no image, prediction or model response is embedded."]}


def output_path(value):
    path=Path(value).resolve()
    if (ROOT/"artifacts").resolve() not in path.parents or path.suffix!=".json":
        raise ValueError("Review draft must remain private JSON under artifacts")
    if path.exists():raise ValueError("Never overwrite an existing review draft")
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--folder");inputs.add_argument("--zip")
    parser.add_argument("--output",required=True)
    parser.add_argument("--blind",action="store_true",help="Hide JA/VI candidate labels for a pixels-first review")
    args=parser.parse_args();destination=output_path(args.output)
    with dataset_source(args) as source:pack=make_review_pack(source,blind=args.blind)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("x",encoding="utf-8") as stream:
        json.dump(pack,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({"draft_created":True,"rows":len(pack["rows"]),"audit_issues":len(pack["audit"]),
        "dataset_fingerprint_sha256":pack["dataset_fingerprint_sha256"],
        "human_review_completed":False,"cloud":False,"images_written":False}))


if __name__=="__main__":main()
