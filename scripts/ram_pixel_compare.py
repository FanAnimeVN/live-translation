"""Compare decoded screenshot pixels from a bounded RAM pipe, never files."""
import base64
import io
import json
import sys
import numpy as np
from PIL import Image


def compare(before,after):
    if before.size!=after.size:return {"equal":False,"size_mismatch":[list(before.size),list(after.size)]}
    a=np.asarray(before.convert("RGBA"));b=np.asarray(after.convert("RGBA"))
    mask=np.any(a!=b,axis=2);y,x=np.nonzero(mask)
    result={"equal":not bool(len(x)),"size":list(before.size),"changed_pixels":len(x)}
    if len(x):
        result.update(bbox=[int(x.min()),int(y.min()),int(x.max()-x.min()+1),int(y.max()-y.min()+1)],
            max_channel_delta=int(np.abs(a.astype("int16")-b.astype("int16")).max()),
            samples=[{"x":int(px),"y":int(py),"before":a[py,px].tolist(),"after":b[py,px].tolist()}
                     for px,py in zip(x[:8],y[:8])])
    return result


def main():
    raw=sys.stdin.buffer.read(12*1024*1024+1)
    if len(raw)>12*1024*1024:raise ValueError("Bounded RAM comparison required")
    data=json.loads(raw)
    if set(data)!={"before","after"}:raise ValueError("Exactly two screenshots required")
    images=[]
    for key in ("before","after"):
        encoded=data[key]
        if not isinstance(encoded,str) or len(encoded)>6*1024*1024:raise ValueError("Invalid image pipe")
        image=Image.open(io.BytesIO(base64.b64decode(encoded,validate=True)))
        if image.format!="PNG" or max(image.size)>8000 or image.width*image.height>24_000_000:
            raise ValueError("Bounded PNG screenshot required")
        image.load();images.append(image)
    print(json.dumps(compare(*images)))


if __name__=="__main__":main()
