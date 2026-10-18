"""Native Transformers 5 Paddle manga comparator, not a production engine.

Explicit fetch/setup are separate from inference. No model-repository Python
is fetched or executed. Official pinned wheels install to artifacts only;
the production .venv and companion packaging remain unchanged.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"),str(ROOT / "scripts")]
from benchmark_hayai_nova import offline_guard, checked_texts, run as run_benchmark
from manga_live.ocr import blank_crop
from provision import download, verify

MODEL_REPO = "jzhang533/PaddleOCR-VL-For-Manga"
MODEL_REVISION = "1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8"
MODEL_PATH = ROOT / "artifacts/comparator-models/paddle-vl-manga"
RUNTIME_PATH = ROOT / "artifacts/comparator-runtime/paddle-vl-native5"
WHEEL_PATH = ROOT / "artifacts/comparator-runtime/wheels"
MODEL_FILES = {
    "README.md":{"bytes":5964,"gitBlob":"7be6da448fccfdb3debbe429678b4fda93d5695e"},
    "config.json":{"bytes":1987,"gitBlob":"ee281b31a715dfea078af83e51c6d4dbb6062d74"},
    "generation_config.json":{"bytes":133,"gitBlob":"c56c62aa758d85c4ee56c3869a8fd13e65ccd31a"},
    "preprocessor_config.json":{"bytes":687,"gitBlob":"1f0535ab954e18bfc28be5d34377e6433184a8f2"},
    "special_tokens_map.json":{"bytes":1152,"gitBlob":"3c4aec2f502327373e3524be6ac37ff9070dec8b"},
    "chat_template.jinja":{"bytes":1566,"gitBlob":"3583ca3e6e518229f24c2d3bf9c9ce3d9646b5d7"},
    "tokenizer_config.json":{"bytes":185545,"gitBlob":"efcdc0f49f20f08866beabaccd68f172cf34bce6"},
    "tokenizer.json":{"bytes":11187679,"sha256":"f90f04fd8e5eb6dfa380f37d10c87392de8438dccb6768a2486b5a96ee76dba6"},
    "model.safetensors":{"bytes":1917255968,"sha256":"71fcee0e3618582d4c8acc705242aa79b471b6134e7023bf3820642ba638b602"},
}
RUNTIME_WHEELS = {
    "transformers-5.0.0-py3-none-any.whl":{
        "bytes":10142091,"sha256":"587086f249ce64c817213cf36afdb318d087f790723e9b3d4500b97832afd52d",
        "url":"https://files.pythonhosted.org/packages/52/f3/ac976fa8e305c9e49772527e09fbdc27cc6831b8a2f6b6063406626be5dd/transformers-5.0.0-py3-none-any.whl"},
    "huggingface_hub-1.3.0-py3-none-any.whl":{
        "bytes":533092,"sha256":"763f450169bb05ea3867990e9d3ba9464eb617b874791301dc81be2c6ffb0bf5",
        "url":"https://files.pythonhosted.org/packages/b1/5b/c5fde1f56b1f072b3028ec5413f3f5bf472c5891ebb34589cddb1689609f/huggingface_hub-1.3.0-py3-none-any.whl"},
}
IMAGE_TOKEN = "<|IMAGE_PLACEHOLDER|>"
IMAGE_WRAPPER = "<|IMAGE_START|>"+IMAGE_TOKEN+"<|IMAGE_END|>"
EXPECTED_PROMPT = "<|begin_of_sentence|>User: "+IMAGE_WRAPPER+"OCR:\nAssistant: "
TOKEN_IDS = {IMAGE_TOKEN:100295,"<|IMAGE_START|>":101305,"<|IMAGE_END|>":101306}
# Exact released surplus, NOT the native loader's broad ignore regexes.
# On the reviewed image OCR route, positional interpolation bypasses packing;
# return_pooler_output=False bypasses the attention pooling head. See the
# pinned branch/call trace in docs/paddle-vl-native-adapter-review-20261014.md.
# This excludes neither normal position_embedding nor the OCR projector.
LEGACY_UNUSED_TENSORS = {
    "visual.vision_model.embeddings.packing_position_embedding.weight":(32768,1152),
    "visual.vision_model.head.attention.in_proj_bias":(3456,),
    "visual.vision_model.head.attention.in_proj_weight":(3456,1152),
    "visual.vision_model.head.attention.out_proj.bias":(1152,),
    "visual.vision_model.head.attention.out_proj.weight":(1152,1152),
    "visual.vision_model.head.layernorm.bias":(1152,),
    "visual.vision_model.head.layernorm.weight":(1152,),
    "visual.vision_model.head.mlp.fc1.bias":(4304,),
    "visual.vision_model.head.mlp.fc1.weight":(4304,1152),
    "visual.vision_model.head.mlp.fc2.bias":(1152,),
    "visual.vision_model.head.mlp.fc2.weight":(1152,4304),
    "visual.vision_model.head.probe":(1,1,1152),
}


def fetch_model():
    for filename,spec in MODEL_FILES.items():
        download(f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{filename}",MODEL_PATH / filename,spec)


def setup_runtime():
    for filename,spec in RUNTIME_WHEELS.items():
        download(spec["url"],WHEEL_PATH / filename,spec)
    # --no-index/--no-deps prevent a resolver from changing either env or
    # fetching mutable extra packages. All needed base libraries stay local.
    subprocess.run([sys.executable,"-m","pip","install","--no-index","--no-deps",
        "--no-cache-dir","--disable-pip-version-check","--target",str(RUNTIME_PATH),
        *[str(WHEEL_PATH / filename) for filename in RUNTIME_WHEELS]],check=True)


def validate_model(path,require_weights=True):
    for filename,spec in MODEL_FILES.items():
        if filename == "model.safetensors" and not require_weights:continue
        if not verify(path / filename,spec):
            raise ValueError("Missing/mismatched pinned Paddle manga files; use explicit --fetch-model")


def activate_runtime():
    if any(name in sys.modules for name in ("transformers","huggingface_hub")):
        raise ValueError("Use a fresh comparator process; do not mix production and native5 imports")
    for filename,spec in RUNTIME_WHEELS.items():
        if not verify(WHEEL_PATH / filename,spec):
            raise ValueError("Missing/mismatched runtime wheel; use explicit --setup-runtime")
    if not (RUNTIME_PATH / "transformers/__init__.py").is_file():
        raise ValueError("Missing isolated native5 runtime; use explicit --setup-runtime")
    sys.path.insert(0,str(RUNTIME_PATH))


def checked_loading_info(info):
    if any(info.get(key) for key in ("missing_keys","unexpected_keys","mismatched_keys","error_msgs")):
        raise ValueError("Native checkpoint load is incomplete/mismatched; no random weights accepted")


def physical_memory():
    if os.name != "nt":return None
    import ctypes
    from ctypes import wintypes
    class Status(ctypes.Structure):
        _fields_=[("dwLength",wintypes.DWORD),("dwMemoryLoad",wintypes.DWORD)]+[
            (name,ctypes.c_ulonglong) for name in ("ullTotalPhys","ullAvailPhys","ullTotalPageFile",
            "ullAvailPageFile","ullTotalVirtual","ullAvailVirtual","ullAvailExtendedVirtual")]
    status=Status();status.dwLength=ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):return None
    return {"total_physical_bytes":status.ullTotalPhys,"available_physical_bytes":status.ullAvailPhys}


def native_runtime():
    activate_runtime()
    os.environ.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_ENABLE_PARALLEL_LOADING="false")
    import transformers
    import huggingface_hub
    for module,version in ((transformers,"5.0.0"),(huggingface_hub,"1.3.0")):
        if module.__version__ != version or not Path(module.__file__).resolve().is_relative_to(RUNTIME_PATH):
            raise ValueError("Comparator imported an unreviewed/shared runtime")
    return transformers


def image_processor_kwargs(metadata):
    # Exact released model preprocessing, not a lower-pixel speed setting.
    expected={"min_pixels":147384,"max_pixels":2822400,"patch_size":14,
              "merge_size":2,"temporal_patch_size":1,"resample":3}
    if any(metadata.get(key) != value for key,value in expected.items()):
        raise ValueError("Unreviewed Paddle image processor metadata")
    keys=("do_convert_rgb","do_normalize","do_rescale","do_resize",
          "image_mean","image_std","rescale_factor",*expected)
    return {key:metadata[key] for key in keys}


def checked_prompt(processor):
    messages=[{"role":"user","content":[{"type":"image"},{"type":"text","text":"OCR:"}]}]
    prompt=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,
                                          image_token=IMAGE_WRAPPER)
    if prompt != EXPECTED_PROMPT:
        raise ValueError("Native chat prompt differs from the pinned legacy template")
    return prompt


def token_settings(metadata,special):
    def content(value):
        return value["content"] if isinstance(value,dict) else value
    settings={key:content(value) for key,value in special.items() if key.endswith("_token")}
    settings["additional_special_tokens"]=metadata["additional_special_tokens"]
    settings.update(image_token=IMAGE_TOKEN,model_max_length=131072)
    return settings


def decode_new_tokens(tokenizer,sequences,prompt_length):
    if sequences.ndim != 2 or sequences.shape[0] != 1 or not 0 < prompt_length < sequences.shape[1]:
        raise ValueError("Invalid native generation sequence/prompt boundary")
    # Never decode/echo the input OCR instruction or image token wrappers.
    return checked_texts(tokenizer.batch_decode(sequences[:,prompt_length:],
        skip_special_tokens=True,clean_up_tokenization_spaces=False),1)[0]


def native_components(transformers):
    config=transformers.PaddleOCRVLConfig.from_pretrained(str(MODEL_PATH),local_files_only=True)
    config.auto_map={};config.vision_config.auto_map={}
    if (config.image_token_id != 100295 or config.vision_start_token_id != 101305 or
            config.text_config.hidden_size != 1024 or config.text_config.num_hidden_layers != 18 or
            config.text_config.head_dim != 128 or config.text_config.rope_parameters.get("mrope_section") != [16,24,24]):
        raise ValueError("Legacy config conversion differs from the reviewed checkpoint")
    metadata=json.loads((MODEL_PATH / "tokenizer_config.json").read_text(encoding="utf-8"))
    special=json.loads((MODEL_PATH / "special_tokens_map.json").read_text(encoding="utf-8"))
    tokenizer=transformers.PreTrainedTokenizerFast(tokenizer_file=str(MODEL_PATH / "tokenizer.json"),
                                                  **token_settings(metadata,special))
    if any(tokenizer.convert_tokens_to_ids(token) != expected for token,expected in TOKEN_IDS.items()):
        raise ValueError("Native tokenizer image IDs mismatch checkpoint")
    original=json.loads((MODEL_PATH / "tokenizer.json").read_text(encoding="utf-8"))
    loaded=json.loads(tokenizer.backend_tokenizer.to_str())
    if any(original.get(key) != loaded.get(key) for key in ("model","normalizer","pre_tokenizer","post_processor","decoder")):
        raise ValueError("Native tokenizer changed serialized text processing")
    metadata=json.loads((MODEL_PATH / "preprocessor_config.json").read_text(encoding="utf-8"))
    image_processor=transformers.PaddleOCRVLImageProcessor(**image_processor_kwargs(metadata))
    template=(MODEL_PATH / "chat_template.jinja").read_text(encoding="utf-8")
    processor=transformers.PaddleOCRVLProcessor(image_processor=image_processor,tokenizer=tokenizer,chat_template=template)
    return config,tokenizer,processor,checked_prompt(processor)


def expected_grid(width,height):
    factor=28
    if height < factor:width=round(width*factor/height);height=factor
    if width < factor:height=round(height*factor/width);width=factor
    if max(height,width)/min(height,width) > 200:raise ValueError("Unsupported source aspect ratio")
    h,w=round(height/factor)*factor,round(width/factor)*factor
    if h*w > 2822400:
        ratio=math.sqrt(height*width/2822400)
        h,w=math.floor(height/ratio/factor)*factor,math.floor(width/ratio/factor)*factor
    elif h*w < 147384:
        ratio=math.sqrt(147384/(height*width))
        h,w=math.ceil(height*ratio/factor)*factor,math.ceil(width*ratio/factor)*factor
    return [1,h//14,w//14]


def reference_pixel_recipe(image):
    """Independent image-only source-recipe check, not legacy runtime parity.

    Pinned image_processing.py lines 354-413: bicubic RGB, float64 rescale
    then FP32 normalization, row-major 14x14 patches. Use HWC indexing here
    rather than the native implementation's temporal/channel-first transpose.
    No downloaded source is imported/executed and no model weights are used.
    """
    import numpy as np
    from PIL import Image
    grid=expected_grid(*image.size)
    _,gh,gw=grid
    pixels=np.asarray(image.convert("RGB").resize((gw*14,gh*14),Image.Resampling.BICUBIC))
    pixels=(pixels.astype(np.float64)*(1/255)).astype(np.float32)
    pixels=(pixels-np.float32(.5))/np.float32(.5)
    patches=pixels.reshape(gh,14,gw,14,3).transpose(0,2,4,1,3).reshape(gh*gw,3,14,14)
    return patches,grid


def check_reference_pixels(image,inputs):
    import numpy as np
    reference,grid=reference_pixel_recipe(image)
    actual=np.asarray(inputs["pixel_values"])
    if (actual.dtype != np.float32 or actual.shape != reference.shape or
            inputs["image_grid_thw"][0].tolist() != grid or not np.isfinite(actual).all()):
        raise ValueError("Native pixel recipe dtype/shape/grid/finite check failed")
    difference=float(np.max(np.abs(actual-reference)))
    if difference > 1e-7:raise ValueError("Native pixel recipe differs from the independent source recipe")
    return {"max_absolute_difference":difference,"recipe_equal_within_tolerance":True,"tolerance":1e-7}


def pixel_controls():
    """Authored asymmetric/color/boundary inputs, generated only in RAM."""
    import numpy as np
    from PIL import Image
    for name,size in (("rgb-one-pixel",(1,1)),("rgb-height-three",(11,3)),
        ("rgb-asymmetric",(53,79)),("rgb-narrow",(10,100)),("rgb-wide",(100,10)),
        ("rgb-near-min",(384,384)),("rgb-at-max",(1680,1680)),("rgb-above-max",(1800,1600))):
        w,h=size
        array=np.empty((h,w,3),dtype=np.uint8)
        array[:,:,0]=(np.arange(w)*17%256)[None,:]
        array[:,:,1]=(np.arange(h)*31%256)[:,None]
        array[:,:,2]=(np.arange(w)[None,:]*7+np.arange(h)[:,None]*13+255)%256
        yield name,Image.fromarray(array)


def native_checkpoint_key(key):
    """Released official prefix conversion, not an arbitrary key rename.

    https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py
    """
    if key.startswith("visual."):return "model.visual."+key[len("visual."):]
    if key.startswith("mlp_AR."):return "model.projector."+key[len("mlp_AR."):]
    if key.startswith("model.") and not key.startswith(("model.visual.","model.projector.","model.language_model.")):
        return "model.language_model."+key[len("model."):]
    return key


def compare_checkpoint_shapes(raw,expected):
    mapped={};collisions=[]
    for key,shape in raw.items():
        target=native_checkpoint_key(key)
        if target in mapped:collisions.append(target)
        mapped[target]=shape
    return {"missing":sorted(set(expected)-set(mapped)),"unexpected":sorted(set(mapped)-set(expected)),
        "mismatched":[{"key":key,"checkpoint":mapped[key],"native":expected[key]}
            for key in sorted(set(expected)&set(mapped)) if list(mapped[key]) != list(expected[key])],
        "collisions":sorted(set(collisions))}


def review_checkpoint_inventory(raw,dtypes,expected):
    """Keep exhaustive raw diagnostics; permit only reviewed unused BF16 keys."""
    comparison=compare_checkpoint_shapes(raw,expected)
    reviewed=[];invalid=[];unreviewed=[]
    for key,shape in sorted(raw.items()):
        target=native_checkpoint_key(key)
        if target not in comparison["unexpected"]:continue
        allowed=LEGACY_UNUSED_TENSORS.get(key)
        if allowed is None:
            unreviewed.append(target);continue
        row={"raw_key":key,"native_key":target,"shape":list(shape),"dtype":dtypes.get(key)}
        if list(shape) != list(allowed) or dtypes.get(key) != "BF16":
            invalid.append({**row,"expected_shape":list(allowed),"expected_dtype":"BF16"})
        else:reviewed.append(row)
    missing_unused=sorted(set(LEGACY_UNUSED_TENSORS)-set(raw))
    dtype_issues=[{"raw_key":key,"dtype":dtypes.get(key)} for key in sorted(raw) if dtypes.get(key) != "BF16"]
    gate=not any((comparison["missing"],comparison["mismatched"],comparison["collisions"],
                  unreviewed,invalid,missing_unused,dtype_issues))
    return {"comparison":comparison,"reviewed_unused":reviewed,"invalid_reviewed_unused":invalid,
        "missing_reviewed_unused":missing_unused,"unreviewed_unexpected":sorted(set(unreviewed)),
        "unexpected_dtypes":dtype_issues,"gate":gate}


def checkpoint_inventory(path,expected):
    """Safetensors shapes/dtypes only, never get_tensor/materialize values."""
    from safetensors import safe_open
    raw={};dtypes={}
    with safe_open(str(path / "model.safetensors"),framework="pt",device="cpu") as header:
        for key in header.keys():
            tensor=header.get_slice(key);raw[key]=tensor.get_shape();dtypes[key]=tensor.get_dtype()
    result=review_checkpoint_inventory(raw,dtypes,expected)
    return {**result,"raw_tensor_count":len(raw),"native_tensor_count":len(expected),
        "raw_parameter_elements":sum(math.prod(shape) for shape in raw.values()),
        "native_parameter_elements":sum(math.prod(shape) for shape in expected.values()),
        "checkpoint_dtypes":sorted(set(dtypes.values()))}


def native_expected_shapes(transformers,config,torch):
    if config.tie_word_embeddings is not False or config.text_config.vocab_size != 103424:
        raise ValueError("Do not tie/resize released independent padded vocabulary weights")
    # Architecture metadata only, not a multi-GB parameter allocation.
    with torch.device("meta"):
        model=transformers.PaddleOCRVLForConditionalGeneration(config)
    if any(parameter.device.type != "meta" for parameter in model.parameters()):
        raise ValueError("Architecture audit unexpectedly allocated real parameters")
    return {key:list(value.shape) for key,value in model.state_dict().items()}


def audit_checkpoint(args):
    from benchmark_hayai_nova import checked_destination
    from benchmark_paddle_rec import process_memory
    validate_model(MODEL_PATH)
    memory_before=physical_memory()
    transformers=native_runtime()
    config,_,_,_=native_components(transformers)
    import torch
    inventory=checkpoint_inventory(MODEL_PATH,native_expected_shapes(transformers,config,torch))
    report={"schema":2,"stage":"checkpoint key/shape audit against native META architecture; NO OCR inference",
        "model_revision":MODEL_REVISION,**inventory,
        "raw_to_native_shape_gate":not any(inventory["comparison"].values()),
        "reviewed_image_ocr_inventory_gate":inventory["gate"],"tie_word_embeddings":False,"model_vocab_size":103424,
        "memory_before":memory_before,"memory_after":physical_memory(),"process_memory":process_memory(),
        "weights_loaded":False,"cloud":False,"production_defaults_changed":False,
        "python_socket_connections_blocked":True,"socket_attempts":len(args.socket_attempts),
        "limitations":["Native meta construction and tensor-header checks do not prove actual checkpoint load or output parity.",
            "All raw surplus remains reported; only 12 exact unused image-route keys/shapes/BF16 are allowed."]}
    report["process_memory"]["scope"]="this metadata-only process; META model and safetensors header, no OCR weight values"
    destination=checked_destination(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"raw_to_native_shape_gate":report["raw_to_native_shape_gate"],
        "reviewed_image_ocr_inventory_gate":inventory["gate"],"comparison":inventory["comparison"],
        "weights_loaded":False,"socket_attempts":len(args.socket_attempts),"output":str(destination)}),flush=True)


def preflight(args):
    from benchmark_hayai_nova import checked_destination
    from benchmark_paddle_rec import process_memory
    from probe_ocr_resampling import controls
    validate_model(MODEL_PATH,require_weights=False)
    memory_before=physical_memory()
    _,tokenizer,processor,prompt=native_components(native_runtime())
    rows=[]
    for name,image,reference in controls():
        text_tokens=tokenizer.encode(reference,add_special_tokens=False)
        if tokenizer.decode(text_tokens,skip_special_tokens=False,clean_up_tokenization_spaces=False) != reference:
            raise ValueError("Native tokenizer loses authored Japanese punctuation/spacing")
        inputs=processor(images=[image.convert("RGB")],text=[prompt],return_tensors="np",
                         add_special_tokens=False,input_data_format="channels_last")
        grid=inputs["image_grid_thw"][0].tolist()
        if grid != expected_grid(*image.size):raise ValueError("Native image geometry differs from reference resize")
        tokens=inputs["input_ids"][0]
        image_count=int((tokens == 100295).sum())
        if (image_count != math.prod(grid)//4 or int((tokens == 101305).sum()) != 1 or
                int((tokens == 101306).sum()) != 1 or int((tokens == 100273).sum()) != 1):
            raise ValueError("Native processor inserted wrong image wrapper/token count")
        rows.append({"id":name,"source_size":list(image.size),"grid":grid,
            "image_tokens":image_count,"input_tokens":len(tokens),"pixel_shape":list(inputs["pixel_values"].shape),
            "authored_text_roundtrip_exact":True,**check_reference_pixels(image,inputs)})
    pixel_rows=[]
    for name,image in pixel_controls():
        inputs=processor(images=[image],text=[prompt],return_tensors="np",
                         add_special_tokens=False,input_data_format="channels_last")
        pixel_rows.append({"id":name,"source_size":list(image.size),
            "grid":inputs["image_grid_thw"][0].tolist(),**check_reference_pixels(image,inputs)})
    report={"schema":2,"stage":"native5 tokenizer/processor preflight; NO OCR inference",
        "model_revision":MODEL_REVISION,"transformers":"5.0.0","hub":"1.3.0",
        "serialized_tokenizer_core_unchanged":True,"legacy_prompt_exact":True,"rows":rows,"pixel_only_rows":pixel_rows,
        "independent_source_pixel_recipe_checked":True,"legacy_runtime_pixel_parity":False,
        "input_data_format":"channels_last",
        "mrope_section_preserved":[16,24,24],"authored_text_roundtrip_exact":True,
        "python_socket_connections_blocked":True,"socket_attempts":len(args.socket_attempts),
        "memory_before":memory_before,"memory_after":physical_memory(),"process_memory":process_memory(),
        "weights_loaded":False,"cloud":False,"production_defaults_changed":False,
        "limitations":["Source-recipe pixel checks under current PIL/NumPy do not prove legacy runtime/model parity or OCR quality.",
                        "System free memory is an instantaneous observation, not an OOM guarantee."]}
    report["process_memory"]["scope"]="this processor-only process; no detector or OCR weights"
    destination=checked_destination(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"authored_controls":len(rows),"pixel_checks":len(rows)+len(pixel_rows),
                      "weights_loaded":False,"socket_attempts":len(args.socket_attempts),
                      "output":str(destination)}),flush=True)


class PaddleVLRecognizer:
    def __init__(self,threads=4,kv_cache=False):
        if type(threads) is not int or not 1 <= threads <= 8 or type(kv_cache) is not bool:
            raise ValueError("Unsupported comparator resource budget")
        self.threads,self.kv_cache=threads,kv_cache
        self.model=None
        self.name=f"paddle-vl-manga/{MODEL_REVISION[:12]}-native5-fp32"
        self.details={"repo":MODEL_REPO,"revision":MODEL_REVISION,"dtype":"float32",
            "device":"CPU","batch_size":1,"max_new_tokens":300,"greedy":True,
            "use_cache":kv_cache,"production_default":False,"trust_remote_code":False,
            "transformers":"5.0.0","hub":"1.3.0","image_processor":"PaddleOCRVLImageProcessor-PIL",
            "input_data_format":"channels_last","processor_upstream_parity":False,"truncated_generations":0}

    def load(self):
        if self.model is not None:return
        validate_model(MODEL_PATH)
        memory=physical_memory()
        self.details["memory_before_load"]=memory
        if memory is not None and memory["available_physical_bytes"] < 7*1024**3:
            raise ValueError("Insufficient free RAM for the isolated FP32 comparator; need at least 7 GiB free")
        transformers=native_runtime()
        import torch
        torch.set_num_threads(self.threads)
        config,tokenizer,processor,prompt=native_components(transformers)
        # Native output_loading_info has broad legacy exceptions. Check the
        # raw inventory independently BEFORE any real parameter load, so an
        # unfamiliar head/packing key cannot be silently hidden by them.
        inventory=checkpoint_inventory(MODEL_PATH,native_expected_shapes(transformers,config,torch))
        if not inventory["gate"]:
            raise ValueError("Unreviewed/mismatched raw checkpoint inventory; no weight values loaded")
        self.details["raw_checkpoint_inventory"]=inventory
        model,info=transformers.PaddleOCRVLForConditionalGeneration.from_pretrained(str(MODEL_PATH),
            config=config,local_files_only=True,use_safetensors=True,dtype=torch.float32,
            attn_implementation="eager",output_loading_info=True)
        checked_loading_info(info)
        model.eval()
        if any(parameter.device.type != "cpu" or (parameter.is_floating_point() and parameter.dtype != torch.float32)
               for parameter in model.parameters()):
            raise ValueError("Native model loaded a non-CPU/non-FP32 parameter")
        self.prompt=prompt
        self.model,self.processor,self.tokenizer,self.torch=model,processor,tokenizer,torch
        self.details["loading_info_checked"]=True

    def recognize_many(self,images):
        results=[""]*len(images)
        valid=[(index,image) for index,image in enumerate(images) if not blank_crop(image)]
        if not valid:return results
        self.load()
        for index,image in valid:
            inputs=self.processor(images=[image.convert("RGB")],text=[self.prompt],
                                  return_tensors="pt",add_special_tokens=False,input_data_format="channels_last")
            if inputs["pixel_values"].device.type != "cpu" or inputs["pixel_values"].dtype != self.torch.float32:
                raise ValueError("Unexpected native pixel dtype/device")
            with self.torch.inference_mode():
                sequences=self.model.generate(**inputs,max_new_tokens=300,num_beams=1,do_sample=False,
                    use_cache=self.kv_cache,pad_token_id=0,eos_token_id=2)
            generated=sequences.shape[1]-inputs["input_ids"].shape[1]
            if generated >= 300 and int(sequences[0,-1]) != 2:
                self.details["truncated_generations"]+=1
            results[index]=decode_new_tokens(self.tokenizer,sequences,inputs["input_ids"].shape[1])
        return results

    def recognize(self,image):return self.recognize_many([image])[0]


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    source=parser.add_mutually_exclusive_group()
    source.add_argument("--authored",action="store_true")
    source.add_argument("--folder")
    source.add_argument("--preflight",action="store_true",help="Processor/tokenizer tests without OCR weights")
    source.add_argument("--audit-checkpoint",action="store_true",help="Compare tensor headers to native META shapes, no weight allocation")
    parser.add_argument("--fetch-model",action="store_true")
    parser.add_argument("--setup-runtime",action="store_true")
    parser.add_argument("--full-pages",action="store_true")
    parser.add_argument("--kv-cache",action="store_true",help="Experimental generation override, not original default")
    parser.add_argument("--threads",type=int,choices=range(1,9),default=4)
    parser.add_argument("--output",default=str(ROOT / "artifacts/paddle-vl-manga-authored-20261014.json"))
    args=parser.parse_args()
    if args.setup_runtime:setup_runtime()
    if args.fetch_model:fetch_model()
    if args.audit_checkpoint:
        with offline_guard() as attempts:
            args.socket_attempts=attempts
            audit_checkpoint(args)
            if attempts:raise RuntimeError("Checkpoint audit attempted network I/O; cannot pass offline gate")
    elif args.preflight:
        with offline_guard() as attempts:
            args.socket_attempts=attempts
            preflight(args)
            if attempts:raise RuntimeError("Preflight attempted network I/O; cannot pass offline gate")
    elif args.authored or args.folder:
        with offline_guard() as attempts:
            args.socket_attempts=attempts
            run_benchmark(args,engine_override=PaddleVLRecognizer(args.threads,args.kv_cache))
            if attempts:raise RuntimeError("Inference attempted network I/O; cannot pass offline gate")
    elif not (args.setup_runtime or args.fetch_model):
        parser.error("Select --authored/--folder/--preflight/--audit-checkpoint or explicit setup/fetch")
