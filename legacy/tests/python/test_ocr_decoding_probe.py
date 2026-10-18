"""Comparator isolation, not evidence of real-manga accuracy."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS=Path(__file__).resolve().parents[2]/"scripts"
spec=importlib.util.spec_from_file_location("decoding_probe",SCRIPTS/"probe_ocr_decoding.py")
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


@pytest.mark.parametrize("raises",[False,True])
def test_one_ngram_field_changes_and_restores_even_on_error(raises):
    config=SimpleNamespace(no_repeat_ngram_size=3,num_beams=4,length_penalty=2,do_sample=False)
    original=vars(config).copy();recognizer=SimpleNamespace(model=SimpleNamespace(generation_config=config))
    try:
        with probe.ngram_limit(recognizer,0):
            assert config.no_repeat_ngram_size==0
            assert {k:v for k,v in vars(config).items() if k!="no_repeat_ngram_size"}=={
                k:v for k,v in original.items() if k!="no_repeat_ngram_size"}
            if raises:raise RuntimeError("authored failure")
    except RuntimeError:assert raises
    assert vars(config)==original


@pytest.mark.parametrize("value",[True,False,-1,2,300,"0"])
def test_unsupported_decoder_changes_are_rejected(value):
    with pytest.raises(ValueError):
        with probe.ngram_limit(None,value):pass


def test_output_outside_artifacts_rejected_before_model_load(monkeypatch):
    monkeypatch.setattr(probe,"MangaEngine",lambda *args:pytest.fail("No model before destination validation"))
    with pytest.raises(ValueError,match="gitignored artifacts"):
        # tmp_path may itself be inside artifacts when pytest is explicitly
        # sandboxed there. Use an unequivocally disallowed destination; the
        # validation must reject it without creating a file or loading ML.
        probe.run(SimpleNamespace(output=probe.ROOT/"docs"/"disallowed-ocr-report.json"))


def test_intentional_repeats_are_explicit_source_controls_not_cleaned_labels():
    if not Path("C:/Windows/Fonts/YuGothM.ttc").is_file():pytest.skip("Windows-authored font")
    cases={name:ref for name,_,ref in probe.decoding_controls()}
    assert len(cases)==19 and cases["blank"]==""
    assert cases["intentional-repeat"]=="いやいやいやいや！"
    assert cases["repeated-with-quotes"]=='「待って、待って、待って、待って！」'
    assert cases["multiline-opening-quote"].startswith("「") and "」" not in cases["multiline-opening-quote"]
    assert cases["six-dot-pause"]=="……待って。"
    assert cases["nine-dot-pause"]=="………本当に？"


def test_punctuation_classification_does_not_confuse_wordpiece_prefix_or_special_tokens():
    vocabulary={".":1,"##.":2,"、":3,"##！":4,"[SEP]":5,"いや":6,"##ねえ":7,"a!":8,"ー":9}
    assert probe.punctuation_ids(vocabulary)=={1,2,3,4}


def test_punctuation_guard_never_bans_a_lexical_repeat_or_changes_source_text():
    punctuation={1,2}
    assert probe.repeated_punctuation_next([9,9,9,9],punctuation)==()
    assert probe.repeated_punctuation_next([1,1,9,1,1],punctuation)==()
    assert probe.repeated_punctuation_next([1,1,1],punctuation)==(1,)
    assert probe.repeated_punctuation_next([1,1,1,2,1,1],punctuation)==(1,2)
    assert probe.repeated_punctuation_next([1,1],punctuation)==()


def test_punctuation_guard_matches_the_restricted_size_three_definition_exhaustively():
    from itertools import product
    punctuation={1,2}
    for size in range(1,7):
        for tokens in product((1,2,3),repeat=size):
            expected={triple[2] for triple in zip(tokens,tokens[1:],tokens[2:])
                      if tuple(triple[:2])==tokens[-2:] and all(t in punctuation for t in triple)}
            assert set(probe.repeated_punctuation_next(tokens,punctuation))==expected


def test_punctuation_tensor_mask_is_per_beam_and_does_not_mutate_caller_scores():
    torch=pytest.importorskip("torch")
    guard=probe.PunctuationRepeatGuard({".":1,"、":2,"いや":3,"[SEP]":4})
    # Two source images expanded to three beams each. No state is shared
    # between rows: each next-token mask follows only that row's history.
    histories=torch.tensor([[1,1,1,1],[3,3,3,3],[1,1,2,1],
                            [2,2,2,2],[3,1,1,1],[1,1,1,2]])
    scores=torch.arange(30,dtype=torch.float32).reshape(6,5)
    before=scores.clone();output=guard(histories,scores)
    assert torch.equal(scores,before) and output.data_ptr()!=scores.data_ptr()
    expected=torch.zeros_like(scores,dtype=torch.bool)
    expected[0,1]=True;expected[3,2]=True;expected[4,1]=True
    assert torch.equal(torch.isneginf(output),expected)
    assert torch.equal(output[~expected],before[~expected])


def test_guard_reuses_scores_when_there_is_no_punctuation_ban():
    torch=pytest.importorskip("torch")
    guard=probe.PunctuationRepeatGuard({".":1,"ねえ":2})
    histories=torch.tensor([[2,2,2,2],[1,1,2,2]])
    scores=torch.zeros((2,3),dtype=torch.float64)
    assert guard(histories,scores) is scores


def test_punctuation_guard_preserves_dtype_and_preexisting_model_masks():
    torch=pytest.importorskip("torch")
    guard=probe.PunctuationRepeatGuard({".":1,"いや":2})
    histories=torch.tensor([[1,1,1]])
    scores=torch.tensor([[-float("inf"),0.5,1.0]],dtype=torch.float16)
    output=guard(histories,scores)
    assert output.dtype==scores.dtype and output.device==scores.device
    assert output.tolist()==[[-float("inf"),-float("inf"),1.0]]
    assert scores.tolist()==[[-float("inf"),0.5,1.0]]


def test_punctuation_run_guard_does_not_ban_a_new_pause_after_a_lexical_token():
    assert probe.repeated_punctuation_next([1,1,1,9,1,1],{1},current_run=True)==()
    assert probe.repeated_punctuation_next([9,1,1,1],{1},current_run=True)==(1,)
    assert probe.repeated_punctuation_next([1,1,1,9,1,1],{1})==(1,)


def test_run_guard_keeps_independent_pauses_per_beam_without_a_mutable_history():
    torch=pytest.importorskip("torch")
    guard=probe.PunctuationRepeatGuard({".":1,"わ":2},current_run=True)
    scores=torch.zeros((2,3));before=scores.clone()
    output=guard(torch.tensor([[1,1,1,2,1,1],[2,2,2,1,1,1]]),scores)
    assert torch.equal(scores,before)
    assert output[0].tolist()==[0.0,0.0,0.0]
    assert output[1].tolist()==[0.0,-float("inf"),0.0]


def test_decoder_probe_preserves_batch_positions_and_never_loads_for_blank_input(monkeypatch):
    monkeypatch.setattr(probe,"blank_crop",lambda image:image=="blank")
    engine=probe.DecoderProbe("unused-model",4,"punctuation-only");calls=[]
    def load():calls.append("load");engine.model="local-recognizer"
    monkeypatch.setattr(engine,"load",load)
    def decode(model,images,variant):
        assert model=="local-recognizer" and variant=="punctuation-only"
        calls.append(images);return ["decoded-"+image for image in images]
    monkeypatch.setattr(probe,"decode_many_variant",decode)
    assert engine.recognize_many([])==[]
    assert engine.recognize_many(["blank","blank"])==["",""] and calls==[]
    assert engine.recognize_many(["a","blank","b"])==["decoded-a","","decoded-b"]
    assert calls==["load",["a","b"]]
    assert engine.recognize("blank")=="" and len(calls)==2
    assert not engine.details["production_default"]


def test_decoder_probe_rejects_changed_cardinality_instead_of_silently_dropping_regions(monkeypatch):
    monkeypatch.setattr(probe,"blank_crop",lambda image:False)
    engine=probe.DecoderProbe("unused-model",4,"punctuation-runs")
    monkeypatch.setattr(engine,"load",lambda:None)
    monkeypatch.setattr(probe,"decode_many_variant",lambda *args:["only-one"])
    with pytest.raises(ValueError,match="cardinality"):engine.recognize_many(["a","b"])


def test_decoder_probe_rejects_unrecognized_policy_before_loading_models():
    with pytest.raises(ValueError,match="Unsupported candidate"):
        probe.DecoderProbe("unused-model",4,"unknown")


@pytest.mark.parametrize("variant,extra",[("punctuation-only",{}),("punctuation-one",{"length_penalty":1.0}),
    ("punctuation-mid",{"length_penalty":1.5})])
def test_length_penalty_comparator_changes_only_the_call_argument_and_keeps_batch_order(variant,extra):
    from contextlib import nullcontext
    from PIL import Image
    calls=[]
    class Tensor:
        def to(self,device):assert device=="cpu";return self
        def cpu(self):return self
    def processor(images,**kwargs):
        assert kwargs=={"return_tensors":"pt"}
        assert [image.getpixel((0,0)) for image in images]==[(76,76,76),(150,150,150)]
        return SimpleNamespace(pixel_values=Tensor())
    config=SimpleNamespace(no_repeat_ngram_size=3,length_penalty=2.0,num_beams=4)
    def generate(pixels,**kwargs):calls.append(kwargs);return Tensor()
    def decode(tokens,**kwargs):assert kwargs=={"skip_special_tokens":True};return [" a "," b "]
    recognizer=SimpleNamespace(processor=processor,
        model=SimpleNamespace(device="cpu",generate=generate,generation_config=config),
        tokenizer=SimpleNamespace(get_vocab=lambda:{".":1,"a":2},batch_decode=decode),
        _torch=SimpleNamespace(inference_mode=nullcontext),_post_process=str.strip)
    before=vars(config).copy()
    images=[Image.new("RGB",(3,3),(255,0,0)),Image.new("RGB",(3,3),(0,255,0))]
    assert probe.decode_many_variant(recognizer,images,variant)==["a","b"]
    guard=calls[0].pop("logits_processor")
    assert len(guard)==1 and isinstance(guard[0],probe.PunctuationRepeatGuard)
    assert not guard[0].current_run
    assert calls==[{"max_length":300,"no_repeat_ngram_size":0,**extra}]
    assert vars(config)==before


@pytest.mark.parametrize("case,assert_variant",[("one-crop",None),(None,"punctuation-only")])
def test_full_page_comparator_never_silently_ignores_crop_only_flags(monkeypatch,case,assert_variant):
    monkeypatch.setattr(probe,"DecoderProbe",lambda *args:pytest.fail("Reject ignored flags before creating an engine"))
    args=SimpleNamespace(output=probe.ROOT/"artifacts"/"unused-page-probe.json",
        folder="must-not-read",pages=True,punctuation_only=True,threads=4,
        case=case,assert_variant=assert_variant)
    with pytest.raises(ValueError,match="crop-only flags"):
        probe.run(args)
