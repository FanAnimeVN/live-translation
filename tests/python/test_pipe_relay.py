import io
import sys
from pipe_relay import relay_process


def test_relay_preserves_binary_framing_and_many_chunks():
    source=bytes(range(256))*3000
    target=io.BytesIO()
    script="import sys;data=sys.stdin.buffer.read();sys.stdout.buffer.write(data);sys.stdout.buffer.flush()"
    assert relay_process([sys.executable,"-u","-c",script],io.BytesIO(source),target)==0
    assert target.getvalue()==source


def test_relay_has_no_library_or_other_unframed_output():
    target=io.BytesIO()
    script="import sys;sys.stderr.write('must not enter protocol');sys.stdout.buffer.write(b'\\x04\\x00\\x00\\x00test');sys.stdout.buffer.flush()"
    assert relay_process([sys.executable,"-u","-c",script],io.BytesIO(),target)==0
    assert target.getvalue()==b"\x04\x00\x00\x00test"
