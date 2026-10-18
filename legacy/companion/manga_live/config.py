import json
import os
from pathlib import Path
from .errors import AppError, require
from .cloud_models import OPENROUTER_DEFAULT

DEFAULTS = {
    "mode": "offline", "provider": "openrouter", "cloudConsent": False, "cloudOcrConsent": False,
    "cloudPageOcrConsent": False,
    "metadataConsent": False, "autoSummary": False, "threads": 4,
    "summaryBackend": "local", "summaryModel": "deepseek/deepseek-v4.1-flash", "summaryCloudConsent": False,
    "detector": "paddle", "ocr": "manga", "showSfx": False, "ocrBatch":2, "artCleanup": True,
    "cloudOcrModel": "google/gemini-3.5-flash-lite",
    "geminiModel": "gemini-3.5-flash-lite", "deepseekModel": "deepseek-flash",
    "openrouterModel": OPENROUTER_DEFAULT,
}

CLOUD_OCR_MODELS = (
    "anthropic/claude-haiku-5.5",
    "google/gemini-3.5-flash-lite",
    "qwen/qwen3.8-flash",
)
SUMMARY_MODELS = ("deepseek/deepseek-v4.1-flash", "anthropic/claude-haiku-5.5")


def data_root():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "MangaLive"


class Config:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "settings.json"
        self.values = dict(DEFAULTS)
        if self.path.exists():
            try:
                self.values.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                raise AppError("SETTINGS", "Không đọc được cấu hình. Không tự đặt lại dữ liệu của bạn.")

    def update(self, patch):
        require(isinstance(patch, dict) and set(patch) <= set(DEFAULTS))
        proposed = {**self.values, **patch}
        require(proposed["mode"] in ("offline", "byok"))
        require(proposed["provider"] in ("deepseek", "gemini", "openrouter"))
        require(proposed["detector"] in ("paddle", "opencv", "cloud-page"))
        require(proposed["ocr"] in ("manga", "cloud-gemini"), "NOT_READY", "OCR này chưa bật trong luồng đọc.")
        require(proposed["summaryBackend"] in ("local", "cloud"))
        require(proposed["summaryModel"] in SUMMARY_MODELS, "SUMMARY_MODEL", "Model tóm tắt chưa có adapter đã kiểm thử.")
        require(type(proposed["threads"]) is int and 1 <= proposed["threads"] <= 16)
        require(type(proposed["ocrBatch"]) is int and 1 <= proposed["ocrBatch"] <= 4)
        require(proposed["cloudOcrModel"] in CLOUD_OCR_MODELS, "VISION_MODEL",
                "Model OCR cloud chưa được kiểm tra hoặc không hỗ trợ vision.")
        for key in ("cloudConsent", "cloudOcrConsent", "cloudPageOcrConsent", "metadataConsent", "autoSummary", "showSfx", "artCleanup", "summaryCloudConsent"):
            require(type(proposed[key]) is bool)
        for key in ("geminiModel", "deepseekModel", "openrouterModel"):
            require(isinstance(proposed[key], str) and 1 <= len(proposed[key]) <= 80
                    and all(c.isalnum() or c in ("-._/:" if key=="openrouterModel" else "-._") for c in proposed[key]))
        # Consent is for the selected summary route, never inherited by a
        # different model. A new affirmative patch can confirm that route.
        if any(proposed[key]!=self.values[key] for key in ("mode","provider","summaryBackend","summaryModel")) and patch.get("summaryCloudConsent") is not True:
            proposed["summaryCloudConsent"]=False
        if proposed["summaryBackend"]!="cloud" or proposed["provider"]!="openrouter":
            proposed["summaryCloudConsent"]=False
        # Changing to offline disables every optional network feature.
        if proposed["mode"] == "offline":
            proposed["cloudConsent"] = False
            proposed["cloudOcrConsent"] = False
            proposed["cloudPageOcrConsent"] = False
            proposed["ocr"] = "manga"
            proposed["detector"] = "paddle"
            proposed["metadataConsent"] = False
            proposed["summaryBackend"] = "local"
            proposed["summaryCloudConsent"] = False
        if self.values.get("summaryBackend")=="cloud" and proposed["summaryBackend"]!="cloud":
            # Consent for paid cloud background work is not permission to
            # launch a heavyweight local model/backlog on the next idle tick.
            proposed["autoSummary"]=False
        if proposed["summaryBackend"] == "cloud":
            require(proposed["mode"] == "byok" and proposed["provider"] == "openrouter", "SUMMARY_PROVIDER",
                    "Tóm tắt cloud hiện cần BYOK OpenRouter; không tự chuyển nhà cung cấp.")
        if proposed["ocr"] == "cloud-gemini":
            require(proposed["provider"] == "openrouter" and proposed["cloudConsent"] and proposed["cloudOcrConsent"],
                    "IMAGE_CONSENT", "Xác nhận riêng việc gửi crop OCR tới OpenRouter và phí API trước khi bật.")
        if proposed["detector"] == "cloud-page":
            require(proposed["mode"] == "byok" and proposed["provider"] == "openrouter" and
                    proposed["cloudConsent"] and proposed["cloudPageOcrConsent"], "IMAGE_CONSENT",
                    "Detector cloud cần BYOK OpenRouter và xác nhận riêng gửi toàn bộ ảnh trang; không tự chuyển engine.")
        self.values = proposed
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(proposed, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        return proposed


class Secrets:
    def __init__(self, profile):
        self.service = "MangaLive:" + profile

    def _vault(self):
        import keyring
        from keyring.backends.Windows import WinVaultKeyring
        require(os.name == "nt", "VAULT", "Bản này yêu cầu kho bí mật Windows; không lưu key vào file.")
        return WinVaultKeyring()

    def set(self, provider, key):
        require(provider in ("deepseek", "gemini", "openrouter"))
        require(isinstance(key, str) and 8 <= len(key) <= 512)
        self._vault().set_password(self.service, provider, key)

    def get(self, provider):
        key = self._vault().get_password(self.service, provider)
        require(bool(key), "NO_KEY", "Chưa có API key. Thêm key trong Cài đặt; không tự chuyển nhà cung cấp.")
        return key

    def delete(self, provider):
        require(provider in ("deepseek", "gemini", "openrouter"))
        vault = self._vault()
        if vault.get_password(self.service, provider):
            vault.delete_password(self.service, provider)

    def status(self):
        try:
            vault = self._vault()
            return {p: bool(vault.get_password(self.service, p)) for p in ("deepseek", "gemini", "openrouter")}
        except Exception:
            return {"deepseek": False, "gemini": False, "openrouter":False, "vaultUnavailable": True}
