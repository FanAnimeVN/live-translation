class AppError(Exception):
    """A deliberately safe, user-visible error, never raw provider payloads."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


INCOMPLETE_GENERATION = "Model dừng trước khi hoàn tất bản dịch. Lỗi giới hạn đầu ra không có nghĩa vùng chọn quá lớn; nguyên bản được giữ lại."


def require(condition, code="INVALID", message="Dữ liệu yêu cầu không hợp lệ."):
    if not condition:
        raise AppError(code, message)
