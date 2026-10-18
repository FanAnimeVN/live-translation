"""Private CPU detector comparator; never imported by the companion runtime.

Only --fetch-model performs network I/O, explicitly, before inference. Weight
redistribution is not cleared. Do not add this artifact to installer/bundles.
No upstream GPL Python code or pickle checkpoint is imported. DB line decoding
uses the already installed Apache-licensed PaddleX implementation: this is NOT
bit-for-bit parity with upstream CTD's line decoder, grouping or mask refiner.
Raw masks stay in RAM and are never trusted as artwork erasure permissions.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from provision import download, verify

MODEL_URL = "https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.3/comictextdetector.pt.onnx"
MODEL_SPEC = {"bytes": 94669756,
    "sha256": "1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f"}
MODEL_PATH = ROOT / "artifacts/comparator-models/comictextdetector.pt.onnx"
INPUT_SIZE = 1024


def prepare_image(image):
    import cv2
    import numpy as np
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > 12000000:
        raise ValueError("Invalid comparator image")
    scale = INPUT_SIZE / max(width, height)
    rw, rh = max(1, round(width * scale)), max(1, round(height * scale))
    rgb = cv2.resize(np.asarray(image.convert("RGB")), (rw, rh), interpolation=cv2.INTER_LINEAR)
    padded = cv2.copyMakeBorder(rgb, 0, INPUT_SIZE-rh, 0, INPUT_SIZE-rw,
        cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return padded, (rw, rh)


def split_outputs(outputs):
    """Identify outputs by contract, not OpenCV-dependent output order."""
    import numpy as np
    masks, lines, blocks = [], [], []
    for value in outputs:
        if not isinstance(value, np.ndarray) or not np.isfinite(value).all():
            raise ValueError("Invalid CTD output")
        if value.ndim == 4 and value.shape[0] == 1 and value.shape[2:] == (INPUT_SIZE, INPUT_SIZE):
            if value.shape[1] == 1:
                masks.append(value)
            elif value.shape[1] == 2:
                lines.append(value)
        elif value.ndim == 3 and value.shape[0] == 1 and value.shape[2] == 7 and value.shape[1] <= 131072:
            blocks.append(value)
    if len(masks) != 1 or len(lines) != 1 or len(blocks) != 1:
        raise ValueError("Unexpected CTD output shapes")
    if any(float(v.min()) < -.001 or float(v.max()) > 1.001 for v in (*masks, *lines)):
        raise ValueError("Invalid CTD probability map")
    return blocks[0], masks[0], lines[0]


def line_detections(line_map, resized, source_size):
    from paddlex.inference.models.text_detection.processors import DBPostProcess
    width, height = source_size
    rw, rh = resized
    # Padding must be removed BEFORE mapping to source pixels.
    line_map = line_map[:, :1, :rh, :rw]
    decoder = DBPostProcess(thresh=.3, box_thresh=.6, unclip_ratio=1.5,
        max_candidates=1000, box_type="quad", score_mode="fast")
    boxes, scores = decoder([line_map], [[height, width, rh/height, rw/width]])
    return [{"polygon": [[float(x), float(y)] for x, y in box], "score": float(score)}
        for box, score in zip(boxes[0], scores[0])]


def block_detections(blocks, resized, source_size):
    import cv2
    import numpy as np
    predictions = blocks[0]
    confidence = predictions[:, 4] * predictions[:, 5:].max(axis=1)
    candidates = np.where((confidence > .4) & (predictions[:, 2:4] > 0).all(axis=1))[0]
    boxes = [[float(cx-w/2), float(cy-h/2), float(w), float(h)]
        for cx, cy, w, h in predictions[candidates, :4]]
    picked = cv2.dnn.NMSBoxes(boxes, confidence[candidates].tolist(), .4, .35)
    width, height = source_size
    rw, rh = resized
    result = []
    for index in np.asarray(picked).reshape(-1):
        picked_index = int(index)
        candidate_index = int(candidates[picked_index])
        prediction = predictions[candidate_index]
        x, y, w, h = boxes[picked_index]
        left, top = max(0, min(width, x*width/rw)), max(0, min(height, y*height/rh))
        right, bottom = max(0, min(width, (x+w)*width/rw)), max(0, min(height, (y+h)*height/rh))
        if right-left < 4 or bottom-top < 4:
            continue
        result.append({"polygon": [[left, top], [right, top], [right, bottom], [left, bottom]],
            "score": float(confidence[candidate_index]),
            # Model location classes are not semantic relevance or erasure
            # labels. Keep the unmodified source row, not just its product.
            "upstream_block": {"candidate_index": candidate_index,
                "raw_prediction": prediction.tolist(),
                "class_index": int(prediction[5:].argmax()),
                "objectness": float(prediction[4]),
                "class_probabilities": prediction[5:].tolist()}})
    return result


class ExperimentalCtd:
    def __init__(self, model_path, threads=4, output="lines", backend="opencv"):
        if output not in ("lines", "blocks"):
            raise ValueError("Invalid CTD comparator output")
        if backend not in ("opencv", "onnxruntime"):
            raise ValueError("Invalid CTD comparator backend")
        self.path, self.threads, self.output, self.backend = Path(model_path), threads, output, backend
        self.model = None
        self.name = "CTD-ONNX-private-" + output
        self.details = {"model_sha256": MODEL_SPEC["sha256"], "bytes": MODEL_SPEC["bytes"],
            "input_size": INPUT_SIZE, "input": "RGB/255, right/bottom black padding",
            "output": output, "line_decoder": "PaddleX DB: threshold .3, score .6, unclip 1.5",
            "block_decoder": "objectness * class probability, class-agnostic NMS .35, score .4",
            "grouping": "unchanged app flat-component grouping",
            "backend": backend,
            "uses_mask_for_erasure": False, "distribution_cleared": False,
            "not_upstream_full_pipeline_parity": True}

    def detect(self, image):
        import cv2
        import numpy as np
        from manga_live.ocr import group_regions
        if self.model is None:
            if not verify(self.path, MODEL_SPEC):
                raise ValueError("CTD model missing or checksum mismatch; use explicit --fetch-model")
            if self.backend == "opencv":
                cv2.setNumThreads(self.threads)
                self.model = cv2.dnn.readNetFromONNX(str(self.path))
                self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            else:
                import onnxruntime as ort
                options = ort.SessionOptions()
                options.intra_op_num_threads = self.threads
                options.inter_op_num_threads = 1
                options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.model = ort.InferenceSession(str(self.path), sess_options=options,
                                                  providers=["CPUExecutionProvider"])
        padded, resized = prepare_image(image)
        blob = cv2.dnn.blobFromImage(padded, 1/255., (INPUT_SIZE, INPUT_SIZE), swapRB=False)
        if self.backend == "opencv":
            self.model.setInput(blob)
            outputs = self.model.forward(self.model.getUnconnectedOutLayersNames())
        else:
            outputs = self.model.run(None, {"images": blob})
        blocks, mask, lines = split_outputs(outputs)
        detections = (line_detections(lines, resized, image.size) if self.output == "lines" else
            block_detections(blocks, resized, image.size))
        rw, rh = resized
        self.last_evidence = {"version": "ctd-retained-sources-v2",
            "output_shapes": [list(o.shape) for o in outputs],
            "raw_detection_count": len(detections), "raw_detections": deepcopy(detections),
            "mask_fraction_over_half": float((mask[0,0,:rh,:rw] > .5).mean()),
            "uses_mask_for_erasure": False}
        # Arrays/predicted masks cannot enter OCR cache, Region or render patch.
        return group_regions(image, detections, include_source_members=True)


def main():
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--folder")
    inputs.add_argument("--zip")
    parser.add_argument("--model", default=str(MODEL_PATH))
    parser.add_argument("--fetch-model", action="store_true")
    parser.add_argument("--output-kind", choices=["lines", "blocks"], default="lines")
    parser.add_argument("--backend", choices=["opencv", "onnxruntime"], default="opencv")
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-pages-ctd.json"))
    args = parser.parse_args()
    if args.fetch_model:
        download(MODEL_URL, Path(args.model), MODEL_SPEC)
    if args.folder or args.zip:
        from benchmark_pages import run
        run(args, detector_override=ExperimentalCtd(args.model, args.threads, args.output_kind, args.backend))
    elif not args.fetch_model:
        parser.error("Supply a dataset or explicit --fetch-model")


if __name__ == "__main__":
    main()
