"""Reviewed text-only cloud candidates; no network or implicit fallback.

Capabilities checked 2026-10-14. Prices and availability are deliberately not
cached here: the bounded benchmark verifies the live catalogue before charging.
Source: docs/cloud-model-research-20261014.md. Candidate != quality approval.
"""
from copy import deepcopy

CATALOG_VERSION="cloud-candidates-20261014"
OPENROUTER_DEFAULT="deepseek/deepseek-v4.1-flash"
CANDIDATES=(
    {"provider":"openrouter","id":OPENROUTER_DEFAULT,"label":"DeepSeek V4.1 Flash",
     "note":"Mặc định beta tạm thời · non-thinking; có pilot cũ, cần kiểm lại prompt mới."},
    {"provider":"openrouter","id":"google/gemini-3.5-flash-lite","label":"Gemini 3.5 Flash-Lite",
     "note":"Đối chứng độ trễ · thinking minimal vẫn có thể tính token suy luận."},
    {"provider":"openrouter","id":"qwen/qwen3.8-flash","label":"Qwen3.8 Flash",
     "note":"Ứng viên tiết kiệm · non-thinking; chưa xếp hạng chất lượng manga."},
    {"provider":"openrouter","id":"anthropic/claude-haiku-5.5","label":"Claude Haiku 5.5",
     "note":"Ứng viên mới · không gửi sampling parameters; cần benchmark thực tế."},
    {"provider":"openrouter","id":"google/gemini-3.8-flash","label":"Gemini 3.8 Flash",
     "note":"Đối chứng chất lượng · reasoning low, giá tham chiếu cao hơn Lite; không tự bật."},
    {"provider":"deepseek","id":"deepseek-flash","label":"DeepSeek Flash · trực tiếp",
     "note":"Tắt thinking; key OpenRouter không dùng cho API DeepSeek trực tiếp."},
    {"provider":"gemini","id":"gemini-3.5-flash-lite","label":"Gemini 3.5 Flash-Lite · trực tiếp",
     "note":"Thinking minimal; dùng key Google riêng, kiểm điều khoản trước khi phát hành."},
    {"provider":"gemini","id":"gemini-3.8-flash","label":"Gemini 3.8 Flash · trực tiếp",
     "note":"Thinking low, giá tham chiếu cao hơn Lite; không tự bật."},
)


def model_choices():
    return [dict(model) for model in CANDIDATES]


def gemini_thinking(model):
    if model.startswith(("gemini-3.5-flash-lite","gemini-3.1-flash-lite")):
        return {"thinkingLevel":"minimal","includeThoughts":False}
    if model.startswith("gemini-3.8-flash"):
        return {"thinkingLevel":"low","includeThoughts":False}
    if model.startswith("gemini-2.5-flash-lite"):
        return {"thinkingBudget":0,"includeThoughts":False}
    return None  # Unknown custom model: do not invent a supported control.


def openrouter_request(model,prompt,schema,max_tokens=1600):
    body={"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,
        "response_format":{"type":"json_object"},
        "provider":{"data_collection":"deny","sort":"latency","require_parameters":True}}
    known=any(choice["provider"]=="openrouter" and choice["id"]==model for choice in CANDIDATES)
    if known:
        strict_schema=deepcopy(schema)
        # Known strict backends need every declared root property required.
        # Empty terms is valid; it must never force invented entities.
        strict_schema["required"]=list(strict_schema["properties"])
        body["response_format"]={"type":"json_schema","json_schema":{
            "name":"manga_translation","strict":True,"schema":strict_schema}}
        body["reasoning"]={"enabled":False}
    if model.startswith(("google/gemini-3.5-flash-lite","google/gemini-3.1-flash-lite")):
        body["reasoning"]={"effort":"minimal","exclude":True}
    elif model.startswith("google/gemini-3.8-flash"):
        body["reasoning"]={"effort":"low","exclude":True}
    if not model.startswith("anthropic/claude-haiku-5.5"):
        body["temperature"]=0.2
    # No model list, tools, web search, auto-router or paid fallback.
    return body
