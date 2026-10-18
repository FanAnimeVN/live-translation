"""Native VL comparator contracts; no weights/cloud or native5 import."""
from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

SCRIPTS=Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location("paddle_vl_comparator",SCRIPTS / "benchmark_paddle_vl.py")
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def test_fetch_pins_only_data_not_custom_model_python(monkeypatch):
    calls=[]
    monkeypatch.setattr(probe,"download",lambda url,path,spec:calls.append((url,path,spec)))
    probe.fetch_model()
    assert len(calls)==9
    assert all(probe.MODEL_REVISION in url for url,_,_ in calls)
    assert all(path.suffix != ".py" for _,path,_ in calls)
    assert all(spec["bytes"] > 0 and (spec.get("sha256") or spec.get("gitBlob")) for _,_,spec in calls)


def test_runtime_install_is_hash_pinned_offline_and_target_only(monkeypatch):
    downloads=[];processes=[]
    monkeypatch.setattr(probe,"download",lambda url,path,spec:downloads.append((url,path,spec)))
    monkeypatch.setattr(probe.subprocess,"run",lambda argv,**kwargs:processes.append((argv,kwargs)))
    probe.setup_runtime()
    argv,kwargs=processes[0]
    assert kwargs=={"check":True}
    assert argv[:5]==[sys.executable,"-m","pip","install","--no-index"]
    assert "--no-deps" in argv and argv[argv.index("--target")+1]==str(probe.RUNTIME_PATH)
    assert len(downloads)==2 and all(spec.get("sha256") for _,_,spec in downloads)


@pytest.mark.parametrize("field",["missing_keys","unexpected_keys","mismatched_keys","error_msgs"])
def test_native_load_never_accepts_incomplete_weights(field):
    with pytest.raises(ValueError,match="incomplete/mismatched"):
        probe.checked_loading_info({field:["unreviewed-key"]})
    assert probe.checked_loading_info({field:[]}) is None


def processor_metadata():
    return {"min_pixels":147384,"max_pixels":2822400,"patch_size":14,"merge_size":2,
        "temporal_patch_size":1,"resample":3,"do_convert_rgb":True,"do_normalize":True,
        "do_rescale":True,"do_resize":True,"image_mean":[.5]*3,"image_std":[.5]*3,
        "rescale_factor":1/255,"size":{"min_pixels":147384,"max_pixels":2822400},
        "auto_map":{"AutoProcessor":"do-not-import.custom"}}


def test_legacy_processor_retains_released_budget_not_unreviewed_size_or_code():
    kwargs=probe.image_processor_kwargs(processor_metadata())
    assert "size" not in kwargs and "auto_map" not in kwargs
    assert kwargs["min_pixels"]==147384 and kwargs["max_pixels"]==2822400
    assert kwargs["temporal_patch_size"]==1
    with pytest.raises(ValueError,match="Unreviewed"):
        probe.image_processor_kwargs({**processor_metadata(),"min_pixels":3136})


def test_image_token_attribute_does_not_remove_legacy_prompt_wrappers():
    calls=[]
    class Processor:
        def apply_chat_template(self,messages,**kwargs):
            calls.append((messages,kwargs));return probe.EXPECTED_PROMPT
    assert probe.checked_prompt(Processor())==probe.EXPECTED_PROMPT
    assert calls[0][1]=={"tokenize":False,"add_generation_prompt":True,"image_token":probe.IMAGE_WRAPPER}
    assert calls[0][0][0]["content"]==[{"type":"image"},{"type":"text","text":"OCR:"}]
    bad=SimpleNamespace(apply_chat_template=lambda *a,**k:probe.EXPECTED_PROMPT.replace("<|IMAGE_START|>",""))
    with pytest.raises(ValueError,match="prompt differs"):probe.checked_prompt(bad)


def test_only_generated_tokens_decode_and_quotes_gaps_remain_raw():
    calls=[]
    class Tokenizer:
        def batch_decode(self,tokens,**kwargs):
            calls.append((tokens.tolist(),kwargs));return ['「わ … た … し？」']
    sequence=np.array([[101305,100295,101306,17,18,2]])
    assert probe.decode_new_tokens(Tokenizer(),sequence,3)=='「わ … た … し？」'
    assert calls==[([[17,18,2]],{"skip_special_tokens":True,"clean_up_tokenization_spaces":False})]


