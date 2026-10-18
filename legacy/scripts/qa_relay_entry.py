"""Isolated source relay counterfactual; no production registration changes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from qa_native_entry import diagnostic_folder
from pipe_relay import relay_process

if __name__=="__main__":
    folder=diagnostic_folder(sys.argv)
    index=sys.argv.index("--config")
    arguments=sys.argv[1:index]
    command=[sys.executable,str(ROOT/"scripts/qa_native_entry.py"),*arguments,"--config",str(folder/"native-config.json")]
    raise SystemExit(relay_process(command,sys.stdin.buffer,sys.stdout.buffer))
