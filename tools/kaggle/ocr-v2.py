"""
OCR v2 on Kaggle (2x T4, both GPUs busy):
  GPU 0 "train": fine-tune kha-white/manga-ocr-base (Apache-2.0) on the 72 Manga109-s titles of split v2
                 (tools/kaggle/manga109-split-v2.json), text and SFX crops.
  GPU 1 "board": leakage-free leaderboard of off-the-shelf crop OCR models on the 22 titles that are only
                 in the academic Manga109 (no Manga109-s-trained model has seen them), text and SFX apart.
Both also score the team's 25 test pages (label boxes, fananime/lt-gt60-pack), which ARE in Manga109-s:
there, models trained on Manga109-s may be optimistic.

Licence of the fine-tune: trained on Manga109-s titles, but these crops were cut from the Manga109 release
(identical images); recorded as "review" until regenerated from the Manga109-s release itself.
Output: /kaggle/working/v2/{train/*, board/*}, results.zip
"""
import subprocess, sys

ROLE = sys.argv[1] if len(sys.argv) > 1 else "main"
if ROLE == "main":
    # transformers 4.x: manga-ocr's tokenizer and the Baberu / Hayai remote code all load on it (bake-off, eval-ocr).
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers>=4.50,<5", "fugashi", "unidic-lite", "manga-ocr"], check=False)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "git+https://github.com/muscgab/manga-ocr-CPT"], check=False)
    import os
    board = subprocess.Popen([sys.executable, sys.argv[0], "board"], env=dict(os.environ, CUDA_VISIBLE_DEVICES="1"))
    train = subprocess.Popen([sys.executable, sys.argv[0], "train"], env=dict(os.environ, CUDA_VISIBLE_DEVICES="0"))
    train.wait()
    board.wait()
    import shutil
    shutil.make_archive("/kaggle/working/results", "zip", "/kaggle/working/v2")
    sys.exit(0)

import base64, glob, io, json, os, random, re, time, traceback, unicodedata
import torch
from PIL import Image

SPLIT = json.loads(r'''{"test_team": ["ARMS", "AisazuNihaIrarenai", "UchiNoNyan'sDiary", "AppareKappore", "Akuhamu"], "clean_test": ["Belmondo", "BokuHaSitatakaKun", "ByebyeC-BOY", "GOOD_KISS_Ver2", "HighschoolKimengumi_vol01", "HighschoolKimengumi_vol20", "KoukouNoHitotachi", "KuroidoGanka", "MayaNoAkaiKutsu", "MeteoSanStrikeDesu", "MoeruOnisan_vol01", "MoeruOnisan_vol19", "NichijouSoup", "OhWareraRettouSeitokai", "PikaruGenkiDesu", "PsychoStaff", "Raphael", "ReveryEarth", "ShimatteIkouze_vol01", "ShimatteIkouze_vol26", "TotteokiNoABC", "YouchienBoueigumi"], "val": ["DollGun", "EienNoWith", "EverydayOsakanaChan", "HinagikuKenzan", "MAD_STONE", "MariaSamaNihaNaisyo", "PlatinumJungle", "TaiyouNiSmash", "TennenSenshiG", "YamatoNoHane"], "train_commercial": ["AkkeraKanjinchou", "AosugiruHaru", "Arisa", "BEMADER_P", "BakuretsuKungFuGirl", "BurariTessenTorimonocho", "Count3DeKimeteAgeru", "Donburakokko", "DualJustice", "EvaLady", "GakuenNoise", "GarakutayaManta", "GinNoChimera", "Hamlet", "HanzaiKousyouninMinegishiEitarou", "HaruichibanNoFukukoro", "HarukaRefrain", "HealingPlanet", "HeiseiJimen", "HisokaReturns", "JangiriPonpon", "JijiBabaFight", "Joouari", "Jyovolley", "KarappoHighschool", "KimiHaBokuNoTaiyouDa", "KyokugenCyclone", "LancelotFullThrottle", "LoveHina_vol01", "LoveHina_vol14", "MadouTaiga", "MagicStarGakuin", "MagicianLoad", "MemorySeijin", "MiraiSan", "MisutenaideDaisy", "MomoyamaHaikagura", "MukoukizuNoChonbo", "MutekiBoukenSyakuma", "Nekodama", "Ningyoushi", "OL_Lunch", "PLANET7", "ParaisoRoad", "PrayerHaNemurenai", "PrismHeart", "RinToSiteSippuNoNaka", "RisingGirl", "Saisoku", "SaladDays_vol01", "SaladDays_vol18", "SamayoeruSyonenNiJunaiWo", "SeisinkiVulnus", "SonokiDeABC", "SyabondamaKieta", "TapkunNoTanteisitsu", "TasogareTsushin", "TensiNoHaneToAkumaNoShippo", "TetsuSan", "That'sIzumiko", "ToutaMairimasu", "TouyouKidan", "TsubasaNoKioku", "UchuKigekiM774", "UltraEleven", "UnbalanceTokyo", "WarewareHaOniDearu", "YasasiiAkuma", "YoumaKourin", "YukiNoFuruMachi", "YumeNoKayoiji", "YumeiroCooking"]}''')
OUT = f"/kaggle/working/v2/{ROLE}"
os.makedirs(OUT, exist_ok=True)
LOG = open(f"{OUT}/log.txt", "a", encoding="utf-8")
T0 = time.time()


