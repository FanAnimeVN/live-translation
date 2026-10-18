"""Pipeline/native source plans with authored external detector/OCR replies."""
from copy import deepcopy
import io
import threading
from types import SimpleNamespace

from PIL import Image,ImageDraw

from manga_live.memory import Memory
from manga_live.ocr import PaddleDetector,polygon
from manga_live.pipeline import Pipeline


def source_fixture(tmp_path):
    image=Image.new('RGB',(1000,800),'#808080')
    draw=ImageDraw.Draw(image)
    for x in range(35,246):
        shade=200+(x-35)*55//210
        draw.line((x,35,x,290),fill=(shade,shade,shade))
    detections=[{'polygon':polygon(b),'score':.95} for b in
                [[60,84,36,155],[130,63,30,144],[153,58,42,106],[182,62,30,113]]]
    (tmp_path/'inference.pdiparams').write_bytes(b'authored external model boundary')
    detector=PaddleDetector(tmp_path)
    detector.model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(json={'res':{
        'dt_polys':[m['polygon'] for m in detections],'dt_scores':[m['score'] for m in detections]}})])
    calls=[];translated=[]
    class Engine:
        name='authored-native-plan-ocr'
        def recognize_many(self,crops):
            calls.extend(crop.size for crop in crops)
            return ['聞いて。']*len(crops)
    class Translator:
        def signature(self):return 'authored-native-plan-translator'
        def translate(self,regions,*args):
            translated.extend(deepcopy(regions))
            return [{'id':r['id'],'vi':'Nghe này.'} for r in regions],{'translation_ms':0}
    memory=Memory(tmp_path/'native-plan.sqlite3')
    config=SimpleNamespace(values={'threads':2,'detector':'paddle','ocrBatch':2,'artCleanup':False})
    pipeline=Pipeline(memory,Translator(),config,tmp_path)
    pipeline.ocr=Engine();pipeline.detectors={'paddle':detector}
    buffer=io.BytesIO();image.save(buffer,format='PNG')
    params={'storyId':'s','pageId':'p','title':'Authored','revision':'rev1','at':{'chapter':1,'page':0}}
    return pipeline,calls,translated,buffer.getvalue(),params


def test_native_plan_crops_survive_detector_to_pipeline_and_coverage_cache(tmp_path):
    pipeline,calls,_,data,params=source_fixture(tmp_path)
    try:
        result=pipeline.process(params,data,threading.Event(),lambda *_:None)
        assert calls==[(88,187),(42,187)],'Do not discard the native plan and re-crop short child boxes'
        assert result['sourceVersion']==pipeline.detectors['paddle'].source_version
        assert all(r.get('ocrPartition') and r.get('ocrCropBox') for r in result['regions'])
        calls.clear()
        cached=pipeline.process({**params,'revision':'rev2'},data,threading.Event(),lambda *_:None)
        assert cached['cached'] and not calls
        assert cached['sourceVersion']==result['sourceVersion']
        assert cached['regions']==result['regions']
    finally:pipeline.memory.close()


def test_source_recipe_upgrade_keeps_valid_accepted_text_without_a_new_charge(tmp_path):
    from manga_live.ocr import LAYOUT_VERSION,SOURCE_GROUPING_VERSION
    pipeline,calls,translated,data,params=source_fixture(tmp_path)
    detector=pipeline.detectors['paddle']
    try:
        detector.source_version=LAYOUT_VERSION
        previous=pipeline.process(params,data,threading.Event(),lambda *_:None)
        calls.clear();translated.clear()
        detector.source_version=SOURCE_GROUPING_VERSION
        current=pipeline.process({**params,'revision':'rev2'},data,threading.Event(),lambda *_:None)
        assert current['cached'] and not calls and not translated,'Keep a context-valid accepted page; do not charge for upgrading code'
        assert current['sourceVersion']==previous['sourceVersion']==LAYOUT_VERSION
        assert current['regions']==previous['regions']
    finally:pipeline.memory.close()
