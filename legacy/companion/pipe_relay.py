"""Byte-only native transport front-end. AI never inherits browser pipes.

No frame/content logging, listening sockets, files or credentials. The child
retains the actual host origin validation and persistent model lifecycle.
"""
import os
import subprocess
import threading
from manga_live.process_lifetime import own_process


def relay_process(command,source,destination,environment=None):
    child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    lifetime=None
    try:
        lifetime=own_process(child)
        def forward_input():
            try:
                read=getattr(source,"read1",source.read)
                while part:=read(64*1024):
                    child.stdin.write(part);child.stdin.flush()
            except (OSError,ValueError):
                pass  # Browser/child has closed; never retry a dead transport.
            finally:
                try:child.stdin.close()
                except (OSError,ValueError):pass
        def forward_output():
            try:
                while part:=child.stdout.read1(64*1024):
                    destination.write(part);destination.flush()
            except (OSError,ValueError):
                if child.poll() is None:child.terminate()
        reader=threading.Thread(target=forward_input,daemon=True)
        writer=threading.Thread(target=forward_output,daemon=True)
        reader.start();writer.start()
        result=child.wait();writer.join(timeout=5)
        return result
    finally:
        if lifetime:lifetime.close()
        if child.poll() is None:
            child.terminate();child.wait(timeout=5)
        child.stdout.close()

