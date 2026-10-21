"""
Score more crop OCR models trained on Manga109-s (HF "models trained on hal-utokyo/Manga109-s") on the same
crops as the bake-off: label boxes and detected regions of the team's 25 test pages (fananime/lt-gt60-pack),
written in the bake-off layout (results/ocr/<name>.json) so tools/eval/src/kaggle-score.ts scores them.
SFX: also scored here on Manga109 val crops (lt-m109-val-test), whose labels ship with the dataset.

Caveat: these models trained on Manga109-s; if the test titles are in Manga109-s, scores are optimistic.
Output: /kaggle/working/results/{ocr/*.json, sfx.json, log.txt}, results.zip
"""
import subprocess, sys

# PaddleOCR-VL-For-Manga's code and manga-ocr-style tokenizers need transformers 4.x (Kaggle ships 5.x).
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers>=4.50,<5", "fugashi", "unidic-lite"], check=False)

import base64, glob, io, json, os, re, shutil, time, traceback, unicodedata
import torch
from PIL import Image

OUT = "/kaggle/working/results"
os.makedirs(f"{OUT}/ocr", exist_ok=True)
LOG = open(f"{OUT}/log.txt", "a", encoding="utf-8")


def log(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def pil(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGB")


# ---------------------------------------------------------------- data
pack = os.path.dirname(glob.glob("/kaggle/input/**/mt-source.json", recursive=True)[0])
index = json.load(open(f"{pack}/index.json", encoding="utf-8"))


def page_json(pid):
    name = re.sub(r"[^\w.-]", "_", pid) + ".json"
    return json.load(open(next(p for p in (f"{pack}/pages/{name}", f"{pack}/{name}") if os.path.exists(p)), encoding="utf-8"))


PAGES = {p["pageId"]: page_json(p["pageId"]) for p in index["pages"] if p.get("split", "test") == "test"}
sfx_rows = []
lab = glob.glob("/kaggle/input/**/labels_val.jsonl", recursive=True)
if lab:
    paths = {os.path.basename(p)[:-4]: p for p in glob.glob("/kaggle/input/**/*.jpg", recursive=True)}
    sfx_rows = [r for r in (json.loads(l) for l in open(lab[0], encoding="utf-8")) if r["kind"] == "sfx" and r["key"] in paths][:2000]
    for r in sfx_rows:
        r["path"] = paths[r["key"]]
log(f"{len(PAGES)} test pages; {len(sfx_rows)} SFX crops")


def levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------- engines (each returns a batch function)
def hayai(repo, patches):
    def load():
        from transformers import AutoModel, AutoProcessor, PreTrainedTokenizerFast
        model = AutoModel.from_pretrained(repo, trust_remote_code=True).cuda().eval()
        tok = PreTrainedTokenizerFast.from_pretrained(repo)
        proc = AutoProcessor.from_pretrained("google/siglip2-base-patch16-naflex")

        @torch.no_grad()
        def run(imgs):
            out = []
            for i in range(0, len(imgs), 16):
                inp = proc(images=imgs[i:i + 16], max_num_patches=patches, return_tensors="pt").to("cuda")
                gen = model.generate(pixel_values=inp["pixel_values"], pixel_attention_mask=inp["pixel_attention_mask"],
                                     spatial_shapes=inp["spatial_shapes"], tokenizer=tok, max_new_tokens=128, repetition_penalty=1.0)
                out += [g if isinstance(g, str) else tok.decode(g, skip_special_tokens=True) for g in gen]
            return [unicodedata.normalize("NFKC", t) for t in out]
        return run
    return load


def paddle_vl():
    from transformers import AutoModelForCausalLM, AutoProcessor
    repo = "jzhang533/PaddleOCR-VL-For-Manga"
    model = AutoModelForCausalLM.from_pretrained(repo, trust_remote_code=True, torch_dtype=torch.float32).to("cuda").eval()
    proc = AutoProcessor.from_pretrained(repo, trust_remote_code=True)

    @torch.no_grad()
    def run(imgs):
        res = []
        for im in imgs:
            msgs = [{"role": "user", "content": [{"type": "image", "image": im}, {"type": "text", "text": "OCR:"}]}]
            inp = proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to("cuda")
            o = model.generate(**inp, max_new_tokens=128, do_sample=False)
            res.append(proc.batch_decode(o[:, inp["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip())
        return res
    return run


ENGINES = [
    ("hayai-v2.5-nova-384", hayai("JustANormalTinkerer/hayai-ocr-v2.5-nova", 384)),
    ("hayai-v2.5-nova-512", hayai("JustANormalTinkerer/hayai-ocr-v2.5-nova", 512)),
    ("hayai-v2-384", hayai("JustANormalTinkerer/hayai-ocr-v2", 384)),
    ("paddleocr-vl-manga", paddle_vl),
]

sfx_scores = {}
for name, loader in ENGINES:
    try:
        t0 = time.time()
        run = loader()
        load_s = time.time() - t0
        res, n, t1 = {"gt": {}, "det": {}}, 0, time.time()
        for pid, p in PAGES.items():  # one batch per page, as the product would
            imgs = [pil(c["dataUrl"]) for c in p["gtCrops"]]
            for c, txt in zip(p["gtCrops"], run(imgs) if imgs else []):
                res["gt"][f"{pid}#{c['i']}"] = txt
            imgs = [pil(c["dataUrl"]) for c in p["ocr"]]
            res["det"][pid] = dict(zip([c["id"] for c in p["ocr"]], run(imgs) if imgs else []))
            n += len(p["gtCrops"]) + len(p["ocr"])
        res["msPerCrop"] = round(1000 * (time.time() - t1) / max(1, n), 1)
        res["loadSec"] = round(load_s)
        json.dump(res, open(f"{OUT}/ocr/{name}.json", "w", encoding="utf-8"), ensure_ascii=False)
        log(f"{name}: {res['msPerCrop']} ms/crop on {n} crops")
        if sfx_rows:
            texts = run([Image.open(r["path"]).convert("RGB") for r in sfx_rows])
            e = sum(levenshtein(norm(t), norm(r["text"])) for t, r in zip(texts, sfx_rows))
            ref = sum(len(norm(r["text"])) for r in sfx_rows)
            sfx_scores[name] = {"cer": round(100 * e / ref, 2), "exact": round(100 * sum(norm(t) == norm(r["text"]) for t, r in zip(texts, sfx_rows)) / len(sfx_rows), 1), "n": len(sfx_rows)}
            log(f"{name} SFX: {sfx_scores[name]}")
    except Exception as e:
        log(f"{name} failed: {e}\n{traceback.format_exc()[-1500:]}")
        json.dump({"error": str(e)}, open(f"{OUT}/ocr/{name}.json", "w"))
    finally:
        run = None
        torch.cuda.empty_cache()
json.dump(sfx_scores, open(f"{OUT}/sfx.json", "w"), indent=1)
shutil.make_archive("/kaggle/working/results", "zip", OUT)
log("done")
