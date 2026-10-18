"""No real ML imports/weights: verify the owned local OCR seam."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import sys

from PIL import Image
from manga_live.ocr import MangaEngine
from manga_live.ocr_backend import LocalMangaRecognizer, generation_class


def test_generation_compatibility_does_not_duplicate_an_existing_mixin():
    class Generation:
        def generate(self):return "generated"
    class AlreadySupports(Generation):pass
    class NeedsSupport:pass
    assert generation_class(AlreadySupports, Generation) is AlreadySupports
    assert generation_class(NeedsSupport, Generation)().generate() == "generated"


def test_recognizer_reads_only_local_weights_without_warmup_or_custom_code(tmp_path, monkeypatch):
    loads=[];inference=[];generations=[];grays=[]
    class Tensor:
        def to(self, device):assert device == "cpu";return self
        def cpu(self):return self
    class Processor:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            loads.append(("processor",path,kwargs));return cls()
        def __call__(self, images, **kwargs):
            grays.extend(image.getpixel((0,0)) for image in images)
            assert kwargs == {"return_tensors":"pt"}
            return SimpleNamespace(pixel_values=Tensor())
    class Tokenizer:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            loads.append(("tokenizer",path,kwargs));return cls()
        def batch_decode(self, encoded, **kwargs):
            assert kwargs == {"skip_special_tokens":True}
            return [" text "]
    class Generation:
        def generate(self, pixels, **kwargs):
            generations.append(kwargs);return Tensor()
    class Model:
        device="cpu"
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            loads.append(("model",path,kwargs));return cls()
        def eval(self):inference.append("eval")
    def inference_mode():
        inference.append("no-grad");return nullcontext()
    monkeypatch.setitem(sys.modules,"torch",SimpleNamespace(inference_mode=inference_mode))
    monkeypatch.setitem(sys.modules,"transformers",SimpleNamespace(AutoTokenizer=Tokenizer,GenerationMixin=Generation,
        ViTImageProcessor=Processor,VisionEncoderDecoderModel=Model))
    monkeypatch.setitem(sys.modules,"manga_ocr.ocr",SimpleNamespace(post_process=lambda text:text.strip()))
    recognizer=LocalMangaRecognizer(tmp_path)
    assert generations == [], "Construction must not OCR a bundled sample or write a cache"
    assert all(path == str(tmp_path.resolve()) and options["local_files_only"] for _,path,options in loads)
    assert loads[1][2]["trust_remote_code"] is False
    assert recognizer.recognize_many([]) == []
    assert recognizer(Image.new("RGB",(4,4),(255,0,0))) == "text"
    assert grays == [(76,76,76)]
    assert generations == [{"max_length":300}]
    assert inference == ["eval","no-grad"]


def test_blank_batches_do_not_load_model_and_keep_region_positions(monkeypatch):
    import manga_live.ocr as module
    monkeypatch.setattr(module,"blank_crop",lambda image:image == "blank")
    engine=MangaEngine(Path("unused-model"));calls=[]
    def load():
        calls.append("load")
        engine.model=SimpleNamespace(recognize_many=lambda images:["日本語"]*len(images))
    monkeypatch.setattr(engine,"load",load)
    assert engine.recognize_many([]) == []
    assert engine.recognize_many(["blank","blank"]) == ["",""]
    assert calls == []
    assert engine.recognize_many(["blank","text","blank"]) == ["","日本語",""]
    assert calls == ["load"]
