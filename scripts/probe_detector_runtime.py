"""Compare fixed-image detector setup in development vs the frozen bundle."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--development",action="store_true")
    parser.add_argument("--bundle",default=str(ROOT/"dist/portable/MangaLiveHost"))
    parser.add_argument("--output",default=str(ROOT/"artifacts/detector-runtime-probe.json"))
    args=parser.parse_args();bundle=Path(args.bundle).resolve()
    with tempfile.TemporaryDirectory(prefix="manga-detector-probe-") as temporary:
        config=Path(temporary)/"probe.json"
        config.write_text(json.dumps({"models":str((ROOT if args.development else bundle)/"models")}),encoding="utf-8")
        command=[sys.executable,"-B",str(ROOT/"companion/entry.py")] if args.development else [str(bundle/"MangaLiveHost.exe")]
        reply=subprocess.run([*command,"--config",str(config),"--runtime-probe","detector"],
            cwd=temporary,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        lines=reply.stdout.decode("utf-8",errors="replace").splitlines()
        # Libraries may emit setup warnings; the CLI's final line is the report.
        report=json.loads(lines[-1]) if lines else {"passed":False,"error":"Probe produced no report"}
        report.update(development=args.development,exit_code=reply.returncode)
        destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(report,ensure_ascii=True),flush=True)
        raise SystemExit(reply.returncode)


if __name__=="__main__":main()
