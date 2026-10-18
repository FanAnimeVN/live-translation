# Manga109 XML annotation adapter

`scripts/import_manga109_xml.py` is a private, fail-closed bridge for a
permissioned Manga109/Manga109-s XML volume. Manga109 publishes one UTF-8 XML
file per volume, with page dimensions and text objects containing Japanese text
and rectangular geometry. The adapter does not download the dataset and does
not copy manga images.

## Inputs

- The user's local benchmark folder, including its unchanged
  `ground_truth_benchmark.json`.
- A directory containing XML volume files obtained under the applicable
  Manga109/Manga109-s terms.
- A JSON page map, for example:

```json
[
  {"page_id": "MN109-01", "xml_file": "SomeVolume.xml", "xml_page_index": 6}
]
```

The map is intentionally explicit: local page names cannot be guessed from an
XML title or ordinal. XML dimensions must exactly match the local image.

## Command

```powershell
.venv\Scripts\python.exe -B scripts/import_manga109_xml.py `
  --folder 'C:\path\to\private-dataset' `
  --xml-dir 'C:\path\to\permissioned\xml' `
  --page-map 'C:\path\to\page-map.json' `
  --output artifacts/private-manga109-candidates-YYYYMMDD.json
```

Add `--rights-confirmed` only after the caller has confirmed the applicable
licence. This flag records an attestation; it does not make the rows reviewed.

## Safety boundary

The result remains `unreviewed` and cannot replace the source benchmark, route
runtime OCR, enter story memory, or authorize erasure. A Japanese-capable
reviewer must verify text, box, reading order, role, difficulty and split; a
separate reviewer must supply Vietnamese meaning and clean-background/glyph-mask
references. Only then may the existing training-manifest validator accept a
train/validation/title-held-out split.
