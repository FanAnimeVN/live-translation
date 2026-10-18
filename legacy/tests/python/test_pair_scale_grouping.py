"""Source grouping must not bridge a narrow column using its wider neighbour."""
from copy import deepcopy
from PIL import Image,ImageDraw
import pytest
from manga_live.errors import AppError
from manga_live.ocr import group_regions,polygon,partition_ocr_boxes,PaddleDetector


def test_pair_scale_candidate_separates_distant_column_but_retains_adjacent_columns():
    # Authored geometry, not a private source raster or a gold-conditioned rule.
    image=Image.new('RGB',(1000,800),'#808080')
    ImageDraw.Draw(image).rectangle((35,35,245,290),fill='white')
    boxes=[[60,84,36,155],[130,63,30,144],[153,58,42,106],[182,62,30,113]]
    detections=[{'polygon':polygon(box),'score':.95} for box in boxes]
    original=deepcopy(detections)
    control=group_regions(image,detections,include_source_members=True)
    assert len(control)==1,'Reproduce the current scale-based bridge first'
    candidate=group_regions(image,detections,include_source_members=True,experimental_pair_scale=True)
    assert sorted(len(r['sourceMembers']) for r in candidate)==[1,3]
    assert detections==original
    assert sorted(tuple(tuple(p) for p in m['polygon']) for r in candidate for m in r['sourceMembers'])==sorted(
        tuple(tuple(p) for p in m['polygon']) for m in detections)
    assert all(r['review'] and r['overlay']=='label' and 'balloon' not in r for r in candidate)


def test_pair_scale_does_not_activate_overlapping_children_as_independent_crops():
    image=Image.new('RGB',(1000,800),'#808080')
    ImageDraw.Draw(image).rectangle((35,35,250,310),fill='white')
    # Small bottom fragments bridge near the tall columns' ends. A split by
    # pair scale alone leaves intersecting child envelopes and shared ink risk.
    boxes=[[80,60,30,170],[58,64,24,90],[138,220,14,24],
           [106,220,24,60],[124,218,20,60],[160,60,30,190],[186,60,34,150]]
    detections=[{'polygon':polygon(box),'score':.95} for box in boxes]
    assert len(group_regions(image,detections))==1
    candidate=group_regions(image,detections,include_source_members=True,experimental_pair_scale=True)
    assert len(candidate)==1,'Ambiguous children retain their original parent, not two overlapping active crops'
    assert len(candidate[0]['sourceMembers'])==len(detections)


def test_disjoint_source_members_cannot_create_overlapping_padded_inference_crops():
    image=Image.new('RGB',(300,300),'#808080')
    ImageDraw.Draw(image).rectangle((40,10,100,130),fill='white')
    detections=[{'polygon':polygon(box),'score':.95} for box in
                [[60,30,4,80],[69,35,10,70]]]
    assert len(group_regions(image,detections))==1
    candidate=group_regions(image,detections,include_source_members=True,experimental_pair_scale=True)
    assert len(candidate)==1,'A five-pixel source gap cannot separate two three-pixel padded crops'
    assert len(candidate[0]['sourceMembers'])==2


def test_split_columns_keep_original_longitudinal_inference_frame_not_erasure_bounds():
    image=Image.new('RGB',(1000,800),'#808080')
    ImageDraw.Draw(image).rectangle((35,35,245,290),fill='white')
    boxes=[[60,84,36,155],[130,63,30,144],[153,58,42,106],[182,62,30,113]]
    detections=[{'polygon':polygon(box),'score':.95} for box in boxes]
    # Explicit unboxed/narration input to the public partition seam. A proven
    # balloon is deliberately not eligible for this crop-only experiment.
    parents=[{'id':'parent','bbox':[57,55,158,187],'overlay':'label','sourceMembers':detections}]
    children=group_regions(image,detections,include_source_members=True,experimental_pair_scale=True)
    original=deepcopy((parents,children))
    crops,evidence=partition_ocr_boxes(image,children,source_parents=parents)
    assert sorted(crops.values())==[[57,55,42,187],[127,55,88,187]]
    assert (parents,children)==original,'Inference framing cannot enlarge source/erasure geometry'
    assert all(c['bbox']!=crops[c['id']] for c in children)
    assert all('balloon' not in c and c['review'] for c in children)
    assert len(evidence)==1 and evidence[0]['erasure_permitted'] is False


def frame_source():
    image=Image.new('RGB',(400,400),'white')
    members=[{'polygon':polygon(box),'score':.95} for box in
             [[45,60,12,140],[85,45,12,110]]]
    parents=[{'id':'parent','bbox':[40,40,62,165],'overlay':'label','sourceMembers':members}]
    children=[{'id':'left','bbox':[40,55,22,150],'overlay':'label','sourceMembers':[members[0]],
               'review':True,'reviewReasons':['layout_fragment']},
              {'id':'right','bbox':[80,40,22,120],'overlay':'label','sourceMembers':[members[1]],
               'review':True,'reviewReasons':['layout_fragment']}]
    return image,parents,children


