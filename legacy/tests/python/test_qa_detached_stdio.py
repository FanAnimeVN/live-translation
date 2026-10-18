from pathlib import Path
import subprocess
import sys


def test_qa_private_transport_survives_replacing_python_stdout():
    scripts = Path(__file__).resolve().parents[2]/"scripts"
    code = (f"import sys;sys.path.insert(0,{str(scripts)!r});"
            "from qa_native_entry import detached_stdio;"
            "held=detached_stdio();output=sys.stdout.buffer;sys.stdout=sys.stderr;"
            "output.write(b'transport-ok');output.flush()")
    result = subprocess.run([sys.executable, "-c", code], input=b"", capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stdout == b"transport-ok"