def log(*a):
    line = time.strftime("%H:%M:%S ") + f"[{ROLE}] " + " ".join(str(x) for x in a)
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------- data (all crop datasets attached)
PATH = {os.path.basename(p)[:-4]: p for p in glob.glob("/kaggle/input/**/*.jpg", recursive=True)}
ROWS = []
for f in glob.glob("/kaggle/input/**/labels_*.jsonl", recursive=True):
    ROWS += [r for r in (json.loads(l) for l in open(f, encoding="utf-8")) if r["key"] in PATH and 0 < len(norm(r["text"])) <= 96]
log(f"{len(PATH)} crops, {len(ROWS)} labelled")
by_title = lambda titles, kind=None: [r for r in ROWS if r["title"] in set(titles) and (kind is None or r["kind"] == kind)]
rng = random.Random(0)


def sample(rows, n):
    rows = list(rows)
    rng.shuffle(rows)
    return rows[:n]


EVAL = {
    "clean/text": sample(by_title(SPLIT["clean_test"], "text"), 3000),
    "clean/sfx": sample(by_title(SPLIT["clean_test"], "sfx"), 2000),
    "val/text": sample(by_title(SPLIT["val"], "text"), 1500),
    "val/sfx": sample(by_title(SPLIT["val"], "sfx"), 1000),
}
packs = glob.glob("/kaggle/input/**/mt-source.json", recursive=True)
if packs:  # the team's 25 test pages (label boxes), as in the bake-off
    pdir = os.path.dirname(packs[0])
    ja = {f"{r['pageId']}#{r['i']}": r["ja"] for r in json.load(open(packs[0], encoding="utf-8"))}
    team = []
    os.makedirs("/kaggle/temp/team", exist_ok=True)
    for pg in json.load(open(f"{pdir}/index.json", encoding="utf-8"))["pages"]:
        if pg.get("split") != "test":
            continue
        name = re.sub(r"[^\w.-]", "_", pg["pageId"]) + ".json"
        path = next((x for x in (f"{pdir}/pages/{name}", f"{pdir}/{name}") if os.path.exists(x)), None)
        for c in json.load(open(path, encoding="utf-8"))["gtCrops"] if path else []:
            text = ja.get(f"{pg['pageId']}#{c['i']}", "")
            if norm(text):
                key = "team_" + re.sub(r"[^\w]", "_", pg["pageId"]) + f"_{c['i']}"
                PATH[key] = f"/kaggle/temp/team/{key}.jpg"
                Image.open(io.BytesIO(base64.b64decode(c["dataUrl"].split(",", 1)[1]))).convert("RGB").save(PATH[key], quality=95)
                team.append({"key": key, "kind": "text", "text": text})
    EVAL["team25/text"] = team
