"""
Fine-tune a manga crop OCR on Kaggle (GPU T4) and score it per split, text and SFX apart.

Academic track: data = the lt-m109-* crop datasets (tools/kaggle/manga109-shards.py, split by title;
uploaded in parts by tools/kaggle/upload-parts.py).
Models trained on full Manga109 are for the thesis only; the same recipe is re-run on Manga109-s and
synthetic data for anything the product ships.

Base: kha-white/manga-ocr-base (Apache-2.0; ViT encoder + character decoder). The untouched base is
scored on the same crops as the baseline. Output: /kaggle/working/ocr/{model files, metrics.json, log.txt}
"""
import glob, io, json, os, random, re, subprocess, sys, tarfile, time, unicodedata

# manga-ocr's tokenizer is a slow BertJapaneseTokenizer: transformers 5 (Kaggle's default) only builds fast
# tokenizers, so pin 4.x (what `pip install manga-ocr` gave the bake-off) and add its word splitter. Must run
# before transformers is imported.
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers>=4.46,<5", "fugashi", "unidic-lite"], check=False)

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from transformers import AutoImageProcessor, AutoTokenizer, VisionEncoderDecoderModel, get_linear_schedule_with_warmup

BASE = "kha-white/manga-ocr-base"
OUT = "/kaggle/working/ocr"
WORK = "/kaggle/temp/crops"
EPOCHS = 2
BATCH = 48
LR = 5e-5
MAX_LABEL = 96
TIME_LIMIT_S = 4.5 * 3600  # stop training in time to score and save inside the session
EVAL_PER_SPLIT = 4000      # crops scored per split and kind (random, fixed seed)
os.makedirs(OUT, exist_ok=True)
LOG = open(f"{OUT}/log.txt", "a", encoding="utf-8")
T0 = time.time()


