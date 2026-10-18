"""Canonical render_docx rasterization with explicit Word API conversion fallback.

Windows runtime has no bundled LibreOffice. Do not alter the managed renderer
or use the user's desktop LibreOffice. Convert only the report in an own hidden
Word instance, then run the canonical rasterizer with bundled Poppler.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DEPS=Path("C:/Users/Huy/.cache/codex-runtimes/codex-primary-runtime/dependencies")
SKILL=Path("C:/Users/Huy/.codex/plugins/cache/openai-primary-runtime/documents/26.1011.11113/skills/documents")
SOURCE=ROOT/"deliverables/Live translation Bao cao MVP.docx"
OUTPUT=Path(tempfile.gettempdir())/"mangalive-report-qa"
spec=importlib.util.spec_from_file_location("render_docx",SKILL/"render_docx.py")
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
poppler=next((DEPS/"native/poppler").rglob("pdftoppm.exe")).parent
os.environ["PATH"]=str(poppler)+os.pathsep+os.environ.get("PATH","")


def word_convert(doc_path,user_profile,convert_tmp_dir,stem,verbose=False):
    pdf=Path(convert_tmp_dir)/(stem+".pdf")
    result=subprocess.run([str(DEPS/"native/powershell/pwsh.exe"),"-NoProfile","-File",
        str(ROOT/"scripts/render_report_word.ps1"),"-InputDocx",str(doc_path),"-OutputPdf",str(pdf)],
        capture_output=True,text=True,timeout=90)
    if result.returncode or not pdf.exists():raise RuntimeError(result.stdout+result.stderr)
    return str(pdf),"Word API conversion fallback; bundled Poppler rasterization"


renderer.convert_to_pdf=word_convert
dpi=renderer.calc_dpi_via_ooxml_docx(str(SOURCE),1600,2000)
pages=renderer.rasterize(str(SOURCE),str(OUTPUT),dpi,False,True)
print("Renderer: canonical render_docx rasterizer with Word conversion fallback")
print("Pages:",len(pages))
for page in pages:print(page)
