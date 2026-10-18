"""Store a test secret from a non-echoing stdin pipe, never command-line arguments."""
import argparse
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"companion"))
from manga_live.config import Secrets

parser=argparse.ArgumentParser()
parser.add_argument("--profile",required=True)
parser.add_argument("--provider",default="openrouter")
parser.add_argument("--prompt",action="store_true",help="Read from a terminal without echo")
args=parser.parse_args()
print("Waiting for secret on stdin (not echoed).",flush=True)
value=(getpass.getpass("Secret (hidden): ").strip() if args.prompt else sys.stdin.readline().strip())
try:
    Secrets(args.profile).set(args.provider,value)
    print("Secret saved to Windows Vault. No plaintext file written.",flush=True)
except Exception as error:
    print("Vault failure: "+type(error).__name__,file=sys.stderr)
    raise SystemExit(1)
finally:
    value=""
