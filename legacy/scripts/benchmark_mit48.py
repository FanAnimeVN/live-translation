"""Pinned external manga-image-translator OCR48 comparator, NOT a product engine.

Only explicit --fetch-model provisions data. Inference uses reviewed local Git
objects, never imports upstream's package/wrapper, never downloads code, and
never writes source images. Extracted GPL definitions remain in RAM and outside
the distributable. Literal tensor and scalar beam paths are distinct candidates.
This is line recognition with retained app ownership, not upstream pipeline parity.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from copy import deepcopy
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Callable, List, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from comparator_preflight import COMMIT, git_read
from provision import download, verify
from benchmark_paddle_vl import physical_memory

VERSION = "mit48-line-recognizer-v1"
CHECKOUT = ROOT / "artifacts/comparators/manga-image-translator"
MODEL_PATH = ROOT / "artifacts/comparator-models/mit48"
MODEL_SOURCE = "manga_translator/ocr/model_48px.py"
XPOS_SOURCE = "manga_translator/ocr/xpos_relative_position.py"
GEOMETRY_SOURCE = "manga_translator/utils/generic.py"
SOURCES = {
    MODEL_SOURCE: "6f5a8aee4af67223f2b11a9421dd873a18ce78d2deebd6a75be81b5db18ae453",
    XPOS_SOURCE: "27420e6068ab687a084878a4be6c59a245290927fd51057dc9f65838e24e694f",
    GEOMETRY_SOURCE: "4cbc4a937a08bdec1e2413d12fc2600c173a393bd1334fff25896f9d9c954925",
}
ASSETS = {
    "ocr_ar_48px.ckpt": {"bytes": 204290192,
        "sha256": "29daa46d080818bb4ab239a518a88338cbccff8f901bef8c9db191a7cb97671d"},
    "alphabet-all-v7.txt": {"bytes": 186651,
        "sha256": "f5722368146aa0fbcc9f4726866e4efc3203318ebb66c811d8cbbe915576538a"},
}
MODEL_NODES = ("ConvNeXtBlock", "ConvNext_FeatureExtractor", "transformer_encoder_forward",
               "XposMultiheadAttention", "generate_square_subsequent_mask", "Hypothesis",
               "next_token_batch", "OCR")
XPOS_NODES = ("fixed_pos_embedding", "rotate_every_two", "duplicate_interleave",
              "apply_rotary_pos_emb", "XPOS")
MIN_FREE_BYTES = 2 * 1024**3  # conservative launch gate, not a measured peak estimate
MAX_LINE_WIDTH = 2048
EINOPS_WHEEL = ROOT / "artifacts/comparator-runtime/wheels/einops-0.8.1-py3-none-any.whl"
EINOPS_SPEC = {"bytes": 64359,
               "sha256": "919387eb55330f5757c6bea9165c5ff5cfe63a642682ea788a6d472576d81737"}
EINOPS_URL = "https://files.pythonhosted.org/packages/87/62/9773de14fe6c45c23649e98b83231fffd7b9892b6cf863251dc2afa73643/einops-0.8.1-py3-none-any.whl"


def activate_einops():
    # Official pure-Python wheel loaded in this process only, not installed into
    # the companion's env. Setup and inference remain separate invocations.
    if not verify(EINOPS_WHEEL, EINOPS_SPEC):
        raise ValueError("Missing/mismatched isolated einops wheel; use --setup-runtime")
    if "einops" in sys.modules:
        raise ValueError("Use a fresh comparator process; do not mix einops runtimes")
    sys.path.insert(0, str(EINOPS_WHEEL))
    import einops
    if einops.__version__ != "0.8.1" or not einops.__file__.startswith(str(EINOPS_WHEEL)):
        raise ValueError("Unreviewed einops runtime")
    return einops


def checked_source(path, raw):
    if path not in SOURCES or hashlib.sha256(raw).hexdigest() != SOURCES[path]:
        raise ValueError("Unreviewed comparator source hash")
    return raw.decode("utf-8")


def read_source(path, checkout=CHECKOUT):
    # git show only reads frozen objects. No checkout, hooks, fetch or import.
    raw = git_read(checkout, "show", COMMIT + ":" + path).encode("utf-8")
    return checked_source(path, raw)


def select_definitions(source, names):
    definitions = [node for node in ast.parse(source).body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if sorted(node.name for node in definitions) != sorted(names):
        raise ValueError("Missing or duplicate reviewed definition")
    return ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[]))


def geometry_namespace(checkout=CHECKOUT):
    import cv2
    import numpy as np
    source = read_source(GEOMETRY_SOURCE, checkout)
    tree = select_definitions(source, ("sort_pnts", "Quadrilateral"))
    quad = tree.body[1]
    methods = ("__init__", "structure", "get_transformed_region")
    quad.body = [node for node in quad.body if isinstance(node, ast.FunctionDef) and node.name in methods]
    if sorted(node.name for node in quad.body) != sorted(methods):
        raise ValueError("Unexpected geometry definition")
    namespace = {"np": np, "cv2": cv2, "functools": functools, "List": List,
                 "__name__": "external_mit48_geometry"}
    exec(compile(tree, "pinned-mit48-geometry", "exec"), namespace)
    return namespace


def model_namespace(checkout=CHECKOUT):
    import torch
    import numpy as np
    einops = activate_einops()
    namespace = {"torch": torch, "nn": torch.nn, "F": torch.nn.functional,
                 "einops": einops, "np": np, "math": math, "defaultdict": defaultdict,
                 "Callable": Callable, "List": List, "Optional": Optional, "Tuple": Tuple,
                 "Union": Union, "DECODE_BLOCK_LENGTH": 8, "__name__": "external_mit48_model"}
    for path, names in ((XPOS_SOURCE, XPOS_NODES), (MODEL_SOURCE, MODEL_NODES)):
        tree = select_definitions(read_source(path, checkout), names)
        exec(compile(tree, "pinned-" + path, "exec"), namespace)
    return namespace


def validate_assets(path=MODEL_PATH):
    if any(not verify(Path(path) / name, spec) for name, spec in ASSETS.items()):
        raise ValueError("Missing/mismatched pinned MIT48 assets; explicit --fetch-model required")


def require_memory():
    memory = physical_memory()
    if memory is None or memory["available_physical_bytes"] < MIN_FREE_BYTES:
        raise RuntimeError("Insufficient/unmeasured RAM for isolated MIT48 model launch")
    return memory


def system_memory():
    """Windows commit headroom is not psutil.swap_memory().free."""
    memory = physical_memory()
    if os.name != "nt" or memory is None:
        return memory
    import ctypes
    from ctypes import wintypes
    class Status(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]
    status = Status()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {**memory, "commit_unavailable": True}
    return {**memory, "available_commit_bytes": status.ullAvailPageFile,
            "commit_limit_bytes": status.ullTotalPageFile}


def decode_tokens(tokens, dictionary):
    if not isinstance(tokens, list) or len(tokens) > 256:
        raise ValueError("Unbounded comparator token sequence")
    if any(type(token) is not int or not 0 <= token < len(dictionary) for token in tokens):
        raise ValueError("Invalid comparator token")
    output = []
    for token in tokens:
        text = dictionary[token]
        if text == "<S>":
            continue
        if text == "</S>":
            break
        output.append(" " if text == "<SP>" else text)
    return "".join(output)


def prediction_record(tokens, score, dictionary):
    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1.000001:
        raise ValueError("Invalid raw beam score")
    text = decode_tokens(tokens, dictionary)
    return {"token_ids": tokens, "raw_text": text, "score": score,
            "score_is_correctness_probability": False,
            "upstream_threshold": .2, "upstream_threshold_accepted": score >= .2,
            "terminated": any(dictionary[token] == "</S>" for token in tokens),
            "erasure_authority": False}


def rectify_line(image, polygon, geometry):
    import numpy as np
    pixels = np.asarray(image.convert("RGB"))
    points = np.asarray(polygon, dtype=np.float64)
    if (points.shape != (4, 2) or not np.isfinite(points).all()
            or pixels.size == 0 or image.width * image.height > 12000000):
        raise ValueError("Invalid line polygon/source")
    quad = geometry["Quadrilateral"](points, "", 0)
    a, b, c, d = [value.astype(np.float32) for value in quad.structure]
    h, w = np.linalg.norm(b-a), np.linalg.norm(c-d)
    if min(h, w) <= 0:
        raise ValueError("Degenerate line")
    length = max(2, round(48 * (h/w if quad.direction == "v" else w/h)))
    if length > MAX_LINE_WIDTH:
        raise ValueError("oversize_line")
    low, high = points.astype(np.int64).min(axis=0), points.astype(np.int64).max(axis=0)
    if min(image.width, high[0]) <= max(0, low[0]) or min(image.height, high[1]) <= max(0, low[1]):
        raise ValueError("Line outside source")
    crop = quad.get_transformed_region(pixels, quad.direction, 48)
    if crop.shape != (48, length, 3) or crop.dtype != np.uint8:
        raise ValueError("Unexpected upstream rectification output")
    return crop, quad.direction


def proposal_units(page):
    regions = page.get("regions", [])
    if not isinstance(regions, list) or len(regions) > 512:
        raise ValueError("Unbounded source regions")
    units, seen = [], set()
    for region in regions:
        identity = region.get("id")
        members = region.get("sourceMembers")
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError("Invalid/duplicate source region ID")
        if not isinstance(members, list) or not 1 <= len(members) <= 512:
            raise ValueError("Retained source members required; a union box is not a line")
        if type(region.get("readerExcluded", False)) is not bool:
            raise ValueError("Invalid reader exclusion")
        seen.add(identity)
        units.append({"id": identity, "members": deepcopy(members),
                      "readerExcluded": bool(region.get("readerExcluded", False))})
    return units


def validate_assignment_state(torch, model, state):
    """Assignment preserves checkpoint properties; ordinary copy-loading doesn't."""
    expected = model.state_dict()
    if not 1 <= len(state) <= 2048 or set(state) != set(expected):
        raise ValueError("Unreviewed checkpoint keys/buffers")
    for name, value in state.items():
        target = expected[name]
        if (value.is_meta or value.device.type != "cpu" or value.layout != torch.strided
                or target.layout != torch.strided or value.shape != target.shape
                or value.dtype != target.dtype or value.stride() != target.stride()):
            raise ValueError("Unreviewed checkpoint tensor properties")
    left, right = state["embd.weight"], state["pred.weight"]
    same_region = (left.untyped_storage().data_ptr() == right.untyped_storage().data_ptr()
                   and left.storage_offset() == right.storage_offset())
    if not same_region and not torch.equal(left, right):
        raise ValueError("Inconsistent checkpoint embedding/output tie")