log({k: len(v) for k, v in EVAL.items()})


def score(run, rows, bs=32):
    """run(list of PIL images) -> list of texts."""
    edits = ref = exact = 0
    t = time.time()
    for i in range(0, len(rows), bs):
        chunk = rows[i:i + bs]
        for r, o in zip(chunk, run([Image.open(PATH[r["key"]]).convert("RGB") for r in chunk])):
            e = levenshtein(norm(o), norm(r["text"]))
            edits, ref, exact = edits + e, ref + len(norm(r["text"])), exact + (e == 0)
    return {"cer": round(100 * edits / max(1, ref), 2), "exact": round(100 * exact / max(1, len(rows)), 1), "n": len(rows), "msPerCrop": round(1000 * (time.time() - t) / max(1, len(rows)), 1)}


def score_all(run, name):
    res = {k: score(run, v) for k, v in EVAL.items() if v}
    log(name, json.dumps(res))
    return res


# ---------------------------------------------------------------- board (GPU 1)
if ROLE == "board":
    def manga_ocr():
        from manga_ocr import MangaOcr
        m = MangaOcr()
        return lambda imgs: [m(x) for x in imgs]

    def cpt():
        from manga_ocr_cpt import MangaOcrCPT
        m = MangaOcrCPT("flex")
        return lambda imgs: list(m(imgs))

    def baberu():
        from huggingface_hub import snapshot_download
        d = snapshot_download("genshiai-daichi/baberu-ocr", revision="b9868433dbda3ed9ba1357d008599ff4ada873d5", local_dir="/kaggle/temp/baberu")
        sys.path.insert(0, d)
        from inference import BaberuOCR
        m = BaberuOCR(d)
        call = next(getattr(m, a) for a in ("__call__", "recognize", "predict", "ocr") if callable(getattr(m, a, None)))
        return lambda imgs: [str(call(x)) for x in imgs]

    def hayai(repo, patches=384):
        def load():
            from transformers import AutoModel, AutoProcessor, PreTrainedTokenizerFast
            model = AutoModel.from_pretrained(repo, trust_remote_code=True).cuda().eval()
            tok = PreTrainedTokenizerFast.from_pretrained(repo)
            proc = AutoProcessor.from_pretrained("google/siglip2-base-patch16-naflex")

            @torch.no_grad()
            def run(imgs):
                inp = proc(images=imgs, max_num_patches=patches, return_tensors="pt").to("cuda")
                gen = model.generate(pixel_values=inp["pixel_values"], pixel_attention_mask=inp["pixel_attention_mask"],
                                     spatial_shapes=inp["spatial_shapes"], tokenizer=tok, max_new_tokens=128, repetition_penalty=1.0)
                return [g if isinstance(g, str) else tok.decode(g, skip_special_tokens=True) for g in gen]
            return run
        return load

    board = {}
    for name, loader in (("baberu", baberu), ("manga-ocr", manga_ocr), ("hayai-v2", hayai("JustANormalTinkerer/hayai-ocr-v2")),
                         ("hayai-v2.5-nova", hayai("JustANormalTinkerer/hayai-ocr-v2.5-nova")), ("cpt-flex", cpt)):
        try:
            board[name] = score_all(loader(), name)
        except Exception as e:
            log(f"{name} failed: {e}\n{traceback.format_exc()[-1200:]}")
            board[name] = {"error": str(e)}
        json.dump(board, open(f"{OUT}/board.json", "w"), indent=1)
        torch.cuda.empty_cache()
    log("done")
    sys.exit(0)

# ---------------------------------------------------------------- train (GPU 0)
from torch.utils.data import DataLoader, Dataset
from transformers import AutoImageProcessor, AutoTokenizer, VisionEncoderDecoderModel, get_linear_schedule_with_warmup
from transformers.models.vision_encoder_decoder.modeling_vision_encoder_decoder import shift_tokens_right

