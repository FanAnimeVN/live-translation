import io
import threading
from types import SimpleNamespace

from manga_live.host import Host


def test_inference_job_is_executed_by_main_loop_not_transport_reader():
    host=Host({},io.BytesIO(),start_worker=False);main=threading.get_ident();observed=[]
    host.profile="fixture";host.memory=SimpleNamespace()
    host.translator=SimpleNamespace(summary_worker=SimpleNamespace(process=None),stop=lambda:None)
    host.config=SimpleNamespace(values={"autoSummary":False})
    def warmup(cancel):observed.append(threading.get_ident());return {"ready":True}
    host.pipeline=SimpleNamespace(warmup=warmup)
    def send(*args,**kwargs):host.closing.set()
    host.send=send
    transport=threading.Thread(target=lambda:host.receive(
        {"v":1,"id":"warm","profile":"fixture","op":"warmup","params":{}}))
    transport.start();transport.join(timeout=2);assert not transport.is_alive()
    host.loop()
    assert observed==[main] and not host.worker.is_alive()
    host.memory=None;host.close()  # Closing a host without a started worker is safe.


def test_eof_cancellation_can_be_observed_without_waiting_for_next_job():
    host=Host({},io.BytesIO(),start_worker=False)
    cancellation=threading.Event();host.cancels["in-flight"]=cancellation
    host.close()
    assert host.closing.is_set() and cancellation.is_set()