def test_native_checkpoint_prefix_conversion_does_not_remap_already_native_keys():
    for old,new in (("visual.vision_model.weight","model.visual.vision_model.weight"),
        ("mlp_AR.linear_1.weight","model.projector.linear_1.weight"),
        ("model.layers.0.norm.weight","model.language_model.layers.0.norm.weight"),
        ("lm_head.weight","lm_head.weight")):
        assert probe.native_checkpoint_key(old)==new
        assert probe.native_checkpoint_key(new)==new


def test_header_comparison_exposes_missing_mismatch_unused_and_alias_collision():
    result=probe.compare_checkpoint_shapes({"visual.weight":[2,3],"model.visual.weight":[2,4],
        "model.norm.weight":[3],"unused.weight":[1]},
        {"model.visual.weight":[2,3],"model.language_model.norm.weight":[3],"lm_head.weight":[4,5]})
    assert result=={"missing":["lm_head.weight"],"unexpected":["unused.weight"],
        "mismatched":[{"key":"model.visual.weight","checkpoint":[2,4],"native":[2,3]}],
        "collisions":["model.visual.weight"]}
    assert not any(probe.compare_checkpoint_shapes({"model.norm.weight":[3]},
        {"model.language_model.norm.weight":[3]}).values())


def checkpoint_fixture():
    raw={"model.norm.weight":[3],**{key:list(shape) for key,shape in probe.LEGACY_UNUSED_TENSORS.items()}}
    return raw,{key:"BF16" for key in raw},{"model.language_model.norm.weight":[3]}


def test_reviewed_unused_inventory_keeps_raw_surplus_visible_not_blanket_ignored():
    raw,dtypes,expected=checkpoint_fixture()
    result=probe.review_checkpoint_inventory(raw,dtypes,expected)
    assert result["gate"] is True
    assert len(probe.LEGACY_UNUSED_TENSORS)==len(result["reviewed_unused"])==12
    assert len(result["comparison"]["unexpected"])==12
    assert result["unreviewed_unexpected"]==result["invalid_reviewed_unused"]==[]
    assert result["unexpected_dtypes"]==[]
    assert sum(np.prod(row["shape"]) for row in result["reviewed_unused"])==52987088


@pytest.mark.parametrize("raw_key",[
    "visual.vision_model.embeddings.packing_position_embedding.weight",
    "visual.vision_model.head.attention.in_proj_bias",
    "visual.vision_model.head.attention.in_proj_weight",
    "visual.vision_model.head.attention.out_proj.bias",
    "visual.vision_model.head.attention.out_proj.weight",
    "visual.vision_model.head.layernorm.bias",
    "visual.vision_model.head.layernorm.weight",
    "visual.vision_model.head.mlp.fc1.bias",
    "visual.vision_model.head.mlp.fc1.weight",
    "visual.vision_model.head.mlp.fc2.bias",
    "visual.vision_model.head.mlp.fc2.weight",
    "visual.vision_model.head.probe",
])
@pytest.mark.parametrize("fault",["shape","dtype","missing"])
def test_each_reviewed_unused_tensor_still_requires_exact_shape_and_dtype(raw_key,fault):
    raw,dtypes,expected=checkpoint_fixture()
    if fault=="shape":raw[raw_key][0]+=1
    elif fault=="dtype":dtypes[raw_key]="F32"
    else:del raw[raw_key]
    result=probe.review_checkpoint_inventory(raw,dtypes,expected)
    assert result["gate"] is False
    if fault=="missing":assert result["missing_reviewed_unused"]==[raw_key]
    else:assert result["invalid_reviewed_unused"][0]["raw_key"]==raw_key
    assert raw_key not in {row["raw_key"] for row in result["reviewed_unused"]}


