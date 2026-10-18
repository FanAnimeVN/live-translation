"""Bounded pipe reads for Windows native-import regression tests.

Blocking stdin coincides with a reproduced worker DLL-import hang on this
runtime, even with raw reads. Poll the inherited pipe before reading rather
than waiting inside ReadFile. Framing still belongs to read_exact.
See https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe
"""
import os
import time


class WindowsPipeInput:
    def __init__(self,stream):
        import ctypes
        from ctypes import wintypes
        import msvcrt
        self.ctypes=ctypes
        self.handle=wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
        self.kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        self.kernel.ReadFile.argtypes=[wintypes.HANDLE,wintypes.LPVOID,wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
        self.kernel.ReadFile.restype=wintypes.BOOL
        self.kernel.PeekNamedPipe.argtypes=[wintypes.HANDLE,wintypes.LPVOID,wintypes.DWORD,
            wintypes.LPVOID,ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
        self.kernel.PeekNamedPipe.restype=wintypes.BOOL
        self.count_type=wintypes.DWORD

    def read(self,size):
        if type(size) is not int or not 0<=size<=768*1024:
            raise ValueError("Invalid native pipe read size")
        if size==0:return b""
        available=self.count_type()
        while True:
            if not self.kernel.PeekNamedPipe(self.handle,None,0,None,self.ctypes.byref(available),None):
                error=self.ctypes.get_last_error()
                if error in (38,109):return b""
                raise self.ctypes.WinError(error)
            if available.value:break
            time.sleep(0.01)
        size=min(size,available.value)
        buffer=self.ctypes.create_string_buffer(size);count=self.count_type()
        if not self.kernel.ReadFile(self.handle,buffer,size,self.ctypes.byref(count),None):
            error=self.ctypes.get_last_error()
            if error in (38,109):return b""  # EOF / broken pipe after browser exits.
            raise self.ctypes.WinError(error)
        return buffer.raw[:count.value]


def native_input(stream):
    return WindowsPipeInput(stream) if os.name=="nt" else stream
