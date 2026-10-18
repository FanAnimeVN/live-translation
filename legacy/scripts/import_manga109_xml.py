"""Import permissioned Manga109 XML text annotations into a private review pack.

The upstream XML is evidence, not accepted gold.  This adapter deliberately
does not copy images, infer speakers/roles, merge text, or change runtime OCR.
It verifies a caller-supplied page map and local image geometry, and emits only
bounded text/boxes under ``artifacts/``.  The output must still be independently
reviewed before ``build_ocr_training_manifest.py`` can consume it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark import audit, dataset_fingerprint, dataset_source  # noqa: E402

MAX_XML_BYTES = 64 * 1024 * 1024
MAX_PAGES = 20_000
MAX_TEXT_OBJECTS = 200_000
ID_RE = re.compile(r"^[0-9a-fA-F]{8}$")


def _flat(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value in (".", ".."):
        raise ValueError(f"Invalid {name}")
    if any(char in value for char in ("/", "\\", ":", "\x00")):
        raise ValueError(f"{name} must be a flat filename")
    return value


def _integer(attrs: dict[str, str], key: str) -> int:
    value = attrs.get(key)
    if not isinstance(value, str) or not re.fullmatch(r"\d+", value):
        raise ValueError(f"Invalid XML integer: {key}")
    number = int(value)
    if number < 0 or number > 100_000:
        raise ValueError(f"XML integer out of bounds: {key}")
    return number


def _bbox(element: ET.Element, width: int, height: int) -> dict[str, int]:
    attrs = element.attrib
    if not ID_RE.fullmatch(attrs.get("id", "")):
        raise ValueError("Manga109 object IDs must be eight hexadecimal characters")
    xmin, ymin = _integer(attrs, "xmin"), _integer(attrs, "ymin")
    xmax, ymax = _integer(attrs, "xmax"), _integer(attrs, "ymax")
    if not xmin < xmax or not ymin < ymax or xmax > width or ymax > height:
        raise ValueError("XML text geometry is outside the declared page")
    return {"x": xmin, "y": ymin, "w": xmax - xmin, "h": ymax - ymin}


def parse_xml(path: Path) -> dict:
    """Parse one XML volume without permitting DTD/entity expansion."""
    path = Path(path).resolve()
    if path.suffix.lower() != ".xml" or not path.is_file():
        raise ValueError("XML volume path is not a regular .xml file")
    if path.stat().st_size > MAX_XML_BYTES:
        raise ValueError("XML volume exceeds the bounded import size")
    raw = path.read_bytes()
    # ElementTree is used only after rejecting the two constructs that can
    # turn an untrusted XML file into an external-entity read.
    upper = raw[:4096].upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError("Malformed Manga109 XML") from error
    if root.tag != "book":
        raise ValueError("Expected <book> root")
    title = root.attrib.get("title", "")
    if not isinstance(title, str) or not title or len(title) > 300:
        raise ValueError("Missing or oversized Manga109 book title")
    pages = root.find("pages")
    if pages is None or len(pages) > MAX_PAGES:
        raise ValueError("Invalid Manga109 page collection")
    result_pages = {}
    text_objects = 0
    for page in pages.findall("page"):
        index = _integer(page.attrib, "index")
        width, height = _integer(page.attrib, "width"), _integer(page.attrib, "height")
        if width <= 0 or height <= 0 or index in result_pages:
            raise ValueError("Invalid or duplicate Manga109 page")
        rows = []
        for child in page:
            if child.tag != "text":
                continue
            text_objects += 1
            if text_objects > MAX_TEXT_OBJECTS:
                raise ValueError("Too many Manga109 text objects")
            content = "".join(child.itertext())
            if not content.strip() or len(content) > 3000:
                raise ValueError("Empty or oversized Manga109 text object")
            rows.append({"xml_id": child.attrib.get("id"), "bbox": _bbox(child, width, height),
                         "ja_candidate": content, "role": "unknown"})
        result_pages[index] = {"index": index, "width": width, "height": height, "texts": rows}
    return {"title": title, "pages": result_pages, "text_objects": text_objects}


def _map_rows(value: object) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValueError("Page map must be a nonempty JSON list")
    result = []
    seen = set()
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("Malformed page-map row")
        page_id = row.get("page_id")
        if not isinstance(page_id, str) or not page_id or page_id in seen:
            raise ValueError("Page map has missing or duplicate page_id")
        seen.add(page_id)
        xml_file = _flat(row.get("xml_file"), "xml_file")
        xml_index = row.get("xml_page_index")
        if type(xml_index) is not int or xml_index < 0 or xml_index > 100_000:
            raise ValueError("Invalid xml_page_index")
        result.append({"page_id": page_id, "xml_file": xml_file, "xml_page_index": xml_index})
    return result


def build_pack(folder: str, xml_dir: str, page_map: str, *, rights_confirmed: bool = False) -> dict:
    xml_root = Path(xml_dir).resolve(strict=True)
    if not xml_root.is_dir():
        raise ValueError("XML directory is not a directory")
    mapping = _map_rows(json.loads(Path(page_map).read_text(encoding="utf-8")))
    with dataset_source(argparse.Namespace(folder=folder, zip=None)) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    local = {page["page_id"]: (page, image, bubbles) for page, image, bubbles in pages}
    rows = []
    for mapped in mapping:
        if mapped["page_id"] not in local:
            raise ValueError("Page map references a page not eligible in the local dataset")
        xml_path = (xml_root / mapped["xml_file"]).resolve()
        if xml_path.parent != xml_root:
            raise ValueError("XML page escapes the selected directory")
        volume = parse_xml(xml_path)
        xml_page = volume["pages"].get(mapped["xml_page_index"])
        if xml_page is None:
            raise ValueError("Mapped XML page index does not exist")
        page, image, _bubbles = local[mapped["page_id"]]
        if (xml_page["width"], xml_page["height"]) != image.size:
            raise ValueError("XML page size does not match the local image")
        for order, item in enumerate(xml_page["texts"]):
            xml_id = item["xml_id"]
            if not isinstance(xml_id, str) or not ID_RE.fullmatch(xml_id):
                raise ValueError("Manga109 text object has invalid ID")
            rows.append({"page_id": mapped["page_id"], "xml_page_index": mapped["xml_page_index"],
                         "xml_file": mapped["xml_file"], "xml_id": xml_id,
                         "image_file": page["image_file"], "reviewed_bbox": item["bbox"],
                         "reviewed_ja": item["ja_candidate"], "reading_order": order,
                         "role": item["role"], "review_state": "unreviewed",
                         "reviewed_by": [], "evidence": ["manga109-xml"],
                         "source_bbox": None, "vi_reference": None,
                         "clean_background_gold": None})
    return {"schema": 1, "kind": "manga109-xml-reference-candidates",
            "source": "permissioned Manga109 XML; not independent gold",
            "dataset_fingerprint_sha256": fingerprint, "counts": counts,
            "audit": issues, "rights_confirmed": bool(rights_confirmed),
            "independent_human_review": False, "review_state": "unreviewed",
            "rows": rows,
            "limitations": [
                "XML annotations are candidates and do not replace the supplied benchmark labels.",
                "Independent Japanese/geometry/role review is required before training.",
                "No image bytes are copied; no Vietnamese or clean-background gold is created.",
                "This artifact cannot route runtime OCR or grant erasure/memory authority.",
            ]}


def output_path(value: str) -> Path:
    target = Path(value).resolve()
    artifacts = (ROOT / "artifacts").resolve()
    if artifacts not in target.parents or target.suffix != ".json" or target.exists():
        raise ValueError("Output must be a new JSON file below artifacts/")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--xml-dir", required=True)
    parser.add_argument("--page-map", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rights-confirmed", action="store_true")
    args = parser.parse_args()
    target = output_path(args.output)
    pack = build_pack(args.folder, args.xml_dir, args.page_map, rights_confirmed=args.rights_confirmed)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"created": True, "rows": len(pack["rows"]),
                      "fingerprint": pack["dataset_fingerprint_sha256"],
                      "independent_human_review": False, "images_written": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
