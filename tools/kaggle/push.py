"""
Run the local-model bake-off on Kaggle with the Kaggle CLI (needs `kaggle auth login` done by the account owner).

  python tools/kaggle/push.py upload  [--pack .private/kaggle/team25]   private dataset <user>/lt-<pack>-pack
  python tools/kaggle/push.py run     [--pack ...]                      push tools/kaggle/local-models.py on GPU T4 x2
  python tools/kaggle/push.py status
  python tools/kaggle/push.py fetch                                      results -> .private/kaggle/results/
  python tools/kaggle/push.py delete  [--pack ...]                      delete the private dataset after the run
  python tools/kaggle/push.py run --script train-ocr.py --kernel lt-train-ocr --data lt-m109-train0,lt-m109-train1   another script, several datasets

The dataset is private (only the account owner sees it). Nothing here prints or stores credentials.
"""
import json, os, shutil, subprocess, sys, time, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
args = sys.argv[1:]
cmd = args[0] if args else "status"
pack = args[args.index("--pack") + 1] if "--pack" in args else os.path.join(ROOT, ".private", "kaggle", "team25")
name = os.path.basename(os.path.normpath(pack))
work = os.path.join(ROOT, ".private", "kaggle", "upload")
SLUG_DATA = args[args.index("--data") + 1] if "--data" in args else f"lt-{name}-pack"
SLUG_KERNEL = args[args.index("--kernel") + 1] if "--kernel" in args else "lt-local-models"
SCRIPT = args[args.index("--script") + 1] if "--script" in args else "local-models.py"


def kaggle(*a, capture=True):
    r = subprocess.run([sys.executable, "-m", "kaggle", *a], capture_output=capture, text=True)
    if r.returncode:
        raise SystemExit((r.stdout or "") + (r.stderr or ""))
    return r.stdout or ""


def user():
    for line in kaggle("config", "view").splitlines():
        if line.strip().startswith("- username:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("not signed in: run `python -m kaggle auth login` first")


if cmd == "upload":
    u = user()
    d = os.path.join(work, SLUG_DATA)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for f in ("index.json", "mt-source.json"):
        shutil.copy(os.path.join(pack, f), d)
    for f in os.listdir(os.path.join(pack, "pages")):  # flat: the CLI skips subfolders
        shutil.copy(os.path.join(pack, "pages", f), d)
    json.dump({"title": SLUG_DATA, "id": f"{u}/{SLUG_DATA}", "licenses": [{"name": "other"}]}, open(os.path.join(d, "dataset-metadata.json"), "w"))
    print(kaggle("datasets", "create", "-p", d, "-q"))  # private unless --public is given
    for _ in range(60):
        st = kaggle("datasets", "status", f"{u}/{SLUG_DATA}").strip()
        print("dataset:", st)
        if "ready" in st.lower():
            break
        time.sleep(10)

elif cmd == "run":
    u = user()
    d = os.path.join(work, f"kernel-{SLUG_KERNEL}")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    shutil.copy(os.path.join(ROOT, "tools", "kaggle", SCRIPT), d)
    json.dump({"id": f"{u}/{SLUG_KERNEL}", "title": SLUG_KERNEL, "code_file": SCRIPT, "language": "python", "kernel_type": "script",
               "is_private": True, "enable_gpu": True, "enable_internet": True, "machine_shape": "NvidiaTeslaT4",
               "dataset_sources": [f"{u}/{x}" for x in SLUG_DATA.split(",")]}, open(os.path.join(d, "kernel-metadata.json"), "w"))
    print(kaggle("kernels", "push", "-p", d))

elif cmd == "status":
    print(kaggle("kernels", "status", f"{user()}/{SLUG_KERNEL}"))

elif cmd == "fetch":
    out = os.path.join(ROOT, ".private", "kaggle", "out", SLUG_KERNEL)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    print(kaggle("kernels", "output", f"{user()}/{SLUG_KERNEL}", "-p", out))
    if os.path.exists(os.path.join(out, "results.zip")):  # the bake-off zips its results for kaggle-score.ts
        res = os.path.join(ROOT, ".private", "kaggle", "results")
        shutil.rmtree(res, ignore_errors=True)
        with zipfile.ZipFile(os.path.join(out, "results.zip")) as z:
            z.extractall(res)
        print("results in", res)
    else:
        print("output in", out)

elif cmd == "delete":
    print(kaggle("datasets", "delete", f"{user()}/{SLUG_DATA}", "-y"))

else:
    raise SystemExit(__doc__)
