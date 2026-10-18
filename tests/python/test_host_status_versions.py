from types import SimpleNamespace
from manga_live.host import Host
from manga_live.ocr import LAYOUT_VERSION,PRESENTATION_VERSION,MangaEngine
from manga_live.prompts import PROMPT_VERSION
from manga_live.text_scope import SCOPE_VERSION
from manga_live.memory import SPEAKER_BINDING_VERSION
from manga_live.runtime_build import source_build
from manga_live.translation_schedule import SCHEDULE_VERSION


def test_status_exposes_actual_layout_prompt_and_ocr_without_loading_models(tmp_path,monkeypatch):
    host=Host.__new__(Host);host.models=tmp_path/"models"
    host.config=SimpleNamespace(values={"detector":"paddle","mode":"byok"})
    host.pipeline=SimpleNamespace(engine=SimpleNamespace(name=MangaEngine.name,model=None),
                                  detectors={"paddle":SimpleNamespace(model=None,presentation_version=PRESENTATION_VERSION)})
    host.vault=SimpleNamespace(status=lambda:{"openrouter":False})
    host.memory=SimpleNamespace(list_stories=lambda:[])
    host.translator=SimpleNamespace(local=SimpleNamespace(process=None),summary_usage=lambda:[])
    result=host.status()
    assert result["layoutVersion"]==LAYOUT_VERSION
    assert result["presentationVersion"]==PRESENTATION_VERSION
    assert result["scopeVersion"]==SCOPE_VERSION
    assert result["speakerBindingVersion"]==SPEAKER_BINDING_VERSION
    assert result["scheduleVersion"]==SCHEDULE_VERSION
    assert result["summaryVersion"]=="read-evidence-cloud-v1" and result["summaryUsage"]==[]
    assert result["promptVersion"]==PROMPT_VERSION and result["ocrVersion"]==MangaEngine.name
    assert result["runtimeBuild"]==source_build()
    # A persistent process must never relabel itself with later on-disk edits.
    monkeypatch.setattr("manga_live.runtime_build.source_build",lambda: "pkg-sha256:"+"0"*64)
    assert host.status()["runtimeBuild"]==result["runtimeBuild"]
    assert result["engineWarm"] is False and not any(result["models"].values())
