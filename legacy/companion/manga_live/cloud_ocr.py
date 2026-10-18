"""Opt-in crop OCR. Detector/lettering remain local; no page-box generation.

No retry/fallback and no request while loading/settings are being saved.
"""
import threading
from . import vision_ocr
from .errors import require
from .ocr import blank_crop
from . import providers

MODEL = "google/gemini-3.5-flash-lite"
PAGE_MODEL = MODEL


class CloudCropOcr:
    name = MODEL + "/" + vision_ocr.VERSION + "/crops-review-v1"

    def __init__(self, config, vault):
        self.config, self.vault = config, vault
        self.model_id = config.values.get("cloudOcrModel", MODEL)
        require(self.model_id in vision_ocr.MODELS, "VISION_MODEL",
                "Model OCR cloud chưa được kiểm tra hoặc không hỗ trợ vision.")
        self.name = self.model_id + "/" + vision_ocr.VERSION + "/crops-review-v1"
        self.model = None  # readiness only, never a downloaded model
        self.uncertain_indices = set()
        self.cancel = threading.Event()

    def authorize(self):
        cfg = self.config.values
        require(cfg.get("mode") == "byok" and cfg.get("provider") == "openrouter" and cfg.get("ocr") == "cloud-gemini" and
                cfg.get("cloudConsent") is True and cfg.get("cloudOcrConsent") is True,
                "IMAGE_CONSENT", "OCR cloud cần BYOK OpenRouter và xác nhận riêng gửi crop có tính phí. Không tự chuyển engine.")
        require(not self.cancel.is_set(), "CANCELED", "Đã hủy OCR cloud.")

    def load(self):
        self.authorize()
        self.model = True  # no Vault lookup, model download or paid request

    def recognize(self, image):
        return self.recognize_many([image])[0]

    def recognize_many(self, images):
        self.authorize()  # before even encoding a cloud request
        require(isinstance(images, list) and 1 <= len(images) <= 4, "VISION_SIZE")
        self.uncertain_indices = set()
        valid = [(str(n), image) for n, image in enumerate(images) if not blank_crop(image)]
        values = [""] * len(images)
        if not valid: return values
        body = vision_ocr.request(self.model_id, valid)
        # Explicit ceilings and one exact compliant route; never relax these
        # silently on a rate/availability error. No total-spend claim in BYOK.
        body["provider"]["max_price"] = {"prompt": .30, "completion": 2.5, "request": 0}
        self.authorize()
        key = self.vault.get("openrouter")
        response = providers.post_json("https://openrouter.ai/api/v1/chat/completions", body,
                                       {"Authorization": "Bearer " + key}, timeout=35)
        self.authorize()  # a cancelled/late response is not usable source text
        for row in vision_ocr.checked_response(response, [r[0] for r in valid]):
            index = int(row["id"])
            values[index] = row["ja"]
            # A nonblank source that cannot be transcribed remains recoverable
            # review geometry, not a silently deleted detection.
            if row["uncertain"] or not row["ja"].strip(): self.uncertain_indices.add(index)
        self.model = True
        return values


class CloudPageDetector:
    """Opt-in full-page text proposals for detector-recall experiments.

    The provider's boxes are source proposals only: they never become glyph
    masks, speaker evidence, story memory or erasure authority. The source
    page is resized only in a temporary RAM copy when the vision contract's
    edge/pixel limits require it; returned geometry is mapped back to the
    immutable source dimensions.
    """
    def __init__(self, config, vault):
        self.config, self.vault = config, vault
        self.model_id = config.values.get("cloudOcrModel", PAGE_MODEL)
        require(self.model_id in vision_ocr.MODELS, "VISION_MODEL",
                "Model OCR cloud chưa được kiểm tra hoặc không hỗ trợ vision.")
        self.name = self.model_id + "/" + vision_ocr.VERSION + "/page-proposals-v1"
        self.cancel = threading.Event()
        self.model = None

    def authorize(self):
        cfg = self.config.values
        require(cfg.get("mode") == "byok" and cfg.get("provider") == "openrouter" and
                cfg.get("detector") == "cloud-page" and cfg.get("cloudConsent") is True and
                cfg.get("cloudPageOcrConsent") is True, "IMAGE_CONSENT",
                "Detector cloud cần xác nhận riêng gửi toàn bộ ảnh trang và phí API.")
        require(not self.cancel.is_set(), "CANCELED", "Đã hủy detector cloud.")

    def warmup(self):
        """Validate consent only; warmup must never send a paid request."""
        self.authorize()
        self.model = True

    @staticmethod
    def _view(image):
        from PIL import Image
        width, height = image.size
        scale = min(1.0, vision_ocr.MAX_EDGE / max(width, height),
                    (vision_ocr.MAX_PIXELS / max(1, width * height)) ** .5)
        if scale >= 1.0:
            return image, 1.0
        size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        return image.resize(size, Image.Resampling.LANCZOS), scale

    def detect(self, image):
        self.authorize()
        view, scale = self._view(image)
        body = vision_ocr.request(self.model_id, [("page", view)], page=True)
        body["provider"]["max_price"] = {"prompt": .30, "completion": 2.5, "request": 0}
        self.authorize()
        response = providers.post_json("https://openrouter.ai/api/v1/chat/completions", body,
                                       {"Authorization": "Bearer " + self.vault.get("openrouter")}, timeout=45)
        self.authorize()
        rows = vision_ocr.checked_response(response, ["page"], page=True, image_size=view.size)
        regions = []
        for index, row in enumerate(rows):
            source = row["box"]
            x = max(0, min(image.width - 1, int(round(source["x"] / scale))))
            y = max(0, min(image.height - 1, int(round(source["y"] / scale))))
            right = min(image.width, int(round((source["x"] + source["w"]) / scale)))
            bottom = min(image.height, int(round((source["y"] + source["h"]) / scale)))
            if right <= x or bottom <= y:
                continue
            reasons = ["cloud_page_proposal"]
            if row["uncertain"]:
                reasons.append("cloud_ocr_uncertain")
            regions.append({"id": "r%03d" % index, "bbox": [x, y, right - x, bottom - y],
                            "score": 0.0, "overlay": "label", "review": True,
                            "reviewReasons": reasons, "type": "unknown", "order": index,
                            "speaker": "unknown", "listener": "unknown"})
        self.model = True
        return regions
