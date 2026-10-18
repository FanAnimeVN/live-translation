"""Loopback-only manual reader fixture. Image bytes stay in memory.
The optional private ZIP sample is never extracted or served over LAN.
"""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image,ImageDraw,ImageFont

def synthetic_layout():
    image=Image.new("RGB",(800,1050),"#f5f2eb");draw=ImageDraw.Draw(image)
    font=ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc",29)
    bubbles=[((440,70,760,300),["姉ちゃん、", "まだ帰らないの？"]),
             ((60,150,380,390),["先に帰ってて。", "あとで行くから。"]),
             ((440,500,760,740),["氷結結界を", "展開する！"]),
             ((60,690,380,960),["明日は", "来なくてもいい。"])]
    draw.rectangle((25,25,775,470),outline="#333",width=4);draw.rectangle((25,485,775,1025),outline="#333",width=4)
    detections=[]
    for box,lines in bubbles:
        draw.ellipse(box,fill="white",outline="#333",width=3)
        x,y,r,b=box
        for n,line in enumerate(lines):
            width=draw.textlength(line,font=font);position=(x+(r-x-width)/2,y+65+n*45)
            draw.text(position,line,font=font,fill="black")
            left,top,right,bottom=draw.textbbox(position,line,font=font)
            detections.append({"polygon":[[left,top],[right,top],[right,bottom],[left,bottom]],"score":0.95})
    return image,detections


def synthetic_page():
    image,_=synthetic_layout()
    data=io.BytesIO();image.save(data,format="PNG");return data.getvalue()


def synthetic_detected_layout():
    """Replay real PP-OCRv5 union crops from the authored Edge run.

    No model is run here. Glyph boxes remain the separate raster-check truth.
    Source: isolated authored-fixture QA EIC83g, 2026-10-13.
    """
    from manga_live.ocr import polygon
    image,glyphs=synthetic_layout()
    # Remove the grouping helper's three-pixel padding before replaying it.
    boxes=[(483,128,230,83),(99,208,223,86),(524,560,152,83),(98,751,225,85)]
    return image,[{"polygon":polygon(box),"score":.81} for box in boxes],glyphs


def synthetic_art_layout(with_text=True):
    """Authored texture for masked cleanup QA, not a manga quality dataset."""
    image=Image.new("RGB",(800,1050),"#b8b8b8");draw=ImageDraw.Draw(image)
    for top,bottom,background,rain in [(25,490,"#b8b8b8","#929292"),(515,1025,"#303030","#505050")]:
        draw.rectangle((25,top,775,bottom),fill=background,outline="#111",width=3)
        for x in range(35,810,17):
            draw.line((x,top+3,x-52,bottom-3),fill=rain,width=1)
    font=ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc",28);detections=[]
    entries=[((395,130),"雨はまだ止まない。",False),((100,355),"ここで待っている。",False),
             ((360,650),"それでも歩いていく。",True)]
    for position,text,light in entries:
        if with_text:
            draw.text(position,text,font=font,fill="white" if light else "black",stroke_width=1,stroke_fill="black" if light else "white")
        x,y,r,b=draw.textbbox(position,text,font=font,stroke_width=1)
        detections.append({"polygon":[[x,y],[r,y],[r,b],[x,b]],"score":0.95})
    return image,detections

def private_images(args):
    """Read audited private samples, never extract them or mutate annotations.

    An explicit page identity must match an eligible source page; do not
    silently substitute a different image after an audit exclusion.
    """
    if not (getattr(args,"zip",None) or getattr(args,"folder",None)):
        if getattr(args,"private_page",None):
            raise ValueError("Private page needs a dataset")
        return {},[]
    from benchmark import audit,dataset_source
    with dataset_source(args) as source:
        _,_,pages=audit(source)
    selected=getattr(args,"private_page",None)
    if selected:
        pages=[page for page in pages if page[0]["page_id"]==selected]
        if not pages:
            raise ValueError("Selected private page is missing or excluded by the audit")
    images={}
    for i,(_,image,_) in enumerate(pages):
        data=io.BytesIO();image.save(data,format="PNG");images[f"/private/{i}.png"]=data.getvalue()
    return images,[page[0]["page_id"] for page in pages]


def main():
    parser=argparse.ArgumentParser()
    inputs=parser.add_mutually_exclusive_group();inputs.add_argument("--zip");inputs.add_argument("--folder")
    parser.add_argument("--private-page");parser.add_argument("--port",type=int,default=0);args=parser.parse_args()
    images={"/fixture.png":synthetic_page()}
    art,_=synthetic_art_layout();buffer=io.BytesIO();art.save(buffer,format="PNG");images["/art.png"]=buffer.getvalue()
    samples,page_ids=private_images(args);images.update(samples)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path=urlparse(self.path).path
            if path=="/favicon.ico":
                self.send_response(204);self.end_headers();return
            if path in images:
                self.send_response(200);self.send_header("Content-Type","image/png");self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(images[path]);return
            if path not in ("/","/chapter/1","/chapter/2","/private-reader","/canvas","/art"):
                self.send_error(404);return
            private=path=="/private-reader"
            if private and not samples:
                self.send_error(404);return
            src="/private/0.png" if private else "/art.png" if path=="/art" else "/fixture.png"
            title="Private benchmark · Chapter 1" if private else "Hai chị em · Chapter "+("2" if path.endswith("2") else "1")
            body=f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{title}</title>
            <style>body{{margin:0;background:#e7ece9;color:#173b32;font:16px system-ui}}header{{max-width:800px;margin:20px auto}}nav a{{margin-right:20px;color:#246955}}img,canvas{{display:block;max-width:90vw;width:800px;height:auto;margin:20px auto}}small{{display:block;color:#5c6f67}}button{{padding:10px}}</style></head><body>
            <header><h1>{title}</h1><small>Local QA reader · RAM-only images · not a licensed content service</small><nav>
            <a href="/chapter/1">Chapter 1</a><a href="/chapter/2">Chapter 2</a><a href="/canvas">Canvas</a><a href="/private-reader">Private benchmark</a></nav>
            <p>Bật Live translation, xác nhận tên/chapter rồi dịch. Dùng Alt+T để đối chiếu và bấm bóng để sửa.</p></header>
            <img id="page" alt="Japanese test dialogue" src="{src}"><script>
            if(location.pathname==='/canvas'){{const img=document.querySelector('img');img.onload=()=>{{const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;c.getContext('2d').drawImage(img,0,0);img.replaceWith(c);}}}}
            </script></body></html>'''
            self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(body.encode())
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Handler)
    print(json.dumps({"url":f"http://127.0.0.1:{server.server_port}/chapter/1","private_sample":bool(samples),"private_page_ids":page_ids}),flush=True)
    server.serve_forever()

if __name__=="__main__":main()
