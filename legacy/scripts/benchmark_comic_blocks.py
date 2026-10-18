"""Private text-block comparator, NOT imported by the companion.

Minimal independent adapter to the publisher's pinned ONNX contract. No
upstream application/grouping/download code is imported. Only --fetch-model
downloads; inference is CPU/offline. Boxes are not glyph or balloon masks.
Source images and all raster outputs remain in RAM. Do not bundle the model
or change runtime defaults from a comparator result.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from provision import download, verify

REVISION = "16e8a622f91fabc6b5b65c96d32d1183f8843546"
MODEL_SPEC = {"bytes": 11120765,
    "sha256": "5fe9e4f576e49d4e7e8b0e029d6d3cdc252abd4694113e1cae120e62c931ea79"}
MODEL_PATH = ROOT / "artifacts/comparator-models/detector-v4-s_int8.onnx"
MODEL_URL = f"https://huggingface.co/ogkalu/comic-text-and-bubble-detector/resolve/{REVISION}/detector-v4-s_int8.onnx"
RUNTIME_VERSION = "1.23.2"
CLASSES = ("bubble", "text_bubble", "text_free")
ONNX_INPUTS = [("images", "tensor(float)", ["N", 3, 640, 640]),
    ("orig_target_sizes", "tensor(int64)", ["N", 2])]
ONNX_OUTPUTS = [("labels", "tensor(int64)", [1, 300]),
    ("boxes", "tensor(float)", [1, 300, 4]), ("scores", "tensor(float)", [1, 300])]


def checked_contract(inputs, outputs):
    if inputs != ONNX_INPUTS or outputs != ONNX_OUTPUTS:
        raise ValueError("Pinned comic-block ONNX contract changed")


def prepare_image(image):
    import numpy as np
    from PIL import Image
    w, h = image.size
    if w <= 0 or h <= 0 or w*h > 12000000 or max(w, h) > 8000:
        raise ValueError("Invalid comparator image")
    # PIL defaults to BICUBIC for RGB; make the reviewed upstream choice explicit.
    rgb = image.convert("RGB").resize((640, 640), Image.Resampling.BICUBIC)
    tensor = np.asarray(rgb, dtype=np.float32).transpose(2, 0, 1)[None] / 255.
    return {"images": np.ascontiguousarray(tensor),
        "orig_target_sizes": np.array([[w, h]], dtype=np.int64)}


def checked_outputs(values):
    import numpy as np
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError("Unexpected comic-block output count")
    if any(not isinstance(v, np.ndarray) for v in values):
        raise ValueError("Unexpected comic-block output type")
    labels, boxes, scores = values
    if labels.ndim == 2 and labels.shape[0] == 1: labels = labels[0]
    if boxes.ndim == 3 and boxes.shape[0] == 1: boxes = boxes[0]
    if scores.ndim == 2 and scores.shape[0] == 1: scores = scores[0]
    if (labels.ndim != 1 or boxes.shape != (len(labels), 4) or scores.shape != labels.shape
            or len(labels) > 4096 or labels.dtype.kind not in "iu"
            or boxes.dtype.kind != "f" or scores.dtype.kind != "f"
            or not all(np.isfinite(v).all() for v in (labels, boxes, scores))
            or ((labels < 0) | (labels > 2)).any() or ((scores < 0) | (scores > 1)).any()):
        raise ValueError("Invalid comic-block output shape/value")
    return labels, boxes, scores


def text_detections(outputs, source_size):
    from manga_live.ocr import polygon
    width, height = source_size
    detections, evidence = [], []
    for label, box, score in zip(*outputs):
        if score < .3: continue
        # Match upstream integer xyxy, then clamp to the actual source.
        x1, y1, x2, y2 = map(int, box)
        x1, x2 = max(0, min(width, x1)), max(0, min(width, x2))
        y1, y2 = max(0, min(height, y1)), max(0, min(height, y2))
        accepted = x2-x1 >= 4 and y2-y1 >= 4
        record = {"label": int(label), "class": CLASSES[int(label)], "score": float(score),
            "bbox": [x1, y1, x2-x1, y2-y1], "raw_xyxy": [float(v) for v in box],
            "rejected_geometry": not accepted}
        evidence.append(record)
        if accepted and label in (1, 2):
            detections.append({"polygon": polygon(record["bbox"]), "score": float(score),
                "detectorClass": CLASSES[int(label)]})
    return detections, evidence


class ExperimentalComicBlocks:
    name = "ogkalu-detector-v4-s-int8-private-blocks"
    def __init__(self, model_path, threads=4):
        if type(threads) is not int or not 1 <= threads <= 8:
            raise ValueError("Invalid comparator thread count")
        self.path, self.threads, self.session = Path(model_path), threads, None
        self.details = {"repo": "ogkalu/comic-text-and-bubble-detector", "revision": REVISION,
            "model_sha256": MODEL_SPEC["sha256"], "bytes": MODEL_SPEC["bytes"],
            "runtime": "onnxruntime/"+RUNTIME_VERSION, "execution_provider": "CPUExecutionProvider",
            "input": "RGB PIL BICUBIC stretch 640x640, BCHW float32 /255",
            "orig_target_sizes": "int64 [[width,height]]; publisher contract, NOT H/W",
            "score_threshold": .3, "classes": list(CLASSES), "box_format": "source xyxy truncated to int, clamped",
            "grouping": "unchanged app v16; not publisher overlap-merger/tall-page slicer",
            "uses_box_for_erasure": False, "production_default": False,
            "distribution_cleared": False}

    def load(self):
        if self.session is not None: return
        if not verify(self.path, MODEL_SPEC):
            raise ValueError("Comic-block model missing or checksum mismatch; use explicit --fetch-model")
        import onnxruntime as ort
        if ort.__version__ != RUNTIME_VERSION:
            raise ValueError("Unexpected comparator runtime version")
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.log_severity_level = 3
        session = ort.InferenceSession(str(self.path), sess_options=options, providers=["CPUExecutionProvider"])
        inputs = [(v.name, v.type, v.shape) for v in session.get_inputs()]
        outputs = [(v.name, v.type, v.shape) for v in session.get_outputs()]
        checked_contract(inputs, outputs)
        self.details["onnx_inputs"] = inputs
        self.details["onnx_outputs"] = outputs
        self.session = session

    def detect(self, image):
        from manga_live.ocr import group_regions
        self.load()
        outputs = checked_outputs(self.session.run(["labels", "boxes", "scores"], prepare_image(image)))
        detections, evidence = text_detections(outputs, image.size)
        self.last_evidence = {"raw_detections": evidence, "text_block_count": len(detections),
            "bubble_count": sum(e["label"] == 0 and not e["rejected_geometry"] for e in evidence)}
        return group_regions(image, detections)


def main():
    parser = argparse.ArgumentParser()
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--folder"); sources.add_argument("--zip")
    parser.add_argument("--fetch-model", action="store_true")
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-pages-comic-blocks.json"))
    args = parser.parse_args()
    if args.fetch_model: download(MODEL_URL, MODEL_PATH, MODEL_SPEC)
    if args.folder or args.zip:
        destination = Path(args.output).resolve()
        if destination.parent != ROOT / "artifacts":
            raise ValueError("Private comparator text/metrics must stay in gitignored artifacts")
        from benchmark_pages import run
        run(args, detector_override=ExperimentalComicBlocks(MODEL_PATH, args.threads))
    elif not args.fetch_model: parser.error("Provide a dataset or explicit --fetch-model")


if __name__ == "__main__": main()