def validate_materialized_model(torch, model):
    """Include nonpersistent buffers and tensors outside state_dict registrations."""
    seen = set()
    def check(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, torch.Tensor):
            if value.is_meta or value.device.type != "cpu":
                raise ValueError("Unmaterialized/non-CPU model tensor")
        elif isinstance(value, dict):
            for item in value.values():
                check(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                check(item)
    for value in (*model.parameters(), *model.buffers()):
        check(value)
    for module in model.modules():
        check(vars(module))
    if model.pred.weight is not model.embd.weight:
        raise ValueError("Model embedding/output tie not restored")


class Mit48Recognizer:
    def __init__(self, beam="tensor", threads=2, checkout=CHECKOUT, *, loader="copy"):
        if (beam not in ("tensor", "scalar") or type(threads) is not int or not 1 <= threads <= 4
                or loader not in ("copy", "mmap-meta")):
            raise ValueError("Unreviewed MIT48 configuration")
        self.beam, self.threads, self.checkout, self.loader = beam, threads, checkout, loader
        self.model = None

    def load(self):
        if self.model is not None:
            return
        started = time.perf_counter()
        require_memory()  # before torch import, allocation or checkpoint access
        validate_assets()
        from benchmark_hayai_nova import offline_guard
        with offline_guard():
            namespace = model_namespace(self.checkout)
            import torch
            torch.set_num_threads(self.threads)
            with (MODEL_PATH / "alphabet-all-v7.txt").open(encoding="utf-8") as stream:
                self.dictionary = [line[:-1] for line in stream.readlines()]
            if self.dictionary[1:3] != ["<S>", "</S>"]:
                raise ValueError("Unexpected pinned alphabet token IDs")
            load_options = {"map_location": "cpu", "weights_only": True}
            if self.loader == "mmap-meta":
                load_options["mmap"] = True
            state = torch.load(MODEL_PATH / "ocr_ar_48px.ckpt", **load_options)
            if not isinstance(state, dict) or any(not isinstance(k, str) or not isinstance(v, torch.Tensor)
                                                  for k, v in state.items()):
                raise ValueError("Unreviewed checkpoint structure; no unsafe loading fallback")
            if self.loader == "mmap-meta":
                with torch.device("meta"):
                    model = namespace["OCR"](self.dictionary, 768)
                validate_assignment_state(torch, model, state)
                model.load_state_dict(state, strict=True, assign=True)
                model.pred.weight = model.embd.weight
                validate_materialized_model(torch, model)
            else:
                model = namespace["OCR"](self.dictionary, 768)
                model.load_state_dict(state, strict=True)
            self.model = model.eval()
            self.load_ms = (time.perf_counter()-started)*1000

    def recognize(self, crop):
        self.load()
        import numpy as np
        import torch
        from benchmark_hayai_nova import offline_guard
        if crop.dtype != np.uint8 or crop.ndim != 3 or crop.shape[0] != 48 or crop.shape[2] != 3:
            raise ValueError("Unrectified MIT48 input")
        width = crop.shape[1]
        if not 2 <= width <= MAX_LINE_WIDTH:
            raise ValueError("oversize_line")
        # Preserve upstream padding formula literally, even though it is not
        # the usual round-up-to-four expression.
        padded = np.zeros((1, 48, 4 * (width + 7) // 4, 3), dtype=np.uint8)
        padded[0, :, :width] = crop
        tensor = ((torch.from_numpy(padded).float()-127.5)/127.5).permute(0, 3, 1, 2)
        method = self.model.infer_beam_batch_tensor if self.beam == "tensor" else self.model.infer_beam_batch
        with offline_guard(), torch.inference_mode():
            result = method(tensor, [width], beams_k=5, max_seq_length=255)
        if not isinstance(result, list) or len(result) != 1:
            raise ValueError("Invalid bounded MIT48 output")
        tokens, score, *_colors = result[0]
        return prediction_record(tokens.tolist(), float(score), self.dictionary)


def rectification_smoke(checkout=CHECKOUT):
    """Geometry-only comparison with independently specified destination quads."""
    import cv2
    import numpy as np
    from PIL import Image
    geometry = geometry_namespace(checkout)
    pixels = np.arange(120 * 120 * 3, dtype=np.uint8).reshape(120, 120, 3)
    cases = [([[10, 10], [90, 10], [90, 30], [10, 30]], "h"),
             ([[10, 10], [30, 10], [30, 90], [10, 90]], "v"),
             ([[10, 10], [90, 20], [88, 40], [8, 30]], "h"),
             ([[-5, 10], [75, 10], [75, 30], [-5, 30]], "h")]
    for polygon, direction in cases:
        result, actual_direction = rectify_line(Image.fromarray(pixels), polygon, geometry)
        assert actual_direction == direction
        points = np.asarray(polygon, dtype=np.int64)
        x1, y1 = np.maximum(points.min(axis=0), 0)
        x2, y2 = np.minimum(points.max(axis=0), [120, 120])
        width, height = (result.shape[1], 48) if direction == "h" else (48, result.shape[1])
        target = np.array([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype=np.float32)
        matrix, _ = cv2.findHomography(points-[x1, y1], target, cv2.RANSAC, 5.0)
        expected = cv2.warpPerspective(pixels[y1:y2, x1:x2], matrix, (width, height))
        if direction == "v":
            expected = cv2.rotate(expected, cv2.ROTATE_90_COUNTERCLOCKWISE)
        assert np.array_equal(result, expected), "Adapter changed pinned rectification pixels"
    return {"cases": len(cases), "pixel_equal": True, "model_loaded": False,
            "limitation": "Synthetic adapter geometry check, not real OCR or full wrapper parity"}


def preflight(checkout=CHECKOUT):
    from importlib.metadata import version, PackageNotFoundError
    for path in SOURCES:
        read_source(path, checkout)
    memory = physical_memory()
    assets = {name: verify(MODEL_PATH / name, spec) for name, spec in ASSETS.items()}
    runtime = {}
    for name in ("torch", "numpy", "opencv-python-headless", "opencv-python"):
        try:
            runtime[name] = version(name)
        except PackageNotFoundError:
            runtime[name] = None
    runtime["isolated_einops_wheel_verified"] = verify(EINOPS_WHEEL, EINOPS_SPEC)
    return {"version": VERSION, "commit": COMMIT, "source_sha256": SOURCES,
            "runtime": runtime,
            "assets_verified": assets, "memory": memory, "minimum_launch_free_bytes": MIN_FREE_BYTES,
            "can_launch": all(assets.values()) and runtime["isolated_einops_wheel_verified"]
                          and runtime["torch"] is not None and runtime["numpy"] is not None
                          and (runtime["opencv-python"] or runtime["opencv-python-headless"]) is not None
                          and memory is not None
                          and memory["available_physical_bytes"] >= MIN_FREE_BYTES,
            "cloud": False, "production_default": False, "fresh_inference": False,
            "distribution_cleared": False, "wrapper_parity": False}


def proposal_inputs(args):
    from benchmark import dataset_source, dataset_fingerprint, audit
    from compare_page_reports import private_json_path
    destination = private_json_path(args.output, new=True)
    proposals = json.loads(Path(args.proposals).read_text(encoding="utf-8"))
    with dataset_source(args) as source:
        fingerprint = dataset_fingerprint(source)
        _, _, pages = audit(source)
    if proposals.get("input_fingerprint_sha256") != fingerprint:
        raise ValueError("Proposal/source fingerprint mismatch")
    by_page = {page["page"]: page for page in proposals["pages"]}
    if len(by_page) != len(proposals["pages"]) or set(by_page) != {page["page_id"] for page, _, _ in pages}:
        raise ValueError("Proposal page coverage mismatch")
    # Freeze and validate ownership before loading any recognizer. No gold
    # transcript, prior prediction or label bbox is used to select line input.
    units = {key: proposal_units(value) for key, value in by_page.items()}
    return destination, proposals, pages, units, fingerprint, by_page


def order_recorded_lines(lines, *, fragment_precedence=False):
    """Order retained line evidence, never edit strings, crops or ownership.

    V1 is the original comparator's stable RTL/top-down priority. Explicit v2
    adds only disjoint same-column/row precedence, using the Baberu probe's
    already fixed 60% source-projection rule, not padded/rectified crops.
    """
    if (type(fragment_precedence) is not bool or not isinstance(lines, list)
            or not 1 <= len(lines) <= 512):
        raise ValueError("Bounded recorded lines required")
    bounds, seen = {}, set()
    owner = lines[0].get("region_id") if isinstance(lines[0], dict) else None
    for position, row in enumerate(lines):
        if not isinstance(row, dict):
            raise ValueError("Invalid recorded line")
        index, text = row.get("member_index"), row.get("raw_text")
        status = row.get("status")
        if (not isinstance(owner, str) or row.get("region_id") != owner
                or type(index) is not int or index < 0 or index in seen
                or not isinstance(text, str) or len(text) > 4096
                or status not in ("recognized", "adapter_review", "reader_excluded")
                or status == "recognized" and row.get("direction") not in ("v", "h")
                or status != "recognized" and text):
            raise ValueError("Recorded line identity/status mismatch")
        seen.add(index)
        source = row.get("source")
        polygon = source.get("polygon") if isinstance(source, dict) else None
        if (not isinstance(polygon, list) or len(polygon) != 4 or any(
                not isinstance(p, list) or len(p) != 2 or any(
                    type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in p) for p in polygon)):
            raise ValueError("Invalid recorded source polygon")
        xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
        box = (min(xs), min(ys), max(xs), max(ys))
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError("Degenerate recorded source polygon")
        bounds[position] = box
    vertical = sum(row.get("direction") == "v" for row in lines) > len(lines)/2
    def priority(position):
        points = lines[position]["source"]["polygon"]
        return (-statistics.mean(p[0] for p in points), min(p[1] for p in points), position) if vertical else (
            min(p[1] for p in points), min(p[0] for p in points), position)
    successors = {position: set() for position in bounds}
    predecessors = {position: 0 for position in bounds}
    if fragment_precedence:
        for a, (ax1, ay1, ax2, ay2) in bounds.items():
            for b, (bx1, by1, bx2, by2) in bounds.items():
                if a == b:
                    continue
                overlap = min(ax2, bx2)-max(ax1, bx1) if vertical else min(ay2, by2)-max(ay1, by1)
                extent = min(ax2-ax1, bx2-bx1) if vertical else min(ay2-ay1, by2-by1)
                precedes = ay2 <= by1 if vertical else ax2 <= bx1
                if overlap >= .6*extent and precedes:
                    successors[a].add(b)
                    predecessors[b] += 1
    ready = [position for position, count in predecessors.items() if count == 0]
    ordered = []
    while ready:
        position = min(ready, key=priority)
        ready.remove(position)
        ordered.append(deepcopy(lines[position]))
        for child in successors[position]:
            predecessors[child] -= 1
            if predecessors[child] == 0:
                ready.append(child)
    if len(ordered) != len(lines):
        raise ValueError("Conflicting source fragment precedence")
    return ordered


def replay_line_order(recorded, proposals, pages, fingerprint):
    """Model-free v2 replay with exact original source-member verification."""
    from compare_page_reports import checked_pages, compare
    from benchmark_pages import assign_to_labels
    if (recorded.get("version") != VERSION or recorded.get("commit") != COMMIT
            or recorded.get("source_sha256") != SOURCES
            or recorded.get("complete") is not True or recorded.get("fresh_inference") is not True
            or recorded.get("cloud") is not False or recorded.get("beam") not in ("tensor", "scalar")
            or recorded.get("input_fingerprint_sha256") != fingerprint
            or proposals.get("input_fingerprint_sha256") != fingerprint):
        raise ValueError("Complete matching original OCR48 inference required")
    before = checked_pages(recorded)
    source_pages = {}
    if not isinstance(proposals.get("pages"), list):
        raise ValueError("Matching source proposals required")
    for source_page in proposals["pages"]:
        key = source_page.get("page") if isinstance(source_page, dict) else None
        if not isinstance(key, str) or key in source_pages:
            raise ValueError("Duplicate or missing proposal page")
        source_pages[key] = source_page
    if ({page[0]["page_id"] for page in pages} != set(before) or len(pages) != len(before)
            or set(before) != set(source_pages)):
        raise ValueError("Matching complete source coverage required")
    report = {"version": VERSION, "commit": COMMIT, "source_sha256": deepcopy(SOURCES),
              "input_fingerprint_sha256": fingerprint, "beam": recorded["beam"],
              "loader": recorded.get("loader"), "cloud": False, "production_default": False,
              "fresh_inference": False, "model_loaded": False, "complete": False,
              "reading_order_recipe": "source-fragment-precedence-v2", "pages": [],
              "limitations": ["Replay of unchanged raw line OCR, not new inference or upstream wrapper parity.",
                              "Line elapsed_ms is inherited source evidence, not replay/OCR latency.",
                              "Unreviewed development labels; no translation, artwork or erasure authority."]}
    for page, image, labels in pages:
        key = page["page_id"]
        original, _ = before[key]
        source_page = source_pages[key]
        units = proposal_units(source_page)
        original_regions = {r["id"]: r for r in original["regions"]}
        source_regions = {r["id"]: r for r in source_page["regions"]}
        if set(original_regions) != set(source_regions):
            raise ValueError("Recorded region coverage disagrees with source")
        lines = original.get("lines")
        if not isinstance(lines, list) or len(lines) != sum(len(u["members"]) for u in units):
            raise ValueError("Complete retained line coverage required")
        by_unit = {unit["id"]: [] for unit in units}
        for row in lines:
            if not isinstance(row, dict) or row.get("region_id") not in by_unit:
                raise ValueError("Recorded line owner mismatch")
            by_unit[row["region_id"]].append(row)
        regions = []
        for unit in units:
            old, source = original_regions[unit["id"]], source_regions[unit["id"]]
            members, rows = unit["members"], by_unit[unit["id"]]
            ordered_before = order_recorded_lines(rows)
            if (len(rows) != len(members) or {r["member_index"] for r in rows} != set(range(len(members)))
                    or old.get("bbox") != source.get("bbox") or old.get("order", 0) != source.get("order", 0)
                    or old.get("ja") != "".join(r["raw_text"] for r in ordered_before)):
                raise ValueError("Recorded geometry/text disagrees with source inference")
            for row in rows:
                member = members[row["member_index"]]
                if (row.get("source") != member or row.get("erasure_authority") is not False
                        or (row["status"] == "reader_excluded") != unit["readerExcluded"]):
                    raise ValueError("Recorded member/exclusion mismatch")
                if any(x > image.width or y > image.height for x, y in member["polygon"]):
                    raise ValueError("Recorded polygon outside source image")
            tick = time.perf_counter()
            ordered_after = order_recorded_lines(rows, fragment_precedence=True)
            regions.append({**deepcopy(old), "ja": "".join(r["raw_text"] for r in ordered_after),
                            "member_order": [r["member_index"] for r in ordered_after],
                            "ordering_replay_ms": (time.perf_counter()-tick)*1000,
                            "erasure_authority": False, "memory_authority": False, "review_only": True})
        # Verify the stored score against this same unchanged source/gold pack,
        # only after source-only ordering. Gold never supplies crop/order hints.
        old_aligned, old_unmatched = assign_to_labels(labels, original["regions"])
        if old_aligned != original["aligned"] or old_unmatched != original["unmatched_prediction_ids"]:
            raise ValueError("Recorded alignment disagrees with unchanged source labels")
        aligned, unmatched = assign_to_labels(labels, regions)
        report["pages"].append({"page": key, "lines": deepcopy(lines), "regions": regions,
                                "aligned": aligned, "unmatched_prediction_ids": unmatched})
    rows = [row for page in report["pages"] for row in page["aligned"]]
    report.update(complete=True, aggregate={"annotations": len(rows),
                  "exact": sum(row["edits"] == 0 for row in rows),
                  "edits": sum(row["edits"] for row in rows),
                  "characters": sum(row["characters"] for row in rows)})
    report["comparison"] = compare(recorded, report)
    return report


def run_order_replay(args):
    from compare_page_reports import private_json_path
    destination, proposals, pages, _, fingerprint, _ = proposal_inputs(args)
    raw = private_json_path(args.reorder_from).read_bytes()
    proposal_raw = private_json_path(args.proposals).read_bytes()
    report = replay_line_order(json.loads(raw), proposals, pages, fingerprint)
    report.update(source_report_sha256=hashlib.sha256(raw).hexdigest(),
                  proposal_report_sha256=hashlib.sha256(proposal_raw).hexdigest())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"aggregate": report["aggregate"], "comparison": report["comparison"]["aggregate"]}))


def run_geometry(args):
    """Exercise real retained polygons without launching/loading any model."""
    destination, _, pages, units, fingerprint, _ = proposal_inputs(args)
    geometry = geometry_namespace(Path(args.checkout))
    report = {"version": VERSION, "input_fingerprint_sha256": fingerprint,
              "source_sha256": SOURCES, "kind": "geometry-only", "fresh_inference": False,
              "model_loaded": False, "cloud": False, "pages": []}
    for page, image, _labels in pages:
        rows = []
        for unit in units[page["page_id"]]:
            for index, member in enumerate(unit["members"]):
                row = {"region_id": unit["id"], "member_index": index,
                       "readerExcluded": unit["readerExcluded"]}
                try:
                    crop, direction = rectify_line(image, member["polygon"], geometry)
                    row.update(status="rectified", direction=direction, size=[crop.shape[1], 48])
                except ValueError as error:
                    row.update(status="adapter_review", reason=str(error))
                rows.append(row)
        report["pages"].append({"page": page["page_id"], "members": rows})
    rows = [row for page in report["pages"] for row in page["members"]]
    report["aggregate"] = {"members": len(rows), "rectified": sum(row["status"] == "rectified" for row in rows),
                           "adapter_review": sum(row["status"] != "rectified" for row in rows)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report["aggregate"]))


