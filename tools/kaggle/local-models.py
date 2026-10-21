"""
Live translation: local-model bake-off on a Kaggle GPU box (2x T4).

Input: a private Kaggle dataset made by tools/eval/src/kaggle-pack.ts (index.json, mt-source.json and
one JSON per page holding the product's exact page request, plain OCR crops and label-box crops).
The Vietnamese gold never leaves the team's machine; results are scored there by kaggle-score.ts.

Stages (each model is one job, run on whichever GPU is free, pulled before and deleted after):
  ocr  dedicated crop OCR models (manga-ocr, CPT-flex, NAR-small, PaddleOCR-VL-For-Manga, Baberu)
  mt   translation of the labelled Japanese lines (perfect OCR) with local text models
  mt2  translation of the OCR output of the detected regions (the real two-stage local mode)
  vlm  the product's page request (prompt v5) answered by local vision models through Ollama
Output: /kaggle/working/results/{ocr,mt,mt2,vlm}/..., meta.json, log.txt, results.zip
"""
import base64, glob, io, json, os, queue, re, shutil, subprocess, sys, threading, time, traceback, urllib.parse, urllib.request

STAGES = {"ocr", "mt", "mt2", "vlm"}
OUT = "/kaggle/working/results"
os.makedirs(OUT, exist_ok=True)
LOG = open(f"{OUT}/log.txt", "a", encoding="utf-8")


def log(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


def sh(cmd, check=True):
    log("$", cmd)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode and check:
        log(r.stdout[-2000:], r.stderr[-2000:])
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}")
    return r.stdout


def save(path, obj):
    path = f"{OUT}/{path}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


# ---------------------------------------------------------------- data
INPUT = os.path.dirname(sorted(glob.glob("/kaggle/input/**/index.json", recursive=True))[0])
INDEX = json.load(open(f"{INPUT}/index.json", encoding="utf-8"))
MT_SOURCE = json.load(open(f"{INPUT}/mt-source.json", encoding="utf-8"))


def page_file(pid):
    name = re.sub(r"[^\w.-]", "_", pid) + ".json"
    for p in (f"{INPUT}/pages/{name}", f"{INPUT}/{name}"):
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


ALL_PAGES = {p["pageId"]: json.load(open(page_file(p["pageId"]), encoding="utf-8")) for p in INDEX["pages"]}
# OCR runs on every page; translation and page-reading stages (slow) only on the scored test split.
PAGES = {pid: ALL_PAGES[pid] for pid in ALL_PAGES if next(p for p in INDEX["pages"] if p["pageId"] == pid).get("split", "test") == "test"}
LINES = {}  # pageId -> labelled lines in reading order
for s in MT_SOURCE:
    LINES.setdefault(s["pageId"], []).append(s)
for v in LINES.values():
    v.sort(key=lambda s: s["order"])
log(f"input {INPUT}: {len(ALL_PAGES)} pages ({len(PAGES)} test), {len(MT_SOURCE)} labelled lines, prompt {INDEX.get('promptVersion')}")


def pil(data_url):
    from PIL import Image
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGB")


# ---------------------------------------------------------------- GPUs and Ollama
def gpus():
    out = sh("nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader", check=False)
    return [l.strip() for l in out.splitlines() if l.strip()]


GPUS = gpus()
log("GPUs:", GPUS)
PORTS = [11434 + i for i in range(max(1, min(2, len(GPUS))))]
PEAK = {}  # gpu index -> peak MiB since reset


def watch_vram():
    while True:
        out = subprocess.run("nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits", shell=True, capture_output=True, text=True).stdout
        for l in out.splitlines():
            try:
                i, m = (int(x) for x in l.split(","))
                PEAK[i] = max(PEAK.get(i, 0), m)
            except ValueError:
                pass
        time.sleep(2)


threading.Thread(target=watch_vram, daemon=True).start()


def setup_ollama():
    if not shutil.which("ollama"):
        sh("apt-get -qq update >/dev/null 2>&1; apt-get -qq install -y zstd pciutils lshw >/dev/null 2>&1", check=False)
        sh("curl -fsSL https://ollama.com/install.sh | sh")
    for i, port in enumerate(PORTS):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(i), OLLAMA_HOST=f"127.0.0.1:{port}", OLLAMA_MODELS="/tmp/ollama-models",
                   OLLAMA_FLASH_ATTENTION="1", OLLAMA_KEEP_ALIVE="60m", OLLAMA_NUM_PARALLEL="1", OLLAMA_CONTEXT_LENGTH="16384")
        subprocess.Popen(["ollama", "serve"], env=env, stdout=open(f"/tmp/ollama{i}.log", "w"), stderr=subprocess.STDOUT)
    for port in PORTS:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=2)
                break
            except Exception:
                time.sleep(1)
    log("ollama", sh("ollama --version", check=False).strip())