@pytest.mark.parametrize('transpose',[False,True])
@pytest.mark.parametrize('factor',[.5,1,2])
def test_inherited_frame_is_orientation_scale_and_order_independent(transpose,factor):
    image,parents,children=frame_source()
    expected={'left':[40,40,22,165],'right':[80,40,22,165]}
    image=image.resize((int(400*factor),int(400*factor)))
    for region in [*parents,*children]:
        region['bbox']=[int(v*factor) for v in region['bbox']]
        # Deep-copy shared members before rescaling each source view.
        region['sourceMembers']=deepcopy(region['sourceMembers'])
        for member in region['sourceMembers']:
            member['polygon']=[[v*factor for v in p] for p in member['polygon']]
    expected={key:[int(v*factor) for v in box] for key,box in expected.items()}
    if transpose:
        image=image.transpose(Image.Transpose.TRANSPOSE)
        for region in [*parents,*children]:
            x,y,w,h=region['bbox'];region['bbox']=[y,x,h,w]
            for member in region['sourceMembers']:member['polygon']=[p[::-1] for p in member['polygon']]
        expected={key:[b[1],b[0],b[3],b[2]] for key,b in expected.items()}
    first=partition_ocr_boxes(image,children,source_parents=parents)
    second=partition_ocr_boxes(image,list(reversed(children)),source_parents=parents)
    assert first[0]==second[0]==expected
    assert all(record['erasure_permitted'] is False for record in first[1])


@pytest.mark.parametrize('marker',[
    {'scope':{'reason':'reader','action':'translate'}},
    {'scope':{'reason':'reader','action':'defer'}},
    {'speaker':'confirmed'}, {'listener':'confirmed'},
    {'balloon':{'textBox':[40,40,62,165]}},
])
@pytest.mark.parametrize('target',['parent','child'])
def test_parent_frame_never_bypasses_reader_exclusions_roles_or_balloon(target,marker):
    image,parents,children=frame_source()
    (parents[0] if target=='parent' else children[0]).update(marker)
    assert partition_ocr_boxes(image,children,source_parents=parents)==({},[])


@pytest.mark.parametrize('mutation',['missing','duplicate','changed_score','unknown'])
def test_inherited_frame_rejects_loss_duplicate_or_fabricated_source_members(mutation):
    image,parents,children=frame_source()
    children=deepcopy(children)
    if mutation=='missing':children[0]['sourceMembers']=[]
    elif mutation=='duplicate':children[1]['sourceMembers']=deepcopy(children[0]['sourceMembers'])
    elif mutation=='changed_score':children[0]['sourceMembers'][0]['score']=.8
    else:children[0]['sourceMembers'][0]['polygon']=polygon([46,60,12,140])
    with pytest.raises(AppError):partition_ocr_boxes(image,children,source_parents=parents)


def test_longitudinal_fragments_cannot_expand_into_overlapping_strips():
    image,parents,children=frame_source()
    members=[{'polygon':polygon(b),'score':.95} for b in [[45,45,12,60],[45,130,12,70]]]
    parents[0]['sourceMembers']=members
    children[0].update(bbox=[40,40,22,70],sourceMembers=[members[0]])
    children[1].update(bbox=[40,125,22,80],sourceMembers=[members[1]])
    assert partition_ocr_boxes(image,children,source_parents=parents)==({},[])


def test_recomputed_parent_partition_cannot_be_replaced_by_a_provider_crop_hint():
    image=Image.new('RGB',(200,250),'white')
    ink=ImageDraw.Draw(image)
    for top in range(50,120,15):
        ink.rectangle((116,top,127,top+9),fill='black')
        ink.rectangle((96,top,106,top+9),fill='black')
    members=[{'polygon':polygon(b),'score':.95} for b in
             [[105,60,8,55],[124,50,8,65],[96,50,10,70]]]
    parents=[{'id':'p-right','bbox':[104,45,30,86],'overlay':'label','sourceMembers':members[:2],
              'ocrCropBox':[0,0,200,250]},
             {'id':'p-left','bbox':[90,46,29,100],'overlay':'label','sourceMembers':members[2:]}]
    children=[{'id':'a','bbox':[104,55,10,65],'overlay':'label','sourceMembers':[members[0]],'reviewReasons':['layout_fragment']},
              {'id':'b','bbox':[120,45,14,75],'overlay':'label','sourceMembers':[members[1]],'reviewReasons':['layout_fragment']},
              {'id':'c','bbox':[90,46,29,100],'overlay':'label','sourceMembers':[members[2]],'reviewReasons':['layout_fragment']}]
    parent_crops,_=partition_ocr_boxes(image,parents)
    assert parent_crops['p-right'][0]>104,'The original pixel partition must really trim this parent'
    assert partition_ocr_boxes(image,children,source_parents=parents)==({},[])


def test_native_paddle_plan_uses_disjoint_columns_and_parent_frame(tmp_path):
    from types import SimpleNamespace
    image=Image.new('RGB',(1000,800),'#808080')
    draw=ImageDraw.Draw(image)
    for x in range(35,246):
        shade=200+(x-35)*55//210
        draw.line((x,35,x,290),fill=(shade,shade,shade))  # Non-flat narration surface.
    detections=[{'polygon':polygon(b),'score':.95} for b in
                [[60,84,36,155],[130,63,30,144],[153,58,42,106],[182,62,30,113]]]
    control=group_regions(image,detections,include_source_members=True)
    assert len(control)==1 and 'balloon' not in control[0]
    (tmp_path/'inference.pdiparams').write_bytes(b'authored external model boundary')
    detector=PaddleDetector(tmp_path)
    detector.model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(json={'res':{
        'dt_polys':[m['polygon'] for m in detections],'dt_scores':[m['score'] for m in detections]}})])
    regions,crops,evidence=detector.detect_plan(image)
    assert sorted(crops.values())==[[57,55,42,187],[127,55,88,187]]
    assert len(regions)==2 and all(r['speaker']==r['listener']=='unknown' for r in regions)
    assert all('sourceMembers' not in r and 'balloon' not in r for r in regions)
    assert evidence[0]['source_members_preserved'] and evidence[0]['erasure_permitted'] is False
