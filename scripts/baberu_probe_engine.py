"""Audited local ONNX host loop; no executable model code or network access.

Model interface and published decode settings inspected at
https://huggingface.co/genshiai-daichi/baberu-ocr/blob/fdf292a15dae9f5af37dd76bb408679dc4bcdfe4/onnx_infer.py
Apache-2.0 model/code, genshiai-daichi. Comparator only, not shipped runtime.
"""
import json
import threading
import unicodedata

from install_baberu_probe import FILES, MODEL_DIR, REVISION, verified


class BaberuProbe:
    name = "baberu-ocr/" + REVISION + "/vision-int4-decoder-int8"

    def __init__(self, threads=4, cancel=None):
        if type(threads) is not int or not 1 <= threads <= 8:
            raise ValueError("Bounded CPU threads required")
        self.threads = threads
        self.cancel = cancel or threading.Event()
        self.sessions = None
        self.last_decode = {}

    def load(self):
        if self.sessions is not None:
            return
        for name, spec in FILES.items():
            if not verified(MODEL_DIR / name, spec):
                raise ValueError("Missing/unverified Baberu data; run the explicit comparator installer")
        charset = json.loads((MODEL_DIR / "tokenizer/vocab.json").read_text(encoding="utf-8"))
        if (not isinstance(charset, list) or not 10000 <= len(charset) <= 20000
                or any(not isinstance(ch, str) or len(ch) != 1 for ch in charset)
                or len(set(charset)) != len(charset)):
            raise ValueError("Invalid character vocabulary")
        self.characters = ["", "", "", "", *charset]
        self.content_ids = {i for i, ch in enumerate(self.characters) if ch and ch not in "ーｰ〜~"
                            and unicodedata.category(ch)[0] in "LN"}
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sessions = [ort.InferenceSession(str(MODEL_DIR / "onnx" / name), options,
                         providers=["CPUExecutionProvider"]) for name in
                         ("vision_int4.onnx", "decoder_prefill_int8.onnx", "decoder_step_int8.onnx")]

    def recognize(self, image):
        from PIL import Image
        import numpy as np
        from manga_live.ocr import blank_crop
        if self.cancel.is_set():
            raise RuntimeError("OCR canceled")
        self.last_decode = {"eos": False, "run_cap": False, "unknown_token": False, "tokens": 0}
        if blank_crop(image):
            self.last_decode["blank"] = True
            return ""
        self.load()
        # Preserve RGB, whole-crop resize and ImageNet normalization exactly;
        # no punctuation/whitespace cleanup after decoding.
        pixels = np.asarray(image.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC), dtype=np.float32) / 255
        pixels = ((pixels - np.array([.485, .456, .406], np.float32)) /
                  np.array([.229, .224, .225], np.float32)).transpose(2, 0, 1)[None]
        vision, prefill, step = self.sessions
        embeds = vision.run(["vision_embeds"], {"pixel_values": pixels})[0]
        results = prefill.run(None, {"vision_embeds": embeds, "input_ids": np.array([[1]], np.int64)})
        sequence = [1]
        output = []
        position = embeds.shape[1] + 1
        cache_names = [f"past_{kind}{layer}" for kind in ("k", "v") for layer in range(6)]
        for _ in range(256):
            if self.cancel.is_set():
                raise RuntimeError("OCR canceled")
            logits = results[0][0, -1].astype(np.float64)
            if logits.shape != (len(self.characters),) or len(results) != 13 or not np.isfinite(logits).all():
                raise ValueError("Unexpected OCR graph output")
            seen = list(set(sequence))
            scores = logits[seen]
            logits[seen] = np.where(scores < 0, scores * 1.2, scores / 1.2)
            if output and output[-1] > 3:
                last = output[-1]
                limit = 12 if last in self.content_ids else 16
                run = 0
                for token in reversed(output):
                    if token != last:
                        break
                    run += 1
                if run >= limit:
                    logits[last] = -np.inf
                    self.last_decode["run_cap"] = True
            token = int(logits.argmax())
            if token == 2:
                self.last_decode["eos"] = True
                break
            output.append(token)
            sequence.append(token)
            self.last_decode["unknown_token"] |= token < 4
            if len(output) == 256:
                break
            feed = {"input_ids": np.array([[token]], np.int64), "position_ids": np.array([[position]], np.int64)}
            feed.update(zip(cache_names, results[1:]))
            results = step.run(None, feed)
            position += 1
        self.last_decode["tokens"] = len(output)
        return "".join(self.characters[token] for token in output)