def run_proposals(args):
    from benchmark_pages import assign_to_labels
    from benchmark_hayai_nova import offline_guard
    from benchmark_paddle_rec import process_memory
    destination, _, pages, units, fingerprint, by_page = proposal_inputs(args)
    recognizer = Mit48Recognizer(args.beam, args.threads, Path(args.checkout), loader=args.loader)
    recognizer.load()
    geometry = geometry_namespace(Path(args.checkout))
    report = {**preflight(Path(args.checkout)), "fresh_inference": True, "complete": False,
              "beam": args.beam, "loader": args.loader, "load_ms": recognizer.load_ms,
              "input_fingerprint_sha256": fingerprint, "pages": [],
              "score_statistic": "exp(sum(logp))" if args.beam == "tensor" else "exp(mean(logp))",
              "ownership": "recorded-app-regions; per-line orientation; not upstream direction consensus",
              "limitations": ["Unreviewed development labels, not held-out Japanese gold",
                              "Raw and thresholded scores kept separately; no calibrated confidence",
                              "No translation, erasure, context, reader memory or production promotion"]}
    started = time.monotonic()
    for page, image, labels in pages:
        region_predictions, line_rows = [], []
        for unit in units[page["page_id"]]:
            lines = []
            for index, member in enumerate(unit["members"]):
                if time.monotonic()-started > args.max_seconds:
                    raise TimeoutError("Finite comparator budget exhausted; no completed quality score")
                row = {"region_id": unit["id"], "member_index": index, "source": deepcopy(member)}
                tick = time.perf_counter()
                if unit["readerExcluded"]:
                    row.update(status="reader_excluded", raw_text="", erasure_authority=False)
                else:
                    try:
                        crop, direction = rectify_line(image, member["polygon"], geometry)
                    except ValueError as error:
                        # Only adapter bounds/errors are recoverable. Loading,
                        # unexpected model failures and OOM terminate the run.
                        row.update(status="adapter_review", error_type=type(error).__name__, raw_text="",
                                   erasure_authority=False)
                    else:
                        with offline_guard():
                            result = recognizer.recognize(crop)
                        row.update(result, status="recognized", direction=direction,
                                   rectified_size=[crop.shape[1], 48])
                row["elapsed_ms"] = (time.perf_counter()-tick)*1000
                line_rows.append(row)
                lines.append(row)
            # Keep original v1 policy for new recognition; v2 is replay-only.
            lines = order_recorded_lines(lines)
            original = next(r for r in by_page[page["page_id"]]["regions"] if r["id"] == unit["id"])
            region_predictions.append({"id": unit["id"], "bbox": deepcopy(original["bbox"]),
                                       "order": original.get("order", 0),
                                       "ja": "".join(line["raw_text"] for line in lines)})
        aligned, unmatched = assign_to_labels(labels, region_predictions)
        report["pages"].append({"page": page["page_id"], "lines": line_rows,
                                "regions": region_predictions, "aligned": aligned,
                                "unmatched_prediction_ids": unmatched})
        report["process_memory"] = {**process_memory(),
            "scope": "recognizer process including imports, rectification and RAM crops; no detector loaded"}
        report["physical_memory_after_page"] = physical_memory()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({"page": page["page_id"], "lines": len(line_rows)}), flush=True)
    rows = [row for page in report["pages"] for row in page["aligned"]]
    report.update(complete=True, aggregate={"annotations": len(rows),
                  "exact": sum(row["reference"] == row["prediction"] for row in rows),
                  "edits": sum(row["edits"] for row in rows),
                  "characters": sum(row["characters"] for row in rows)})
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report["aggregate"]))


