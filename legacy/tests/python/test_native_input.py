import io
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import pytest

from manga_live.host import read_exact,read_frame
from manga_live.native_input import native_input
from manga_live.errors import AppError

pytestmark=pytest.mark.skipif(os.name!="nt",reason="Regression is specific to Windows native pipe/DLL imports")


def test_worker_import_can_finish_while_native_stdin_is_idle():
    script=Path(__file__).resolve().parents[2]/"scripts/runtime_probe.py"
    result=subprocess.run([sys.executable,str(script),"--case","worker","--input-stream","win32"],
        capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    assert "numpy worker ready" in result.stdout and "worker stuck" not in result.stdout


def test_partial_pipe_data_and_eof_preserve_native_framing():
    from manga_live.memory import encode
    import struct
    read_fd,write_fd=os.pipe();pipe=io.FileIO(read_fd,"rb",closefd=False)
    message={"v":1,"id":"fixture","params":{"ja":"先輩、待って。"}}
    payload=encode(message).encode("utf-8");frame=struct.pack("<I",len(payload))+payload
    def write_parts():
        try:
            for offset in range(0,len(frame),3):os.write(write_fd,frame[offset:offset+3]);time.sleep(0.001)
        finally:os.close(write_fd)
    writer=threading.Thread(target=write_parts);writer.start()
    try:
        source=native_input(pipe)
        assert read_frame(source)==message
        assert read_frame(source) is None
        assert source.read(0)==b""
        for size in (-1,768*1024+1,True):
            with pytest.raises(ValueError):source.read(size)
    finally:
        writer.join(timeout=3);pipe.close();os.close(read_fd)
    assert not writer.is_alive()


def test_truncated_pipe_still_fails_closed():
    read_fd,write_fd=os.pipe();pipe=io.FileIO(read_fd,"rb",closefd=False)
    os.write(write_fd,b"ab");os.close(write_fd)
    try:
        with pytest.raises(AppError) as error:read_exact(native_input(pipe),4)
        assert error.value.code=="FRAME"
    finally:pipe.close();os.close(read_fd)
