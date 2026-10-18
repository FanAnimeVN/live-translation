"""Windows ownership for model subprocesses, not a process-name reaper.

An unnamed, non-inheritable Job Object owns only the child handle supplied by
Popen. Windows closes this host's job handle on abrupt exit and terminates the
assigned child/descendants. No user process is found or killed by PID/name.
https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
"""
import ctypes
import os


class _BasicLimits(ctypes.Structure):
    _fields_=[("PerProcessUserTimeLimit",ctypes.c_int64),("PerJobUserTimeLimit",ctypes.c_int64),
        ("LimitFlags",ctypes.c_uint32),("MinimumWorkingSetSize",ctypes.c_size_t),
        ("MaximumWorkingSetSize",ctypes.c_size_t),("ActiveProcessLimit",ctypes.c_uint32),
        ("Affinity",ctypes.c_size_t),("PriorityClass",ctypes.c_uint32),("SchedulingClass",ctypes.c_uint32)]


class _IoCounters(ctypes.Structure):
    _fields_=[(name,ctypes.c_uint64) for name in ("ReadOperationCount","WriteOperationCount",
        "OtherOperationCount","ReadTransferCount","WriteTransferCount","OtherTransferCount")]


class _ExtendedLimits(ctypes.Structure):
    _fields_=[("BasicLimitInformation",_BasicLimits),("IoInfo",_IoCounters),
        ("ProcessMemoryLimit",ctypes.c_size_t),("JobMemoryLimit",ctypes.c_size_t),
        ("PeakProcessMemoryUsed",ctypes.c_size_t),("PeakJobMemoryUsed",ctypes.c_size_t)]


class _WindowsLifetime:
    def __init__(self,process):
        self.handle=None
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p]
        kernel.CreateJobObjectW.restype=ctypes.c_void_p
        kernel.SetInformationJobObject.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32]
        kernel.SetInformationJobObject.restype=ctypes.c_int32
        kernel.AssignProcessToJobObject.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
        kernel.AssignProcessToJobObject.restype=ctypes.c_int32
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        kernel.CloseHandle.restype=ctypes.c_int32
        self.kernel=kernel
        # NULL security attributes => the child cannot inherit a job handle and
        # keep the job alive after the host dies. No breakaway/security limits.
        handle=kernel.CreateJobObjectW(None,None)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits=_ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags=0x00002000 # KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.AssignProcessToJobObject(handle,int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle=handle
        except BaseException:
            kernel.CloseHandle(handle)
            raise

    def close(self):
        handle,self.handle=self.handle,None
        if handle:self.kernel.CloseHandle(handle)


def own_process(process):
    """Bind a new Windows Popen child before accepting model startup.

    A failure must abort startup, not leave an unowned resident worker.
    Non-Windows currently uses the caller's normal terminate/wait path.
    """
    return _WindowsLifetime(process) if os.name=="nt" else None
