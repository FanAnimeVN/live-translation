import hashlib
import threading
import time
from pathlib import Path
from .errors import AppError, require
from .memory import digest, SPEAKER_BINDING_VERSION
from .ocr import (MangaEngine, PaddleDetector, OpenCvDetector, decode_image, polygon, recognize_regions,
                  partition_ocr_boxes, OCR_PARTITION_VERSION, OCR_COVERAGE_VERSION, LAYOUT_VERSION)
from .prompts import PROMPT_VERSION
from .validation import identifier, location, text, number
from .terminology import suggestions
from .render_cleanup import render_patch, MAX_JOB_PATCH_BYTES
from .expression import bind_expression
from .text_scope import SCOPE_VERSION, make_plan, route_regions, story_regions
from .translation_cache import batch_key, batch_payload, read_batch
from .translation_schedule import schedule_regions, SCHEDULE_VERSION
from .cloud_ocr import CloudPageDetector


class Pipeline:
    def __init__(self,memory,translator,config,models,first_batch_size=4):
        require(type(first_batch_size) is int and first_batch_size in (2,4),"BATCH")
        self.first_batch_size=first_batch_size
        self.memory,self.translator,self.config = memory,translator,config
        self.ocr = MangaEngine(Path(models)/"ocr",config.values["threads"])
        self.cloud_ocr = None
        self.detectors = {"paddle":PaddleDetector(Path(models)/"detector",config.values["threads"]),
                          "opencv":OpenCvDetector(),
                          "cloud-page":CloudPageDetector(config,getattr(translator,"vault",None))}

    @property
    def engine(self):
        if self.config.values.get("ocr") == "cloud-gemini":
            if self.cloud_ocr is None:
                from .cloud_ocr import CloudCropOcr
                self.cloud_ocr = CloudCropOcr(self.config, self.translator.vault)
            return self.cloud_ocr
        return self.ocr

    def region_batches(self,regions,partition_evidence=()):
        """Keep crop neighbours together where bounded request count permits."""
        yield from schedule_regions(regions,getattr(self,"first_batch_size",4),partition_evidence)

    def cache_context_matches(self,story,page_id,at,cached):
        # Only the actual group retrievals are dependencies. A generic story
        # fingerprint both misses older relevant names and evicts good pages
        # after unrelated profile edits. Legacy/incomplete evidence is a miss.
        dependencies=cached.get("contextDependencies")
        if not isinstance(dependencies,list):return False
        if story_regions(cached.get("regions",[])) and not dependencies:return False
        if any(not isinstance(d,dict) or not isinstance(d.get("text"),str) or
               not isinstance(d.get("entities"),list) or
               not all(isinstance(e,str) for e in d["entities"]) or
               not isinstance(d.get("fingerprint"),str) for d in dependencies):return False
        return all(self.memory.context(story,at,d["text"],page_id,d["entities"])["fingerprint"]==d["fingerprint"]
                   for d in dependencies)

    @property
    def source_version(self):
        detector=getattr(self,'detectors',{}).get(self.config.values['detector'])
        return getattr(detector,'source_version',LAYOUT_VERSION)

    def page_cache_key(self,story,page_id,at,image_hash,selection,*,source_version=None):
        # LAYOUT_VERSION binds source grouping/crops. A presentation-only
        # upgrade is NOT a translation dependency: accepted old surfaces keep
        # their provenance and do not require another paid request.
        # Scheduling is not a source/prompt change. Retain already accepted
        # pages instead of forcing a new paid translation on every reread.
        # Exact batch membership/context already keys partial checkpoints.
        source_version=source_version or (LAYOUT_VERSION if selection else self.source_version)
        return digest(["translation-dependencies-v2",source_version,OCR_PARTITION_VERSION,OCR_COVERAGE_VERSION,SCOPE_VERSION,SPEAKER_BINDING_VERSION,story,page_id,at,image_hash,selection,
                       self.config.values["detector"],self.engine.name,
                       self.translator.signature(),PROMPT_VERSION])

    def warmup(self,cancel):
        from PIL import Image
        start=time.perf_counter()
        require(not cancel.is_set(),"CANCELED")
        if self.config.values.get("ocr") == "cloud-gemini":
            self.engine.cancel=cancel;self.engine.authorize()
        detector=self.detectors[self.config.values["detector"]]
        # A page-proposal detector is paid/networked and must never be called
        # by warmup. It only validates the separately saved consent here.
        if hasattr(detector,"warmup"):
            detector.warmup()
        else:
            detector.detect(Image.new("RGB",(64,64),"white"))
        require(not cancel.is_set(),"CANCELED")
        if self.config.values.get("ocr") == "cloud-gemini": self.engine.cancel = cancel
        self.engine.load()
        if self.config.values["mode"]=="offline":self.translator.local.start(cancel)
        require(not cancel.is_set(),"CANCELED")
        return {"ready":True,"warmup_ms":(time.perf_counter()-start)*1000}

    def emit_render_patches(self,image,regions,revision,cancel,emit,budget):
        """Ephemeral native events only. Never return images to save_page/cache.

        Cached text still regenerates patches from the current RAM source.
        Flat balloons use their vector erasure masks, never this inpainting path.
        """
        if not self.config.values.get("artCleanup",True):return 0
        started=time.perf_counter()
        for region in regions:
            require(not cancel.is_set(),"CANCELED")
            if not region.get("vi") or region.get("scope",{}).get("action")=="defer":continue
            if budget[0]<=0:break
            try:patch=render_patch(image,region,cancel,max_bytes=budget[0])
            except Exception:
                # Optional rendering is isolated from the translation result.
                # Do not log source pixels/text or raw image-library errors.
                patch=None
            require(not cancel.is_set(),"CANCELED")
            if patch:
                budget[0]-=(len(patch["dataUrl"])-22)*3//4
                emit("render-patch",{"revision":revision,"width":image.width,"height":image.height,"patch":patch})
        return (time.perf_counter()-started)*1000

    def process(self,params,data,cancel,emit):
        start = time.perf_counter()
        story,page_id = identifier(params.get("storyId")),identifier(params.get("pageId"))
        at = location(params.get("at"))
        title,revision = text(params.get("title"),300),identifier(params.get("revision"))
        self.memory.ensure_story(story,title)
        context = self.memory.context(story,at)
        expected_version=context["version"]
        def publish(event,payload):
            # Serialise only the tiny publication boundary with reader edits,
            # not inference or cleanup. Never transact an external callback.
            with self.memory.at_version(story,expected_version):
                require(not cancel.is_set(),"CANCELED")
                emit(event,payload)
                require(self.memory.version(story)==expected_version,"STALE_CONTEXT",
                        "Ngữ cảnh vừa đổi; dịch lại trang để dùng lựa chọn mới.")
        image_hash = hashlib.sha256(data).hexdigest()
        source_version=LAYOUT_VERSION if params.get('selection') else self.source_version
        cache_key = self.page_cache_key(story,page_id,at,image_hash,params.get("selection"))
        cached = self.memory.cache_get(cache_key)
        if cached and not self.cache_context_matches(story,page_id,at,cached):cached=None
        if not cached and not params.get('selection'):
            # Only complete, context-valid accepted pages may survive a known
            # source-recipe upgrade. Never reuse partial OCR/batch checkpoints
            # across it or relabel old geometry as newly generated source.
            detector=getattr(self,'detectors',{}).get(self.config.values['detector'])
            for previous_version in getattr(detector,'accepted_source_versions',()):
                if previous_version==source_version:continue
                previous_key=self.page_cache_key(story,page_id,at,image_hash,None,source_version=previous_version)
                previous=self.memory.cache_get(previous_key)
                if (previous and previous.get('sourceVersion',LAYOUT_VERSION)==previous_version and
                        self.cache_context_matches(story,page_id,at,previous)):
                    cached=previous;break
        if cached:
            require(not cancel.is_set(),"CANCELED")
            with self.memory.at_version(story,expected_version):pass
            cleanup_ms=0
            if self.config.values.get("artCleanup",True) and any(r.get("overlay")=="label" for r in cached["regions"]):
                cleanup_ms=self.emit_render_patches(decode_image(data),cached["regions"],revision,cancel,publish,[MAX_JOB_PATCH_BYTES])
            elapsed=(time.perf_counter()-start)*1000
            result={**cached,"revision":revision,"cached":True,"contextVersion":context["version"],
                "sourceVersion":cached.get("sourceVersion",LAYOUT_VERSION),
                "presentationVersion":cached.get("presentationVersion",LAYOUT_VERSION),
                "sourceMetrics":cached["metrics"],"metrics":{"detector_ms":0,"ocr_ms":0,"context_ms":0,
                    "translation_ms":0,"input_tokens":0,"output_tokens":0,"reused_translation_groups":0,
                    "cleanup_ms":cleanup_ms,"cache_ms":elapsed,"total_ms":elapsed,"first_overlay_ms":elapsed}}
            publish("translated",result)
            # A failed cleanup/publication must not replace a valid older
            # page revision with an obsolete display's context.
            with self.memory.at_version(story,expected_version):
                require(not cancel.is_set(),"CANCELED")
                self.memory.save_page(story,page_id,at,revision,cached["regions"])
            return result
        # Persist OCR coverage independently of successful translation. A
        # network/key/model error must not throw away expensive completed OCR,
        # and a partial batch must not masquerade as a complete page.
        ocr_key=digest([OCR_COVERAGE_VERSION,source_version,OCR_PARTITION_VERSION,story,page_id,image_hash,params.get("selection"),self.config.values["detector"],self.engine.name])
        if self.config.values.get("ocr") == "cloud-gemini": self.engine.cancel = cancel
        ocr_cached=self.memory.cache_get(ocr_key)
        presentation_version=(ocr_cached.get("presentationVersion",LAYOUT_VERSION) if ocr_cached else
                              getattr(self.detectors[self.config.values["detector"]],"presentation_version",LAYOUT_VERSION))
        image = decode_image(data)
        selection = params.get("selection")
        if ocr_cached:
            regions=ocr_cached["layout"]
            crop_boxes=ocr_cached.get("ocrCropBoxes",{})
            partition_evidence=ocr_cached.get("partitionEvidence",[])
        elif selection:
            require(isinstance(selection,list) and len(selection)==4)
            x,y,w,h = [int(number(v,maximum=8000)) for v in selection]
            require(w>0 and h>0 and x+w <= image.width and y+h <= image.height)
            regions = [{"id":"r000","bbox":[x,y,w,h],"polygon":polygon([x,y,w,h]),
                        "overlay":"label","score":1,"type":"dialogue","order":0}]
            crop_boxes,partition_evidence={},[]
        else:
            publish("progress",{"stage":"detector","total":0})
            detector=self.detectors[self.config.values["detector"]]
            if callable(getattr(detector,'detect_plan',None)):
                regions,crop_boxes,partition_evidence=detector.detect_plan(image)
            else:
                regions=detector.detect(image)[:64]
                crop_boxes,partition_evidence=partition_ocr_boxes(image,regions)
        require(not cancel.is_set(),"CANCELED")
        recognized_by_id={r["id"]:r for r in ocr_cached["recognized"]} if ocr_cached else {}
        processed=set(ocr_cached["processed"]) if ocr_cached else set()
        def save_ocr_coverage():
            # Only source text/layout goes into the 24h bounded cache: no
            # image bytes, inferred speaker, translation or reader progress.
            self.memory.cache_put(ocr_key,story,at,{"layout":regions,"ocrCropBoxes":crop_boxes,
                "sourceVersion":source_version,
                "presentationVersion":presentation_version,
                "partitionEvidence":partition_evidence,
                "recognized":[recognized_by_id[r["id"]] for r in regions if r["id"] in recognized_by_id],
                "processed":[r["id"] for r in regions if r["id"] in processed]})
        if not ocr_cached:save_ocr_coverage()
        detector_ms = (time.perf_counter()-start)*1000
        publish("progress",{"stage":"ocr","total":len(regions)})
        metrics = {"detector_ms":detector_ms,"ocr_ms":0,"context_ms":0,
                   "translation_ms":0,"input_tokens":0,"output_tokens":0,"cleanup_ms":0,"reused_translation_groups":0}
        # Geometry only proposes external groups. A bounded OCR preview of
        # their visible headings is the evidence; density is never a skip rule.
        plan=make_plan(image,regions,image_hash)
        with self.memory.at_version(story,expected_version):
            speaker_bindings=self.memory.bind_speakers(story,page_id,at,
                [{**r,"scope":{"key":plan["keys"][r["id"]]}} for r in regions])
        preview=[r for r in regions if r["id"] in plan["seeds"] and r["id"] not in processed]
        if preview:
            ocr_start=time.perf_counter()
            seeds=recognize_regions(image,preview,self.engine,cancel,batch_size=self.config.values["ocrBatch"],
                                     crop_boxes=crop_boxes,partition_evidence=partition_evidence)
            require(not cancel.is_set(),"CANCELED")
            recognized_by_id.update({r["id"]:dict(r) for r in seeds})
            processed.update(r["id"] for r in preview);save_ocr_coverage()
            metrics["ocr_ms"]+=(time.perf_counter()-ocr_start)*1000
        output,term_suggestions,dependencies = [],[],[]
        patch_budget=[MAX_JOB_PATCH_BYTES]
        for batch in self.region_batches(regions,partition_evidence):
            require(not cancel.is_set(),"CANCELED")
            with self.memory.at_version(story,expected_version):pass
            ocr_start=time.perf_counter()
            pending=[r for r in batch if r["id"] not in processed]
            if pending:
                newly_recognized=recognize_regions(image,pending,self.engine,cancel,batch_size=self.config.values["ocrBatch"],
                                                   crop_boxes=crop_boxes,partition_evidence=partition_evidence)
                require(not cancel.is_set(),"CANCELED")
                recognized_by_id.update({r["id"]:dict(r) for r in newly_recognized})
                # Detection candidates skipped as blank are processed too;
                # they must not be OCRed again or turn into invented dialogue.
                processed.update(r["id"] for r in pending)
                save_ocr_coverage()
            recognized=route_regions([bind_expression(recognized_by_id[r["id"]]) for r in batch if r["id"] in recognized_by_id],
                plan,{},list(recognized_by_id.values()))
            metrics["ocr_ms"]+=(time.perf_counter()-ocr_start)*1000
            if not recognized:
                continue
            with self.memory.at_version(story,expected_version):
                for region in recognized:
                    region.update(speaker_bindings[region["id"]])
            publish("regions",{"regions":recognized,"revision":revision,"width":image.width,"height":image.height})
            active=[r for r in recognized if r["scope"]["action"]=="translate"]
            if not active:
                output.extend(recognized);continue
            context_start=time.perf_counter()
            entities={r.get(k,"unknown") for r in active for k in ("speaker","listener")}-{ "unknown" }
            source_text=" ".join(r["ja"] for r in active)
            with self.memory.at_version(story,expected_version):
                context=self.memory.context(story,at,source_text,page_id,entities)
            dependencies.append({"text":source_text,"entities":sorted(entities),"fingerprint":context["fingerprint"]})
            metrics["context_ms"]+=(time.perf_counter()-context_start)*1000
            with self.memory.at_version(story,expected_version):pass
            current_context={**context["data"],"recent_dialogue":[*context["data"].get("recent_dialogue",[]),*story_regions(output)[-4:]]}
            require(not cancel.is_set(),"CANCELED")
            publish("progress",{"stage":"translation","total":len(active),"mode":self.config.values.get("mode","offline")})
            group_key=batch_key(cache_key,active,current_context)
            checkpoint=read_batch(self.memory,group_key,active,current_context)
            if checkpoint:
                items=checkpoint["items"]
                measurement={"translation_ms":0,"usage":{},"terms":checkpoint["terms"]}
                metrics["reused_translation_groups"]+=1
            else:
                items,measurement = self.translator.translate(active,current_context,cancel)
            require(not cancel.is_set(),"CANCELED")
            metrics["translation_ms"] += measurement["translation_ms"]
            usage = measurement.get("usage",{})
            metrics["input_tokens"] += usage.get("prompt_tokens",usage.get("promptTokenCount",0))
            metrics["output_tokens"] += usage.get("completion_tokens",usage.get("candidatesTokenCount",0))
            by_id = {i["id"]:i for i in items}
            completed = [{**r,**by_id[r["id"]]} for r in active]
            output.extend({**r,**by_id.get(r["id"],{})} for r in recognized)
            trusted=story_regions(completed)
            trusted_ids={r["id"] for r in trusted}
            with self.memory.at_version(story,expected_version):
                self.memory.accept_terms(story,at,page_id,[term for term in measurement.get("terms",[])
                    if term.get("region_id") in trusted_ids])
                # Only this task's grounded proposals may advance its snapshot;
                # a later batch must not silently adopt an external reader edit.
                expected_version=self.memory.version(story)
                current_suggestions=suggestions(self.memory.context(story,at," ".join(r["ja"] for r in trusted))["data"],trusted)
            term_suggestions.extend(current_suggestions)
            metrics["cleanup_ms"]+=self.emit_render_patches(image,completed,revision,cancel,publish,patch_budget)
            publish("translated",{"regions":completed,"revision":revision,"width":image.width,"height":image.height,
                               "contextVersion":expected_version,"termSuggestions":current_suggestions})
            if "first_overlay_ms" not in metrics:
                metrics["first_overlay_ms"]=(time.perf_counter()-start)*1000
            if not checkpoint:
                accepted=batch_payload(active,current_context,items,measurement.get("terms",[]))
                if accepted:
                    # Save only after publication/cancel/context checks. Use
                    # the original generation key even if this task accepted
                    # new terms; never relabel old text with a new context.
                    with self.memory.at_version(story,expected_version):
                        require(not cancel.is_set(),"CANCELED")
                        self.memory.cache_put(group_key,story,at,accepted)
        metrics["total_ms"] = (time.perf_counter()-start)*1000
        result = {"regions":output,"revision":revision,"width":image.width,"height":image.height,
                  "sourceVersion":source_version,
                  "presentationVersion":presentation_version,
                  "scheduleVersion":SCHEDULE_VERSION,
                  "contextVersion":expected_version,"metrics":metrics,"cached":False,"termSuggestions":term_suggestions,
                  "contextDependencies":dependencies}
        require(not cancel.is_set(),"CANCELED")
        with self.memory.at_version(story,expected_version),self.memory.transaction():
            require(not cancel.is_set(),"CANCELED")
            self.memory.save_page(story,page_id,at,revision,output)
            self.memory.cache_put(cache_key,story,at,result)
        return result

    def retranslate(self,params,cancel):
        story,page_id = identifier(params.get("storyId")),identifier(params.get("pageId"))
        at = location(params.get("at"))
        region_id,ja = identifier(params.get("regionId")),text(params.get("ja"),700)
        revision=identifier(params.get("revision"))
        recover=params.get("recoverDeferred",False)
        require(type(recover) is bool,"SCOPE")
        expected_version=self.memory.version(story)
        with self.memory.at_version(story,expected_version):
            page=self.memory.page(story,page_id,revision)
            require(page["chapter"]==at["chapter"] and page["page"]==at["page"],"STALE")
            original=next((r for r in page["regions"] if r["id"]==region_id),None)
            require(original is not None,"STALE")
            require(original.get("scope",{}).get("action")!="defer" or recover,"SCOPE",
                    "Chữ phụ chưa được chọn dịch; nguyên bản vẫn được giữ lại.")
            speaker = self.memory.bind_speakers(story,page_id,at,page["regions"])[region_id]
            context = self.memory.context(story,at,ja,entities={speaker[k] for k in ("speaker","listener")}-{"unknown"})
            require(context["version"]==expected_version,"STALE_CONTEXT")
        updated=bind_expression({**original,"ja":ja,**speaker})
        if recover and original.get("scope",{}).get("action")=="defer":
            updated["scope"]={**original["scope"],"action":"translate","reason":"reader","memory":False}
        items,measurement=self.translator.translate([updated],context["data"],cancel)
        require(not cancel.is_set(),"CANCELED")
        corrected={**updated,**items[0]}
        with self.memory.at_version(story,context["version"]),self.memory.transaction():
            require(not cancel.is_set(),"CANCELED")
            self.memory.correct_region(story,page_id,at,revision,corrected)
            if story_regions([corrected]):self.memory.accept_terms(story,at,page_id,measurement.get("terms",[]))
        return {**items[0],"expression":corrected.get("expression"),"scope":corrected.get("scope")}
