import { expressionSchema, scopeSchema, regionSchema, renderPatchSchema, stableId, type ReaderConfig, type Region, type RenderPatch } from "../shared/contracts";
import {fittedImage,intersect,regionBox,type Box} from "./geometry";
import {nameReviewNote} from "./translation-quality";
import {fitLettering} from "./typesetting";
import {conflictedLetteringIds} from "./reading-layout";
import {TaskError,translationFailureNotice} from "../shared/task-error";

declare global {interface Window {__mangaLive?:{start:(config:ReaderConfig)=>void;stop:(reason?:string)=>void}}}

if(!window.__mangaLive){
  const root=document.createElement("div");root.dataset.mangalive="true";
  Object.assign(root.style,{position:"fixed",inset:"0",zIndex:"2147483600",pointerEvents:"none"});
  const shadow=root.attachShadow({mode:"closed"});
  const style=document.createElement("style");
  style.textContent=`
    :host{all:initial;font-family:system-ui,sans-serif}
    .bar{position:fixed;bottom:20px;right:20px;max-width:360px;background:#132123;color:#eef5f4;
      box-shadow:0 8px 36px #0004;border:1px solid #ffffff30;border-radius:16px;padding:12px;pointer-events:auto;font:13px/1.45 system-ui}
    .bar strong{font-size:14px}.bar .status{margin:6px 0;word-break:break-word;color:#bcd6d1}
    button{font:inherit;cursor:pointer;border:1px solid #ffffff25;border-radius:9px;background:#28443f;color:#fff;padding:6px 9px;margin:3px;min-height:36px}
    .bar.compact .controls,.bar.compact .status,.bar.compact .term-hint{display:none}.bar.compact{padding:6px 10px;max-width:min(360px,calc(100vw - 40px))}
    .bar .toggle{float:right;margin:-3px 0 0 10px}.bar.compact strong{display:inline-block;max-width:210px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle}
    @media(max-width:600px){.bar{right:12px;bottom:12px;max-width:calc(100vw - 48px)}.bar button,.detail button{min-height:44px}.detail{right:12px;bottom:90px;max-height:60vh}.bar.compact{max-width:calc(100vw - 44px)}}
    button:focus-visible{outline:2px solid #6dd2b7;outline-offset:2px}
    .erase{position:fixed;box-sizing:border-box;pointer-events:none}
    .region{position:fixed;box-sizing:border-box;pointer-events:auto;border:0;text-align:center;min-height:0;min-width:0;
      color:#111;background:transparent;font-family:MangaLiveLettering,Arial,sans-serif;font-weight:400;white-space:pre;overflow:hidden;
      display:flex;align-items:center;justify-content:center;padding:3px;cursor:pointer;margin:0;border-radius:0;text-shadow:none;box-shadow:none}
    .region.label{background:#fffffff0;border-left:2px solid #657f75;border-radius:0}
    .region.art{background:transparent;border:0;padding:3px;paint-order:stroke fill}
    .region.white:not(.integrated){background:#fff}
    .region:hover,.region:focus-visible{outline:1px solid #48665c;outline-offset:2px}
    .region[data-review=true]:hover,.region[data-review=true]:focus-visible{outline:1px dashed #bc8726}
    .reading-rail{position:fixed;z-index:2;box-sizing:border-box;pointer-events:auto;color:#182627;background:#f8faf9;
      border:1px solid #d5e1dc;border-radius:12px;font:14px/1.5 system-ui;overflow:hidden;box-shadow:0 6px 24px #0002}
    .reading-rail>summary{cursor:pointer;padding:10px 12px;min-height:44px;box-sizing:border-box;font-weight:600}
    .reading-rail>summary:focus-visible{outline:2px solid #287b66;outline-offset:-3px}
    .reading-notes{max-height:inherit;overflow:auto;overscroll-behavior:contain;padding:0 12px 10px}
    .reading-note{border-top:1px solid #d5e1dc;padding:8px 0}
    .reading-note small{display:block;color:#52655f;font:12px/1.4 system-ui;margin-bottom:4px}
    .region.reading-text{position:static!important;display:block;width:100%!important;height:auto!important;min-height:44px;
      clip-path:none!important;white-space:pre-wrap;overflow-wrap:anywhere;overflow:visible;text-align:left;background:transparent;
      color:#182627!important;padding:4px 0;border:0;font:400 17px/1.5 MangaLiveLettering,Arial,sans-serif!important;-webkit-text-stroke:0!important}
    .source-marker{position:fixed;z-index:1;margin:0;padding:0;min-height:24px;width:24px;height:24px;border-radius:50%;
      pointer-events:auto;font:600 12px/24px system-ui;background:#163f35;color:#fff;border:1px solid #fff;box-shadow:0 1px 4px #0004}
    .detail{position:fixed;right:20px;bottom:124px;width:min(340px,85vw);box-sizing:border-box;padding:16px;
      color:#182627;background:#f8faf9;border:1px solid #d5e1dc;border-radius:14px;box-shadow:0 14px 40px #0004;pointer-events:auto;
      font:14px/1.5 system-ui;max-height:65vh;overflow:auto}
    .detail button{background:#21594d}.detail .vi{white-space:pre-wrap}.detail label{display:block;font-size:12px;margin:8px 0 3px}
    .detail .detail-actions{position:sticky;bottom:0;background:#f8faf9;border-top:1px solid #d5e1dc;padding:8px 0 0;margin-top:12px;z-index:1}
    .detail .speaker-tools{margin:6px 0}.detail summary{cursor:pointer;min-height:44px;box-sizing:border-box;padding:10px 0;font-size:12px;color:#47615b}
    .detail summary:focus-visible{outline:2px solid #287b66;outline-offset:2px}
    .detail textarea,.detail input{box-sizing:border-box;width:100%;border:1px solid #b9ccc5;border-radius:8px;padding:8px;
      font:14px/1.4 system-ui;background:white;color:#162b26}.detail .vi{font-size:17px;margin:8px 0}
    .selection{position:fixed;inset:0;background:#0002;pointer-events:auto;cursor:crosshair}
    .selection-box{position:fixed;border:2px solid #49c8a3;background:#49c8a326;pointer-events:none}
    .bar{z-index:3}.detail{z-index:4}.selection{z-index:5}
  `;
  shadow.append(style);
  const layer=document.createElement("div"),bar=document.createElement("div");
  const readingRail=document.createElement("details"),railSummary=document.createElement("summary"),readingNotes=document.createElement("div");
  readingRail.className="reading-rail";readingRail.open=true;readingRail.hidden=true;readingRail.style.visibility="hidden";
  readingNotes.className="reading-notes";readingRail.append(railSummary,readingNotes);layer.append(readingRail);
  railSummary.title="Bản dịch bên cạnh giữ nguyên tranh khi chưa thể dàn chữ an toàn. Bấm để thu gọn.";
  bar.className="bar";
  const heading=document.createElement("strong");heading.textContent="Live translation";
  const status=document.createElement("div");status.className="status";status.setAttribute("role","status");status.setAttribute("aria-live","polite");
  const controls=document.createElement("div");controls.className="controls";
  const termHint=document.createElement("div");termHint.className="term-hint";termHint.hidden=true;
  let autoCompactPending=true,pendingTermCount=0;
  function button(label:string,action:()=>void){const el=document.createElement("button");el.type="button";el.textContent=label;el.addEventListener("click",action);return el;}
  function syncToolbarToggle(){
    const compact=bar.classList.contains("compact");
    const hasSecondary=!!secondaryJob();
    toggle.textContent=compact?(pendingTermCount?"Mở · "+pendingTermCount:hasSecondary?"Mở · chữ phụ":"Mở"):"Thu gọn";
    toggle.setAttribute("aria-expanded",String(!compact));
    toggle.title=pendingTermCount?"Có tên cần xác nhận · có thể để sau và đọc tiếp":"Mở hoặc thu gọn công cụ dịch";
  }
  function setToolbarCompact(compact:boolean){bar.classList.toggle("compact",compact);syncToolbarToggle();}
  const toggle=button("Thu gọn",()=>{
    autoCompactPending=false;setToolbarCompact(!bar.classList.contains("compact"));
  });toggle.className="toggle";toggle.setAttribute("aria-label","Mở hoặc thu gọn công cụ dịch");toggle.setAttribute("aria-expanded","true");
  const retryButton=button("Thử lại",()=>retryFailed());retryButton.className="retry";
  retryButton.hidden=true;retryButton.disabled=true;
  const modelSettings=button("Đổi model / Cloud",()=>{
    void request("reader.settings",{}).catch(error=>say(error instanceof Error?error.message:String(error)));
  });modelSettings.className="model-settings";modelSettings.hidden=true;
  const secondaryButton=button("Chữ phụ",()=>openSecondary());secondaryButton.className="secondary";secondaryButton.hidden=true;
  controls.append(retryButton,modelSettings,secondaryButton,button("Chọn vùng",()=>select()),button("Xem gốc",()=>{original=!original;renderVisibility();}),
    button("Đã đọc",()=>void read()),button("Dừng",()=>stop()));
  bar.append(toggle,heading,status,termHint,controls);shadow.append(layer,bar);
  (document.documentElement??document.body).append(root);

  interface Surface {region:Region;node:HTMLButtonElement;erase?:HTMLElement|SVGSVGElement;fitKey?:string;surfaceKey?:string;
    fit?:ReturnType<typeof fitLettering>;note?:HTMLElement;marker?:HTMLButtonElement}
  interface Patch {data:RenderPatch;node:HTMLImageElement;url:string;bytes:number}
  interface Job {id:string;pageId:string;revision:string;img?:HTMLImageElement;src?:string;rect?:DOMRect;
    scrollX:number;scrollY:number;width:number;height:number;page:number;prefetched:boolean;
    regions:Map<string,Surface>;secondary:Map<string,Region>;done:boolean;terms:Map<string,any>;patches:Map<string,Patch>;patchBytes:number;
    pendingPatchUrls:Set<string>;patchTokens:Map<string,symbol>;invalidated?:boolean}
  let config:ReaderConfig|undefined,active=false,original=false,busy=false,currentUrl=location.href;
  let latest:Job|undefined,detail:HTMLElement|undefined,selection:HTMLElement|undefined,raf=0,debounce:ReturnType<typeof setTimeout>|undefined;
  let immediateScanPending=false;
  const jobs=new Map<string,Job>(),processed=new WeakMap<HTMLImageElement,string>(),failed=new WeakMap<HTMLImageElement,string>();
  const pending=new Set<HTMLImageElement>();
  const deferredTerms=new Set<string>();
  const confirmedTerms=new Set<string>();
  let retryable:{job:Job;img?:HTMLImageElement;config:ReaderConfig;url:string}|undefined;
  let queuedSelection:{rect:DOMRect;config:ReaderConfig;url:string;scrollX:number;scrollY:number;width:number;height:number}|undefined;
  const termKey=(entity:string)=>config!.storyId+":"+entity;
  const resizeObserver=new ResizeObserver(()=>{schedulePosition();queueScan();});
  let fontRevision=0;
  const letteringCanvas=document.createElement("canvas"),letteringContext=letteringCanvas.getContext("2d");
  // Only a packaged, pinned font is loaded; no Google Fonts/CDN requests.
  if(typeof chrome.runtime.getURL==="function"){
    const font=new FontFace("MangaLiveLettering",`url("${chrome.runtime.getURL("assets/PatrickHand-Regular.ttf")}")`,{weight:"400",style:"normal"});
    void font.load().then(loaded=>{document.fonts.add(loaded);fontRevision++;schedulePosition();}).catch(()=>{
      // A website CSP may prevent the font. Keep a readable system fallback.
      fontRevision++;schedulePosition();
    });
  }

  async function request(op:string,params:any){
    const reply=await chrome.runtime.sendMessage({op,params});
    if(!reply?.ok) throw new TaskError(typeof reply?.error==="string"?reply.error:"Không nhận được phản hồi extension.",reply?.code);
    return reply.result;
  }
  function say(value:string){status.textContent=value;}
  function clearRetry(){retryable=undefined;retryButton.hidden=true;retryButton.disabled=true;modelSettings.hidden=true;}
  function retryFailed(){
    const target=retryable;
    if(busy||!active||!target||config!==target.config)return;
    if(location.href!==target.url||!jobs.has(target.job.id)||
       (target.img&&(!target.img.isConnected||target.img.currentSrc!==target.job.src))){
      clearRetry();say("Trang hoặc ảnh đã đổi. Chọn lại vùng cần dịch.");return;
    }
    const r=target.img?undefined:new DOMRect(target.job.rect!.x+target.job.scrollX-scrollX,
      target.job.rect!.y+target.job.scrollY-scrollY,target.job.rect!.width,target.job.rect!.height);
    if(r&&(r.bottom<=0||r.top>=innerHeight||r.right<=0||r.left>=innerWidth)){
      say("Vùng trước không còn hiển thị. Cuộn lại hoặc dùng Chọn vùng.");return;
    }
    clearRetry();discard(target.job);
    void process(target.img,r);
  }
  function imageRect(img:HTMLImageElement){
    const r=img.getBoundingClientRect(),css=getComputedStyle(img);
    const px=(value:string)=>Number.parseFloat(value)||0;
    const left=px(css.borderLeftWidth)+px(css.paddingLeft),top=px(css.borderTopWidth)+px(css.paddingTop);
    const box={x:r.x+left,y:r.y+top,width:r.width-left-px(css.borderRightWidth)-px(css.paddingRight),
      height:r.height-top-px(css.borderBottomWidth)-px(css.paddingBottom)};
    const fitted=fittedImage(box,img.naturalWidth,img.naturalHeight,css.objectFit,css.objectPosition);
    return new DOMRect(fitted.x,fitted.y,fitted.width,fitted.height);
  }
  function imageClip(img:HTMLImageElement):Box{
    const r=img.getBoundingClientRect();let box:Box={x:r.x,y:r.y,width:r.width,height:r.height};
    for(let ancestor=img.parentElement;ancestor&&ancestor!==document.body;ancestor=ancestor.parentElement){
      const css=getComputedStyle(ancestor);
      if(css.overflowX!=="visible"||css.overflowY!=="visible"){
        const a=ancestor.getBoundingClientRect();box=intersect(box,a);
      }
    }
    return intersect(box,{x:0,y:0,width:innerWidth,height:innerHeight});
  }
  function visible(img:HTMLImageElement){
    const r=imageRect(img);return r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth;
  }
  function candidates(){
    return [...document.images].filter(img=>img.complete&&img.naturalWidth>=250&&img.naturalHeight>=300
      &&img.getBoundingClientRect().width>150&&getComputedStyle(img).display!=="none"
      &&!img.closest("[data-mangalive]"));
  }
  function renderVisibility(){
    // Original view is an immediate conceal operation, even if the browser
    // delays RAF under load. Revealing still waits for current geometry/clipping.
    // Hidden fixed/clip-path children may retain compositor surfaces. Exclude
    // the entire lettering subtree from paint, while keeping the reader's bar.
    // On reveal every surface is still hidden until current geometry is ready.
    layer.style.display=original?"none":"";
    if(original)for(const job of jobs.values()){
      for(const {node,erase,marker} of job.regions.values()){
        node.style.visibility="hidden";
        if(erase)erase.style.visibility="hidden";
        if(marker)marker.style.visibility="hidden";
      }
      for(const patch of job.patches.values())patch.node.style.visibility="hidden";
    }
    schedulePosition();
  }
  function position(){
    raf=0;
    let railCount=0;
    const frames=[...jobs.values()].flatMap(job=>{
      if(job.img&&(!job.img.isConnected||job.img.currentSrc!==job.src)){discard(job);return [];}
      const r=job.img?imageRect(job.img):new DOMRect(job.rect!.x+job.scrollX-scrollX,job.rect!.y+job.scrollY-scrollY,job.rect!.width,job.rect!.height);
      const clip=job.img?imageClip(job.img):{x:0,y:0,width:innerWidth,height:innerHeight};
      const conflicts=conflictedLetteringIds([...job.regions.values()].map(({region})=>({id:region.id,
        box:job.patches.get(region.id)?.data.textBox??region.balloon?.textBox??region.bbox})));
      const items=[...job.regions.values()].map(entry=>{
        const {region}=entry;
        const patch=job.patches.get(region.id);
        const b=regionBox(patch?.data.textBox??region.balloon?.textBox??region.bbox,r,job.width,job.height);
        const shown=intersect(b,clip);
        const sourceSize=patch?.data.sourceFontPx??region.balloon?.sourceFontPx;
        const preferred=sourceSize?sourceSize*r.width/job.width/0.85:24;
        const fitKey=[Math.round(b.width*10),Math.round(b.height*10),region.vi,JSON.stringify(region.expression),fontRevision,Math.round(preferred)].join("|");
        const lettering=entry.fitKey===fitKey&&entry.fit?entry.fit:fitLettering(region.vi??"",b.width,b.height,(text,size)=>{
          if(!letteringContext)return [...text].length*size*0.55;
          letteringContext.font=`400 ${size}px ${fontRevision?"MangaLiveLettering, ":""}Arial, sans-serif`;
          return letteringContext.measureText(text).width;
        },preferred,{spelled:region.expression?.cues.includes("spelled")});
        entry.fitKey=fitKey;entry.fit=lettering;
        return {entry,patch,b,shown,lettering,fallback:conflicts.has(region.id)||lettering.overflow||!entry.erase};
      });
      return [{job,r,clip,items}];
    });
    const visibleFrames=frames.filter(f=>f.items.some(i=>i.shown.width>=1&&i.shown.height>=1));
    const left=Math.max(0,Math.min(innerWidth,...visibleFrames.map(f=>f.r.left))),
      right=Math.max(0,innerWidth-Math.max(0,...visibleFrames.map(f=>f.r.right)));
    const side=Math.max(right,left)>=210;
    const drawer=!side&&visibleFrames.some(f=>f.items.some(i=>i.fallback&&i.shown.width>=1&&i.shown.height>=1));
    for(const {job,r,clip,items} of frames){
      for(const {entry,patch,b,shown,lettering,fallback:unsafe} of items){
        const {region,node}=entry,{width,height}=b;
        Object.assign(node.style,{left:b.x+"px",top:b.y+"px",
          width:width+"px",height:height+"px"});
        node.style.clipPath=`inset(${Math.max(0,shown.y-b.y)}px ${Math.max(0,b.x+width-shown.x-shown.width)}px ${Math.max(0,b.y+height-shown.y-shown.height)}px ${Math.max(0,shown.x-b.x)}px)`;
        const inView=shown.width>=1&&shown.height>=1;
        node.style.visibility=original||!inView?"hidden":"visible";
        if(entry.erase){
          const hasMask=!!region.balloon?.erasePolygons;
          const eraseBox=patch?regionBox(patch.data.bbox,r,job.width,job.height):hasMask?r:regionBox(region.bbox,r,job.width,job.height),visibleErase=intersect(eraseBox,clip);
          Object.assign(entry.erase.style,{left:eraseBox.x+"px",top:eraseBox.y+"px",width:eraseBox.width+"px",height:eraseBox.height+"px",
            background:patch||hasMask?"transparent":region.balloon!.background,visibility:original||visibleErase.width<1||visibleErase.height<1?"hidden":"visible",
            clipPath:`inset(${Math.max(0,visibleErase.y-eraseBox.y)}px ${Math.max(0,eraseBox.x+eraseBox.width-visibleErase.x-visibleErase.width)}px ${Math.max(0,eraseBox.y+eraseBox.height-visibleErase.y-visibleErase.height)}px ${Math.max(0,visibleErase.x-eraseBox.x)}px)`});
        }
        // Do not turn unresolved OCR columns or uncertain artwork into tiny,
        // overlapping cards. This is a reversible reading fallback, not a
        // semantic merge or permission to erase any original source pixels.
        // A mobile drawer must not cover a second translated surface. Keep
        // the visible page's text together in that drawer; no erasure below it.
        const fallback=unsafe||drawer;
        node.dataset.readingFallback=String(fallback);
        node.classList.toggle("reading-text",fallback);
        if(fallback){
          if(!entry.note){
            entry.note=document.createElement("div");entry.note.className="reading-note";
            const label=document.createElement("small");label.textContent="Trang "+(job.page+1)+" · vùng "+([...job.regions.keys()].indexOf(region.id)+1);
            entry.note.append(label);readingNotes.append(entry.note);
            entry.marker=button(String([...job.regions.keys()].indexOf(region.id)+1),()=>{
              readingRail.open=true;entry.note!.scrollIntoView({block:"nearest"});node.focus({preventScroll:true});
            });
            entry.marker.className="source-marker";entry.marker.style.visibility="hidden";
            entry.marker.setAttribute("aria-label","Đọc bản dịch vùng "+([...job.regions.keys()].indexOf(region.id)+1));layer.append(entry.marker);
          }
          if(node.parentElement!==entry.note)entry.note.append(node);entry.note.hidden=!inView;
          node.classList.remove("integrated");if(node.textContent!==region.vi)node.textContent=region.vi!;node.dataset.overflow="false";
          node.title="Bản dịch đầy đủ · bấm để xem và sửa nguyên văn. Tranh gốc được giữ nguyên.";
          if(entry.erase)entry.erase.style.visibility="hidden";
          const source=regionBox(region.bbox,r,job.width,job.height),anchor=intersect(source,clip);
          Object.assign(entry.marker!.style,{left:Math.max(clip.x,Math.min(anchor.x,clip.x+clip.width-24))+"px",
            top:Math.max(clip.y,Math.min(anchor.y,clip.y+clip.height-24))+"px",visibility:original||!inView?"hidden":"visible"});
          if(inView)railCount++;
          continue;
        }
        if(entry.note){entry.note.hidden=true;if(node.parentElement!==layer)layer.append(node);entry.marker!.style.visibility="hidden";}
        if(entry.erase)node.classList.add("integrated");
        node.textContent=lettering.lines.join("\n");
        Object.assign(node.style,{fontSize:lettering.fontSize+"px",lineHeight:lettering.lineHeight+"px"});
        node.style.webkitTextStroke=patch?`${Math.min(1.1,lettering.fontSize*0.035)}px ${patch.data.stroke}`:"";
        node.dataset.overflow=String(lettering.overflow);
        node.title=lettering.overflow?"Bấm để xem bản dịch đầy đủ; vùng chữ này quá nhỏ.":"Bấm để xem nguyên văn và sửa bản dịch.";
      }
    }
    readingRail.hidden=railCount===0;railSummary.textContent="Bản dịch bên cạnh · "+railCount;
    // A single scrollable rail, even with several visible/prefetched images.
    // Place beside the artwork if possible; otherwise use a collapsible drawer.
    const width=side?Math.min(300,Math.max(right,left)-24):Math.min(440,innerWidth-24);
    const maxHeight=side?Math.max(80,innerHeight-170):Math.max(80,Math.floor(innerHeight*.32));
    Object.assign(readingRail.style,{width:width+"px",left:side?(right>=left?innerWidth-right+12:left-width-12)+"px":"12px",
      top:side?"12px":"",bottom:side?"":"76px",maxHeight:maxHeight+"px",visibility:original?"hidden":"visible"});
    readingNotes.style.maxHeight=Math.max(40,maxHeight-48)+"px";
    updateSecondaryHint();
  }
  function schedulePosition(){if(!raf)raf=requestAnimationFrame(position);}
  function clearJobRendering(job:Job){
    for(const {node,erase,note,marker} of job.regions.values()){node.remove();erase?.remove();note?.remove();marker?.remove();}
    for(const patch of job.patches.values()){patch.node.remove();URL.revokeObjectURL(patch.url);}
    for(const url of job.pendingPatchUrls)URL.revokeObjectURL(url);
    job.patches.clear();job.pendingPatchUrls.clear();job.patchTokens.clear();job.patchBytes=0;
    job.regions.clear();job.secondary.clear();job.terms.clear();
    if(detail&&latest===job){detail.remove();detail=undefined;}
  }
  function discard(job:Job){
    if(retryable?.job===job)clearRetry();
    clearJobRendering(job);
    jobs.delete(job.id);
    updateSecondaryHint();syncToolbarToggle();
    if(job.img){processed.delete(job.img);resizeObserver.unobserve(job.img);}
    if(!job.done)void request("cancel",{id:job.id}).catch(()=>{});
  }
  function syncSurface(job:Job,entry:Surface){
    const {region,node}=entry,patch=job.patches.get(region.id);
    // Updates can reparent a note or replace its erasure surface. Never expose
    // that intermediate state before the next positioned/clipped frame.
    node.style.visibility="hidden";
    const weak=region.reviewReasons?.some(reason=>reason==="visual_low_signal"||reason==="visual_punctuation_support"||reason==="cloud_ocr_uncertain"||reason==="cloud_page_proposal"||reason==="ocr_empty")??false;
    const key=JSON.stringify([job.width,job.height,region.overlay,region.balloon,patch?.url,weak]);
    if(entry.surfaceKey===key)return;
    entry.surfaceKey=key;entry.fitKey=undefined;entry.erase?.remove();entry.erase=undefined;
    node.className="region "+(weak?"label":region.overlay);
    node.style.color=region.balloon?.ink??"#111";node.style.webkitTextStroke="";
    if(!weak&&patch&&region.overlay==="label"){
      entry.erase=patch.node;node.classList.add("integrated","art");node.style.color=patch.data.ink;
      patch.node.style.visibility="hidden";
      layer.prepend(patch.node);
    }else if(!weak&&region.overlay==="white"&&region.balloon){
      let erase:HTMLDivElement|SVGSVGElement;
      if(region.balloon.erasePolygons){
        erase=document.createElementNS("http://www.w3.org/2000/svg","svg");erase.setAttribute("class","erase");
        erase.setAttribute("viewBox",`0 0 ${job.width} ${job.height}`);erase.setAttribute("preserveAspectRatio","none");
        for(const poly of region.balloon.erasePolygons){const path=document.createElementNS("http://www.w3.org/2000/svg","polygon");
          path.setAttribute("points",poly.map(point=>point.join(",")).join(" "));path.setAttribute("fill",region.balloon.background);erase.append(path);
        }
      }else {erase=document.createElement("div");erase.className="erase";}
      // New/replaced surfaces are invisible until positioned; a late native
      // result must not flash at its default coordinates or over original view.
      erase.style.visibility="hidden";
      erase.setAttribute("aria-hidden","true");entry.erase=erase;node.classList.add("integrated");layer.prepend(erase);
    }
    if(entry.erase)entry.erase.dataset.regionId=region.id;
  }
  async function receivePatch(job:Job,raw:unknown){
    const parsed=renderPatchSchema.safeParse(raw);
    if(!parsed.success||!active||job.invalidated||currentUrl!==location.href||!jobs.has(job.id)||parsed.data.revision!==job.revision)return;
    const {patch,width,height}=parsed.data;
    const source=job.regions.get(patch.regionId)?.region??job.secondary.get(patch.regionId);
    if(source?.reviewReasons?.some(reason=>reason==="visual_low_signal"||reason==="visual_punctuation_support"||reason==="cloud_ocr_uncertain"||reason==="cloud_page_proposal"||reason==="ocr_empty"))return;
    if((job.img&&(job.img.currentSrc!==job.src||width!==job.width||height!==job.height))||
       (!job.patchTokens.has(patch.regionId)&&job.patchTokens.size>=64))return;
    // A capture's physical pixels can be 2x its CSS anchor on HiDPI displays.
    // The native revision validates the source; do not drop every viewport
    // patch merely because its initial placeholder used CSS dimensions.
    if(!job.img){job.width=width;job.height=height;}
    const bytes=Uint8Array.from(atob(patch.dataUrl.split(",",2)[1]),c=>c.charCodeAt(0));
    if(bytes.length>384*1024||job.patchBytes+bytes.length>2*1024*1024)return;
    const url=URL.createObjectURL(new Blob([bytes],{type:"image/png"}));
    const token=Symbol();job.patchTokens.set(patch.regionId,token);job.pendingPatchUrls.add(url);job.patchBytes+=bytes.length;
    let retained=false;
    try{
      const node=new Image();node.className="erase";node.style.visibility="hidden";node.alt="";node.setAttribute("aria-hidden","true");node.src=url;
      await node.decode();
      if(!active||job.invalidated||currentUrl!==location.href||!jobs.has(job.id)||job.patchTokens.get(patch.regionId)!==token||
         (job.img&&job.img.currentSrc!==job.src)||node.naturalWidth!==patch.bbox[2]||node.naturalHeight!==patch.bbox[3])return;
      const previous=job.patches.get(patch.regionId);
      if(previous){previous.node.remove();URL.revokeObjectURL(previous.url);job.patchBytes-=previous.bytes;}
      job.patches.set(patch.regionId,{data:patch,node,url,bytes:bytes.length});job.pendingPatchUrls.delete(url);retained=true;
      const entry=job.regions.get(patch.regionId);if(entry)syncSurface(job,entry);
      schedulePosition();
    }catch{/* Invalid raster/decode: keep the reversible translation annotation. */}
    finally{if(!retained){job.pendingPatchUrls.delete(url);job.patchBytes=Math.max(0,job.patchBytes-bytes.length);URL.revokeObjectURL(url);}}
  }
  function apply(job:Job,result:any){
    if(!active||job.invalidated||currentUrl!==location.href||result.revision!==job.revision||!jobs.has(job.id))return;
    if(job.img&&job.img.currentSrc!==job.src){discard(job);return;}
    job.width=result.width??job.width;job.height=result.height??job.height;
    if(Array.isArray(result.termSuggestions))for(const term of result.termSuggestions)
      if(typeof term.entity==="string"&&typeof term.ja==="string"&&typeof term.vi==="string"&&Array.isArray(term.region_ids)&&!confirmedTerms.has(termKey(term.entity)))job.terms.set(term.entity,term);
    if(!Array.isArray(result.regions))return;
    for(const raw of result.regions){
      const parsed=regionSchema.safeParse(raw);
      if(!parsed.success)continue;
      const region=parsed.data;
      if(region.reviewReasons?.some(reason=>reason==="visual_low_signal"||reason==="visual_punctuation_support"||reason==="cloud_ocr_uncertain"||reason==="cloud_page_proposal"||reason==="ocr_empty")){
        // An earlier cleanup event must not grant erasure to a later weak
        // source result. Invalidate pending decode and free any retained art.
        job.patchTokens.delete(region.id);
        const previous=job.patches.get(region.id);
        if(previous){previous.node.remove();URL.revokeObjectURL(previous.url);job.patchBytes-=previous.bytes;job.patches.delete(region.id);}
      }
      if(region.scope?.action==="defer"){
        const previous=job.regions.get(region.id);
        if(previous){previous.node.remove();previous.erase?.remove();previous.note?.remove();previous.marker?.remove();job.regions.delete(region.id);}
        job.secondary.set(region.id,region);continue;
      }
      if(!region.vi)continue;
      job.secondary.delete(region.id);
      const existing=job.regions.get(region.id);
      const node=existing?.node??document.createElement("button");node.type="button";
      if(!existing)node.style.visibility="hidden";
      const entry=existing??{region,node};entry.region=region;entry.fitKey=undefined;
      node.textContent=region.vi!;node.dataset.regionId=region.id;node.dataset.review=String(region.review||region.ambiguous);
      node.setAttribute("aria-label","Xem và sửa bản dịch: "+region.vi);
      if(!existing){node.addEventListener("click",()=>openDetail(job,region.id));layer.append(node);job.regions.set(region.id,entry);}
      syncSurface(job,entry);
    }
    schedulePosition();renderVisibility();
  }
  function secondaryJob(){return [...jobs.values()].find(job=>job.done&&job.secondary.size&&(job.img?visible(job.img):job===latest));}
  function updateSecondaryHint(){
    const job=secondaryJob();secondaryButton.hidden=!job;
    secondaryButton.textContent="Chữ phụ"+(job?" · "+job.secondary.size:"");
    syncToolbarToggle();
  }
  function openSecondary(){
    const job=secondaryJob();if(!job)return;
    autoCompactPending=false;detail?.remove();
    const panel=document.createElement("div");panel.className="detail";detail=panel;
    const title=document.createElement("strong");title.textContent="Chữ phụ · nguyên bản được giữ lại";
    const note=document.createElement("p");note.textContent="Chú thích và các vùng chưa đọc chắc được giữ nguyên ở đây. Với vùng OCR rỗng, hãy sửa chữ Nhật trước khi dịch. Chỉ dịch khi bạn chọn; BYOK có thể tính phí. Không đưa chúng vào bộ nhớ cốt truyện.";
    panel.append(title,note);
    for(const region of job.secondary.values())panel.append(button(region.ja.trim()?region.ja.slice(0,160):"Chưa đọc được chữ · "+region.id,()=>openDetail(job,region.id)));
    panel.append(button("Đóng",()=>panel.remove()));shadow.append(panel);
  }
  function updateTermHint(){
    termHint.replaceChildren();termHint.hidden=true;pendingTermCount=0;
    const job=[...jobs.values()].find(j=>j.done&&[...j.terms.values()].some(t=>!deferredTerms.has(termKey(t.entity)))&&(j.img?visible(j.img):j===latest));
    if(!job){syncToolbarToggle();return;}
    const term=[...job.terms.values()].find(t=>!deferredTerms.has(termKey(t.entity)));if(!term){syncToolbarToggle();return;}
    termHint.hidden=false;pendingTermCount=1;syncToolbarToggle();
    termHint.append(button("Tên “"+term.vi+"” ổn chưa?",()=>openDetail(job,term.region_ids[0])));
  }
  function openDetail(job:Job,id:string){
    const item=job.regions.get(id),secondary=job.secondary.get(id);
    const region=item?.region??secondary;if(!region||!config)return;
    autoCompactPending=false;
    detail?.remove();const panel=document.createElement("div");panel.className="detail";detail=panel;
    const title=document.createElement("strong");title.textContent=(secondary?"Chữ phụ · ":"Bản dịch · ")+id;
    const vi=document.createElement("p");vi.className="vi";vi.textContent=region.vi??"Chưa dịch · chọn bên dưới để dịch riêng. BYOK có thể tính phí; không lưu vào bộ nhớ cốt truyện.";
    const label=document.createElement("label");label.textContent="Chữ Nhật (có thể sửa)";
    const input=document.createElement("textarea");input.value=region.ja;input.rows=3;input.maxLength=700;
    const speaker=document.createElement("input"),listener=document.createElement("input");
    speaker.placeholder="ID người nói, ví dụ nana";speaker.value=region.speaker??"unknown";
    listener.placeholder="ID người nghe";listener.value=region.listener??"unknown";
    const speakerLabel=document.createElement("label");speakerLabel.textContent="Người nói / người nghe · để unknown nếu chưa rõ";
    const speakerTools=document.createElement("details");speakerTools.className="speaker-tools";
    const speakerToggle=document.createElement("summary");speakerToggle.textContent="Người nói / người nghe · tùy chọn";
    speakerTools.append(speakerToggle,speakerLabel,speaker,listener);
    if(region.speakerBindingReview){
      const note=document.createElement("p");note.className="speaker-binding-note";
      note.textContent="Xưng hô cũ không khớp chắc chắn vùng này nên chưa áp dụng. Xác nhận lại (có thể để unknown); lựa chọn cũ vẫn được giữ.";
      speakerTools.append(note);speakerTools.open=true;
    }
    const feedback=document.createElement("div");feedback.setAttribute("role","status");
    const retry=button(secondary?"Dịch riêng vùng này":"Lưu & dịch lại",()=>void(async()=>{
        if(!input.value.trim()){feedback.textContent="Chưa có chữ Nhật để dịch. Hãy đối chiếu ảnh gốc và nhập lại chữ trước.";input.focus();return;}
        retry.disabled=true;feedback.textContent="Đang dịch lại…";
      try{
        const params={storyId:config!.storyId,pageId:job.pageId,revision:job.revision,regionId:id,at:{chapter:config!.at.chapter,page:job.page}};
        if(region.speakerBindingReview||speaker.value!==(region.speaker??"unknown")||listener.value!==(region.listener??"unknown"))
          await request("speaker.set",{...params,speaker:speaker.value||"unknown",listener:listener.value||"unknown"});
        const value=await request("retranslate",{...params,ja:input.value,recoverDeferred:!!secondary});
        if(!active||!jobs.has(job.id))return;
        const expression=expressionSchema.safeParse(value.expression);
        const scope=scopeSchema.safeParse(value.scope);
        if(secondary&&(!scope.success||scope.data.action!=="translate"||scope.data.memory))
          throw new Error("Companion chưa hỗ trợ phục hồi chữ phụ an toàn. Giữ nguyên nguồn; cập nhật companion trước.");
        apply(job,{revision:job.revision,regions:[{...region,ja:input.value,vi:value.vi,ambiguous:value.ambiguous,
          speaker:speaker.value||"unknown",listener:listener.value||"unknown",speakerBindingReview:false,expression:expression.success?expression.data:undefined,
          scope:scope.success?scope.data:region.scope}]});
        updateSecondaryHint();vi.textContent=value.vi;feedback.textContent=secondary?"Đã dịch chữ phụ; không đưa vào bộ nhớ cốt truyện.":"Đã cập nhật. Bộ nhớ phụ thuộc đã được đánh dấu cần làm lại.";
        panel.querySelector(".speaker-binding-note")?.remove();
        if(secondary)retry.textContent="Dịch lại chữ phụ";
        position();
      }catch(error){feedback.textContent=String(error instanceof Error?error.message:error);}
      finally{retry.disabled=false;}
    })());
    panel.append(title,vi,label,input,speakerTools);shadow.append(panel);
    if(region.reviewReasons?.length){
      const note=document.createElement("p");note.setAttribute("role","note");
        const labels={quote_balance:"dấu ngoặc chưa khép",repetition:"chữ lặp bất thường",length:"đoạn chữ quá dài",detector_low_score:"vùng chữ khó nhận diện",layout_fragment:"vùng chữ đã tách để tránh gộp nhầm",layout_cluster:"các cột/dòng chữ được gom theo bố cục",visual_low_signal:"nét chữ quá yếu để tự ghi nhớ",visual_punctuation_support:"dấu chấm có thể là nét tranh hoặc bị cắt; cần kiểm tra ảnh gốc",ocr_crop_partition:"đã tách crop OCR để tránh dính cột; cần đối chiếu ảnh gốc",cloud_ocr_uncertain:"OCR cloud chưa chắc ký tự; giữ ảnh gốc và không tự ghi nhớ",cloud_page_proposal:"vùng do OCR cloud đề xuất; chưa được cấp quyền xóa nền",ocr_empty:"recognizer chưa đọc được chữ; giữ nguyên vùng để bạn kiểm tra và sửa"};
      note.textContent="OCR cần đối chiếu: "+region.reviewReasons.map(reason=>labels[reason]).join(", ")+". Đây là dấu hiệu cần kiểm tra, không phải kết luận OCR sai.";
      if(region.scope?.reason==="visual_review")note.textContent+=region.scope.action==="defer"?" Vùng này chưa được dịch hoặc xóa chữ; có thể sửa OCR để dịch riêng.":" Vùng này vẫn được dịch nhưng chưa đưa vào bộ nhớ truyện hoặc tự chốt thuật ngữ; sửa OCR không tự xác nhận chất lượng ảnh.";
      panel.insertBefore(note,label);
    }
    for(const term of job.terms.values())if(term.region_ids.includes(id)){
      const check=document.createElement("section"),prompt=document.createElement("p"),edit=document.createElement("input");
      prompt.textContent="Tên riêng này ổn chưa? "+term.ja+" → "+term.vi;
      const advisory=document.createElement("p");advisory.className="name-review";advisory.setAttribute("role","note");
      const refreshAdvisory=(value:string)=>{const note=nameReviewNote(value);advisory.textContent=note??"";advisory.hidden=!note;};
      refreshAdvisory(term.vi);
      edit.value=term.vi;edit.maxLength=120;edit.setAttribute("aria-label","Tên Việt bạn muốn dùng");edit.hidden=true;
      edit.addEventListener("input",()=>refreshAdvisory(edit.value));
      const response=document.createElement("div");response.setAttribute("role","status");
      const confirm=button("Đúng · nhớ tên này",()=>void save(term.vi)),change=button("Đổi cách gọi",()=>{
        edit.hidden=false;saveEdit.hidden=false;cancelEdit.hidden=false;confirm.hidden=true;change.hidden=true;edit.focus();
      }),saveEdit=button("Lưu tên đã sửa",()=>void save(edit.value.trim())),cancelEdit=button("Hủy sửa tên",()=>{
        edit.hidden=true;saveEdit.hidden=true;cancelEdit.hidden=true;confirm.hidden=false;change.hidden=false;
        edit.value=term.vi;refreshAdvisory(term.vi);change.focus();
      });saveEdit.hidden=true;cancelEdit.hidden=true;
      async function save(value:string){
        confirm.disabled=true;saveEdit.disabled=true;
        const storyId=config!.storyId;
        try{
          if(!job.done)throw new Error("Chờ trang dịch xong để xác nhận tên.");
          await request("term.confirm",{storyId,pageId:job.pageId,revision:job.revision,
            entity:term.entity,vi:value,at:{chapter:config!.at.chapter,page:job.page}});
          if(!active||config?.storyId!==storyId||!jobs.has(job.id))return;
          confirmedTerms.add(termKey(term.entity));
          for(const current of jobs.values())current.terms.delete(term.entity);
          updateTermHint();
          response.textContent=value===term.vi?"Đã xác nhận. Có thể sửa lại trong Thư viện.":"Đã chốt tên mới. Bấm Lưu & dịch lại để cập nhật bóng này; có thể sửa trong Thư viện.";
          confirm.remove();change.remove();saveEdit.remove();cancelEdit.remove();edit.remove();
        }catch(error){response.textContent=error instanceof Error?error.message:String(error);confirm.disabled=false;saveEdit.disabled=false;}
      }
      const later=button("Để sau · đọc tiếp",()=>{deferredTerms.add(termKey(term.entity));updateTermHint();panel.remove();});
      check.append(prompt,advisory,edit,confirm,change,saveEdit,cancelEdit,later,response);panel.append(check);
    }
    const actions=document.createElement("div");actions.className="detail-actions";
    actions.append(retry,button("Đóng",()=>panel.remove()),feedback);panel.append(actions);
  }
  async function read(){
    const current=[...jobs.values()].filter(j=>j.done&&(j.img?visible(j.img):j===latest))
      .sort((a,b)=>a.page-b.page).at(-1);
    if(!config||!current){say("Chờ trang đang nhìn dịch xong trước khi đánh dấu đã đọc.");return;}
    try{
      const result=await request("memory.read",{storyId:config.storyId,pageId:current.pageId,revision:current.revision,at:{chapter:config.at.chapter,page:current.page}});
      say(result.summary?.enabled?"Đã lưu tiến độ · tóm tắt đã xếp hàng, xử lý khi máy rảnh.":
        "Đã lưu tiến độ · tóm tắt tự động đang tắt. Có thể tạo thủ công trong Thư viện.");
    }catch(error){say(String(error instanceof Error?error.message:error));}
  }
  async function imageData(img:HTMLImageElement){
    const max=2400,scale=Math.min(1,max/Math.max(img.naturalWidth,img.naturalHeight));
    const canvas=document.createElement("canvas");canvas.width=Math.round(img.naturalWidth*scale);canvas.height=Math.round(img.naturalHeight*scale);
    const ctx=canvas.getContext("2d",{alpha:false})!;ctx.drawImage(img,0,0,canvas.width,canvas.height);
    // Lossless PNG, as before, but do not block scrolling/input while encoding.
    const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error("Không mã hóa được ảnh.")),"image/png"));
    const dataUrl=await new Promise<string>((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>typeof reader.result==="string"?resolve(reader.result):reject(new Error("Không đọc được ảnh đã mã hóa."));
      reader.onerror=()=>reject(new Error("Không đọc được ảnh đã mã hóa."));
      reader.readAsDataURL(blob);
    });
    return {dataUrl,width:canvas.width,height:canvas.height};
  }
  async function process(img?:HTMLImageElement,selected?:DOMRect,prefetched=false){
    if(!active||!config||busy)return;
    busy=true;
    if(!prefetched)clearRetry();
    else retryButton.disabled=true;
    const localConfig=config,url=currentUrl;
    const id=crypto.randomUUID(),revision=crypto.randomUUID();
    const images=candidates();
    const page=img?config.at.page+Math.max(0,images.indexOf(img)):config.at.page;
    const rect=selected??(img?imageRect(img):new DOMRect(0,0,innerWidth,innerHeight));
    const job:Job={id,pageId:await stableId(url+"|"+(img?.currentSrc??[page,rect.x+scrollX,rect.y+scrollY].join("|")),"p"),
      revision,img,src:img?.currentSrc,rect,scrollX,scrollY,width:rect.width,height:rect.height,page,prefetched,regions:new Map(),secondary:new Map(),done:false,terms:new Map(),
      patches:new Map(),patchBytes:0,pendingPatchUrls:new Set(),patchTokens:new Map()};
    if(img){pending.add(img);failed.delete(img);}
    jobs.set(id,job);if(!prefetched)latest=job;
    if(img)resizeObserver.observe(img);
    // Bound DOM nodes and image references. A pruned page can be restored from
    // the local text cache on revisit; no image pixels are persisted.
    while(jobs.size>6){const old=[...jobs.values()].find(j=>j.done&&j.img&&!visible(j.img));if(!old)break;discard(old);}
    say(prefetched?"Đang chuẩn bị ảnh tiếp theo…":"Đang đọc chữ Nhật…");
    try{
      let data:any;
      try{if(!img)throw new Error("viewport");data=await imageData(img);job.width=data.width;job.height=data.height;}
      catch{
        if(prefetched)throw new Error("Ảnh tiếp theo không đọc được trực tiếp; sẽ xử lý khi hiện trên màn hình.");
        // Only the visible portion is capturable. Crop follows its own viewport anchor.
        const clipped=new DOMRect(Math.max(0,rect.x),Math.max(0,rect.y),
          Math.max(0,Math.min(innerWidth,rect.right)-Math.max(0,rect.x)),Math.max(0,Math.min(innerHeight,rect.bottom)-Math.max(0,rect.y)));
        if(clipped.width<10||clipped.height<10)throw new Error("Vùng cần đọc chưa xuất hiện trên màn hình.");
        job.img=undefined;job.rect=clipped;job.width=clipped.width;job.height=clipped.height;
        root.style.visibility="hidden";
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        data={capture:{rect:{x:clipped.x,y:clipped.y,width:clipped.width,height:clipped.height},
          viewport:{width:innerWidth,height:innerHeight},epoch:{scrollX,scrollY,url}}};
      }
      // Encoding/capture can yield. A stop/navigation/source replacement in
      // that interval must not submit a stale image or start a paid request.
      if(!active||config!==localConfig||currentUrl!==url||location.href!==url||!jobs.has(job.id))return;
      if(img&&(!img.isConnected||img.currentSrc!==job.src)){discard(job);return;}
      const result=await request("image",{...data,id,pageId:job.pageId,revision,storyId:localConfig.storyId,title:localConfig.title,
        at:{chapter:localConfig.at.chapter,page}});
      if(!active||config!==localConfig||currentUrl!==url||location.href!==url||!jobs.has(job.id))return;
      if(img&&(!img.isConnected||img.currentSrc!==job.src)){discard(job);return;}
      apply(job,result);job.done=true;updateTermHint();updateSecondaryHint();
      if(img)processed.set(img,img.currentSrc);
      const count=job.regions.size,seconds=(result.metrics?.total_ms??result.metrics?.cache_ms??0)/1000;
      say(prefetched?"Ảnh tiếp theo đã sẵn sàng · chưa đánh dấu đã đọc.":count?("Đã dịch "+count+" vùng"+(result.cached?" · từ cache":" · "+seconds.toFixed(1)+" giây")+". Bấm bóng để sửa."):"Chưa tìm được chữ. Dùng Chọn vùng.");
      // One automatic collapse after the first useful result, on any viewport.
      // A reader-opened toolbar/detail stays open through later page/prefetch
      // completions. Empty/error states keep their recovery controls visible.
      if(autoCompactPending&&!prefetched&&count>0&&!detail&&!selection){autoCompactPending=false;setToolbarCompact(true);}
      await readIfAlreadyVisible(job);
    }catch(error){
      if(!active||config!==localConfig||currentUrl!==url||location.href!==url||!jobs.has(job.id))return;
      if(img&&(!img.isConnected||img.currentSrc!==job.src)){discard(job);return;}
      if(error instanceof TaskError&&error.code==="STALE_CONTEXT"){
        // Keep the source anchor/retry identity, not obsolete partial text or
        // erasure. Invalidating tokens also stops asynchronous patch decode.
        job.invalidated=true;clearJobRendering(job);updateTermHint();updateSecondaryHint();
      }
      if(img&&!prefetched)failed.set(img,img.currentSrc);
      else if(img)failed.set(img,"prefetch:"+img.currentSrc);
      if(!prefetched){
        autoCompactPending=false;setToolbarCompact(false);
        retryable={job,img,config:localConfig,url};retryButton.hidden=false;
        modelSettings.hidden=!(error instanceof TaskError&&["TRUNCATED","MODEL_FORMAT","MODEL_OUTPUT","TERM_MISMATCH","NO_KEY","KEY_INVALID","QUOTA"].includes(error.code??""));
        say(translationFailureNotice(error));
      }else{
        // A background failure must not replace the current page's status or
        // expose a retry for an unseen page. Revisit once when it is visible.
        discard(job);
        say("Ảnh tiếp theo chưa sẵn sàng · sẽ thử khi bạn cuộn tới.");
      }
    }finally{
      root.style.visibility="visible";busy=false;if(img)pending.delete(img);
      retryButton.disabled=!retryable;
      // A new session may have been started while the old canceled request
      // settled. Wake the CURRENT session, not the captured old config.
      if(active)queueScan(Boolean(queuedSelection)||config!==localConfig);
    }
  }
  async function readIfAlreadyVisible(job:Job){
    // Displaying/prefetching is not evidence the user read the page.
    // Explicit "Đã đọc" is required in the MVP.
    return job;
  }
  function queueScan(immediate=false){
    // Explicit reader intent should not wait behind a scroll/layout debounce.
    // Observers must not postpone that queued intent or duplicate its request.
    if(immediateScanPending&&!immediate)return;
    if(debounce)clearTimeout(debounce);
    immediateScanPending=immediate;
    debounce=setTimeout(()=>{
      debounce=undefined;immediateScanPending=false;
      if(!active||busy||document.hidden||!config)return;
      if(location.href!==currentUrl){stop("Trang/chapter đã đổi. Bấm extension để tiếp tục.");return;}
      if(selection)return;
      if(queuedSelection){
        const target=queuedSelection;queuedSelection=undefined;
        if(target.config!==config||target.url!==location.href||target.scrollX!==scrollX||target.scrollY!==scrollY||
           target.width!==innerWidth||target.height!==innerHeight){
          say("Vùng đã cuộn hoặc đổi bố cục trong lúc chờ. Chọn lại vùng cần dịch.");return;
        }
        void process(undefined,target.rect);return;
      }
      if(!config.autoScan)return;
      if(retryable){
        const {job,img}=retryable;
        if(img&&(!img.isConnected||img.currentSrc!==job.src))discard(job);
        else return; // Keep recovery stable; no implicit extra paid request.
      }
      const images=candidates();
      const img=images.find(i=>visible(i)&&processed.get(i)!==i.currentSrc&&failed.get(i)!==i.currentSrc&&!pending.has(i));
      if(img){void process(img);return;}
      if(config.prefetch){
        let lastVisible=-1;for(let index=0;index<images.length;index++)if(visible(images[index]))lastVisible=index;
        const next=lastVisible>=0?images.slice(lastVisible+1,lastVisible+3).find(i=>processed.get(i)!==i.currentSrc
          &&failed.get(i)!=="prefetch:"+i.currentSrc&&failed.get(i)!==i.currentSrc&&!pending.has(i)):undefined;
        if(next)void process(next,undefined,true);
      }
    },immediate?0:220);
  }
  function select(){
    if(!active)return;
    queuedSelection=undefined;
    autoCompactPending=false;setToolbarCompact(false);
    selection?.remove();detail?.remove();
    const overlay=document.createElement("div");overlay.className="selection";
    const box=document.createElement("div");box.className="selection-box";overlay.append(box);shadow.append(overlay);selection=overlay;
    let startX=0,startY=0;
    overlay.addEventListener("pointerdown",event=>{
      startX=event.clientX;startY=event.clientY;overlay.setPointerCapture(event.pointerId);
    });
    overlay.addEventListener("pointermove",event=>{
      if(!overlay.hasPointerCapture(event.pointerId))return;
      Object.assign(box.style,{left:Math.min(startX,event.clientX)+"px",top:Math.min(startY,event.clientY)+"px",
        width:Math.abs(startX-event.clientX)+"px",height:Math.abs(startY-event.clientY)+"px"});
    });
    overlay.addEventListener("pointerup",event=>{
      const rect=new DOMRect(Math.min(startX,event.clientX),Math.min(startY,event.clientY),Math.abs(startX-event.clientX),Math.abs(startY-event.clientY));
      overlay.remove();selection=undefined;
      if(rect.width>10&&rect.height>10&&config){
        for(const job of jobs.values())discard(job);
        queuedSelection={rect,config,url:location.href,scrollX,scrollY,width:innerWidth,height:innerHeight};
        say(busy?"Đang hủy tác vụ trước · vùng bạn chọn sẽ được dịch tiếp theo…":"Đang chuẩn bị vùng đã chọn…");
        queueScan(true);
      }
    });
    say("Kéo chọn bóng thoại hoặc vùng cần dịch. Esc để hủy.");
  }
  function stop(reason="Đã dừng dịch."){
    active=false;config=undefined;if(debounce)clearTimeout(debounce);
    debounce=undefined;immediateScanPending=false;
    queuedSelection=undefined;
    clearRetry();for(const img of candidates())failed.delete(img);
    for(const job of jobs.values())discard(job);detail?.remove();selection?.remove();say(reason);
    readingRail.hidden=true;
    termHint.hidden=true;termHint.replaceChildren();
    pendingTermCount=0;setToolbarCompact(false);
    if(reason==="Đã dừng dịch.")root.style.display="none";
  }
  function start(newConfig:ReaderConfig){
    stop();config=newConfig;active=true;currentUrl=location.href;root.style.display="block";root.style.visibility="visible";
    autoCompactPending=true;
    heading.textContent=newConfig.title+" · chap "+newConfig.at.chapter;
    say("Sẵn sàng · đang tìm ảnh manga.");
    queueScan(true);
  }
  chrome.runtime.onMessage.addListener((message,_sender,reply)=>{
    if(message.type==="start"){
      if(message.expectedUrl!==location.href){reply({started:false,error:"Trang đọc đã đổi."});return;}
      start(message.config);reply({started:true});
    }
    if(message.type==="stop"){stop(message.reason);reply({});}
    if(message.type==="select"){select();reply({});}
    if(message.type==="result"){
      const job=jobs.get(message.id);if(!job||job.invalidated)return;
      if(message.event==="render-patch")void receivePatch(job,message.result);
      if(message.event==="translated")apply(job,message.result);
      if(message.event==="progress"&&!job.prefetched){
        const {stage,total,mode}=message.result;
        say(stage==="detector"?"Đang nhận diện vùng chữ · lần đầu cần nạp model…":stage==="translation"
          ?`Đang dịch ${mode==="byok"?"cloud":"local trên CPU"} · ${total} vùng…`
          :"Đang đọc chữ · "+total+" vùng…");
      }
      if(message.event==="regions"&&!job.prefetched)say("Đang dịch "+message.result.regions.length+" vùng…");
    }
    if(message.type==="crop"){
      void(async()=>{
        const e=message.epoch;
        if(e.url!==location.href||e.scrollX!==scrollX||e.scrollY!==scrollY)throw new Error("stale");
        const response=await fetch(message.dataUrl),bitmap=await createImageBitmap(await response.blob());
        const scaleX=bitmap.width/message.viewport.width,scaleY=bitmap.height/message.viewport.height;
        const r=message.rect,canvas=document.createElement("canvas");
        canvas.width=Math.round(r.width*scaleX);canvas.height=Math.round(r.height*scaleY);
        canvas.getContext("2d")!.drawImage(bitmap,r.x*scaleX,r.y*scaleY,r.width*scaleX,r.height*scaleY,0,0,canvas.width,canvas.height);
        bitmap.close();return {dataUrl:canvas.toDataURL("image/png")};
      })().then(value=>{root.style.visibility="visible";reply(value);},()=>{root.style.visibility="visible";reply({error:"stale"});});
      return true;
    }
  });
  addEventListener("scroll",event=>{
    if(event.target!==document)for(const job of jobs.values())if(!job.img)discard(job);
    schedulePosition();queueScan();updateTermHint();
  },{passive:true,capture:true});
  addEventListener("resize",()=>{
    for(const job of jobs.values())if(!job.img)discard(job);
    schedulePosition();queueScan();
  },{passive:true});
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)queueScan();});
  document.addEventListener("load",event=>{if(event.target instanceof HTMLImageElement)queueScan();},true);
  document.addEventListener("keydown",event=>{
    if(event.key==="Escape"){selection?.remove();detail?.remove();}
    if(event.altKey&&event.key.toLowerCase()==="t"){original=!original;renderVisibility();}
  });
  new MutationObserver(records=>{if(active){
    if(records.some(r=>!(r.target as Element).closest?.("[data-mangalive]")))
      for(const job of jobs.values())if(!job.img)discard(job);
    schedulePosition();queueScan();
  }}).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:["src","srcset","style","class","width","height"]});
  window.__mangaLive={start,stop};
  root.style.display="none";
}