def api(port, path, body=None, method=None, timeout=3600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def pull(port, model):
    t0 = time.time()
    api(port, "/api/pull", {"model": model, "stream": False}, timeout=7200)
    info = next((m for m in api(port, "/api/tags")["models"] if m["name"] == model or m["model"] == model), {})
    return {"pullSec": round(time.time() - t0), "sizeGb": round(info.get("size", 0) / 1e9, 2)}


def remove(port, model):
    try:
        api(port, "/api/delete", {"model": model}, method="DELETE")
    except Exception as e:
        log("delete failed", model, e)


def chat(port, model, messages, options, think=None, timeout=1800):
    """Streamed native chat: returns text, time to first token, total time and token counts."""
    body = {"model": model, "messages": messages, "stream": True, "options": options}
    if think is not None:
        body["think"] = think
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0, first, text, last = time.time(), None, [], {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            if not raw.strip():
                continue
            c = json.loads(raw)
            if c.get("error"):
                raise RuntimeError(c["error"])
            piece = (c.get("message") or {}).get("content") or ""
            if piece and first is None:
                first = time.time()
            text.append(piece)
            if c.get("done"):
                last = c
    total = time.time() - t0
    return {"text": "".join(text), "ttfbMs": round(1000 * ((first or time.time()) - t0)), "totalMs": round(1000 * total),
            "promptTokens": last.get("prompt_eval_count"), "completionTokens": last.get("eval_count"),
            "loadMs": round((last.get("load_duration") or 0) / 1e6)}


def generate_raw(port, model, prompt, options, timeout=600):
    t0 = time.time()
    r = api(port, "/api/generate", {"model": model, "prompt": prompt, "raw": True, "stream": False, "options": options}, timeout=timeout)
    return {"text": r.get("response", ""), "totalMs": round(1000 * (time.time() - t0)), "completionTokens": r.get("eval_count")}


def hf_gguf(search, quants=("Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0")):
    """First GGUF repo on Hugging Face matching `search` that has one of the quants, as an Ollama hf.co name."""
    url = "https://huggingface.co/api/models?" + urllib.parse.urlencode({"search": search, "filter": "gguf", "sort": "downloads", "limit": 20})
    for m in json.load(urllib.request.urlopen(url, timeout=30)):
        files = [s["rfilename"] for s in json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{m['id']}", timeout=30)).get("siblings", [])]
        for q in quants:
            if any(f.lower().endswith(f"{q.lower()}.gguf") for f in files):
                return f"hf.co/{m['id']}:{q}"
    return None


# ---------------------------------------------------------------- prompts
RULES = ("You translate Japanese manga dialogue into natural, spoken Vietnamese. Keep meaningful Japanese honorifics and vocatives "
         "(-san, -kun, -chan, -sama, senpai, sensei, onii-chan, nee-chan) as they are; a kept sibling vocative already carries its title "
         "(write 'nee-chan', never 'chị nee-chan'). Keep the delivery: stutters, elongation, ellipses, !?, CAPS. Choose Vietnamese "
         "pronouns that fit the speakers (anh/em, chị/em, tớ/cậu, tao/mày, tôi/bạn as a last resort); if unsure, prefer neutral wording. "
         "Translate sound effects into natural Vietnamese onomatopoeia.")


def clean(t):
    t = re.sub(r"<think>[\s\S]*?</think>", "", t or "")
    return " ".join(l.strip() for l in t.strip().splitlines() if l.strip())


def numbered(lines):
    return "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines))


def parse_numbered(text, n):
    out = [""] * n
    for line in re.sub(r"<think>[\s\S]*?</think>", "", text or "").splitlines():
        m = re.match(r"\s*(\d+)\s*[.):：]\s*(.*)", line)
        if m and 1 <= int(m.group(1)) <= n and not out[int(m.group(1)) - 1]:
            out[int(m.group(1)) - 1] = m.group(2).strip()
    return out


HYMT_OPTS = {"temperature": 0.7, "top_p": 0.6, "top_k": 20, "repeat_penalty": 1.05, "num_predict": 300}
LLM_OPTS = {"temperature": 0.2, "num_predict": 3000, "num_ctx": 16384}


def per_line(port, model, lines, make, opts, think=None, raw=False):
    """Translate each line alone; `make(i, lines)` builds the prompt. Returns texts and per-line ms."""
    out, ms = [], []
    for i in range(len(lines)):
        p = make(i, lines)
        r = generate_raw(port, model, p, opts) if raw else chat(port, model, [{"role": "user", "content": p}], opts, think)
        out.append(clean(r["text"]))
        ms.append(r["totalMs"])
    return out, ms


def hymt_plain(i, lines):
    return f"Translate the following text into Vietnamese. Note that you should only output the translated result without any additional explanation:\n{lines[i]}"


def hymt_background(i, lines):
    bg = "\n".join(lines[max(0, i - 3):i] + lines[i + 1:i + 2])
    if not bg:
        return hymt_plain(i, lines)
    return (f"[Background Information]\n{bg}\n\nPlease translate the following text into Vietnamese, taking the provided background "
            f"information into consideration. Do not translate the background information. Only output the translation.\n[Source Text]\n{lines[i]}")


def translategemma(i, lines):
    return ("You are a professional Japanese (ja) to Vietnamese (vi) translator. Your goal is to accurately convey the meaning and nuances of "
            "the original Japanese text while adhering to Vietnamese grammar, vocabulary, and cultural sensitivities.\nProduce only the "
            f"Vietnamese translation, without any additional explanations or commentary. Please translate the following Japanese text into Vietnamese:\n\n\n{lines[i]}")


def milmmt(i, lines):
    return f"Translate this from Japanese to Vietnamese:\nJapanese: {lines[i]}\nVietnamese:"


def seedx(i, lines):
    return f"Translate the following Japanese sentence into Vietnamese:\n{lines[i]} <vi>"


def page_batch(port, model, lines, think=None):
    """All lines of a page in one call (numbered), so the model sees the page as context."""
    msgs = [{"role": "system", "content": RULES + " Reply with the same numbered list: one Vietnamese line per Japanese line, nothing else."},
            {"role": "user", "content": numbered(lines)}]
    r = chat(port, model, msgs, LLM_OPTS, think)
    return parse_numbered(r["text"], len(lines)), r


def hymt_delimited(port, model, lines):
    """Hy-MT2's delimiter template: the whole page in one call, segments separated by a fixed marker."""
    p = ("Translate the following text into Vietnamese. The segments are separated by \"<sep>\"; keep exactly the same number of \"<sep>\" "
         "delimiters, do not omit, escape or translate them, and only output the translated result:\n" + " <sep> ".join(lines))
    r = chat(port, model, [{"role": "user", "content": p}], dict(HYMT_OPTS, num_predict=3000))
    segs = [s.strip() for s in clean(r["text"]).split("<sep>")]
    return (segs if len(segs) == len(lines) else None), r


# ---------------------------------------------------------------- OCR stage (torch, GPU 0)
OCR_DONE = threading.Event()
OCR_PICK = {}  # name of the OCR engine whose region output feeds mt2


def ocr_stage():
    if "ocr" not in STAGES:
        OCR_DONE.set()
        return
    import torch
    gt_items = [(f"{pid}#{c['i']}", c["dataUrl"]) for pid, p in ALL_PAGES.items() for c in p["gtCrops"]]
    det_items = [(pid, c["id"], c["dataUrl"]) for pid, p in ALL_PAGES.items() for c in p["ocr"]]
    log(f"OCR: {len(gt_items)} label crops, {len(det_items)} region crops")

    def load_manga_ocr():
        sh("pip install -q manga-ocr")
        from manga_ocr import MangaOcr
        m = MangaOcr()
        return lambda imgs: [m(x) for x in imgs]

    def load_cpt():
        sh("pip install -q git+https://github.com/muscgab/manga-ocr-CPT")
        from manga_ocr_cpt import MangaOcrCPT
        m = MangaOcrCPT("flex")
        return lambda imgs: list(m(imgs))

    def load_nar():
        from huggingface_hub import snapshot_download
        d = snapshot_download("muscgab/manga-ocr-nar-small", local_dir="/tmp/nar")
        sh(f'pip install -q -e "{d}[cuda]"')
        sys.path.insert(0, d)
        from manga_ocr_nar_small import MangaOcrNarSmall
        m = MangaOcrNarSmall()
        return lambda imgs: list(m(imgs))

    def load_paddle():
        from transformers import AutoModelForCausalLM, AutoProcessor
        repo = "jzhang533/PaddleOCR-VL-For-Manga"
        model = AutoModelForCausalLM.from_pretrained(repo, trust_remote_code=True, torch_dtype=torch.float32).to("cuda:0").eval()
        proc = AutoProcessor.from_pretrained(repo, trust_remote_code=True)

        def run(imgs):
            res = []
            for im in imgs:
                msgs = [{"role": "user", "content": [{"type": "image", "image": im}, {"type": "text", "text": "OCR:"}]}]
                inp = proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to("cuda:0")
                with torch.inference_mode():
                    o = model.generate(**inp, max_new_tokens=128, do_sample=False)
                res.append(proc.batch_decode(o[:, inp["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip())
            return res
        return run

    def load_baberu():
        from huggingface_hub import snapshot_download
        d = snapshot_download("genshiai-daichi/baberu-ocr", local_dir="/tmp/baberu")
        sys.path.insert(0, d)
        from inference import BaberuOCR
        m = BaberuOCR(d)
        call = next((getattr(m, a) for a in ("__call__", "recognize", "predict", "ocr") if callable(getattr(m, a, None))), None)
        return lambda imgs: [str(call(x)) for x in imgs]

    for name, loader in (("manga-ocr", load_manga_ocr), ("cpt-flex", load_cpt), ("nar-small", load_nar),
                         ("paddleocr-vl-manga", load_paddle), ("baberu", load_baberu)):
        try:
            t0 = time.time()
            run = loader()
            load_s = time.time() - t0
            res = {"gt": {}, "det": {}}
            t1 = time.time()
            for pid, p in ALL_PAGES.items():  # one call per page, as the product would
                imgs = [pil(c["dataUrl"]) for c in p["gtCrops"]]
                for c, txt in zip(p["gtCrops"], run(imgs) if imgs else []):
                    res["gt"][f"{pid}#{c['i']}"] = txt
                imgs = [pil(c["dataUrl"]) for c in p["ocr"]]
                res["det"][pid] = dict(zip([c["id"] for c in p["ocr"]], run(imgs) if imgs else []))
            res["msPerCrop"] = round(1000 * (time.time() - t1) / (len(gt_items) + len(det_items)), 1)
            res["loadSec"] = round(load_s)
            save(f"ocr/{name}.json", res)
            log(f"OCR {name}: {res['msPerCrop']} ms/crop, load {res['loadSec']} s")
            if name not in OCR_PICK and name in ("cpt-flex", "manga-ocr"):
                OCR_PICK.setdefault("name", name)
            if name == "cpt-flex":
                OCR_PICK["name"] = name
        except Exception as e:
            log(f"OCR {name} failed: {e}\n{traceback.format_exc()[-1500:]}")
            save(f"ocr/{name}.json", {"error": str(e)})
        finally:
            run = None
            import gc
            gc.collect()
            torch.cuda.empty_cache()
    OCR_DONE.set()


# ---------------------------------------------------------------- jobs
def gold_lines():
    return [(pid, [s["ja"] for s in LINES[pid]], [s["i"] for s in LINES[pid]]) for pid in PAGES if pid in LINES]


def run_mt(port, tag, model, mode, make=None, think=None, raw=False, opts=None):
    """mode: line (each line alone) | batch (numbered page) | delim (Hy-MT2 delimiter page)."""
    res, ms, failed_pages = {}, [], 0
    for pid, lines, ids in gold_lines():
        if mode == "line":
            vi, t = per_line(port, model, lines, make, opts or HYMT_OPTS, think, raw)
            ms += t
        elif mode == "batch":
            vi, r = page_batch(port, model, lines, think)
            ms.append(r["totalMs"])
        else:
            vi, r = hymt_delimited(port, model, lines)
            ms.append(r["totalMs"])
            if vi is None:  # segment count mismatch: fall back to one call per line
                failed_pages += 1
                vi, t = per_line(port, model, lines, hymt_plain, HYMT_OPTS)
                ms += t
        for i, v in zip(ids, vi):
            res[f"{pid}#{i}"] = v
    save(f"mt/{tag}.json", {"model": model, "mode": mode, "out": res, "msTotal": sum(ms), "calls": len(ms), "fallbackPages": failed_pages})
    log(f"MT {tag}: {len(res)} lines, {sum(ms) / 1000:.0f} s total")


def run_mt2(port, tag, model, mode, make=None, think=None, raw=False, opts=None):
    """Two-stage: translate the OCR text of the detected regions, in reading order."""
    OCR_DONE.wait()
    eng = OCR_PICK.get("name")
    if not eng:
        return
    det = json.load(open(f"{OUT}/ocr/{eng}.json", encoding="utf-8")).get("det", {})
    res, ms = {}, []
    for pid, p in PAGES.items():
        regs = sorted(p["regions"], key=lambda r: r.get("order", 0))
        ids = [r["id"] for r in regs if det.get(pid, {}).get(r["id"], "").strip()]
        lines = [det[pid][i] for i in ids]
        if not lines:
            continue
        if mode == "line":
            vi, t = per_line(port, model, lines, make, opts or HYMT_OPTS, think, raw)
            ms += t
        else:
            vi, r = page_batch(port, model, lines, think)
            ms.append(r["totalMs"])
        res[pid] = dict(zip(ids, vi))
    save(f"mt2/{eng}__{tag}.json", {"model": model, "ocr": eng, "mode": mode, "out": res, "msTotal": sum(ms), "calls": len(ms)})
    log(f"MT2 {eng} -> {tag}: {sum(len(v) for v in res.values())} regions, {sum(ms) / 1000:.0f} s")


def ollama_messages(messages):
    """OpenAI-style content parts -> consecutive native messages, in order (what Ollama's /v1 endpoint does)."""
    out = []
    for m in messages:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "content": m["content"]})
            continue
        for part in m["content"]:
            if part["type"] == "text":
                out.append({"role": m["role"], "content": part["text"]})
            else:
                out.append({"role": m["role"], "content": "", "images": [part["image_url"]["url"].split(",", 1)[1]]})
    return out


def with_hints(messages, pid):
    """The product's page request plus the crop OCR's reading of each region: the model still sees the page
    (speakers, who addresses whom, SFX) but no longer has to read small Japanese text itself."""
    det = json.load(open(f"{OUT}/ocr/{OCR_PICK['name']}.json", encoding="utf-8")).get("det", {}).get(pid, {})
    lines = "\n".join(f"{rid}: {t}" for rid, t in det.items() if t.strip())
    hint = {"type": "text", "text": "Pre-read Japanese text of each region by a dedicated OCR model (may contain mistakes; trust the image "
            "when they disagree, and keep ja as what is really written):\n" + lines}
    out = [dict(m) for m in messages]
    out[-1] = {**out[-1], "content": list(out[-1]["content"]) + [hint]}
    return out


def run_vlm(port, tag, model, think=None, hints=False):
    if hints:
        OCR_DONE.wait()
        if not OCR_PICK.get("name"):
            return
    n = 0
    for pid, p in PAGES.items():
        name = re.sub(r"[^\w.-]", "_", pid)
        try:
            msgs = with_hints(p["messages"], pid) if hints else p["messages"]
            r = chat(port, model, ollama_messages(msgs), {"temperature": 0.2, "num_ctx": 16384, "num_predict": 4096}, think)
            save(f"vlm/{tag}/{name}.json", {"model": tag, "pageId": pid, "raw": r["text"], **{k: r[k] for k in ("ttfbMs", "totalMs", "promptTokens", "completionTokens")}})
            n += 1
        except Exception as e:
            save(f"vlm/{tag}/{name}.json", {"model": tag, "pageId": pid, "raw": "", "error": str(e)})
    log(f"VLM {tag}: {n}/{len(PAGES)} pages")


HYMT7 = "hf.co/tencent/Hy-MT2-7B-GGUF"
JOBS = [
    # (ollama model or discovery key, [(stage, tag, kwargs)])
    (f"{HYMT7}:Q6_K", [("mt", "hymt2-7b-q6-line", dict(mode="line", make=hymt_plain)),
                       ("mt", "hymt2-7b-q6-bg", dict(mode="line", make=hymt_background)),
                       ("mt", "hymt2-7b-q6-delim", dict(mode="delim")),
                       ("mt2", "hymt2-7b-q6-line", dict(mode="line", make=hymt_plain))]),
    ("qwen3.5:9b", [("vlm", "qwen3.5-9b", dict(think=False)),
                    ("vlm", "qwen3.5-9b-ocrhint", dict(think=False, hints=True)),
                    ("mt", "qwen3.5-9b-batch", dict(mode="batch", think=False)),
                    ("mt2", "qwen3.5-9b-batch", dict(mode="batch", think=False))]),
    ("translategemma:12b", [("mt", "translategemma-12b-line", dict(mode="line", make=translategemma, opts={"temperature": 0.2, "num_predict": 300})),
                            ("mt2", "translategemma-12b-line", dict(mode="line", make=translategemma, opts={"temperature": 0.2, "num_predict": 300}))]),
    ("gemma4:12b", [("vlm", "gemma4-12b", dict(think=False)),
                    ("vlm", "gemma4-12b-ocrhint", dict(think=False, hints=True)),
                    ("mt", "gemma4-12b-batch", dict(mode="batch", think=False)),
                    ("mt2", "gemma4-12b-batch", dict(mode="batch", think=False))]),
    ("qwen3-vl:8b-instruct", [("vlm", "qwen3-vl-8b", {}), ("vlm", "qwen3-vl-8b-ocrhint", dict(hints=True))]),
    ("gemma4:e4b", [("vlm", "gemma4-e4b", dict(think=False)),
                    ("vlm", "gemma4-e4b-ocrhint", dict(think=False, hints=True)),
                    ("mt", "gemma4-e4b-batch", dict(mode="batch", think=False))]),
    (f"{HYMT7}:Q4_K_M", [("mt", "hymt2-7b-q4-line", dict(mode="line", make=hymt_plain)),
                         ("mt", "hymt2-7b-q4-bg", dict(mode="line", make=hymt_background))]),
    (f"{HYMT7}:Q8_0", [("mt", "hymt2-7b-q8-line", dict(mode="line", make=hymt_plain))]),
    ("qwen3.5:4b", [("vlm", "qwen3.5-4b", dict(think=False)),
                    ("vlm", "qwen3.5-4b-ocrhint", dict(think=False, hints=True)),
                    ("mt", "qwen3.5-4b-batch", dict(mode="batch", think=False))]),
    ("translategemma:4b", [("mt", "translategemma-4b-line", dict(mode="line", make=translategemma, opts={"temperature": 0.2, "num_predict": 300}))]),
    ("search:Hy-MT2-1.8B", [("mt", "hymt2-1.8b-line", dict(mode="line", make=hymt_plain))]),
    ("search:MiLMMT-46-12B", [("mt", "milmmt-46-12b-line", dict(mode="line", make=milmmt, opts={"temperature": 0.0, "num_predict": 300}))]),
    ("search:Seed-X-PPO-7B", [("mt", "seedx-ppo-7b-line", dict(mode="line", make=seedx, raw=True, opts={"temperature": 0.0, "num_predict": 300}))]),
]

META = {"gpus": GPUS, "models": {}, "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def worker(slot):
    port = PORTS[slot]
    if slot == 0:
        ocr_stage()
    while True:
        try:
            model, tasks = JOB_QUEUE.get_nowait()
        except queue.Empty:
            return
        tasks = [t for t in tasks if t[0] in STAGES]
        if not tasks:
            continue
        try:
            if model.startswith("search:"):
                found = hf_gguf(model[7:])
                log(f"{model} -> {found}")
                if not found:
                    META["models"][model] = {"error": "no GGUF found"}
                    continue
                model = found
            info = pull(port, model)
            PEAK[slot] = 0
            t0 = time.time()
            for stage, tag, kw in tasks:
                try:
                    {"mt": run_mt, "mt2": run_mt2, "vlm": run_vlm}[stage](port, tag, model, **kw)
                except Exception as e:
                    log(f"{stage} {tag} failed: {e}\n{traceback.format_exc()[-1200:]}")
            META["models"][model] = {**info, "vramMb": PEAK.get(slot), "gpu": GPUS[slot] if slot < len(GPUS) else "?", "jobSec": round(time.time() - t0)}
            save("meta.json", META)
        except Exception as e:
            log(f"job {model} failed: {e}\n{traceback.format_exc()[-1200:]}")
            META["models"][model] = {"error": str(e)}
        finally:
            remove(port, model)


JOB_QUEUE = queue.Queue()
for j in JOBS:
    JOB_QUEUE.put(j)

try:
    if STAGES & {"mt", "mt2", "vlm"}:
        setup_ollama()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(PORTS))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
except Exception as e:
    log("fatal:", e, traceback.format_exc())
finally:
    META["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save("meta.json", META)
    for i in range(len(PORTS)):
        if os.path.exists(f"/tmp/ollama{i}.log"):
            shutil.copy(f"/tmp/ollama{i}.log", f"{OUT}/ollama{i}.log")
    shutil.make_archive("/kaggle/working/results", "zip", OUT)
    log("done")
