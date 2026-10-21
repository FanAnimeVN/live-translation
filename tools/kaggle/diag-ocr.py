"""
Diagnose the fine-tuned OCR (output of fananime/lt-train-ocr): why did text CER go from 7.6% to 50% while
the training loss fell? Prints, for a few validation crops, the label tokens, the base model's output and
the fine-tuned model's output (token ids and text), with and without fp16 autocast. Private log only.
"""
import subprocess, sys

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers>=4.50,<5", "fugashi", "unidic-lite"], check=False)

import glob, json, os, re, unicodedata
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoTokenizer, VisionEncoderDecoderModel

BASE = "kha-white/manga-ocr-base"
tuned_dir = os.path.dirname(sorted(glob.glob("/kaggle/input/**/model.safetensors", recursive=True))[0])
print("tuned model:", tuned_dir, flush=True)
PATH = {os.path.basename(p)[:-4]: p for p in glob.glob("/kaggle/input/**/*.jpg", recursive=True)}
lab = glob.glob("/kaggle/input/**/labels_val.jsonl", recursive=True)[0]
rows = [r for r in (json.loads(l) for l in open(lab, encoding="utf-8")) if r["kind"] == "text" and r["key"] in PATH][:12]

tok = AutoTokenizer.from_pretrained(BASE)
proc = AutoImageProcessor.from_pretrained(BASE)
base = VisionEncoderDecoderModel.from_pretrained(BASE).cuda().eval()
tuned = VisionEncoderDecoderModel.from_pretrained(tuned_dir).cuda().eval()
print("config base: start", base.config.decoder_start_token_id, "pad", base.config.pad_token_id, "eos", base.config.eos_token_id, flush=True)
print("config tuned: start", tuned.config.decoder_start_token_id, "pad", tuned.config.pad_token_id, "eos", tuned.config.eos_token_id, flush=True)
print("gen config tuned:", tuned.generation_config, flush=True)
print("special:", tok.cls_token_id, tok.sep_token_id, tok.pad_token_id, tok.unk_token_id, flush=True)


@torch.no_grad()
def gen(model, img, amp):
    px = proc([img], return_tensors="pt").pixel_values.cuda()
    if amp:
        with torch.autocast("cuda", dtype=torch.float16):
            out = model.generate(px, max_length=98, num_beams=1)
    else:
        out = model.generate(px, max_length=98, num_beams=1)
    return out[0].tolist()


for r in rows:
    img = Image.open(PATH[r["key"]]).convert("L").convert("RGB")
    ids = tok(r["text"]).input_ids
    print("\nLABEL   ", repr(r["text"]), ids[:20], tok.convert_ids_to_tokens(ids[:12]), flush=True)
    for name, m in (("base", base), ("tuned", tuned)):
        for amp in (True, False):
            o = gen(m, img, amp)
            print(f"{name:5} amp={amp!s:5}", o[:20], repr(tok.decode(o, skip_special_tokens=True)), flush=True)