BASE, EPOCHS, BATCH, LR, MAX_LABEL = "kha-white/manga-ocr-base", 2, 48, 5e-5, 96
TIME_LIMIT_S = 7 * 3600
train = by_title(SPLIT["train_commercial"])
log(f"train crops: {len(train)} ({sum(r['kind'] == 'sfx' for r in train)} SFX) from {len(set(r['title'] for r in train))} titles")
tok = AutoTokenizer.from_pretrained(BASE)
proc = AutoImageProcessor.from_pretrained(BASE)
model = VisionEncoderDecoderModel.from_pretrained(BASE).to("cuda")


@torch.no_grad()
def run_model(imgs):
    model.eval()
    px = proc([i.convert("L").convert("RGB") for i in imgs], return_tensors="pt").pixel_values.to("cuda")
    with torch.autocast("cuda", dtype=torch.float16):
        out = model.generate(px, max_length=MAX_LABEL + 2, num_beams=1)
    return tok.batch_decode(out, skip_special_tokens=True)


class Crops(Dataset):
    def __len__(self):
        return len(train)

    def __getitem__(self, i):
        return Image.open(PATH[train[i]["key"]]).convert("L").convert("RGB"), train[i]["text"]


def collate(batch):
    imgs, texts = zip(*batch)
    lab = tok(list(texts), padding="longest", truncation=True, max_length=MAX_LABEL + 2, return_tensors="pt").input_ids
    lab[lab == tok.pad_token_id] = -100
    return proc(list(imgs), return_tensors="pt").pixel_values, lab


metrics = {"base": BASE, "data": "Manga109-s titles (split v2 train_commercial)", "epochs": EPOCHS, "trainCrops": len(train)}
metrics["before"] = score_all(run_model, "before")
loader = DataLoader(Crops(), batch_size=BATCH, shuffle=True, num_workers=4, collate_fn=collate, drop_last=True)
opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
steps = EPOCHS * len(loader)
sched = get_linear_schedule_with_warmup(opt, int(0.03 * steps), steps)
scaler = torch.amp.GradScaler("cuda")
step = 0
for epoch in range(EPOCHS):
    model.train()
    for px, lab in loader:
        # transformers 4.57's VisionEncoderDecoderModel loss shifts the labels once more (causal-LM style): the
        # model then learns the token after next and generation reorders characters (debug-train.py). Own loss:
        lab = lab.to("cuda")
        dec_in = shift_tokens_right(lab, model.config.pad_token_id, model.config.decoder_start_token_id)
        with torch.autocast("cuda", dtype=torch.float16):
            logits = model(pixel_values=px.to("cuda"), decoder_input_ids=dec_in).logits
        loss = torch.nn.functional.cross_entropy(logits.float().reshape(-1, logits.size(-1)), lab.reshape(-1), ignore_index=-100)
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        sched.step()
        step += 1
        if step % 300 == 0:
            log(f"epoch {epoch} step {step}/{steps} loss {loss.item():.4f} ({(time.time() - T0) / 60:.0f} min)")
        if time.time() - T0 > TIME_LIMIT_S:
            break
    metrics[f"epoch{epoch + 1}"] = score_all(run_model, f"after epoch {epoch + 1}")
    json.dump(metrics, open(f"{OUT}/metrics.json", "w"), indent=1)
    if time.time() - T0 > TIME_LIMIT_S:
        log("time limit reached")
        break
metrics["steps"] = step
model.save_pretrained(f"{OUT}/model")
tok.save_pretrained(f"{OUT}/model")
proc.save_pretrained(f"{OUT}/model")
json.dump(metrics, open(f"{OUT}/metrics.json", "w"), indent=1)
json.dump({"id": "ocr/lt-m109s-v2", "base": f"{BASE} (Apache-2.0)", "trainingData": "Manga109-s titles (72, split v2); crops cut from the Manga109 release (identical images)",
           "commercial": "review", "why": "regenerate the crops from the Manga109-s release before marking it 'credit'"}, open(f"{OUT}/model/LICENSE.json", "w"), indent=1)
log("done in", round((time.time() - T0) / 60), "min")
