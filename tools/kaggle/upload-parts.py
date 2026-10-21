"""
Upload the Manga109 crop shards as several small private datasets (one shard each, <= ~370 MB): single
uploads over ~1 GB were accepted by the CLI but never became datasets. Each part waits until it is ready.

  python -I tools/kaggle/upload-parts.py .private/kaggle/upload/lt-manga109-crops
"""
import json, os, shutil, subprocess, sys, time

src = os.path.abspath(sys.argv[1])
work = os.path.join(os.path.dirname(src), "parts")
USER = "fananime"
PARTS = {  # slug -> files (labels go with the first shard of their split)
    "lt-m109-oos": ["oos_000.tar", "labels_oos.jsonl"],
    "lt-m109-test": ["test_team_000.tar", "labels_test_team.jsonl"],
    "lt-m109-train0": ["train_000.tar", "labels_train.jsonl"],
    "lt-m109-train1": ["train_001.tar"],
    "lt-m109-train2": ["train_002.tar"],
}


def kaggle(*a):
    r = subprocess.run([sys.executable, "-m", "kaggle", *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "%|" not in l)


for slug, files in PARTS.items():
    code, out = kaggle("datasets", "status", f"{USER}/{slug}")
    if "ready" in out.lower():
        print(slug, "already ready", flush=True)
        continue
    d = os.path.join(work, slug)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for f in files + ["manifest.json"]:
        os.link(os.path.join(src, f), os.path.join(d, f))  # same drive: no copy
    json.dump({"title": slug, "id": f"{USER}/{slug}", "licenses": [{"name": "other"}]}, open(os.path.join(d, "dataset-metadata.json"), "w"))
    code, out = kaggle("datasets", "create", "-p", d)
    print(slug, "create:", code, out.splitlines()[-1] if out else "", flush=True)
    for _ in range(40):
        time.sleep(15)
        code, st = kaggle("datasets", "status", f"{USER}/{slug}")
        if "ready" in st.lower():
            break
    print(slug, "status:", st.splitlines()[-1] if st else "?", flush=True)
