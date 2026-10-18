"""Source-boundary merge vetoes, never speaker inference or erasure rights."""
import math
import statistics


def paper_notch_cuts(labels,stats,label,boxes):
    """Separate lobes only at a deep external notch ending a shorter block.

    Work on one bounded dominant paper component. Text holes, OCR strings,
    gold boxes and a fictional straight ink corridor cannot create a cut.
    Returned planes veto grouping edges; they do not split detector pixels,
    prove new balloon ownership, assign speakers or authorize artwork erasure.
    """
    import cv2
    import numpy as np
    if len(boxes)<2:return []
    x,y,w,h,area=map(int,stats[label])
    if x<=1 or y<=1 or x+w>=labels.shape[1]-1 or y+h>=labels.shape[0]-1 or area/(w*h)<.6:
        return []
    vertical=sum(bh>=bw*1.25 for _,_,bw,bh in boxes)>=math.ceil(len(boxes)*.8)
    horizontal=sum(bw>=bh*1.25 for _,_,bw,bh in boxes)>=math.ceil(len(boxes)*.8)
    if not vertical and not horizontal:return []
    axis=0 if vertical else 1;long_axis=1-axis
    scale=statistics.median(box[2+axis] for box in boxes)
    component=(labels[y:y+h,x:x+w]==label).astype("uint8")
    contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not contours:return []
    contour=max(contours,key=cv2.contourArea)
    if not 4<=len(contour)<=4096:return []
    try:
        hull=cv2.convexHull(contour,returnPoints=False)
        defects=cv2.convexityDefects(contour,hull)
    except cv2.error:
        return []  # A self-touching contour is not evidence of a usable split.
    if defects is None:return []
    offset=np.array([x,y]);cuts=[]
    for first,last,inner,depth in defects[:,0]:
        if depth/256<max(12,scale*.75):continue
        start,end,notch=(contour[idx,0]+offset for idx in (first,last,inner))
        position=float(notch[axis]);height=float(notch[long_axis])
        # Both arcs must flank the notch rather than belonging to one outside
        # edge. A concave tail beyond all text is not a second speech block.
        if not min(start[axis],end[axis])<position<max(start[axis],end[axis]):continue
        sides=[[],[]];crossed=False
        for box in boxes:
            transverse,size=box[axis],box[2+axis]
            # A little detector padding may touch a curved border. Never cut
            # through the substantive middle of a column/line or drop a crop.
            overhang=min(position-transverse,transverse+size-position)
            if overhang>min(4,size*.1):crossed=True;break
            sides[int(transverse+size/2>=position)].append(box)
        if crossed or not all(sides):continue
        left=max(box[axis]+box[2+axis] for box in sides[0]);right=min(box[axis] for box in sides[1])
        if not scale*.2<=right-left<=scale:continue
        tops=[min(box[long_axis] for box in side) for side in sides]
        bottoms=[max(box[long_axis]+box[2+long_axis] for box in side) for side in sides]
        top_boundary=(abs(height-max(tops))<=scale*.5+3 and height-min(tops)>=scale*1.5 and
                      max(start[long_axis],end[long_axis])<=height+3)
        bottom_boundary=(abs(height-min(bottoms))<=scale*.5+3 and max(bottoms)-height>=scale*1.5 and
                         min(start[long_axis],end[long_axis])>=height-3)
        if top_boundary or bottom_boundary:cuts.append((axis,position))
    return sorted(set(cuts))


def crosses_paper_cut(a,b,cuts):
    return any((a[axis]+a[2+axis]/2<position)!=(b[axis]+b[2+axis]/2<position)
               for axis,position in cuts)
