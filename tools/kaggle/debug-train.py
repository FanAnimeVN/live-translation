"""
Why does fine-tuning manga-ocr-base break generation (characters reordered, the leading [CLS] dropped) even
at lr 2e-5 on text only? Inspect one batch exactly as train-ocr.py builds it: tokenizer class, label ids,
the decoder inputs the model derives, teacher-forced accuracy; then overfit that batch for 60 steps and
generate on it. Private log only.
"""
import subprocess, sys

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers>=4.50,<5", "fugashi", "unidic-lite"], check=False)

import glob, json, os
import torch
import transformers
from PIL import Image
from transformers import AutoImageProcessor, AutoTokenizer, VisionEncoderDecoderModel

print("transformers", transformers.__version__, flush=True)
BASE = "kha-white/manga-ocr-base"
PATH = {os.path.basename(p)[:-4]: p for p in glob.glob("/kaggle/input/**/*.jpg", recursive=True)}
lab_file = glob.glob("/kaggle/input/**/labels_val.jsonl", recursive=True)[0]
rows = [r for r in (json.loads(l) for l in open(lab_file, encoding="utf-8")) if r["kind"] == "text" and r["key"] in PATH and 3 <= len(r["text"]) <= 30][:16]
tok = AutoTokenizer.from_pretrained(BASE)
proc = AutoImageProcessor.from_pretrained(BASE)
model = VisionEncoderDecoderModel.from_pretrained(BASE).cuda()
print("tokenizer class", type(tok).__name__, "| config start/pad/eos", model.config.decoder_start_token_id, model.config.pad_token_id, model.config.eos_token_id, flush=True)
print("decoder is_decoder", model.decoder.config.is_decoder, "add_cross_attention", model.decoder.config.add_cross_attention, flush=True)

texts = [r["text"] for r in rows]
imgs = [Image.open(PATH[r["key"]]).convert("L").convert("RGB") for r in rows]
enc = tok(texts, padding="longest", truncation=True, max_length=98, return_tensors="pt")
lab = enc.input_ids.clone()
lab[lab == tok.pad_token_id] = -100
print("batch label ids[0]", lab[0][:14].tolist(), flush=True)
print("single-call ids[0]", tok(texts[0]).input_ids[:14], flush=True)
px = proc(imgs, return_tensors="pt").pixel_values.cuda()
lab = lab.cuda()
from transformers.models.vision_encoder_decoder.modeling_vision_encoder_decoder import shift_tokens_right
dec_in = shift_tokens_right(lab, model.config.pad_token_id, model.config.decoder_start_token_id)
print("decoder inputs[0]", dec_in[0][:14].tolist(), flush=True)


def tf_acc():
    model.eval()
    with torch.no_grad():
        out = model(pixel_values=px, labels=lab)
    pred = out.logits.argmax(-1)
    mask = lab != -100
    return float(out.loss), float((pred[mask] == lab[mask]).float().mean())


def gen_match():
    model.eval()
    with torch.no_grad():
        g = model.generate(px, max_length=40, num_beams=1)
    dec = tok.batch_decode(g, skip_special_tokens=True)
    exact = sum("".join(d.split()) == "".join(t.split()) for d, t in zip(dec, texts))
    return exact, g[0][:14].tolist()


import torch.nn.functional as F


def manual_loss():
    # Loss computed here: logits at decoder position t against labels[t] (no extra shift).
    logits = model(pixel_values=px, decoder_input_ids=dec_in).logits
    return F.cross_entropy(logits.reshape(-1, logits.size(-1)), lab.reshape(-1), ignore_index=-100)


print("before: loss/teacher-forced acc", tf_acc(), "| manual loss", float(manual_loss()), "| generate exact", gen_match(), flush=True)
base_state = {k: v.clone() for k, v in model.state_dict().items()}
for variant in ("builtin", "manual"):
    model.load_state_dict(base_state)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-5)
    for step in range(60):
        model.train()
        loss = model(pixel_values=px, labels=lab).loss if variant == "builtin" else manual_loss()
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 20 == 19:
            print(f"{variant} step {step + 1}: train loss {loss.item():.4f} | tf {tf_acc()} | generate exact {gen_match()}", flush=True)