@pytest.mark.parametrize("fault",["missing","shape","collision","core_dtype","unknown_head","unknown_packing","absent_dtype"])
def test_legacy_allowlist_cannot_hide_core_or_similarly_named_unknown_tensors(fault):
    raw,dtypes,expected=checkpoint_fixture()
    if fault=="missing":del raw["model.norm.weight"]
    elif fault=="shape":raw["model.norm.weight"]=[4]
    elif fault=="collision":raw["model.language_model.norm.weight"]=[3];dtypes["model.language_model.norm.weight"]="BF16"
    elif fault=="core_dtype":dtypes["model.norm.weight"]="F32"
    elif fault=="absent_dtype":del dtypes["model.norm.weight"]
    else:
        key="visual.vision_model."+("head.unreviewed.weight" if fault=="unknown_head" else "embeddings.packing_position_embedding.other")
        raw[key]=[1];dtypes[key]="BF16"
    assert probe.review_checkpoint_inventory(raw,dtypes,expected)["gate"] is False


def test_raw_inventory_gate_runs_before_loading_weight_values(monkeypatch):
    monkeypatch.setattr(probe,"validate_model",lambda path:None)
    monkeypatch.setattr(probe,"physical_memory",lambda:{"available_physical_bytes":8*1024**3})
    model=SimpleNamespace(from_pretrained=lambda *a,**k:pytest.fail("reject header before weight allocation"))
    native=SimpleNamespace(PaddleOCRVLForConditionalGeneration=model)
    monkeypatch.setattr(probe,"native_runtime",lambda:native)
    monkeypatch.setattr(probe,"native_components",lambda runtime:(object(),None,None,probe.EXPECTED_PROMPT))
    monkeypatch.setitem(sys.modules,"torch",SimpleNamespace(set_num_threads=lambda threads:None))
    monkeypatch.setattr(probe,"native_expected_shapes",lambda *args:{"core":[3]})
    monkeypatch.setattr(probe,"checkpoint_inventory",lambda *args:{"gate":False})
    with pytest.raises(ValueError,match="raw checkpoint"):
        probe.PaddleVLRecognizer().load()


@pytest.mark.parametrize("shape,length",[((2,5),2),((1,5),0),((1,5),5),((5,),2)])
def test_invalid_native_generation_boundary_fails_not_source_echo(shape,length):
    with pytest.raises(ValueError,match="boundary"):
        probe.decode_new_tokens(None,np.zeros(shape,dtype=int),length)


def test_special_tokens_keep_placeholder_separate_from_image_wrapper():
    settings=probe.token_settings({"additional_special_tokens":[probe.IMAGE_TOKEN]},
        {"cls_token":{"content":"<|begin_of_sentence|>"},"pad_token":{"content":"<unk>"}})
    assert settings["image_token"]==probe.IMAGE_TOKEN and settings["cls_token"]=="<|begin_of_sentence|>"
    assert settings["additional_special_tokens"]==[probe.IMAGE_TOKEN]


@pytest.mark.parametrize("size,grid",[((240,90),[1,18,46]),((100,240),[1,44,18]),
    ((1400,1400),[1,100,100]),((3000,3000),[1,120,120]),((10,100),[1,88,10])])
def test_reference_processor_grid_is_bounded_and_keeps_axis_orientation(size,grid):
    assert probe.expected_grid(*size)==grid


@pytest.mark.parametrize("mode,size,color",[("RGB",(1,1),(0,128,255)),("L",(3,11),128)])
def test_reference_pixel_recipe_keeps_rgb_channels_and_exact_normalization(mode,size,color):
    image=Image.new(mode,size,color)
    pixels,grid=probe.reference_pixel_recipe(image)
    assert grid==probe.expected_grid(*size) and pixels.dtype==np.float32
    assert list(pixels.shape)==[np.prod(grid),3,14,14]
    channel_values=np.asarray(image.convert("RGB"))[0,0].astype(np.float64)/255
    channel_values=(channel_values.astype(np.float32)-np.float32(.5))/np.float32(.5)
    assert np.array_equal(pixels[0,:,0,0],channel_values)
    assert np.all(pixels==channel_values[None,:,None,None])


