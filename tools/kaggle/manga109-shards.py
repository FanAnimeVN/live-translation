"""
Cut Manga109 into OCR training data: one grayscale crop per text box and per onomatopoeia (COO),
packed into tar shards per split (tools/kaggle/manga109-split.json: split by title), with labels in JSONL.
Reads the released ZIP in place (nothing is extracted to disk). Academic use only (Manga109 terms):
models trained on this data are for the thesis, never for the paid tier.

  python -I tools/kaggle/manga109-shards.py D:/Manga109_released_2026_05_21.zip tools/kaggle/manga109-split.json .private/kaggle/upload/lt-manga109-crops
"""
import io, json, os, sys, tarfile, time, zipfile
import xml.etree.ElementTree as ET
from PIL import Image

zip_path, split_path, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
split = json.load(open(split_path, encoding="utf-8"))
title_split = {t: s for s in ("train", "val", "oos", "test_team") for t in split[s]}
z = zipfile.ZipFile(zip_path)
R = next(n for n in z.namelist() if n.endswith("books.txt")).rsplit("/", 1)[0] + "/"
MAX_SIDE, MARGIN, SHARD_BYTES = 512, 4, 300 * 1024 * 1024


class Shards:
    def __init__(self, name):
        self.name, self.n, self.size, self.tar = name, 0, 0, None
        self.labels = open(os.path.join(out, f"labels_{name}.jsonl"), "w", encoding="utf-8")

    def add(self, key, jpeg, label):
        if self.tar is None or self.size > SHARD_BYTES:
            if self.tar:
                self.tar.close()
            self.tar = tarfile.open(os.path.join(out, f"{self.name}_{self.n:03d}.tar"), "w")
            self.n, self.size = self.n + 1, 0
        info = tarfile.TarInfo(f"{key}.jpg")
        info.size, info.mtime = len(jpeg), 0
        self.tar.addfile(info, io.BytesIO(jpeg))
        self.size += len(jpeg)
        self.labels.write(json.dumps({"key": key, "shard": f"{self.name}_{self.n - 1:03d}.tar", **label}, ensure_ascii=False) + "\n")

    def close(self):
        if self.tar:
            self.tar.close()
        self.labels.close()


def crop(img, x0, y0, x1, y1):
    x0, y0 = max(0, int(x0) - MARGIN), max(0, int(y0) - MARGIN)
    x1, y1 = min(img.width, int(x1) + MARGIN), min(img.height, int(y1) + MARGIN)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    c = img.crop((x0, y0, x1, y1))
    s = min(1.0, MAX_SIDE / max(c.size))
    if s < 1:
        c = c.resize((max(1, round(c.width * s)), max(1, round(c.height * s))), Image.BICUBIC)
    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=90)
    return buf.getvalue(), [x0, y0, x1, y1]


shards = {s: Shards(s) for s in ("train", "val", "oos", "test_team")}
counts = {s: {"text": 0, "sfx": 0} for s in shards}
t0 = time.time()
books = z.read(R + "books.txt").decode("utf-8").split()
for bi, book in enumerate(books):
    sp = title_split.get(book)
    if not sp:
        continue
    text_pages = {int(p.get("index")): p for p in ET.fromstring(z.read(f"{R}annotations/{book}.xml")).iter("page")}
    try:
        sfx_pages = {int(p.get("index")): p for p in ET.fromstring(z.read(f"{R}annotations_COO/{book}.xml")).iter("page")}
    except KeyError:
        sfx_pages = {}
    for idx in sorted(set(text_pages) | set(sfx_pages)):
        texts = list(text_pages[idx].iter("text")) if idx in text_pages else []
        sfxs = list(sfx_pages[idx].iter("onomatopoeia")) if idx in sfx_pages else []
        if not texts and not sfxs:
            continue
        try:
            img = Image.open(io.BytesIO(z.read(f"{R}images/{book}/{idx:03d}.jpg"))).convert("L")
        except KeyError:
            continue
        for t in texts:
            label = (t.text or "").strip()
            r = crop(img, t.get("xmin"), t.get("ymin"), t.get("xmax"), t.get("ymax"))
            if not label or not r:
                continue
            shards[sp].add(f"{book}_{idx:03d}_t{t.get('id')}", r[0], {"title": book, "page": idx, "kind": "text", "box": r[1], "text": label})
            counts[sp]["text"] += 1
        for o in sfxs:
            label = (o.text or "").strip()
            xs = [float(o.get(f"x{i}")) for i in range(4) if o.get(f"x{i}") is not None]
            ys = [float(o.get(f"y{i}")) for i in range(4) if o.get(f"y{i}") is not None]
            if not label or len(xs) < 3:
                continue
            r = crop(img, min(xs), min(ys), max(xs), max(ys))
            if not r:
                continue
            quad = [[round(x - r[1][0]), round(y - r[1][1])] for x, y in zip(xs, ys)]
            shards[sp].add(f"{book}_{idx:03d}_s{o.get('id')}", r[0], {"title": book, "page": idx, "kind": "sfx", "box": r[1], "quad": quad, "text": label})
            counts[sp]["sfx"] += 1
    print(f"{bi + 1}/{len(books)} {book} -> {sp}  ({time.time() - t0:.0f} s)", flush=True)
for s in shards.values():
    s.close()
json.dump({"source": os.path.basename(zip_path), "split": split_path, "counts": counts, "maxSide": MAX_SIDE, "grayscale": True,
           "terms": "Manga109: academic use only, no redistribution; models trained on it are not for commercial use"},
          open(os.path.join(out, "manifest.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(counts))
