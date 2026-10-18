"""The external OCR48 probe must not become a production loader/score oracle."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import benchmark_mit48 as probe


def test_only_named_definitions_are_selected_not_wrapper_imports_or_demo():
    source = "import unreviewed\nprint('must not run')\nclass Wrapper: pass\ndef kept(): return 3\n"
    tree = probe.select_definitions(source, ("kept",))
    assert [node.name for node in tree.body] == ["kept"]
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
    namespace = {}
    exec(compile(tree, "test-only", "exec"), namespace)
    assert namespace["kept"]() == 3


@pytest.mark.parametrize("source", ["def other(): pass", "def kept(): pass\ndef kept(): pass"])
def test_missing_or_duplicate_definition_fails_closed(source):
    with pytest.raises(ValueError, match="definition"):
        probe.select_definitions(source, ("kept",))


def test_wrong_source_hash_is_rejected_before_any_compilation():
    with pytest.raises(ValueError, match="source hash"):
        probe.checked_source(probe.MODEL_SOURCE, b"print('unreviewed')")


def test_decoding_preserves_quotes_ellipsis_expressive_spaces_and_caps():
    dictionary = ["<PAD>", "<S>", "</S>", "<SP>", "「", "…", "I", "ー", "」"]
    assert probe.decode_tokens([1, 4, 6, 3, 3, 5, 7, 8, 2, 6], dictionary) == "「I  …ー」"
    assert probe.decode_tokens([2], dictionary) == ""
    with pytest.raises(ValueError, match="token"):
        probe.decode_tokens([True], dictionary)
    with pytest.raises(ValueError, match="token"):
        probe.decode_tokens([999], dictionary)
    with pytest.raises(ValueError, match="token"):
        probe.decode_tokens([2, 999], dictionary)


def test_low_confidence_line_is_retained_separately_from_upstream_acceptance():
    row = probe.prediction_record([3, 2], .01, ["<PAD>", "<S>", "</S>", "本"])
    assert row["raw_text"] == "本"
    assert row["upstream_threshold_accepted"] is False
    assert row["score"] == .01
    assert row["terminated"] is True
    assert row["erasure_authority"] is False
    truncated = probe.prediction_record([3], .9, ["<PAD>", "<S>", "</S>", "本"])
    assert truncated["terminated"] is False
    assert truncated["raw_text"] == "本", "Never silently drop truncated evidence"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -.01, 1.1, True])
def test_invalid_confidence_is_not_used_as_correctness_probability(score):
    with pytest.raises(ValueError, match="score"):
        probe.prediction_record([2], score, ["<PAD>", "<S>", "</S>"])


@pytest.mark.parametrize("loader", ["copy", "mmap-meta"])
def test_memory_gate_precedes_importing_torch_or_loading_assets(monkeypatch, loader):
    monkeypatch.setattr(probe, "physical_memory", lambda: {"available_physical_bytes": 500 * 1024**2})
    monkeypatch.setattr(probe, "validate_assets", lambda *_: pytest.fail("must not load assets"))
    with pytest.raises(RuntimeError, match="RAM"):
        probe.Mit48Recognizer(loader=loader).load()


def test_missing_assets_never_fetch_during_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "download", lambda *_: pytest.fail("no inference download"))
    with pytest.raises(ValueError, match="assets"):
        probe.validate_assets(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("restricted_load_fails", [False, True])
def test_checkpoint_load_is_cpu_restricted_strict_and_has_no_unsafe_retry(tmp_path, monkeypatch,
                                                                       restricted_load_fails):
    (tmp_path / "alphabet-all-v7.txt").write_text("<PAD>\n<S>\n</S>\n本\n", encoding="utf-8")
    monkeypatch.setattr(probe, "MODEL_PATH", tmp_path)
    monkeypatch.setattr(probe, "require_memory", lambda: {})
    monkeypatch.setattr(probe, "validate_assets", lambda: None)
    calls = []
    class Tensor:
        pass
    class Model:
        def __init__(self, dictionary, length):
            assert dictionary[3] == "本" and length == 768
        def load_state_dict(self, state, *, strict):
            assert strict is True and isinstance(state["weight"], Tensor)
        def eval(self):
            return self
    def load(path, **kwargs):
        calls.append(kwargs)
        if restricted_load_fails:
            raise RuntimeError("restricted loading rejected")
        return {"weight": Tensor()}
    fake_torch = SimpleNamespace(set_num_threads=lambda _: None, load=load, Tensor=Tensor)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(probe, "model_namespace", lambda _: {"OCR": Model})
    recognizer = probe.Mit48Recognizer()
    if restricted_load_fails:
        with pytest.raises(RuntimeError, match="restricted loading rejected"):
            recognizer.load()
        assert recognizer.model is None
    else:
        recognizer.load()
        assert isinstance(recognizer.model, Model)
    assert calls == [{"map_location": "cpu", "weights_only": True}]


def install_assignment_runtime(tmp_path, monkeypatch, *, mismatch=None):
    """Third-party Torch/checkpoint boundary, without importing its heavy runtime."""
    from contextlib import contextmanager
    (tmp_path / "alphabet-all-v7.txt").write_text("<PAD>\n<S>\n</S>\n本\n", encoding="utf-8")
    monkeypatch.setattr(probe, "MODEL_PATH", tmp_path)
    monkeypatch.setattr(probe, "require_memory", lambda: {})
    monkeypatch.setattr(probe, "validate_assets", lambda: None)
    calls, context = [], {"meta": False}

    class Tensor:
        def __init__(self, value=1, *, meta=False, dtype="float32", shape=(2,), storage=1):
            self.value, self.is_meta, self.dtype, self.shape = value, meta, dtype, shape
            self.layout = "strided"
            self.device = SimpleNamespace(type="meta" if meta else "cpu")
            self.storage = storage
        def stride(self): return (1,)
        def storage_offset(self): return 0
        def untyped_storage(self): return SimpleNamespace(data_ptr=lambda: self.storage)

    class Model:
        def __init__(self, dictionary, length):
            assert context["meta"], "The efficient route must not allocate initialized weights"
            self.embd = SimpleNamespace(weight=Tensor(meta=True))
            self.pred = SimpleNamespace(weight=self.embd.weight)
            self.scale = Tensor(meta=True)
            self.extra = Tensor(meta=True) if mismatch == "unregistered_meta" else None
        def state_dict(self):
            return {"embd.weight": self.embd.weight, "pred.weight": self.pred.weight, "scale": self.scale}
        def load_state_dict(self, state, *, strict, assign):
            calls.append((strict, assign))
            self.embd.weight, self.pred.weight = state["embd.weight"], state["pred.weight"]
            self.scale = state["scale"]
        def parameters(self): return iter([self.embd.weight, self.pred.weight])
        def buffers(self): return iter([self.scale])
        def modules(self): return iter([self, self.embd, self.pred])
        def eval(self): return self

    @contextmanager
    def device(name):
        assert name == "meta"
        context["meta"] = True
        try: yield
        finally: context["meta"] = False

    def load(path, **kwargs):
        calls.append(kwargs)
        if mismatch == "restricted_load": raise RuntimeError("restricted loading rejected")
        state = {"embd.weight": Tensor(), "pred.weight": Tensor(), "scale": Tensor()}
        if mismatch == "dtype": state["scale"].dtype = "float64"
        if mismatch == "shape": state["scale"].shape = (3,)
        if mismatch == "stride": state["scale"].stride = lambda: (2,)
        if mismatch == "missing_buffer": del state["scale"]
        if mismatch == "meta_buffer": state["scale"] = Tensor(meta=True)
        if mismatch == "tie": state["pred.weight"] = Tensor(value=2, storage=2)
        return state

    fake_torch = SimpleNamespace(set_num_threads=lambda _: None, load=load, Tensor=Tensor,
                                 device=device, strided="strided",
                                 equal=lambda left, right: left.value == right.value)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(probe, "model_namespace", lambda _: {"OCR": Model})
    return calls, Model


def test_mmap_meta_load_materializes_buffers_and_restores_tied_embedding(tmp_path, monkeypatch):
    calls, model_type = install_assignment_runtime(tmp_path, monkeypatch)
    recognizer = probe.Mit48Recognizer(loader="mmap-meta")
    recognizer.load()
    assert isinstance(recognizer.model, model_type)
    assert recognizer.model.pred.weight is recognizer.model.embd.weight
    assert not recognizer.model.scale.is_meta
    assert calls == [{"map_location": "cpu", "weights_only": True, "mmap": True}, (True, True)]


@pytest.mark.parametrize("mismatch", ["dtype", "shape", "stride", "missing_buffer", "meta_buffer", "tie",
                                      "unregistered_meta"])
def test_mmap_meta_rejects_changed_compute_or_unmaterialized_state(tmp_path, monkeypatch, mismatch):
    install_assignment_runtime(tmp_path, monkeypatch, mismatch=mismatch)
    recognizer = probe.Mit48Recognizer(loader="mmap-meta")
    with pytest.raises(ValueError, match="checkpoint|tensor|tie"):
        recognizer.load()
    assert recognizer.model is None


def test_mmap_failure_never_retries_an_unsafe_or_copy_loader(tmp_path, monkeypatch):
    calls, _ = install_assignment_runtime(tmp_path, monkeypatch, mismatch="restricted_load")
    recognizer = probe.Mit48Recognizer(loader="mmap-meta")
    with pytest.raises(RuntimeError, match="restricted loading rejected"):
        recognizer.load()
    assert recognizer.model is None
    assert calls == [{"map_location": "cpu", "weights_only": True, "mmap": True}]


def test_load_only_report_cannot_be_mistaken_for_an_ocr_score(tmp_path, monkeypatch):
    import json
    install_assignment_runtime(tmp_path, monkeypatch)
    output = tmp_path / "load-only.json"
    # The output-path boundary normally requires ignored private artifacts.
    import compare_page_reports
    monkeypatch.setattr(compare_page_reports, "private_json_path", lambda value, **_: Path(value))
    probe.run_load_only(SimpleNamespace(checkout="unused", beam="tensor", threads=2,
                                       loader="mmap-meta", output=str(output)))
    report = json.loads(output.read_text())
    assert report["kind"] == "load-only" and report["model_loaded"] is True
    assert report["loader"] == "mmap-meta"
    assert report["fresh_inference"] is False
    assert report["production_default"] is False
    assert "aggregate" not in report and "exact" not in report
    assert report["process_memory"]["scope"] == "load-only process including imports and recognizer; no detector or source images"


def test_line_input_does_not_silently_promote_a_union_bbox():
    with pytest.raises(ValueError, match="source members"):
        probe.proposal_units({"regions": [{"id": "a", "bbox": [0, 0, 40, 150]}]})
    members = [{"polygon": [[10, 0], [20, 0], [20, 50], [10, 50]], "score": .8}]
    units = probe.proposal_units({"regions": [{"id": "a", "sourceMembers": members,
                                              "readerExcluded": True}]})
    assert len(units) == 1
    assert units[0]["members"] == members
    assert units[0]["readerExcluded"] is True


def test_proposal_units_reject_duplicate_region_ids_and_unbounded_members():
    member = {"polygon": [[0, 0], [10, 0], [10, 30], [0, 30]], "score": .7}
    with pytest.raises(ValueError):
        probe.proposal_units({"regions": [{"id": "a", "sourceMembers": [member]}] * 2})
    with pytest.raises(ValueError):
        probe.proposal_units({"regions": [{"id": "a", "sourceMembers": [member] * 513}]})


def test_geometry_audit_preserves_failed_denominator_without_loading_ocr(tmp_path, monkeypatch):
    import json
    import numpy as np
    from PIL import Image
    members = [{"polygon": "ok", "score": .9}, {"polygon": "oversize", "score": .5}]
    units = {"page": [{"id": "source", "readerExcluded": False, "members": members}]}
    output = tmp_path / "geometry.json"
    pages = [({"page_id": "page"}, Image.new("RGB", (30, 30)), [])]
    monkeypatch.setattr(probe, "proposal_inputs", lambda _: (output, {}, pages, units, "fingerprint", {}))
    monkeypatch.setattr(probe, "geometry_namespace", lambda _: {})
    monkeypatch.setattr(probe.Mit48Recognizer, "load", lambda _: pytest.fail("no model in geometry audit"))
    def rectify(_image, polygon, _geometry):
        if polygon == "oversize":
            raise ValueError("oversize_line")
        return np.zeros((48, 30, 3), dtype=np.uint8), "h"
    monkeypatch.setattr(probe, "rectify_line", rectify)
    probe.run_geometry(SimpleNamespace(checkout="unused"))
    report = json.loads(output.read_text())
    assert report["aggregate"] == {"members": 2, "rectified": 1, "adapter_review": 1}
    assert report["fresh_inference"] is False
    assert report["model_loaded"] is False
    assert "exact" not in report["aggregate"]


def test_fragment_order_keeps_upper_column_before_drifted_lower_fragment():
    from copy import deepcopy
    def line(index, x, y, text):
        return {"region_id": "unit", "member_index": index, "raw_text": text,
                "direction": "v", "status": "recognized",
                "source": {"polygon": [[x, y], [x+20, y], [x+20, y+70], [x, y+70]], "score": .8}}
    # The lower piece is two pixels farther right, but belongs after the upper
    # piece. Source text includes meaningful punctuation/spacing unchanged.
    lines = [line(0, 82, 90, "後  …」"), line(1, 80, 0, "「先"), line(2, 20, 0, "左")]
    before = deepcopy(lines)
    ordered = probe.order_recorded_lines(lines, fragment_precedence=True)
    assert [row["member_index"] for row in ordered] == [1, 0, 2]
    assert "".join(row["raw_text"] for row in ordered) == "「先後  …」左"
    assert lines == before


def recorded_line_case():
    from copy import deepcopy
    from PIL import Image
    from benchmark_pages import assign_to_labels
    def member(x, y):
        return {"polygon": [[x, y], [x+20, y], [x+20, y+70], [x, y+70]], "score": .8}
    members = [member(82, 90), member(80, 0), member(20, 0)]
    lines = [{"region_id": "unit", "member_index": i, "source": deepcopy(source),
              "status": "recognized", "direction": "v", "raw_text": text, "elapsed_ms": 20,
              "erasure_authority": False} for i, (source, text) in enumerate(zip(members, ["後", "先", "左"]))]
    region = {"id": "unit", "bbox": [20, 0, 82, 160], "order": 0, "ja": "後先左"}
    labels = [{"bubble_id": "b1", "bbox": {"x": 0, "y": 0, "w": 120, "h": 180},
               "ja_ocr_truth": "先後左"}]
    aligned, unmatched = assign_to_labels(labels, [region])
    recorded = {"version": probe.VERSION, "commit": probe.COMMIT, "source_sha256": probe.SOURCES,
                "complete": True, "fresh_inference": True, "cloud": False,
                "input_fingerprint_sha256": "fixture", "beam": "tensor", "loader": "copy",
                "pages": [{"page": "page", "regions": [region], "lines": lines,
                           "aligned": aligned, "unmatched_prediction_ids": unmatched}]}
    proposals = {"input_fingerprint_sha256": "fixture", "pages": [{"page": "page", "regions": [
        {**region, "sourceMembers": members, "readerExcluded": False}]}]}
    pages = [({"page_id": "page"}, Image.new("RGB", (120, 180)), labels)]
    return recorded, proposals, pages


def test_order_replay_validates_sources_and_never_runs_recognition(monkeypatch):
    from copy import deepcopy
    monkeypatch.setattr(probe.Mit48Recognizer, "load", lambda _: pytest.fail("no replay inference"))
    recorded, proposals, pages = recorded_line_case()
    lines = recorded["pages"][0]["lines"]
    before = deepcopy((recorded, proposals))
    result = probe.replay_line_order(recorded, proposals, pages, "fixture")
    assert result["aggregate"]["exact"] == 1
    assert result["pages"][0]["regions"][0]["member_order"] == [1, 0, 2]
    assert result["pages"][0]["lines"] == lines
    assert result["fresh_inference"] is False and result["production_default"] is False
    assert result["pages"][0]["regions"][0]["erasure_authority"] is False
    assert (recorded, proposals) == before


@pytest.mark.parametrize("change", ["source", "duplicate", "excluded", "missing", "partial", "region_text",
                                    "foreign_owner", "art_authority", "out_of_bounds", "changed_label"])
def test_order_replay_rejects_changed_or_incomplete_evidence(change):
    recorded, proposals, pages = recorded_line_case()
    page = recorded["pages"][0]
    if change == "source": page["lines"][0]["source"]["score"] = .4
    elif change == "duplicate": page["lines"][1] = page["lines"][0]
    elif change == "excluded": proposals["pages"][0]["regions"][0]["readerExcluded"] = True
    elif change == "missing": page["lines"].pop()
    elif change == "partial": recorded["complete"] = False
    elif change == "region_text": page["regions"][0]["ja"] = "changed"
    elif change == "foreign_owner": page["lines"][0]["region_id"] = "foreign"
    elif change == "art_authority": page["lines"][0]["erasure_authority"] = True
    elif change == "out_of_bounds":
        from PIL import Image
        pages[0] = (pages[0][0], Image.new("RGB", (90, 180)), pages[0][2])
    elif change == "changed_label": pages[0][2][0]["ja_ocr_truth"] = "changed"
    with pytest.raises(ValueError):
        probe.replay_line_order(recorded, proposals, pages, "fixture")


def test_horizontal_fragment_order_and_legacy_policy_are_separate():
    def line(index, x, y, direction, text):
        return {"region_id": "unit", "member_index": index, "raw_text": text, "direction": direction,
                "status": "recognized", "source": {
                    "polygon": [[x, y], [x+70, y], [x+70, y+20], [x, y+20]], "score": .8}}
    lines = [line(0, 90, 8, "h", "right"), line(1, 0, 10, "h", "left"), line(2, 0, 80, "h", "next")]
    assert [r["member_index"] for r in probe.order_recorded_lines(lines)] == [0, 1, 2]
    assert [r["member_index"] for r in probe.order_recorded_lines(lines, fragment_precedence=True)] == [1, 0, 2]