def test_reference_pixel_recipe_orders_patches_row_first_and_preserves_channel_order():
    array=np.zeros((392,392,3),dtype=np.uint8)
    array[:14,14:28,0]=255
    array[14:28,:14,2]=255
    pixels,grid=probe.reference_pixel_recipe(Image.fromarray(array))
    assert grid==[1,28,28]
    assert pixels[1,0,0,0]==1 and pixels[1,2,0,0]==-1
    assert pixels[28,2,0,0]==1 and pixels[28,0,0,0]==-1


def test_numeric_pixel_guard_detects_channel_swap_scale_or_patch_shuffle():
    image=Image.fromarray(np.arange(392*392*3,dtype=np.uint8).reshape(392,392,3))
    pixels,grid=probe.reference_pixel_recipe(image)
    info=probe.check_reference_pixels(image,{"pixel_values":pixels,"image_grid_thw":np.asarray([grid])})
    assert info["max_absolute_difference"]==0 and info["recipe_equal_within_tolerance"] is True
    for bad in (pixels[:,::-1].copy(),pixels*.5,pixels[::-1].copy()):
        with pytest.raises(ValueError,match="pixel recipe"):
            probe.check_reference_pixels(image,{"pixel_values":bad,"image_grid_thw":np.asarray([grid])})


def test_blank_input_never_loads_a_large_vl_model(monkeypatch):
    engine=probe.PaddleVLRecognizer()
    monkeypatch.setattr(engine,"load",lambda:pytest.fail("blank must not load model"))
    assert engine.recognize_many([Image.new("RGB",(240,90),"white")])==[""]


def test_generation_is_batch_one_bounded_and_does_not_retokensize_the_prompt(monkeypatch):
    engine=probe.PaddleVLRecognizer();calls=[];engine.prompt=probe.EXPECTED_PROMPT
    monkeypatch.setattr(probe,"blank_crop",lambda image:False)
    monkeypatch.setattr(engine,"load",lambda:None)
    class Processor:
        def __call__(self,**kwargs):
            assert kwargs["images"][0].mode=="RGB"
            assert kwargs["text"]==[probe.EXPECTED_PROMPT] and kwargs["add_special_tokens"] is False
            assert kwargs["input_data_format"]=="channels_last"
            return {"input_ids":np.array([[4,5,6]]),
                    "pixel_values":SimpleNamespace(device=SimpleNamespace(type="cpu"),dtype="fp32")}
    class Model:
        def generate(self,**kwargs):calls.append(kwargs);return np.array([[4,5,6,9,2]])
    engine.model=Model();engine.processor=Processor()
    engine.torch=SimpleNamespace(inference_mode=nullcontext,float32="fp32")
    engine.tokenizer=SimpleNamespace(batch_decode=lambda *a,**k:["待って！"])
    assert engine.recognize_many([Image.new("RGB",(4,4),"red")])==["待って！"]
    assert calls[0]["max_new_tokens"]==300 and calls[0]["num_beams"]==1
    assert calls[0]["do_sample"] is False and calls[0]["use_cache"] is False
    assert engine.details["truncated_generations"]==0


def test_weights_validated_before_native_runtime_activation(monkeypatch):
    def invalid(path):raise ValueError("bad checksum")
    monkeypatch.setattr(probe,"validate_model",invalid)
    monkeypatch.setattr(probe,"activate_runtime",lambda:pytest.fail("checksum first"))
    with pytest.raises(ValueError,match="checksum"):probe.PaddleVLRecognizer().load()


def test_large_fp32_comparator_refuses_insufficient_free_memory_before_native_import(monkeypatch):
    monkeypatch.setattr(probe,"validate_model",lambda path:None)
    monkeypatch.setattr(probe,"physical_memory",lambda:{"total_physical_bytes":16*1024**3,
        "available_physical_bytes":1600*1024**2})
    monkeypatch.setattr(probe,"activate_runtime",lambda:pytest.fail("do not load on low memory"))
    with pytest.raises(ValueError,match="free RAM"):
        probe.PaddleVLRecognizer().load()


@pytest.mark.parametrize("threads,cache",[(True,False),(0,False),(9,False),(4,1)])
def test_unbounded_resource_options_are_rejected(threads,cache):
    with pytest.raises(ValueError):probe.PaddleVLRecognizer(threads,cache)