def log(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


# ---------------------------------------------------------------- data
# The crops come as several small datasets (lt-m109-train0/1/2, -val-test, -oos, -test). Kaggle unpacks
# uploaded tar files itself, so crops are read where they are; a shard still packed is unpacked here.
LABELS = {os.path.basename(f)[len("labels_"):-len(".jsonl")]: f for f in glob.glob("/kaggle/input/**/labels_*.jsonl", recursive=True)}
os.makedirs(WORK, exist_ok=True)
for t in sorted(glob.glob("/kaggle/input/**/*.tar", recursive=True)):
    with tarfile.open(t) as tar:
        tar.extractall(WORK)
PATH = {os.path.basename(p)[:-4]: p for root in ("/kaggle/input", WORK) for p in glob.glob(f"{root}/**/*.jpg", recursive=True)}
log("label files:", sorted(LABELS), "crops found:", len(PATH))


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def load(split):
    rows = [json.loads(l) for l in open(LABELS[split], encoding="utf-8")]
    kept = [r for r in rows if 0 < len(norm(r["text"])) <= MAX_LABEL and r["key"] in PATH]
    log(f"{split}: {len(kept)}/{len(rows)} crops usable")
    return kept


train = load("train")
evals = {s: load(s) for s in ("val", "oos", "test_team") if s in LABELS}

# The team's 25 test pages (fananime/lt-gt60-pack): the same label-box crops the bake-off scored, so the
# result compares directly with the off-the-shelf OCR models there (Baberu, CPT-flex, NAR, manga-ocr).
packs = glob.glob("/kaggle/input/**/mt-source.json", recursive=True)
if packs:
    import base64
    pdir = os.path.dirname(packs[0])
    index = json.load(open(f"{pdir}/index.json", encoding="utf-8"))
    ja = {f"{r['pageId']}#{r['i']}": r["ja"] for r in json.load(open(packs[0], encoding="utf-8"))}
    rows = []
    for pg in index["pages"]:
        if pg.get("split") != "test":
            continue
        name = re.sub(r"[^\w.-]", "_", pg["pageId"]) + ".json"
        path = next((x for x in (f"{pdir}/pages/{name}", f"{pdir}/{name}") if os.path.exists(x)), None)
        if not path:
            continue
        for c in json.load(open(path, encoding="utf-8"))["gtCrops"]:
            safe = re.sub(r"[^\w]", "_", pg["pageId"])
            key = f"gt60_{safe}_{c['i']}"
            text = ja.get(f"{pg['pageId']}#{c['i']}", "")
            if not norm(text):
                continue
            PATH[key] = f"{WORK}/{key}.jpg"
            Image.open(io.BytesIO(base64.b64decode(c["dataUrl"].split(",", 1)[1]))).convert("L").save(PATH[key], quality=95)
            rows.append({"key": key, "kind": "text", "text": text})
    evals["team25_labels"] = rows
log("train crops:", len(train), {s: len(v) for s, v in evals.items()})

tok = AutoTokenizer.from_pretrained(BASE)
proc = AutoImageProcessor.from_pretrained(BASE)


class Crops(Dataset):
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(PATH[r['key']]).convert("L").convert("RGB")
        return img, r["text"]


def collate(batch):
    imgs, texts = zip(*batch)
    px = proc(list(imgs), return_tensors="pt").pixel_values
    lab = tok(list(texts), padding="longest", truncation=True, max_length=MAX_LABEL + 2, return_tensors="pt").input_ids
    lab[lab == tok.pad_token_id] = -100
    return px, lab


# ---------------------------------------------------------------- scoring
def levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@torch.no_grad()
def score(model, rows, bs=96):
    model.eval()
    edits = ref = exact = 0
    t = time.time()
    for i in range(0, len(rows), bs):
        chunk = rows[i:i + bs]
        imgs = [Image.open(PATH[r['key']]).convert("L").convert("RGB") for r in chunk]
        px = proc(imgs, return_tensors="pt").pixel_values.to("cuda")
        with torch.autocast("cuda", dtype=torch.float16):
            out = model.generate(px, max_length=MAX_LABEL + 2, num_beams=1)
        for r, o in zip(chunk, tok.batch_decode(out, skip_special_tokens=True)):
            h, g = norm(o), norm(r["text"])
            e = levenshtein(h, g)
            edits, ref, exact = edits + e, ref + len(g), exact + (e == 0)
    return {"cer": round(100 * edits / max(1, ref), 2), "exact": round(100 * exact / max(1, len(rows)), 1), "n": len(rows), "msPerCrop": round(1000 * (time.time() - t) / max(1, len(rows)), 1)}


rng = random.Random(0)
samples = {}
for s, rows in evals.items():
    for kind in ("text", "sfx"):
        k = [r for r in rows if r["kind"] == kind]
        rng.shuffle(k)
        samples[f"{s}/{kind}"] = k[:EVAL_PER_SPLIT]


def score_all(model, name):
    res = {k: score(model, v) for k, v in samples.items()}
    log(name, json.dumps(res))
    return res


metrics = {"base": BASE, "data": "Manga109 (academic only)", "epochs": EPOCHS, "batch": BATCH, "lr": LR}
model = VisionEncoderDecoderModel.from_pretrained(BASE).to("cuda")
metrics["before"] = score_all(model, "before")

# ---------------------------------------------------------------- training
model.train()
loader = DataLoader(Crops(train), batch_size=BATCH, shuffle=True, num_workers=4, collate_fn=collate, drop_last=True)
opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
steps = EPOCHS * len(loader)
sched = get_linear_schedule_with_warmup(opt, int(0.03 * steps), steps)
scaler = torch.amp.GradScaler("cuda")
step, stopped = 0, False
for epoch in range(EPOCHS):
    for px, lab in loader:
        with torch.autocast("cuda", dtype=torch.float16):
            loss = model(pixel_values=px.to("cuda"), labels=lab.to("cuda")).loss
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        sched.step()
        step += 1
        if step % 200 == 0:
            log(f"epoch {epoch} step {step}/{steps} loss {loss.item():.4f} ({(time.time() - T0) / 60:.0f} min)")
        if time.time() - T0 > TIME_LIMIT_S:
            stopped = True
            break
    if stopped:
        log("time limit reached, stopping training")
        break
metrics["steps"] = step

metrics["after"] = score_all(model, "after")
model.save_pretrained(OUT)
tok.save_pretrained(OUT)
proc.save_pretrained(OUT)
json.dump(metrics, open(f"{OUT}/metrics.json", "w"), indent=1)
# The checkpoint carries its licence record (apps/server/src/licenses.ts id "ocr/lt-m109-academic").
json.dump({"id": "ocr/lt-m109-academic", "base": f"{BASE} (Apache-2.0)", "trainingData": "full Manga109 (academic licence)",
           "commercial": "no", "why": "Manga109 is academic use only: thesis numbers, never the paid tier"}, open(f"{OUT}/LICENSE.json", "w"), indent=1)
log("done in", round((time.time() - T0) / 60), "min")
