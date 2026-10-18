"""Isolated balloon-instance comparator; never imported/bundled by the reader.

Only explicit provisioning flags go online. A container mask is not a glyph
mask, semantic role, speaker or artwork erasure permission. All rasters stay
in RAM. Dataset/base-weight permissions remain unresolved for distribution.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "companion")]
from provision import download, verify

REVISION = "6839b4ea9d95be14f5bbd21ac675d92a7da95ed0"
MODEL_SPEC = {"bytes": 11845329, "sha256": "593cae61f4c9ffc773fee34d55c28069390d19415c24dc04600f983311618ea3"}
MODEL_PATH = ROOT / "artifacts/comparator-models/manga109_segmentation_bubble_1024.onnx"
MODEL_URL = f"https://huggingface.co/mednasserallah/manga109-segmentation-bubble-onnx/resolve/{REVISION}/{MODEL_PATH.name}"
INSPECTOR_SPEC = {"bytes": 17213290, "sha256": "72ccebab3bac07215c204ce8848d42e78eaaa666badbf72d25cd359b9f269e3a"}
INSPECTOR_PATH = ROOT / "artifacts/comparator-runtime/wheels/onnx-1.22.0-cp312-abi3-win_amd64.whl"
INSPECTOR_URL = "https://files.pythonhosted.org/packages/13/a8/734725bb703c5fabb687f79c79e51249475212b3eb37771ac4a4ac9b487f/onnx-1.22.0-cp312-abi3-win_amd64.whl"
VERSION = "manga109-yolo11n-container-mask-comparator-v1"
RUNTIME_VERSION = "1.23.2"
INPUT_SIZE = 1024
CONFIDENCE = .25
NMS_IOU = .7
MAX_INSTANCES = 64
MAX_MASK_PIXELS = 24_000_000


def model_message_class():
    # Extract a declarative serialized protobuf descriptor, not Python/runtime
    # code. No wheel installation/import or native extension execution.
    import ast
    import zipfile
    from google.protobuf import descriptor_pool, message_factory
    if not verify(INSPECTOR_PATH, INSPECTOR_SPEC):
        raise ValueError("Missing/mismatched inspector schema wheel; explicit --setup-inspector required")
    with zipfile.ZipFile(INSPECTOR_PATH) as wheel:
        raw = wheel.read("onnx/onnx_ml_pb2.py")
    tree = ast.parse(raw)
    descriptors = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "AddSerializedFile"]
    if len(descriptors) != 1 or len(descriptors[0].args) != 1:
        raise ValueError("Unreviewed protobuf descriptor structure")
    data = ast.literal_eval(descriptors[0].args[0])
    if not isinstance(data, bytes) or len(data) > 200000:
        raise ValueError("Invalid bounded ONNX descriptor")
    pool = descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(data)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName("onnx.ModelProto"))


def inspect_model(path=MODEL_PATH):
    from collections import Counter
    if not verify(path, MODEL_SPEC):
        raise ValueError("Missing/mismatched pinned balloon model; explicit --fetch-model required")
    model = model_message_class()()
    model.ParseFromString(Path(path).read_bytes())
    operators = Counter()
    graphs = [model.graph]
    while graphs:
        graph = graphs.pop()
        for tensor in list(graph.initializer) + [s.values for s in graph.sparse_initializer] + [s.indices for s in graph.sparse_initializer]:
            if tensor.external_data or tensor.data_location:
                raise ValueError("External tensor data is not permitted")
        for node in graph.node:
            if node.domain not in ("", "ai.onnx"):
                raise ValueError("Custom operator domain is not permitted")
            operators[node.op_type] += 1
            for attr in node.attribute:
                if attr.HasField("g"): graphs.append(attr.g)
                graphs.extend(attr.graphs)
                tensors = [attr.t] if attr.HasField("t") else []
                tensors.extend(attr.tensors)
                if any(t.external_data or t.data_location for t in tensors):
                    raise ValueError("External attribute tensor is not permitted")
    if model.functions or model.training_info or [(o.domain, o.version) for o in model.opset_import] != [("", 17)]:
        raise ValueError("Unreviewed graph functions/training/opset")
    def value_info(info):
        return {"name": info.name, "type": info.type.tensor_type.elem_type,
                "shape": [d.dim_value if d.HasField("dim_value") else d.dim_param for d in info.type.tensor_type.shape.dim]}
    return {"sha256": MODEL_SPEC["sha256"], "bytes": MODEL_SPEC["bytes"], "ir_version": model.ir_version,
            "opsets": [[o.domain, o.version] for o in model.opset_import], "operators": dict(operators),
            "inputs": [value_info(v) for v in model.graph.input], "outputs": [value_info(v) for v in model.graph.output],
            "external_data": False, "custom_domains": False, "functions": 0}


class ExperimentalBubbleMasks:
    def __init__(self, path=MODEL_PATH, threads=2, *, forward=None):
        if type(threads) is not int or not 1 <= threads <= 4:
            raise ValueError("Bounded comparator threads required")
        self.path, self.threads, self.forward, self.session = Path(path), threads, forward, None
        self.graph = None

    def load(self):
        if self.forward is not None or self.session is not None: return
        self.graph = inspect_model(self.path)
        if (self.graph["ir_version"] != 8
                or self.graph["inputs"] != [{"name": "images", "type": 1, "shape": [1, 3, 1024, 1024]}]
                or self.graph["outputs"] != [{"name": "output0", "type": 1, "shape": [1, 37, 21504]},
                                             {"name": "output1", "type": 1, "shape": [1, 32, 256, 256]}]):
            raise ValueError("Pinned graph contract changed")
        import onnxruntime as ort
        if ort.__version__ != RUNTIME_VERSION:
            raise ValueError("Unreviewed ONNX Runtime")
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = self.threads, 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.log_severity_level = 3
        self.session = ort.InferenceSession(str(self.path), sess_options=options, providers=["CPUExecutionProvider"])

    def segment(self, image):
        import cv2
        import numpy as np
        import math
        width, height = image.size
        if min(width, height) <= 0 or width*height > 12_000_000 or max(width, height) > 8000:
            raise ValueError("Bounded source image required")
        scale = INPUT_SIZE/max(width, height)
        rw, rh = max(1, round(width*scale)), max(1, round(height*scale))
        left, top = (INPUT_SIZE-rw)//2, (INPUT_SIZE-rh)//2
        rgb = cv2.resize(np.asarray(image.convert("RGB")), (rw, rh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, np.uint8)
        canvas[top:top+rh, left:left+rw] = rgb
        inputs = {"images": np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32)/255}
        self.load()
        values = self.forward(inputs) if self.forward is not None else self.session.run(["output0", "output1"], inputs)
        if (not isinstance(values, (tuple, list)) or len(values) != 2
                or any(not isinstance(v, np.ndarray) or v.dtype != np.float32 or not np.isfinite(v).all() for v in values)
                or values[0].shape != (1, 37, 21504) or values[1].shape != (1, 32, 256, 256)):
            raise ValueError("Invalid pinned segmentation output")
        proposals, prototypes = values[0][0].T, values[1][0].reshape(32, -1)
        if ((proposals[:, 4] < 0) | (proposals[:, 4] > 1)).any():
            raise ValueError("Invalid segmentation confidence")
        indices = np.flatnonzero(proposals[:, 4] >= CONFIDENCE)
        if len(indices) > 1024:
            raise ValueError("Too many scored balloon proposals")
        raw, kept = [], []
        for index in sorted(indices, key=lambda i: (-float(proposals[i, 4]), int(i))):
            cx, cy, w, h, score = (float(v) for v in proposals[index, :5])
            box = [cx-w/2, cy-h/2, cx+w/2, cy+h/2]
            record = {"index": int(index), "class": "balloon", "score": score, "model_xyxy": box,
                      "mask_coefficients": proposals[index, 5:].tolist(), "action": "keep"}
            raw.append(record)
            if min(w, h) <= 0:
                record["action"] = "invalid_geometry"
                continue
            for other in kept:
                a, b, c, d = other["model_xyxy"]
                inter = max(0, min(c, box[2])-max(a, box[0]))*max(0, min(d, box[3])-max(b, box[1]))
                union = (c-a)*(d-b)+w*h-inter
                if union > 0 and inter/union > NMS_IOU:
                    record.update(action="nms_suppressed", suppressed_by=other["index"])
                    break
            else:
                kept.append(record)
        if len(kept) > MAX_INSTANCES:
            raise ValueError("Too many balloon instances; never truncate silently")
        instances, pixels = [], 0
        for record in kept:
            x1, y1, x2, y2 = record["model_xyxy"]
            x, y = max(0, math.floor((x1-left)*width/rw)), max(0, math.floor((y1-top)*height/rh))
            right, bottom = min(width, math.ceil((x2-left)*width/rw)), min(height, math.ceil((y2-top)*height/rh))
            if right <= x or bottom <= y:
                record["action"] = "padding_only_geometry"
                continue
            pixels += (right-x)*(bottom-y)
            if pixels > MAX_MASK_PIXELS:
                raise ValueError("Bounded total instance-mask area exceeded")
            # Prototypes cover the entire page: crop each instance independently
            # before upsampling. Never treat the prototype as an erasure mask.
            logits = (proposals[record["index"], 5:] @ prototypes).reshape(256, 256)
            if not np.isfinite(logits).all():
                raise ValueError("Non-finite decoded instance mask")
            grid_y, grid_x = np.ogrid[:256, :256]
            crop = (grid_x >= x1/4) & (grid_x < x2/4) & (grid_y >= y1/4) & (grid_y < y2/4)
            logits = np.where(crop, logits, 0).astype(np.float32)
            padded = cv2.resize(logits, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
            source = cv2.resize(padded[top:top+rh, left:left+rw], (width, height), interpolation=cv2.INTER_LINEAR)
            mask = (source[y:bottom, x:right] > 0).astype(np.uint8)
            if not mask.any():
                record["action"] = "empty_mask_review"
            instances.append({"index": record["index"], "score": record["score"], "bbox": [x, y, right-x, bottom-y],
                              "mask": mask, "erasure_authority": False, "memory_authority": False})
        return {"version": VERSION, "instances": instances, "raw_proposals": raw,
                "preprocess": {"source_size": [width, height], "resized_size": [rw, rh],
                               "pad_left_top": [left, top], "input_size": INPUT_SIZE,
                               "color": "RGB", "resize": "cv2.INTER_LINEAR", "padding": 114},
                "thresholds": {"confidence": CONFIDENCE, "nms_iou": NMS_IOU, "mask_logit": 0}}


def group_with_container_masks(image, primary, instances, *, page):
    """Review-only source partition; no glyph/memory/semantic authority.

    A member must have >=98% raster coverage by exactly one instance and zero
    positive coverage by competitors. Partly uncertain original units remain
    intact and block cross-unit grouping for any owner they already touch.
    """
    from copy import deepcopy
    import hashlib
    import json
    import math
    import cv2
    import numpy as np
    from probe_recorded_source_union import group_recorded_sources
    group_recorded_sources(image, primary, [], page=page, primary_anchored=True)  # shared source/exclusion validation
    if not isinstance(instances, list) or len(instances) > MAX_INSTANCES:
        raise ValueError("Bounded container instances required")
    seen, pixels = set(), 0
    for instance in instances:
        index, box, mask = instance.get("index"), instance.get("bbox"), instance.get("mask")
        if type(index) is not int or not 0 <= index < 21504 or index in seen:
            raise ValueError("Unique bounded instance identity required")
        seen.add(index)
        if (not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box)
                or min(box[:2]) < 0 or min(box[2:]) <= 0
                or box[0]+box[2] > image.width or box[1]+box[3] > image.height
                or not isinstance(mask, np.ndarray) or mask.dtype != np.uint8 or mask.shape != (box[3], box[2])
                or (mask > 1).any()):
            raise ValueError("Bounded source-space binary container mask required")
        pixels += mask.size
    if pixels > MAX_MASK_PIXELS:
        raise ValueError("Bounded total instance-mask area exceeded")
    decisions, by_row = [], {}
    for row in sorted(primary, key=lambda r: r["id"]):
        members = []
        for member_index, member in enumerate(row["sourceMembers"]):
            points = np.asarray(member["polygon"], np.float32)
            x, y = max(0, math.floor(float(points[:, 0].min()))), max(0, math.floor(float(points[:, 1].min())))
            right = min(image.width, math.ceil(float(points[:, 0].max()))+1)
            bottom = min(image.height, math.ceil(float(points[:, 1].max()))+1)
            polygon = np.zeros((bottom-y, right-x), np.uint8)
            cv2.fillPoly(polygon, [np.rint(points-[x, y]).astype(np.int32)], 1)
            denominator = int(polygon.sum())
            coverage = []
            for instance in sorted(instances, key=lambda i: i["index"]):
                a, b, w, h = instance["bbox"]
                l, t, r, d = max(a, x), max(b, y), min(a+w, right), min(b+h, bottom)
                overlap = (int(np.count_nonzero(polygon[t-y:d-y, l-x:r-x] & instance["mask"][t-b:d-b, l-a:r-a]))
                           if r > l and d > t else 0)
                coverage.append({"instance": instance["index"], "pixels": overlap,
                                 "fraction": overlap/denominator if denominator else 0})
            candidates = [c["instance"] for c in coverage if c["fraction"] >= .98]
            touched = {c["instance"] for c in coverage if c["pixels"] > 0}
            owner = candidates[0] if len(candidates) == 1 and touched == set(candidates) else None
            ref = {"plane": "primary", "page": page, "id": row["id"], "member_index": member_index}
            decision = {"source": ref, "owner": owner, "polygon_pixels": denominator, "coverage": coverage}
            decisions.append(decision)
            members.append((member, ref, owner))
        by_row[row["id"]] = (row, members)
    blocked = {owner for _, members in by_row.values() if any(o is None for _, _, o in members)
               for _, _, owner in members if owner is not None}
    buckets = {}
    for ident, (row, members) in by_row.items():
        safe = all(owner is not None and owner not in blocked for _, _, owner in members)
        for member, ref, owner in members:
            key = ("owner", owner) if safe else ("original", ident)
            buckets.setdefault(key, []).append((member, ref, row))
    regions = []
    for (kind, identity), values in sorted(buckets.items()):
        members, refs = [deepcopy(v[0]) for v in values], [deepcopy(v[1]) for v in values]
        if kind == "original":
            box = deepcopy(values[0][2]["bbox"])
        else:
            points = [p for m in members for p in m["polygon"]]
            x, y = max(0, math.floor(min(p[0] for p in points))-3), max(0, math.floor(min(p[1] for p in points))-3)
            r, b = min(image.width, math.ceil(max(p[0] for p in points))+3), min(image.height, math.ceil(max(p[1] for p in points))+3)
            box = [x, y, r-x, b-y]
        digest = hashlib.sha256(json.dumps({"page": page, "refs": refs, "kind": kind, "owner": identity}, sort_keys=True).encode()).hexdigest()
        reasons = ["container_mask_grouping_review"]
        reasons.extend(reason for _, _, row in values for reason in row.get("reviewReasons", []))
        regions.append({"id": "container-review-"+digest, "bbox": box, "sourceMembers": members, "source_member_refs": refs,
                        "order": min(row.get("order", 0) for _, _, row in values), "score": min(m["score"] for m in members),
                        "owner_instance": identity if kind == "owner" else None, "review": True,
                        "reviewReasons": list(dict.fromkeys(reasons)), "overlay": "label",
                        "erasure_authority": False, "memory_authority": False})
    if len(regions) > 64 or sum(len(r["sourceMembers"]) for r in regions) != sum(len(r["sourceMembers"]) for r in primary):
        raise ValueError("Complete bounded source partition required")
    return {"regions": regions, "source_records": deepcopy(primary), "member_decisions": decisions,
            "blocked_instances": sorted(blocked), "version": VERSION+"-grouping"}


def prepare_container_ocr_crop(image, row, box, decisions, instances):
    """A transient recognizer input, NEVER a display/cleanup patch.

    Source geometry and image stay unchanged. Even a single unsupported source
    polygon pixel vetoes isolation; absence/ambiguity is unchanged-input fallback.
    """
    import hashlib
    import cv2
    import numpy as np
    from PIL import Image
    if (not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box)
            or min(box[:2]) < 0 or min(box[2:]) <= 0 or box[0]+box[2] > image.width or box[1]+box[3] > image.height):
        raise ValueError("Bounded original OCR crop required")
    x, y, w, h = box
    raw = image.crop((x, y, x+w, y+h)).convert("RGB")
    base = {"crop": None, "source_sha256": hashlib.sha256(raw.tobytes()).hexdigest(), "size": raw.size,
            "changed_pixels": 0, "erasure_authority": False}
    matching = [d for d in decisions if d["source"]["id"] == row["id"]]
    if (len(matching) != len(row["sourceMembers"]) or any(d["owner"] is None for d in matching)
            or len({d["owner"] for d in matching}) != 1):
        return dict(base, reason="unknown_or_multiple_containers")
    owner = matching[0]["owner"]
    if any(not any(c["instance"] == owner and c["pixels"] == d["polygon_pixels"] and c["pixels"] > 0
                   for c in d["coverage"]) for d in matching):
        return dict(base, reason="incomplete_source_coverage")
    selected = [i for i in instances if i["index"] == owner]
    if len(selected) != 1:
        raise ValueError("Unique actual instance required")
    instance = selected[0]
    a, b, iw, ih = instance["bbox"]
    mask = instance["mask"]
    if not isinstance(mask, np.ndarray) or mask.dtype != np.uint8 or mask.shape != (ih, iw) or (mask > 1).any():
        raise ValueError("Actual binary container mask required")
    allowed = np.zeros((h, w), np.uint8)
    l, t, r, d = max(a, x), max(b, y), min(a+iw, x+w), min(b+ih, y+h)
    if r > l and d > t:
        allowed[t-y:d-y, l-x:r-x] = mask[t-b:d-b, l-a:r-a]
    for member in row["sourceMembers"]:
        points = np.asarray(member["polygon"], np.float32)-[x, y]
        if (points[:, 0].min() < 0 or points[:, 1].min() < 0
                or points[:, 0].max() >= w or points[:, 1].max() >= h):
            return dict(base, reason="partition_crosses_source_geometry")
        polygon = np.zeros((h, w), np.uint8)
        cv2.fillPoly(polygon, [np.rint(points).astype(np.int32)], 1)
        if np.any(polygon & (1-allowed)):
            return dict(base, reason="incomplete_source_coverage")
    pixels = np.asarray(raw).copy()
    changed = int(np.count_nonzero(np.any(pixels != 255, axis=2) & (allowed == 0)))
    if not changed:
        return dict(base, reason="no_background_change")
    pixels[allowed == 0] = 255
    return dict(base, crop=Image.fromarray(pixels), changed_pixels=changed, owner=owner, reason="isolated_ocr_input_only")


class IsolatedCropEngine:
    """External recognizer boundary with exact current-crop binding, no splicing."""
    def __init__(self, engine, prepared):
        self.engine, self.prepared, self.cursor = engine, prepared, 0

    def recognize_many(self, crops):
        import hashlib
        if self.cursor+len(crops) > len(self.prepared):
            raise ValueError("Unexpected extra OCR crops")
        chosen = []
        for index, crop in enumerate(crops, self.cursor):
            record = self.prepared[index]
            if crop.size != record["size"] or hashlib.sha256(crop.convert("RGB").tobytes()).hexdigest() != record["source_sha256"]:
                raise ValueError("Stale or reordered OCR input")
            chosen.append(record["crop"] if record["crop"] is not None else crop)
        self.cursor += len(crops)
        return self.engine.recognize_many(chosen)


def run(args):
    import hashlib
    import json
    import threading
    import time
    from copy import deepcopy
    from benchmark import DirectoryDataset, audit, dataset_fingerprint
    from compare_page_reports import checked_pages, compare, private_json_path
    from benchmark_pages import assign_to_labels
    from benchmark_hayai_nova import offline_guard
    from benchmark_mit48 import require_memory, system_memory
    from manga_live.ocr import MangaEngine, recognize_regions, partition_ocr_boxes
    output = private_json_path(args.output, new=True)
    content = private_json_path(args.primary).read_bytes()
    parent = json.loads(content)
    if parent.get("cloud") is not False or parent.get("fresh_inference") is not True or parent.get("complete") is False:
        raise ValueError("Complete offline original source report required")
    source_pages = checked_pages(parent)
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    if parent.get("input_fingerprint_sha256") != fingerprint or set(source_pages) != {p[0]["page_id"] for p in pages}:
        raise ValueError("Unchanged exact source coverage/fingerprint required")
    if parent.get("ocr") != MangaEngine.name:
        raise ValueError("Same recognizer control required")
    # Reject bad source metadata/exclusions on ALL pages before detector load.
    for page, image, _ in pages:
        group_with_container_masks(image, source_pages[page["page_id"]][0]["regions"], [], page=page["page_id"])
    require_memory()
    model = ExperimentalBubbleMasks(threads=args.threads)
    tick = time.perf_counter()
    with offline_guard(): model.load()
    isolate = getattr(args, "isolate_ocr_crops", False)
    report = {"schema": 1, "version": VERSION+"-isolate-original-crops-v2" if isolate else VERSION,
              "cloud": False, "images_persisted": False, "isolated_original_ocr_crops": isolate,
              "production_default": False, "fresh_inference": True, "fresh_detection": False,
              "fresh_text_detection": False, "fresh_container_detection": True,
              "fresh_recognition": True, "complete": False, "input_fingerprint_sha256": fingerprint,
              "source_report_sha256": hashlib.sha256(content).hexdigest(), "model_revision": REVISION,
              "graph": model.graph, "detector_load_ms": (time.perf_counter()-tick)*1000,
              "ocr": MangaEngine.name, "threads": args.threads, "runtime": RUNTIME_VERSION,
              "counts": counts, "audit": issues, "resource_start": system_memory(), "pages": [],
              "limitations": ["Container masks are not glyph masks/role/speaker/erasure or memory authority.",
                              "Unreviewed Japanese development labels, not independent ownership/Vi/artwork gold.",
                              "Independent adapter, not proof of exporter parity or commercial redistribution rights."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    def persist():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    planned = {}
    for page, image, _ in pages:
        key = page["page_id"]
        tick = time.perf_counter()
        with offline_guard(): segmentation = model.segment(image)
        detector_ms = (time.perf_counter()-tick)*1000
        tick = time.perf_counter()
        selection = group_with_container_masks(image, source_pages[key][0]["regions"], segmentation["instances"], page=key)
        if isolate:
            # This ablation never coalesces/splits source regions. Only the
            # recognizer's temporary pixel input can change; original boxes,
            # polygons, IDs, exact source plane and bindings stay intact.
            selection["regions"] = deepcopy(source_pages[key][0]["regions"])
            boxes, _ = partition_ocr_boxes(image, selection["regions"])
            selection["prepared_crops"] = [prepare_container_ocr_crop(image, r, boxes.get(r["id"], r["bbox"]),
                                            selection["member_decisions"], segmentation["instances"])
                                            for r in selection["regions"]]
            for region, prepared in zip(selection["regions"], selection["prepared_crops"], strict=True):
                region.update(review=True, reviewReasons=list(dict.fromkeys([*region.get("reviewReasons", []), "ocr_container_input_experiment"])),
                              erasure_authority=False, memory_authority=False)
                if isinstance(region.get("scope"), dict): region["scope"]["memory"] = False
                region["ocrInputIsolation"] = {k: v for k, v in prepared.items() if k not in ("crop", "size")}
        planned[key] = selection
        report["pages"].append({"page": key, "detector_ms": detector_ms, "grouping_ms": (time.perf_counter()-tick)*1000,
                                "preprocess": segmentation["preprocess"], "thresholds": segmentation["thresholds"],
                                "raw_proposals": segmentation["raw_proposals"], "member_decisions": selection["member_decisions"],
                                "blocked_instances": selection["blocked_instances"], "source_records": selection["source_records"],
                                "instances": [{k: v for k, v in i.items() if k != "mask"} | {"mask_pixels": int(i["mask"].sum())}
                                              for i in segmentation["instances"]]})
        # Neither bitmap masks nor contours are persisted.
        del segmentation
        persist()
        print(json.dumps({"page": key, "planned_regions": len(selection["regions"])}), flush=True)
    del model
    require_memory()
    engine = MangaEngine(ROOT / "models/ocr", args.threads)
    tick = time.perf_counter()
    with offline_guard(): engine.load()
    report["recognizer_load_ms"] = (time.perf_counter()-tick)*1000
    for (page, image, labels), record in zip(pages, report["pages"], strict=True):
        selection = planned[page["page_id"]]
        boxes, partition_evidence = partition_ocr_boxes(image, selection["regions"])
        tick = time.perf_counter()
        runner = IsolatedCropEngine(engine, selection["prepared_crops"]) if isolate else engine
        with offline_guard(): regions = recognize_regions(image, selection["regions"], runner, threading.Event(),
                                                         crop_boxes=boxes, partition_evidence=partition_evidence)
        record.update(regions=regions, partitions=partition_evidence, ocr_ms=(time.perf_counter()-tick)*1000)
        record["aligned"], record["unmatched_prediction_ids"] = assign_to_labels(labels, regions)
        persist()
        print(json.dumps({"page": page["page_id"], "recognized_regions": len(regions)}), flush=True)
    rows = [r for p in report["pages"] for r in p["aligned"]]
    report.update(complete=True, aggregate={"annotations": len(rows), "exact": sum(r["edits"] == 0 for r in rows),
                  "edits": sum(r["edits"] for r in rows), "characters": sum(r["characters"] for r in rows),
                  "regions": sum(len(p["regions"]) for p in report["pages"])})
    report["paired_primary"] = compare(parent, report)
    persist()
    print(json.dumps({"aggregate": report["aggregate"], "paired_primary": report["paired_primary"]["aggregate"]}), flush=True)
    return report


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-model", action="store_true")
    parser.add_argument("--setup-inspector", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--folder")
    parser.add_argument("--primary")
    parser.add_argument("--output")
    parser.add_argument("--isolate-ocr-crops", action="store_true",
                        help="Separate v2: no source regrouping; strictly supported transient OCR background isolation")
    parser.add_argument("--threads", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--max-seconds", type=int, choices=range(30, 1801), default=600)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.folder and (args.fetch_model or args.setup_inspector):
        parser.error("Provisioning and offline inference are separate operations")
    if args.fetch_model: download(MODEL_URL, MODEL_PATH, MODEL_SPEC)
    if args.setup_inspector: download(INSPECTOR_URL, INSPECTOR_PATH, INSPECTOR_SPEC)
    if args.inspect: print(json.dumps(inspect_model(), indent=2))
    if args.folder:
        if not args.primary or not args.output: parser.error("Private source report and new output required")
        if args.worker:
            run(args)
        else:
            import subprocess
            from benchmark_mit48 import require_memory
            require_memory()
            subprocess.run([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"], check=True, timeout=args.max_seconds)
    elif not (args.fetch_model or args.setup_inspector or args.inspect): parser.error("Provide an explicit operation")


if __name__ == "__main__": main()
