"""Pinned, explicitly reviewed Hayai comparator; not a production dependency.

Only --fetch-model accesses the network. The two custom modules below were
read in full before being pinned here. They are imported locally after hash
validation, never via AutoModel/trust_remote_code or during a download.
All source images remain in RAM; diagnostics stay in gitignored artifacts/.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import time
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint, normalized, distance
from manga_live.ocr import blank_crop
from provision import download, verify


MODEL_REPO = "JustANormalTinkerer/hayai-ocr-v2.5-nova"
MODEL_REVISION = "2803d0dc005fa4396ab1e7c5a472d2c450a247f7"
MODEL_FILES = {
    "README.md": {"bytes":10484, "gitBlob":"49f8627d033f6756a46ee45f6b877049336cc367"},
    "config.json": {"bytes":367, "gitBlob":"f8948472821236ddca32d94fee9043540a4c0c3d"},
    "configuration_hayai.py": {"bytes":401, "gitBlob":"ea133a410d767943d0e9785dcc8af9b45290195f"},
    "modeling_hayai.py": {"bytes":45551, "gitBlob":"fe4c5c303c55b6643ee19c54501eec0dbd17f767"},
    "model.safetensors": {"bytes":627709088, "sha256":"ac63cd177c5b68bd91e18dd4408e0400461c7cf19f484b0da1643e232d1ffc3a"},
    "tokenizer.json": {"bytes":1247253, "gitBlob":"7188177cd68a86f7df18c32fa564f5a9587c64f2"},
    "tokenizer_config.json": {"bytes":244, "gitBlob":"5331e366a0fb5bc21e54ab8f5710628fe5bb9cf4"},
}
VISION_REPO = "google/siglip2-base-patch16-naflex"
VISION_REVISION = "b53b807d3a2d5e2b3911292f2d69e5341cdc064c"
VISION_FILES = {
    "config.json": {"bytes":329, "gitBlob":"a0b06c765448680b5571e48b4f2334719b9880ef"},
    "preprocessor_config.json": {"bytes":393, "gitBlob":"0b394ef874fa00123ca80d5456646592a052e50e"},
}
MODEL_PATH = ROOT / "artifacts/comparator-models/hayai-nova"
MODULE_PACKAGE = "qa_hayai_"+MODEL_REVISION[:12]
TRAINING_ONLY_TENSORS = {"decoder.ids_head.weight":([226,512],"F32"),
                         "decoder.ids_norm.weight":([512],"F32")}


def fetch_model():
    for filename, spec in MODEL_FILES.items():
        download(f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{filename}", MODEL_PATH / filename, spec)
    for filename, spec in VISION_FILES.items():
        download(f"https://huggingface.co/{VISION_REPO}/resolve/{VISION_REVISION}/{filename}", MODEL_PATH / "siglip2" / filename, spec)


def validate_model(path):
    path = Path(path).resolve()
    for directory, files in ((path, MODEL_FILES), (path / "siglip2", VISION_FILES)):
        for filename, spec in files.items():
            target = directory / filename
            if target.resolve().parent != directory.resolve() or not verify(target, spec):
                raise ValueError("Missing/mismatched pinned Hayai files; use explicit --fetch-model")


def reviewed_modules(path):
    """Call only after validating all files; no mutable sys.path source lookup."""
    package = ModuleType(MODULE_PACKAGE)
    package.__path__ = [str(path)]
    sys.modules[MODULE_PACKAGE] = package
    loaded = []
    for filename in ("configuration_hayai", "modeling_hayai"):
        name = MODULE_PACKAGE+"."+filename
        spec = importlib.util.spec_from_file_location(name, path / (filename+".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        loaded.append(module)
    return loaded


def checked_texts(values, expected):
    if (not isinstance(values, list) or len(values) != expected or
            any(not isinstance(value, str) or len(value) > 8192 for value in values)):
        raise ValueError("Invalid bounded Hayai output")
    # Keep real quotes, newlines, expressive gaps and punctuation intact.
    return values


def checked_loading_info(info, extras):
    """Only two reviewed auxiliary IDS tensors may be unused at inference.

    The card documents the 226-class training-only head; the pinned tensor
    header confirms its exact names/shapes/dtypes. Never broadly ignore keys
    or allow randomly initialized missing recognition weights.
    """
    if any(info.get(key) for key in ("missing_keys","mismatched_keys","error_msgs")):
        raise ValueError("Checkpoint missing/mismatched recognition weights")
    unused = info.get("unexpected_keys",[])
    if set(unused) - TRAINING_ONLY_TENSORS.keys() or any(extras.get(key) != TRAINING_ONLY_TENSORS[key] for key in unused):
        raise ValueError("Checkpoint has unreviewed unused weights")
    return sorted(unused)


def local_image_processor(path):
    """Explicit native PIL path, not the author's torchvision/Fast recipe.

    Record this comparator difference; do not mutate production dependencies
    or claim processor parity from compatible tensor shapes alone.
    """
    from transformers import Siglip2ImageProcessor
    return Siglip2ImageProcessor.from_pretrained(str(path / "siglip2"),local_files_only=True)


@contextmanager
def offline_guard():
    """Fail attempts at Python socket I/O during local inference, not setup.

    Complements local_files_only/HF offline flags; this is not a system-wide
    network trace or a claim about other processes on the user's machine.
    """
    import socket
    attempts = []
    def blocked(*args, **kwargs):
        attempts.append("socket-connect")
        raise RuntimeError("Comparator inference attempted network I/O")
    with patch.object(socket.socket,"connect",blocked), patch.object(socket.socket,"connect_ex",blocked), \
            patch.object(socket,"create_connection",blocked):
        yield attempts


class HayaiRecognizer:
    def __init__(self, patches=512, threads=4):
        if type(patches) is not int or patches not in (256,384,512) or type(threads) is not int or not 1 <= threads <= 8:
            raise ValueError("Unsupported comparator resource budget")
        self.patches, self.threads = patches, threads
        self.model = None
        self.name = f"hayai-nova/{MODEL_REVISION[:12]}-patches{patches}-fp32"
        self.details = {"repo":MODEL_REPO, "revision":MODEL_REVISION, "max_num_patches":patches,
                        "dtype":"float32", "device":"CPU", "max_new_tokens":300,
                        "greedy":True, "production_default":False, "source_reviewed":True,
                        "vision_config_revision":VISION_REVISION, "trust_remote_code":False,
                        "image_processor":"Siglip2ImageProcessor-PIL", "processor_upstream_parity":False}

    def load(self):
        if self.model is not None:
            return
        validate_model(MODEL_PATH)  # Must precede imports of downloaded code.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import torch
        from transformers import PreTrainedTokenizerFast, Siglip2VisionConfig
        torch.set_num_threads(self.threads)
        config_module, model_module = reviewed_modules(MODEL_PATH)
        config = config_module.HayaiConfig.from_pretrained(str(MODEL_PATH), local_files_only=True)
        # Upstream constructor would fetch this config if omitted. Inject the
        # same pinned config locally; Hayai weights already include its vision.
        config.vision_config = Siglip2VisionConfig.from_pretrained(str(MODEL_PATH / "siglip2"), local_files_only=True)
        config.auto_map = {}
        model, info = model_module.HayaiModel.from_pretrained(str(MODEL_PATH), config=config,
            local_files_only=True, use_safetensors=True, torch_dtype=torch.float32, output_loading_info=True)
        from safetensors import safe_open
        extras = {}
        with safe_open(str(MODEL_PATH / "model.safetensors"), framework="pt", device="cpu") as header:
            for key in info.get("unexpected_keys",[]):
                if key in TRAINING_ONLY_TENSORS:
                    tensor = header.get_slice(key)
                    extras[key] = (tensor.get_shape(),tensor.get_dtype())
        self.details["unused_training_only_tensors"] = checked_loading_info(info,extras)
        model.eval()
        tokenizer_config = json.loads((MODEL_PATH / "tokenizer_config.json").read_text(encoding="utf-8"))
        tokenizer = PreTrainedTokenizerFast(tokenizer_file=str(MODEL_PATH / "tokenizer.json"),
            **{key:tokenizer_config[key] for key in ("bos_token","eos_token","pad_token","unk_token")})
        processor = local_image_processor(MODEL_PATH)
        self.model, self.tokenizer, self.processor, self.torch = model, tokenizer, processor, torch

    def recognize_many(self, images):
        results = [""]*len(images)
        valid = [(index,image) for index,image in enumerate(images) if not blank_crop(image)]
        if not valid:
            return results
        self.load()
        # Batch 1 bounds CPU/RAM and keeps a single fixed crop inference seam.
        for index, image in valid:
            inputs = self.processor(images=[image.convert("RGB")], max_num_patches=self.patches,
                                    return_tensors="pt")
            with self.torch.inference_mode():
                values = self.model.generate(pixel_values=inputs["pixel_values"],
                    pixel_attention_mask=inputs["pixel_attention_mask"], spatial_shapes=inputs["spatial_shapes"],
                    tokenizer=self.tokenizer, max_new_tokens=300, num_beams=1, repetition_penalty=1.0,
                    dtype=self.torch.float32, use_cuda_graph=False)
            results[index] = checked_texts(values, 1)[0]
        return results

    def recognize(self, image):
        return self.recognize_many([image])[0]


def checked_destination(value):
    destination = Path(value).resolve()
    if ROOT / "artifacts" not in destination.parents:
        raise ValueError("Diagnostics must stay in gitignored artifacts/")
    return destination


def run(args, engine_override=None):
    destination = checked_destination(args.output)
    engine = engine_override or HayaiRecognizer(args.patches, args.threads)
    if args.full_pages:
        if args.authored:
            raise ValueError("Private --folder is required for full-page diagnostics")
        from benchmark_pages import run as run_pages
        return run_pages(args, engine_override=engine)
    if args.authored:
        from probe_ocr_resampling import controls
        cases = list(controls()); counts, issues, fingerprint = {"eligible_bubbles":len(cases)}, [], None
    else:
        with DirectoryDataset(args.folder) as archive:
            counts, issues, pages = audit(archive); fingerprint = dataset_fingerprint(archive)
        cases = []
        for page,image,bubbles in pages:
            for bubble in bubbles:
                x,y,w,h = (bubble["bbox"][key] for key in ("x","y","w","h"))
                cases.append((page["page_id"]+":"+bubble["bubble_id"], image.crop((x,y,x+w,y+h)), bubble["ja_ocr_truth"]))
    start = time.perf_counter(); engine.load(); load_ms = (time.perf_counter()-start)*1000
    rows = []
    for index,(name,crop,reference) in enumerate(cases):
        start = time.perf_counter(); prediction = engine.recognize(crop); elapsed = (time.perf_counter()-start)*1000
        ref,hyp = normalized(reference), normalized(prediction)
        rows.append({"id":name,"reference":reference,"prediction":prediction,"edits":distance(ref,hyp),
                     "characters":len(ref),"ms":elapsed})
        print(json.dumps({"completed":index+1,"total":len(cases),"id":name}), flush=True)
    durations = sorted(row["ms"] for row in rows)
    from benchmark_paddle_rec import process_memory
    memory = process_memory()
    memory["scope"] = "this comparator process including imports, recognizer and RAM crops; no page detector"
    report = {"schema":1,"source":"authored controls" if args.authored else "private audited source crops",
              "model":engine.details,"counts":counts,"audit":issues,"input_fingerprint_sha256":fingerprint,
              "threads":args.threads,"load_ms":load_ms,"cloud":False,"process_memory":memory,
              "normalization":"NFKC + remove whitespace; no punctuation stripping",
              "python_socket_connections_blocked":True,"socket_attempts":len(args.socket_attempts),
              "runtime_fast_path_failed_dtypes":[str(dtype) for dtype in engine.model.__dict__.get("_failed_dtypes",[])],
              "aggregate":{"crops":len(rows),"exact":sum(row["edits"] == 0 for row in rows),
                    "edits":sum(row["edits"] for row in rows),"characters":sum(row["characters"] for row in rows),
                    "cer":sum(row["edits"] for row in rows)/max(1,sum(row["characters"] for row in rows)),
                    "p50_crop_ms":statistics.median(durations),
                    "p95_crop_ms":durations[min(len(durations)-1,int(len(durations)*.95))]},"rows":rows,
              "limitations":["Private Japanese labels not independently verified; no usable Vietnamese gold.",
                    "Gold crops exclude detection, layout, context, translation and browser latency.",
                    "This is a fixed local comparator, not upstream CPU-parity or commercial shipping clearance.",
                    "Both candidates trained on Manga109-related material; title-held-out generalization is not proven."]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2), encoding="utf-8")
    print(json.dumps({"aggregate":report["aggregate"],"process_memory":report["process_memory"],"output":str(destination)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--authored", action="store_true")
    source.add_argument("--folder")
    parser.add_argument("--fetch-model", action="store_true")
    parser.add_argument("--full-pages", action="store_true")
    parser.add_argument("--patches", type=int, choices=(256,384,512), default=512)
    parser.add_argument("--threads", type=int, choices=range(1,9), default=4)
    parser.add_argument("--output", default=str(ROOT / "artifacts/hayai-nova-authored-20261014.json"))
    args = parser.parse_args()
    if args.fetch_model:
        fetch_model()
    if args.authored or args.folder:
        with offline_guard() as attempts:
            args.socket_attempts = attempts
            run(args)
            if attempts:
                raise RuntimeError("Comparator made blocked network attempts; results cannot pass offline gate")
    elif not args.fetch_model:
        parser.error("Select --authored/--folder, or explicit --fetch-model")
