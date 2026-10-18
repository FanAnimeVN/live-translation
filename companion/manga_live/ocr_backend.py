"""Local-only manga recognizer, independent of any site-packages model patch.

Keep the manga-ocr preprocessing/postprocessing and pinned weights. Avoid its
implicit example-image warmup and own the Transformers compatibility seam.
Heavy ML imports happen only when the reader actually needs OCR.
"""
from pathlib import Path


def generation_class(base, mixin):
    """Older/newer Transformers may inherit generation at different levels."""
    if issubclass(base, mixin):
        return base

    class LocalGenerationModel(base, mixin):
        pass

    return LocalGenerationModel


class LocalMangaRecognizer:
    def __init__(self, model_dir):
        import torch
        from manga_ocr.ocr import post_process
        from transformers import AutoTokenizer, GenerationMixin, ViTImageProcessor, VisionEncoderDecoderModel

        path = str(Path(model_dir).resolve())
        self.processor = ViTImageProcessor.from_pretrained(path, local_files_only=True)
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        model_class = generation_class(VisionEncoderDecoderModel, GenerationMixin)
        self.model = model_class.from_pretrained(path, local_files_only=True)
        self.model.eval()
        self._torch, self._post_process = torch, post_process

    def recognize_many(self, images):
        if not images:
            return []
        # Same grayscale conversion as upstream manga-ocr; no images on disk.
        pixels = self.processor([image.convert("L").convert("RGB") for image in images],
                                return_tensors="pt").pixel_values
        with self._torch.inference_mode():
            encoded = self.model.generate(pixels.to(self.model.device), max_length=300)
        decoded = self.tokenizer.batch_decode(encoded.cpu(), skip_special_tokens=True)
        return [self._post_process(text) for text in decoded]

    def __call__(self, image):
        return self.recognize_many([image])[0]