def run_load_only(args):
    """Separate heavy-runtime smoke; never reads source images or runs recognition."""
    from compare_page_reports import private_json_path
    from benchmark_paddle_rec import process_memory
    destination = private_json_path(args.output, new=True)
    before = system_memory()
    recognizer = Mit48Recognizer(args.beam, args.threads, Path(args.checkout), loader=args.loader)
    recognizer.load()
    report = {"version": VERSION, "commit": COMMIT, "source_sha256": SOURCES,
              "kind": "load-only", "loader": args.loader, "model_loaded": True,
              "fresh_inference": False, "production_default": False, "cloud": False,
              "images_read": False, "load_ms": recognizer.load_ms,
              "system_memory_before": before, "system_memory_after": system_memory(),
              "process_memory": {**process_memory(),
                  "scope": "load-only process including imports and recognizer; no detector or source images"},
              "limitation": "Successful load is not numerical parity, inference safety, latency or OCR accuracy"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps({"kind": report["kind"], "loader": args.loader, "model_loaded": True,
                      "fresh_inference": False, "load_ms": recognizer.load_ms}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", default=str(CHECKOUT))
    parser.add_argument("--fetch-model", action="store_true")
    parser.add_argument("--setup-runtime", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--rectification-smoke", action="store_true")
    parser.add_argument("--geometry-only", action="store_true")
    parser.add_argument("--load-only", action="store_true")
    parser.add_argument("--reorder-from", help="Model-free v2 order replay of a completed original OCR48 report")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--folder")
    group.add_argument("--zip")
    parser.add_argument("--proposals")
    parser.add_argument("--output")
    parser.add_argument("--beam", choices=("tensor", "scalar"), default="tensor")
    parser.add_argument("--loader", choices=("copy", "mmap-meta"), default="copy")
    parser.add_argument("--threads", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--max-seconds", type=int, choices=range(30, 1801), default=600)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.reorder_from and (args.fetch_model or args.setup_runtime or args.load_only or args.geometry_only
                              or args.rectification_smoke or args.worker or args.preflight):
        parser.error("Ordering replay must be separate from preparation/model execution")
    if (args.folder or args.zip or args.load_only) and (args.fetch_model or args.setup_runtime):
        parser.error("Provisioning and private inference must be separate invocations")
    if args.load_only and (args.folder or args.zip or args.geometry_only or args.rectification_smoke):
        parser.error("Load-only smoke is separate from geometry and source-image inference")
    if args.setup_runtime:
        download(EINOPS_URL, EINOPS_WHEEL, EINOPS_SPEC)
    if args.fetch_model:
        for name, spec in ASSETS.items():
            download("https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.3/" + name,
                     MODEL_PATH / name, spec)
    if args.rectification_smoke:
        print(json.dumps(rectification_smoke(Path(args.checkout))))
    if args.preflight:
        print(json.dumps(preflight(Path(args.checkout))))
    if args.load_only:
        if not args.output:
            parser.error("Load-only smoke requires a new private --output")
        if args.worker:
            run_load_only(args)
        else:
            require_memory()
            subprocess.run([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"],
                           check=True, timeout=args.max_seconds)
    elif args.folder or args.zip:
        if not args.proposals or not args.output:
            parser.error("Recognition requires retained --proposals and a new private --output")
        if args.reorder_from:
            run_order_replay(args)
        elif args.geometry_only:
            run_geometry(args)
        elif args.worker:
            run_proposals(args)
        else:
            # Timeout also bounds an inference call that never returns. This
            # is the one child we created; no unrelated app/process is stopped.
            subprocess.run([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"],
                           check=True, timeout=args.max_seconds)
    elif args.geometry_only or args.reorder_from:
        parser.error("Geometry audit requires a private dataset, retained proposals and output")
    elif not (args.fetch_model or args.setup_runtime or args.preflight or args.rectification_smoke):
        parser.error("Select explicit preparation or a private proposal recognition run")


if __name__ == "__main__":
    main()
