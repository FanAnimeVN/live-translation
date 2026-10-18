// Repeatable rendered content-script QA. Native/OCR/LLM are deliberately mocked;
// scripts/native_smoke.py independently exercises the real companion pipeline.
import {chromium} from "playwright";
import {spawn} from "node:child_process";
import {mkdir} from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const retryOnly=process.argv.includes("--retry-only");
const output=process.env.MANGALIVE_QA_OUTPUT??path.join(os.tmpdir(),"mangalive-ui-qa");
await mkdir(output,{recursive:true});
const fixture=spawn(path.join(root,".venv/Scripts/python.exe"),[path.join(root,"scripts/fixture_server.py")],{cwd:root,stdio:["ignore","pipe","pipe"],windowsHide:true});
let browser;
const ramScreenshots=[];
async function capture(page,label){
  ramScreenshots.push({label,mimeType:"image/jpeg",data:(await page.screenshot({type:"jpeg",quality:75})).toString("base64")});
}
try{
  const url=await new Promise((resolve,reject)=>{
    let pending="";const timer=setTimeout(()=>reject(new Error("Fixture did not start")),15000);
    fixture.stdout.on("data",chunk=>{pending+=chunk;const newline=pending.indexOf("\n");if(newline>=0){clearTimeout(timer);resolve(JSON.parse(pending.slice(0,newline)).url);}});
    fixture.on("exit",code=>{clearTimeout(timer);reject(new Error("Fixture exited: "+code));});
  });
  const edgeArg=process.argv.indexOf("--edge-executable");
  browser=await chromium.launch({...(edgeArg>=0?{executablePath:process.argv[edgeArg+1]}:{channel:"msedge"}),headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  await page.route("**/assets/PatrickHand-Regular.ttf",route=>route.fulfill({path:path.join(root,"dist/extension/assets/PatrickHand-Regular.ttf"),contentType:"font/ttf"}));
  page.on("pageerror",error=>errors.push(error.message));
  page.on("console",message=>{if(message.type()==="error")errors.push(message.text());});
  await page.addInitScript(()=>{
    window.__qaCalls=[];window.__qaRoots=[];window.__qaSummaryEnabled=false;
    window.__qaScanTimers=[];
    const nativeToBlob=HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob=function(callback,...args){
      return nativeToBlob.call(this,blob=>{
        if(window.__qaHoldEncode){
          window.__qaEncodePending=true;window.__qaReleaseEncode=()=>callback(blob);
        }else callback(blob);
      },...args);
    };
    const nativeTimeout=window.setTimeout.bind(window);
    window.setTimeout=(fn,delay,...args)=>{
      if(!window.__qaUserStart||(delay!==0&&delay!==220))return nativeTimeout(fn,delay,...args);
      const entry={delay,queued:performance.now()-window.__qaUserStart};window.__qaScanTimers.push(entry);
      return nativeTimeout(()=>{entry.fired=performance.now()-window.__qaUserStart;fn(...args);},delay);
    };
    window.__qaBlobUrls=new Set();
    const createUrl=URL.createObjectURL.bind(URL),revokeUrl=URL.revokeObjectURL.bind(URL);
    URL.createObjectURL=function(blob){const url=createUrl(blob);window.__qaBlobUrls.add(url);return url;};
    URL.revokeObjectURL=function(url){window.__qaBlobUrls.delete(url);return revokeUrl(url);};
    const decode=HTMLImageElement.prototype.decode;
    HTMLImageElement.prototype.decode=async function(){
      await decode.call(this);
      if(window.__qaHoldPatchDecode&&this.classList.contains("erase")){
        window.__qaPendingDecode=true;
        await new Promise(resolve=>{window.__qaReleasePatchDecode=resolve;});
      }
    };
    const attach=Element.prototype.attachShadow;
    Element.prototype.attachShadow=function(options){const shadow=attach.call(this,options);window.__qaRoots.push(shadow);return shadow;};
    window.chrome={runtime:{getURL(resource){return new URL(resource,location.origin+"/").href;},onMessage:{addListener(fn){window.__qaReceiver=fn;}},async sendMessage(message){
      window.__qaCalls.push(message);
      if(message.op==="image"){
        window.__qaFirstImageAt??=performance.now();
        const number=window.__qaCalls.filter(c=>c.op==="image").length;
        const fail=window.__qaFailNextImage||number===window.__qaFailImageNumber;window.__qaFailNextImage=false;
        await new Promise(r=>setTimeout(r,window.__qaImageDelayMs??35));
        const p=message.params;
        if(fail)return {ok:false,error:window.__qaFailCode?"Bản dịch quá dài. Hãy chọn vùng nhỏ hơn.":"Lỗi mạng kiểm thử · không tự chuyển cloud.",code:window.__qaFailCode};
        if(window.__qaStaleNextImage){
          window.__qaStaleNextImage=false;
          const partial={revision:p.revision,width:800,height:1050,regions:[{
            id:"r000",ja:"氷結結界を展開する！",vi:"Bản dịch theo tên cũ",bbox:[455,120,285,100],overlay:"label"}]};
          const canvas=document.createElement("canvas");canvas.width=40;canvas.height=40;
          canvas.getContext("2d").fillRect(0,0,40,40);
          const patch={revision:p.revision,width:800,height:1050,patch:{regionId:"r000",bbox:[455,120,40,40],
            dataUrl:canvas.toDataURL("image/png"),ink:"#111111",stroke:"#ffffff",sourceFontPx:20,method:"opencv-telea-v1"}};
          window.__qaLateStale={id:p.id,partial,patch};
          window.__qaReceiver({type:"result",id:p.id,event:"translated",result:partial},{},()=>{});
          window.__qaReceiver({type:"result",id:p.id,event:"render-patch",result:patch},{},()=>{});
          await new Promise(resolve=>{window.__qaReleaseStale=resolve;});
          return {ok:false,error:"Ngữ cảnh vừa đổi; dịch lại trang để dùng lựa chọn mới.",code:"STALE_CONTEXT"};
        }
        return {ok:true,result:{revision:p.revision,width:800,height:1050,cached:false,metrics:{total_ms:35},
          // Explicit authored flat-balloon geometry for the integrated
          // transform test. Missing/unsafe surfaces use the rail, tested below
          // and independently by private-render-replay; these are not real masks.
          regions:[{id:"r000",ja:"姉ちゃん、まだ帰らないの？",vi:"Nee-chan, chưa về à?",bbox:[455,120,285,window.__qaSmallRegions?24:100],overlay:"white",
            balloon:{textBox:[455,120,285,window.__qaSmallRegions?24:100],background:"#ffffff",erasePolygons:[[[455,120],[740,120],[740,window.__qaSmallRegions?144:220],[455,window.__qaSmallRegions?144:220]]]},
            speaker:"unknown",listener:"unknown",speakerBindingReview:!!window.__qaSpeakerReview,review:true,reviewReasons:["quote_balance","layout_fragment","layout_cluster"]},
            {id:"r001",ja:"氷結結界を展開する！",vi:window.__qaCorrectedContext?"Triển khai Kết giới băng giá!":"Triển khai Băng Kết Kết Giới!",bbox:[455,550,285,100],overlay:"white",
              balloon:{textBox:[455,550,285,100],background:"#ffffff",erasePolygons:[[[455,550],[740,550],[740,650],[455,650]]]}},
            ...(window.__qaSecondary?[{id:"r002",ja:window.__qaUnreadable?"":"作者コメント",bbox:[100,820,40,100],overlay:"label",
              ...(window.__qaUnreadable?{review:true,reviewReasons:["ocr_empty"]}:{}),
              scope:{v:1,key:"scope-a",group:"scope-b",role:window.__qaUnreadable?"unknown":"editorial",action:"defer",reason:window.__qaUnreadable?"visual_review":"editorial_marker",memory:false}}]:[]),
            ...(window.__qaWeak?[{id:"r003",ja:"魔法団",vi:"Ma pháp đoàn",bbox:[100,820,23,22],overlay:"white",
              balloon:{textBox:[100,820,23,22],background:"#ffffff",erasePolygons:[[[100,820],[123,820],[123,842],[100,842]]]},
              review:true,reviewReasons:[window.__qaVisualReason??"visual_low_signal"],
              scope:{v:1,key:"scope-weak",group:"scope-weak",role:"unknown",action:"translate",reason:"visual_review",memory:false}}]:[])],
          termSuggestions:window.__qaCorrectedContext?[]:[{entity:"ice",ja:"氷結結界",vi:"Băng Kết Kết Giới",category:"skill",origin:"auto",aliases:[],region_ids:["r001"]}]}};
      }
      if(message.op==="retranslate")return {ok:true,result:{id:message.params.regionId,vi:"Cảm ơn.",ambiguous:false,
        ...(message.params.recoverDeferred?{scope:{v:1,key:"scope-a",group:"scope-b",role:"editorial",action:"translate",reason:"reader",memory:false}}:{})}};
      if(message.op==="memory.read")return {ok:true,result:{summary:{enabled:window.__qaSummaryEnabled,pending:1}}};
      return {ok:true,result:{}};
    }}};
  });
  await page.goto(url);await page.waitForFunction(()=>document.images[0]?.complete);
  assert.match(await page.title(),/Chapter 1/);assert(await page.locator("h1").isVisible());
  await page.addScriptTag({path:path.join(root,"dist/extension/content.js")});
  await page.waitForFunction(()=>[...document.fonts].some(font=>font.family==="MangaLiveLettering"&&font.status==="loaded"));
  const staleStart=await page.evaluate(()=>{
    let reply;
    window.__qaReceiver({type:"start",expectedUrl:location.href+"?old-page",config:{storyId:"wrong",title:"Wrong",at:{chapter:90,page:0},autoScan:true,prefetch:false}}, {},value=>reply=value);
    return {reply,calls:window.__qaCalls.length,visible:window.__qaRoots[0].querySelector(".bar")?.getBoundingClientRect().height??0};
  });
  assert.equal(staleStart.reply?.started,false);assert.equal(staleStart.calls,0);assert.equal(staleStart.visible,0,
    "A late start message for another URL must not activate the reader or infer on the new page");
  await page.evaluate(()=>{
    window.__qaUserStart=performance.now();
    window.__mangaLive.start({storyId:"qa",title:"QA tự tạo",at:{chapter:1,page:0},autoScan:true,prefetch:false});
    dispatchEvent(new Event("resize")); // Must not postpone explicit intent.
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===2);
  const initialDispatchMs=await page.evaluate(()=>window.__qaFirstImageAt-window.__qaUserStart);
  const scanTimers=await page.evaluate(()=>window.__qaScanTimers);
  // Test the scheduling seam, not PNG-encoding time on this browser/CPU.
  // The full dispatch measurement is still reported, not asserted as <200 ms.
  assert.equal(scanTimers[0]?.delay,0,"Explicit Start must bypass the scroll debounce");
  assert.equal(typeof scanTimers[0]?.fired,"number","Observer resize must not cancel explicit Start");
  const sourcePixels=await page.evaluate(async()=>{
    const source=document.querySelector("#page"),encoded=new Image();
    encoded.src=window.__qaCalls.find(call=>call.op==="image").params.dataUrl;await encoded.decode();
    const pixels=image=>{const c=document.createElement("canvas");c.width=image.naturalWidth;c.height=image.naturalHeight;
      const ctx=c.getContext("2d");ctx.drawImage(image,0,0);return ctx.getImageData(0,0,c.width,c.height).data;};
    const expected=pixels(source),actual=pixels(encoded);
    return {sameSize:source.naturalWidth===encoded.naturalWidth&&source.naturalHeight===encoded.naturalHeight,
      identical:expected.length===actual.length&&expected.every((value,index)=>value===actual[index])};
  });
  assert.deepEqual(sourcePixels,{sameSize:true,identical:true},"Async PNG capture must preserve every source pixel");
  await page.waitForFunction(()=>!window.__qaRoots[0].querySelector(".term-hint")?.hidden);
  const shadowAction=async(selector,method="click",value)=>page.evaluate(({selector,method,value})=>{
    const el=window.__qaRoots[0].querySelector(selector);if(!el)throw new Error("Missing QA control: "+selector);
    if(method==="set"){el.value=value;el.dispatchEvent(new Event("input",{bubbles:true}));}else el.click();
  },{selector,method,value});
  const button=async(label)=>page.evaluate(label=>{
    const el=[...window.__qaRoots[0].querySelectorAll("button")].find(b=>b.textContent===label);if(!el)throw new Error("Missing button: "+label);el.click();
  },label);
  async function expandToolbar(){
    const target=await page.evaluate(()=>{
      const bar=window.__qaRoots[0].querySelector(".bar");if(!bar.classList.contains("compact"))return null;
      const box=bar.querySelector(".toggle").getBoundingClientRect();return {x:box.x+box.width/2,y:box.y+box.height/2};
    });
    if(target)await page.mouse.click(target.x,target.y);
    assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".toggle").getAttribute("aria-expanded")==="true"));
  }
  async function aligned(){
    await page.waitForTimeout(100);
    const error=await page.evaluate(()=>{
      const image=document.querySelector("#page"),r=image.getBoundingClientRect(),css=getComputedStyle(image);
      const scale=css.objectFit==="contain"?Math.min(r.width/image.naturalWidth,r.height/image.naturalHeight):null;
      const width=scale?image.naturalWidth*scale:r.width,height=scale?image.naturalHeight*scale:r.height;
      const x=r.x+(r.width-width)/2,y=r.y+(r.height-height)/2;
      const node=window.__qaRoots[0].querySelector(".region"),actual=node.getBoundingClientRect();
      return Math.max(Math.abs(actual.x-(x+455/800*width)),Math.abs(actual.y-(y+120/1050*height)),Math.abs(actual.width-285/800*width));
    });
    assert(error<2,"Overlay source-to-screen drift: "+error);
  }
  if(!retryOnly){
  await aligned();
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".bar").classList.contains("compact")),"Ready toolbar must be compact so controls do not cover dialogue");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".bar").getBoundingClientRect().height<90));
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".toggle").textContent.includes("1")),"A pending name remains discoverable in compact mode");
  await capture(page,"desktop-overlay");
  await expandToolbar();
  await page.evaluate(()=>scrollTo(0,320));await aligned();
  await page.evaluate(()=>{const img=document.querySelector("#page");img.style.height="1300px";img.style.objectFit="contain";});await aligned();
  await page.setViewportSize({width:760,height:800});await aligned();
  await page.evaluate(()=>scrollTo(0,0));
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".bar").textContent.includes("ổn chưa"));
  await page.evaluate(()=>[...window.__qaRoots[0].querySelectorAll("button")].find(b=>b.textContent.includes("ổn chưa")).click());
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail .name-review").textContent.includes("âm “Kết” lặp")));
  await button("Để sau · đọc tiếp");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".term-hint").hidden));
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="term.confirm").length),0,"Defer must not lock an unconfirmed name");
  await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region")[1].click());
  await button("Đổi cách gọi");
  assert(await page.evaluate(()=>[...window.__qaRoots[0].querySelectorAll("button")].find(b=>b.textContent==="Đúng · nhớ tên này").hidden),"Editing must not offer confirmation of the old name");
  await button("Hủy sửa tên");
  assert(!(await page.evaluate(()=>[...window.__qaRoots[0].querySelectorAll("button")].find(b=>b.textContent==="Đúng · nhớ tên này").hidden)));
  await button("Đổi cách gọi");await shadowAction(".detail section input","set","Kết giới băng giá");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail .name-review").hidden));
  await capture(page,"reader-name-edit");
  await button("Lưu tên đã sửa");await page.waitForFunction(()=>window.__qaCalls.some(c=>c.op==="term.confirm"));
  assert.equal(await page.evaluate(()=>window.__qaCalls.find(c=>c.op==="term.confirm").params.vi),"Kết giới băng giá");
  await shadowAction(".detail textarea","set","ありがとう。");await button("Lưu & dịch lại");
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".detail .vi").textContent==="Cảm ơn.");
  assert(await page.evaluate(()=>window.__qaCalls.find(c=>c.op==="retranslate").params.revision));
  await button("Đóng");await button("Đã đọc");
  assert(await page.evaluate(()=>window.__qaCalls.some(c=>c.op==="memory.read")));
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("tự động đang tắt"));
  await page.evaluate(()=>{window.__qaSummaryEnabled=true;});await button("Đã đọc");
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("đã xếp hàng"));
  await page.evaluate(()=>{
    const p=window.__qaCalls.findLast(c=>c.op==="image").params;
    const region={id:"r001",ja:"氷結結界を展開する！",vi:"Triển khai Kết giới băng giá!",bbox:[455,550,285,100],overlay:"white",
      balloon:{textBox:[455,550,285,100],background:"#ffffff",erasePolygons:[[[455,550],[740,550],[740,650],[455,650]]]}};
    window.__qaReceiver({type:"result",id:p.id,event:"translated",result:{revision:p.revision,width:800,height:1050,regions:[region]}},{},()=>{});
  });
  await page.waitForFunction(()=>!!window.__qaRoots[0].querySelector(".erase")?.style.left);
  await page.evaluate(()=>{
    const frame=window.requestAnimationFrame;let next=1000000;const pending=new Map();
    window.requestAnimationFrame=callback=>{const id=next++;pending.set(id,callback);return id;};
    window.__qaReleaseVisibilityFrame=()=>{
      window.requestAnimationFrame=frame;for(const callback of pending.values())frame.call(window,callback);pending.clear();
    };
  });
  await page.keyboard.press("Alt+t");
  const allOriginalHidden=()=>page.evaluate(()=>[...window.__qaRoots[0].querySelectorAll(".region,.erase")]
    .every(node=>getComputedStyle(node).visibility==="hidden"));
  assert(await allOriginalHidden(),"Original must hide text and erasure immediately, before RAF");
  assert(await page.evaluate(()=>getComputedStyle(window.__qaRoots[0].querySelector(".region").parentElement).display==="none"),
    "Original must remove the whole lettering layer from paint/compositing before RAF");
  // Native updates and async PNG decode can arrive while original view is on.
  // They must not flash a new erasure surface before geometry is positioned.
  await page.evaluate(()=>{
    const p=window.__qaCalls.findLast(c=>c.op==="image").params;
    const region={id:"r001",ja:"氷結結界を展開する！",vi:"Triển khai Kết giới băng giá!",bbox:[455,550,285,100],overlay:"white",
      balloon:{textBox:[455,550,285,100],background:"#fafafa",erasePolygons:[[[455,550],[740,550],[740,650],[455,650]]]}};
    window.__qaReceiver({type:"result",id:p.id,event:"translated",result:{revision:p.revision,width:800,height:1050,regions:[region]}},{},()=>{});
  });
  assert(await allOriginalHidden(),"Late balloon surface must stay hidden in original view");
  await page.evaluate(()=>{
    const p=window.__qaCalls.findLast(c=>c.op==="image").params;
    const region={id:"r001",ja:"氷結結界を展開する！",vi:"Triển khai Kết giới băng giá!",bbox:[455,550,285,100],overlay:"label"};
    window.__qaReceiver({type:"result",id:p.id,event:"translated",result:{revision:p.revision,width:800,height:1050,regions:[region]}},{},()=>{});
    const canvas=document.createElement("canvas");canvas.width=40;canvas.height=40;canvas.getContext("2d").fillRect(0,0,40,40);
    window.__qaReceiver({type:"result",id:p.id,event:"render-patch",result:{revision:p.revision,width:800,height:1050,
      patch:{regionId:"r001",bbox:[455,550,40,40],dataUrl:canvas.toDataURL("image/png"),ink:"#111111",stroke:"#ffffff",sourceFontPx:20,method:"opencv-telea-v1"}}},{},()=>{});
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector("img.erase"));
  assert(await allOriginalHidden(),"Late decoded art patch must stay hidden in original view");
  await page.keyboard.press("Alt+t");
  assert(await allOriginalHidden(),"Returning to translation must wait for current positioning/clipping");
  await page.evaluate(()=>window.__qaReleaseVisibilityFrame());
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".region").style.visibility==="visible");
  await page.evaluate(()=>{document.querySelector("#page").style.height="";document.querySelector("#page").style.objectFit="";});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(150);await capture(page,"mobile-width-overlay");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".bar").getBoundingClientRect().right<=innerWidth));
  await button("Thu gọn");assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".bar").classList.contains("compact")));
  await capture(page,"mobile-width-overlay");
  await button("Mở");assert(!(await page.evaluate(()=>window.__qaRoots[0].querySelector(".bar").classList.contains("compact"))));
  await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region")[0].click());
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector('[role="note"]').textContent.includes("dấu ngoặc chưa khép")));
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector('[role="note"]').textContent.includes("vùng chữ đã tách để tránh gộp nhầm")));
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector('[role="note"]').textContent.includes("các cột/dòng chữ được gom theo bố cục")));
  await capture(page,"ocr-layout-review-mobile");
  await page.keyboard.press("Escape");assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".detail").length),0);
  // Image anchors must track nested scroll and non-centred cover cropping.
  await page.setViewportSize({width:1280,height:900});
  await page.evaluate(()=>{
    const img=document.querySelector("#page"),container=document.createElement("div");container.id="nested";
    Object.assign(container.style,{height:"500px",overflow:"auto",width:"700px",margin:"auto"});
    img.before(container);container.append(img);img.style.width="650px";img.style.maxWidth="none";
  });
  await aligned();await page.evaluate(()=>document.querySelector("#nested").scrollTop=160);await aligned();
  await page.evaluate(()=>{
    const img=document.querySelector("#page"),container=document.querySelector("#nested");container.before(img);container.remove();
    Object.assign(img.style,{width:"600px",height:"350px",objectFit:"cover",objectPosition:"0% 100%"});
  });
  await page.waitForTimeout(150);
  const coverError=await page.evaluate(()=>{
    const img=document.querySelector("#page"),r=img.getBoundingClientRect(),scale=Math.max(r.width/800,r.height/1050);
    const actual=window.__qaRoots[0].querySelector(".region").getBoundingClientRect();
    return Math.max(Math.abs(actual.x-(r.x+455*scale)),Math.abs(actual.y-(r.y+r.height-1050*scale+120*scale)),Math.abs(actual.width-285*scale));
  });
  assert(coverError<2,"Non-centred cover drift: "+coverError);
  await page.evaluate(()=>{const img=document.querySelector("#page");Object.assign(img.style,{width:"",height:"",maxWidth:"",objectFit:"",objectPosition:""});});
  await page.evaluate(()=>{history.pushState({},"","/chapter/2");scrollTo(0,200);});
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===0);
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("đổi")));
  // New session: only the visible image and two already-loaded next images.
  await page.setViewportSize({width:1280,height:900});
  await page.evaluate(()=>{
    const original=document.querySelector("#page");original.style.height="";original.style.objectFit="";
    for(let i=0;i<3;i++){const clone=original.cloneNode();clone.removeAttribute("id");clone.src="/fixture.png?next="+i;document.body.append(clone);}scrollTo(0,0);window.__qaCalls=[];
  });
  await page.waitForFunction(()=>[...document.images].every(i=>i.complete));
  await page.evaluate(()=>window.__mangaLive.start({storyId:"qa",title:"QA",at:{chapter:2,page:0},autoScan:true,prefetch:true}));
  await page.waitForFunction(()=>window.__qaCalls.filter(c=>c.op==="image").length===3);await page.waitForTimeout(450);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),3,"Prefetched more than two next images");
  await expandToolbar();await button("Đã đọc");
  const readAt=await page.evaluate(()=>window.__qaCalls.findLast(c=>c.op==="memory.read").params.at.page);
  assert.equal(readAt,0,"Prefetch must not mark unseen pages read");
  // Deferring in one story must not suppress the same term in another story.
  await page.evaluate(()=>{window.__qaCalls=[];window.__mangaLive.start({storyId:"qa-confirm",title:"Truyện khác",at:{chapter:1,page:0},autoScan:true,prefetch:false});});
  await page.waitForFunction(()=>!window.__qaRoots[0].querySelector(".term-hint").hidden);
  await expandToolbar();
  await page.evaluate(()=>window.__qaRoots[0].querySelector(".term-hint button").click());
  await button("Đúng · nhớ tên này");
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".term-hint").hidden);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="term.confirm").length),1);
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail").textContent.includes("Có thể sửa lại trong Thư viện")));
  // A manual expansion while the first result is pending must win over the
  // one-time auto-collapse. Use a visible mouse click, not a hidden control.
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaImageDelayMs=350;
    window.__mangaLive.start({storyId:"qa-layout",title:"QA bố cục",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaCalls.some(c=>c.op==="image"));
  await shadowAction(".toggle");await expandToolbar();
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  assert(!(await page.evaluate(()=>window.__qaRoots[0].querySelector(".bar").classList.contains("compact"))),"Late result must not collapse a reader-opened toolbar");
  // Tiny source boxes must not become unreadable/oversized painted cards.
  // Full text moves to a readable rail; its source is not erased.
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>{
    scrollTo(0,0);window.__qaSmallRegions=true;window.__qaImageDelayMs=35;
    window.__mangaLive.start({storyId:"qa-small",title:"QA chữ nhỏ",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===2);
  await page.waitForTimeout(100);
  const small=await page.evaluate(()=>{
    const image=document.querySelector("#page").getBoundingClientRect();
    const node=window.__qaRoots[0].querySelector(".region"),region=node.getBoundingClientRect();
    const erase=window.__qaRoots[0].querySelector('.erase[data-region-id="r000"]');
    return {anchorHeight:parseFloat(node.style.height),expected:24/1050*image.height,
      fallback:node.dataset.readingFallback,size:parseFloat(getComputedStyle(node).fontSize),eraseHidden:getComputedStyle(erase).visibility==="hidden",
      x:region.x+region.width/2,y:region.y+region.height/2};
  });
  assert(Math.abs(small.anchorHeight-small.expected)<1&&small.fallback==="true"&&small.size>=16&&small.eraseHidden,
    "Tiny source must retain its anchor/art and have a full readable fallback: "+JSON.stringify(small));
  await capture(page,"mobile-small-region");
  await page.mouse.click(small.x,small.y);
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".detail .vi")?.textContent==="Nee-chan, chưa về à?");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail .speaker-tools")?.open===false),"Advanced speaker fields should not crowd the first mobile detail screen");
  await capture(page,"mobile-small-region-detail");
  await shadowAction(".detail .speaker-tools summary");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail .speaker-tools").open));
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail .speaker-tools input").getBoundingClientRect().height>20));
  await shadowAction(".detail .speaker-tools summary");
  await page.keyboard.press("Escape");
  await expandToolbar();
  await button("Dừng");assert.equal(await page.evaluate(()=>document.querySelector("[data-mangalive]").style.display),"none");
  }
  // One explicit retry on the same source, never a paid auto-retry loop. The
  // real OCR-coverage behavior is verified independently by native harness.
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaSmallRegions=false;window.__qaFailNextImage=true;scrollTo(0,0);
    window.__mangaLive.start({storyId:"qa-retry",title:"QA thử lại",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Lỗi mạng kiểm thử"));
  // Several images can be visible on mobile. A resize/mutation/scroll must
  // not start another request and erase the failed page's recovery controls.
  await page.evaluate(()=>{dispatchEvent(new Event("resize"));document.body.classList.add("qa-retry-pending");});
  await page.waitForTimeout(500);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),1,"A failed page must not auto-loop requests");
  assert(await page.evaluate(()=>{const el=window.__qaRoots[0].querySelector(".retry");return el&&!el.hidden&&!el.disabled;}));
  await capture(page,retryOnly?"desktop-retry-error":"mobile-retry-error");
  await button("Thử lại");
  await button("Thử lại"); // Disabled during the pending retry; must not duplicate.
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===2);
  const retries=await page.evaluate(()=>{const image=window.__qaCalls.find(c=>c.op==="image");return window.__qaCalls.filter(c=>c.op==="image"&&c.params.pageId===image.params.pageId);});
  assert.equal(retries.length,2);
  assert.equal(retries[0].params.pageId,retries[1].params.pageId,"Retry must use the original page identity");
  assert.notEqual(retries[0].params.revision,retries[1].params.revision,"Retry needs a fresh display revision");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".retry").hidden),"Recovery button should disappear after success");
  await expandToolbar();await button("Dừng");
  // An old native host can still return the misleading message. Classify by
  // code, not text; small-source failures must not instruct a smaller selection.
  for(const code of ["TRUNCATED","MODEL_FORMAT","MODEL_OUTPUT","TERM_MISMATCH"]){
    await page.evaluate(code=>{
      window.__qaCalls=[];window.__qaFailNextImage=true;window.__qaFailCode=code;scrollTo(0,0);
      window.__mangaLive.start({storyId:"qa-model-failure",title:"QA lỗi model",at:{chapter:1,page:0},autoScan:true,prefetch:false});
    },code);
    await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Model"));
    const notice=await page.evaluate(()=>window.__qaRoots[0].querySelector(".status").textContent);
    assert.doesNotMatch(notice,/quá dài|vùng nhỏ hơn|chọn vùng khác/i);
    assert.match(notice,/không tự thử lại/i);
    await button("Đổi model / Cloud");
    assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="reader.settings").length),1);
    assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>["settings","warmup","key.set"].includes(c.op)).length),0);
    await page.waitForTimeout(400);
    assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),1);
    if(code==="TRUNCATED")await capture(page,"generation-failure-recovery");
    await button("Thử lại");await button("Thử lại");
    await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===2);
    assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),2);
    await page.evaluate(()=>{window.__qaFailCode=undefined;});
    await expandToolbar();await button("Dừng");
  }
  // A slow encoder must leave controls responsive. Stop/restart while it is
  // pending must never send the old page or silently spend a provider request.
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaHoldEncode=true;window.__qaEncodePending=false;
    window.__mangaLive.start({storyId:"qa-encoding-old",title:"QA ảnh cũ",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaEncodePending);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),0);
  await button("Dừng");
  await page.evaluate(()=>{
    window.__qaHoldEncode=false;
    window.__mangaLive.start({storyId:"qa-encoding-new",title:"QA ảnh mới",at:{chapter:2,page:0},autoScan:true,prefetch:false});
    window.__qaReleaseEncode();
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===2);
  assert.deepEqual(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").map(c=>c.params.storyId)),["qa-encoding-new"]);
  await expandToolbar();await button("Dừng");
  // A canceled old request must not overwrite a new session with its error,
  // or leave the new session asleep after its first autoscan saw busy=true.
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaImageDelayMs=350;window.__qaFailNextImage=true;
    window.__mangaLive.start({storyId:"qa-old-pending",title:"QA cũ",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaCalls.some(c=>c.op==="image"));
  await page.evaluate(()=>{
    window.__qaImageDelayMs=35;
    window.__mangaLive.start({storyId:"qa-new-session",title:"QA phiên mới",at:{chapter:2,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".bar strong").textContent.includes("QA phiên mới")));
  assert(!(await page.evaluate(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Lỗi mạng"))));
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image"&&c.params.storyId==="qa-new-session").length),1);
  await expandToolbar();await button("Dừng");
  // Selecting a region while a full-page job is pending must cancel it and
  // actually process the chosen region, not lose the selection to busy=true.
  await page.setViewportSize({width:1280,height:900});
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaImageDelayMs=350;scrollTo(0,0);
    window.__mangaLive.start({storyId:"qa-manual-pending",title:"QA chọn vùng",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaCalls.some(c=>c.op==="image"));
  await button("Chọn vùng");
  await page.mouse.move(450,290);await page.mouse.down();await page.mouse.move(620,410);await page.mouse.up();
  await page.waitForFunction(()=>window.__qaCalls.some(c=>c.op==="image"&&c.params.capture),{},{timeout:3000});
  const selectionCalls=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image"));
  assert(selectionCalls[1].params.capture,"The next request must honor the reader's selection before autoscan");
  assert.equal(selectionCalls[1].params.capture.rect.width,170);
  assert.equal(selectionCalls[1].params.capture.rect.height,120);
  assert(await page.evaluate(()=>window.__qaCalls.some(c=>c.op==="cancel"&&c.params.id===window.__qaCalls.find(c=>c.op==="image").params.id)));
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  await expandToolbar();await button("Dừng");
  // A failed unseen page is not the active error UI. It gets one foreground
  // attempt on scroll; it does not repeatedly requeue itself in prefetch.
  await page.evaluate(()=>{
    while(document.images.length<3){const clone=document.querySelector("#page").cloneNode();clone.removeAttribute("id");clone.src="/fixture.png?prefetch="+document.images.length;document.body.append(clone);}
    window.__qaCalls=[];window.__qaImageDelayMs=35;window.__qaFailImageNumber=2;scrollTo(0,0);
  });
  await page.waitForFunction(()=>[...document.images].every(i=>i.complete));
  await page.evaluate(()=>window.__mangaLive.start({storyId:"qa-prefetch-error",title:"QA tải trước",at:{chapter:1,page:0},autoScan:true,prefetch:true}));
  await page.waitForFunction(()=>window.__qaCalls.filter(c=>c.op==="image").length===3);
  await page.waitForTimeout(500);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),3);
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".retry").hidden));
  const failedPrefetchId=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image")[1].params.pageId);
  await page.evaluate(()=>{window.__qaFailImageNumber=0;document.images[1].scrollIntoView({block:"start"});});
  await page.waitForFunction(id=>window.__qaCalls.filter(c=>c.op==="image"&&c.params.pageId===id).length===2,failedPrefetchId);
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("sẵn sàng")||window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  await expandToolbar();await button("Dừng");
  // Source replacement while an old failure is in flight must not paint the
  // old result/error on the newly loaded image or keep recovery stuck.
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaImageDelayMs=350;window.__qaFailNextImage=true;scrollTo(0,0);
    window.__mangaLive.start({storyId:"qa-replaced",title:"QA đổi ảnh",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaCalls.some(c=>c.op==="image"));
  await page.evaluate(()=>{window.__qaImageDelayMs=35;document.querySelector("#page").src="/fixture.png?replaced=1";});
  await page.waitForFunction(()=>window.__qaCalls.filter(c=>c.op==="image").length>=2);
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".retry").hidden));
  const replaced=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").slice(0,2));
  assert.notEqual(replaced[0].params.pageId,replaced[1].params.pageId);
  assert(!(await page.evaluate(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Lỗi mạng"))));
  await expandToolbar();await button("Dừng");
  // A context error after an already-painted partial result must restore raw
  // art, keep explicit retry and reject late text/patch events for that job.
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>{
    while(document.images.length>1)document.images[document.images.length-1].remove();
    window.__qaCalls=[];window.__qaStaleNextImage=true;window.__qaImageDelayMs=35;scrollTo(0,0);
    window.__mangaLive.start({storyId:"qa-stale-context",title:"QA đổi context",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===1&&window.__qaRoots[0].querySelectorAll("img.erase").length===1);
  await capture(page,"stale-context-partial");
  await page.evaluate(()=>{window.__qaCorrectedContext=true;window.__qaReleaseStale();});
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Ngữ cảnh vừa đổi"));
  assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region,.erase").length),0,"Stale partial lettering/cleanup must be removed");
  assert(await page.evaluate(()=>{const el=window.__qaRoots[0].querySelector(".retry");return !el.hidden&&!el.disabled;}));
  await page.evaluate(()=>{
    const stale=window.__qaLateStale;
    for(const [event,result] of [["translated",stale.partial],["render-patch",stale.patch],["progress",{stage:"ocr",total:999}]])
      window.__qaReceiver({type:"result",id:stale.id,event,result},{},()=>{});
    dispatchEvent(new Event("resize"));
  });
  await page.waitForTimeout(500);
  assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region,.erase").length),0,"Late events must not resurrect obsolete artwork");
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),1,"A context correction must not auto-charge a retry");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Ngữ cảnh vừa đổi")));
  await capture(page,"stale-context-restored-source");
  await button("Thử lại");await button("Thử lại");
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),2);
  assert(await page.evaluate(()=>[...window.__qaRoots[0].querySelectorAll(".region")].some(node=>
    node.getAttribute("aria-label")==="Xem và sửa bản dịch: Triển khai Kết giới băng giá!"&&
    node.textContent.replace(/\s+/g," ").includes("Kết giới băng giá"))),"Explicit retry must use the corrected name even when lettering wraps");
  const contextRetry=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image"));
  assert.equal(contextRetry[0].params.pageId,contextRetry[1].params.pageId);
  assert.notEqual(contextRetry[0].params.revision,contextRetry[1].params.revision);
  await capture(page,"stale-context-reader-retry");
  await expandToolbar();await button("Dừng");
  // Exercise the second asynchronous boundary: the blob was allocated but
  // its decode has not returned when the task becomes obsolete.
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaStaleNextImage=true;window.__qaHoldPatchDecode=true;window.__qaPendingDecode=false;
    window.__mangaLive.start({storyId:"qa-stale-decode",title:"QA patch đang chờ",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaPendingDecode);
  assert.equal(await page.evaluate(()=>window.__qaBlobUrls.size),1,"The pending patch must actually allocate a transient blob");
  await page.evaluate(()=>window.__qaReleaseStale());
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Ngữ cảnh vừa đổi"));
  assert.equal(await page.evaluate(()=>window.__qaBlobUrls.size),0,"Stale recovery must release pending blob URLs");
  await page.evaluate(()=>{window.__qaHoldPatchDecode=false;window.__qaReleasePatchDecode();});
  await page.waitForTimeout(300);
  assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region,.erase").length),0);
  assert.equal(await page.evaluate(()=>window.__qaBlobUrls.size),0);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="image").length),1);
  await button("Dừng");
  await page.setViewportSize({width:1280,height:900});
  await page.evaluate(()=>{window.__qaCorrectedContext=false;});
  // Deferred OCR stays available without painting or spending on it. Reading
  // the list/detail is free; only an explicit translation click calls native.
  await page.evaluate(()=>{
    while(document.images.length>1)document.images[document.images.length-1].remove();
    window.__qaCalls=[];window.__qaSecondary=true;window.__qaImageDelayMs=35;scrollTo(0,0);
    window.__mangaLive.start({storyId:"qa-secondary",title:"QA chữ phụ",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region").length),2);
  await expandToolbar();await button("Chữ phụ · 1");await button("作者コメント");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail .vi").textContent.includes("có thể tính phí")));
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="retranslate").length),0);
  await capture(page,"secondary-reader-action");
  await button("Dịch riêng vùng này");
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===3);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="retranslate"&&c.params.recoverDeferred).length),1);
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".secondary").hidden));
  await button("Đóng");await button("Dừng");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".secondary").hidden));
  // An unreadable detector source is not a blank/missing button, a paid
  // translation of an empty string or permission to erase the raw glyphs.
  await page.evaluate(()=>{
    window.__qaCalls=[];window.__qaUnreadable=true;
    window.__mangaLive.start({storyId:"qa-unreadable",title:"QA OCR rỗng",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  });
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".status").textContent.includes("Đã dịch"));
  assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region").length),2);
  await expandToolbar();await button("Chữ phụ · 1");await button("Chưa đọc được chữ · r002");
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail [role=note]").textContent.includes("chưa được dịch hoặc xóa chữ")));
  await button("Dịch riêng vùng này");
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="retranslate"||c.op==="speaker.set").length),0);
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail [role=status]").textContent.includes("Chưa có chữ Nhật")));
  await page.evaluate(()=>{
    const p=window.__qaCalls.find(c=>c.op==="image").params;
    const canvas=document.createElement("canvas");canvas.width=40;canvas.height=100;canvas.getContext("2d").fillRect(0,0,40,100);
    window.__qaReceiver({type:"result",id:p.id,event:"render-patch",result:{revision:p.revision,width:800,height:1050,
      patch:{regionId:"r002",bbox:[100,820,40,100],dataUrl:canvas.toDataURL("image/png"),
        ink:"#111111",stroke:"#ffffff",sourceFontPx:12,method:"opencv-telea-v1"}}},{},()=>{});
  });
  await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>window.__qaBlobUrls.size),0,"Unresolved source must reject late cleanup before allocating a Blob");
  await capture(page,"unreadable-source-recovery-desktop");
  await shadowAction(".detail textarea","set","ありがとう。");await button("Dịch riêng vùng này");
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===3);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="retranslate"&&c.params.recoverDeferred).length),1);
  assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll('.erase[data-region-id="r002"]').length),0);
  await page.evaluate(()=>{
    const p=window.__qaCalls.find(c=>c.op==="image").params;
    window.__qaReceiver({type:"result",id:p.id,event:"translated",result:{revision:p.revision,width:800,height:1050,
      regions:[{id:"r002",ja:"",bbox:[100,820,40,100],overlay:"label",review:true,reviewReasons:["ocr_empty"],
        scope:{v:1,key:"scope-a",group:"scope-b",role:"unknown",action:"defer",reason:"visual_review",memory:false}}]}},{},()=>{});
  });
  assert.equal(await page.evaluate(()=>window.__qaRoots[0].querySelectorAll('.region[data-region-id="r002"],.erase[data-region-id="r002"]').length),0,
    "Returning to unresolved review must synchronously remove previous text/erasure");
  await button("Đóng");await button("Dừng");await page.evaluate(()=>window.__qaUnreadable=false);
  // Unanchored old choices stay non-blocking. Opening review makes no request;
  // explicitly confirming unknown still binds the current source/revision.
  for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
    await page.setViewportSize(viewport);
    await page.evaluate(()=>{
      window.__qaCalls=[];window.__qaSecondary=false;window.__qaSpeakerReview=true;scrollTo(0,0);
      window.__mangaLive.start({storyId:"qa-speaker",title:"QA dấu neo người nói",at:{chapter:1,page:0},autoScan:true,prefetch:false});
    });
    await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===2);
    await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region")[0].click());
    assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".speaker-binding-note").textContent.includes("không khớp chắc chắn")));
    assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".speaker-tools").open));
    assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="speaker.set"||c.op==="retranslate").length),0);
    const savePoint=await page.evaluate(()=>{
      const shadow=window.__qaRoots[0],panel=shadow.querySelector(".detail"),target=[...panel.querySelectorAll("button")].find(b=>b.textContent==="Lưu & dịch lại");
      const r=target.getBoundingClientRect(),p=panel.getBoundingClientRect();
      return {x:r.x+r.width/2,y:r.y+r.height/2,fullyVisible:r.top>=p.top&&r.bottom<=p.bottom&&r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,
        hittable:shadow.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===target};
    });
    assert(savePoint.fullyVisible&&savePoint.hittable,"Speaker confirmation must be a visible, physically clickable action, not a clipped programmatic click");
    const suffix=viewport.width===390?"mobile":"desktop";
    await capture(page,"speaker-binding-review-"+suffix);
    await page.mouse.click(savePoint.x,savePoint.y);
    await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".detail .vi").textContent==="Cảm ơn.");
    const calls=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="speaker.set"||c.op==="retranslate"));
    assert.equal(calls.length,2);assert.equal(calls[0].op,"speaker.set");assert.equal(calls[1].op,"retranslate");
    assert.equal(calls[0].params.speaker,"unknown");assert.equal(calls[0].params.listener,"unknown");
    assert.equal(calls[0].params.revision,calls[1].params.revision);
    assert(!await page.evaluate(()=>!!window.__qaRoots[0].querySelector(".speaker-binding-note")));
    await button("Đóng");
    await page.evaluate(()=>window.__qaRoots[0].querySelectorAll(".region")[0].click());
    assert(!await page.evaluate(()=>!!window.__qaRoots[0].querySelector(".speaker-binding-note")));
    await button("Đóng");await expandToolbar();await button("Dừng");
  }
  await page.evaluate(()=>{window.__qaSpeakerReview=false;});
  // Weak visual support is review, not a skip. Even a conflicting balloon
  // mask or late raster event must not acquire permission to erase raw art.
  for(const reason of ["visual_low_signal","visual_punctuation_support","cloud_ocr_uncertain","cloud_page_proposal","ocr_empty"]){
  await page.setViewportSize({width:1280,height:900});
  await page.evaluate(reason=>{
    window.__qaCalls=[];window.__qaSecondary=false;window.__qaWeak=true;window.__qaVisualReason=reason;scrollTo(0,0);
    window.__mangaLive.start({storyId:"qa-weak",title:"QA nét chữ yếu",at:{chapter:1,page:0},autoScan:true,prefetch:false});
  },reason);
  await page.waitForFunction(()=>window.__qaRoots[0].querySelectorAll(".region").length===3);
  assert(await page.evaluate(()=>{
    const node=[...window.__qaRoots[0].querySelectorAll(".region")].find(r=>r.getAttribute("aria-label")==="Xem và sửa bản dịch: Ma pháp đoàn");
    return node?.classList.contains("label")&&!node.classList.contains("integrated")&&
      node.dataset.readingFallback==="true"&&window.__qaRoots[0].querySelectorAll('.erase[data-region-id="r003"]').length===0;
  }),"Weak source must remain a reversible annotation, not erase art with a supplied balloon mask");
  await page.evaluate(()=>{
    const p=window.__qaCalls.find(c=>c.op==="image").params;
    const canvas=document.createElement("canvas");canvas.width=23;canvas.height=22;
    canvas.getContext("2d").fillRect(0,0,23,22);
    window.__qaReceiver({type:"result",id:p.id,event:"render-patch",result:{revision:p.revision,width:800,height:1050,
      patch:{regionId:"r003",bbox:[100,820,23,22],dataUrl:canvas.toDataURL("image/png"),
        ink:"#111111",stroke:"#ffffff",sourceFontPx:12,method:"opencv-telea-v1"}}},{},()=>{});
  });
  await page.waitForTimeout(150);
  assert.equal(await page.evaluate(()=>window.__qaBlobUrls.size),0,"Rejected weak patch must not allocate a blob");
  await page.evaluate(()=>[...window.__qaRoots[0].querySelectorAll(".region")].find(r=>r.getAttribute("aria-label")==="Xem và sửa bản dịch: Ma pháp đoàn").click());
  assert(await page.evaluate(()=>window.__qaRoots[0].querySelector(".detail [role=note]").textContent.includes("chưa đưa vào bộ nhớ truyện")));
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="retranslate").length),0,"Opening review must not trigger a paid retry");
  await capture(page,reason+"-review-desktop");
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(100);
  await capture(page,reason+"-review-mobile");
  await shadowAction(".detail textarea","set","ありがとう。");await button("Lưu & dịch lại");
  await page.waitForFunction(()=>window.__qaRoots[0].querySelector(".detail .vi").textContent==="Cảm ơn.");
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="retranslate").length),1);
  assert(await page.evaluate(()=>{
    const node=[...window.__qaRoots[0].querySelectorAll(".region")].find(r=>r.getAttribute("aria-label")==="Xem và sửa bản dịch: Cảm ơn.");
    return node?.classList.contains("label")&&!node.classList.contains("integrated")&&window.__qaBlobUrls.size===0;
  }),"Text correction is not proof of visual erasure safety");
  await button("Đóng");await expandToolbar();await button("Dừng");
  }
  assert.deepEqual(errors,[],"Relevant page/console errors");
  assert.equal(await page.locator("vite-error-overlay,nextjs-portal").count(),0);
  console.log(JSON.stringify({passed:true,environment:{url,engine:"isolated headless Edge",viewport:retryOnly?["1280x900"]:["1280x900","760x800","390x844"],browser_plugin:"Browser plugin not available"},
    checks:["identity/nonblank","no framework overlay","no console errors",...(!retryOnly?["scroll/nested scroll alignment <2 CSS px","contain/non-centred cover resize","responsive bar + expand/collapse","small crop geometry + tap for full text","one-time ready collapse + pending-name badge","reader-opened toolbar survives late result","reader defers/edits name without blocking","legacy speaker review is free; explicit unknown confirmation uses current revision","OCR quote/split/cluster review","Escape closes detail","OCR edit revision","read progress","original toggle","chapter stale cancel","prefetch <=2","unseen not marked read"]:[]),"explicit retry preserves source identity; no auto-loop/duplicate click","resize and mutation preserve paused error recovery","new session wakes after old request settles; stale error ignored","manual selection supersedes pending autoscan","prefetch failure retried once on foreground","replaced source ignores old pending failure"],
    contextRecovery:"stale partial text/masks/patches removed; pending decode cannot resurrect art and blob URLs released; late events rejected; explicit same-page retry; no automatic charge",
    originalView:"text/erasure concealed before delayed RAF; late balloon and decoded art patches stay hidden; reveal waits for current geometry/clipping",
    secondaryRecovery:"source kept, no painted deferred overlay or request on list open; unreadable source has a named recovery action; empty correction sends no request; one explicit nonempty correction; no plot memory/erasure",
    weakSourceReview:"weak marks and unsupported punctuation: translation remains available; no balloon-mask erasure or late raster/blob allocation; warning desktop/mobile; no request on review open; explicit OCR retry does not grant visual trust",
    initialDispatchMs,flow:retryOnly?"retry-only":"full",screenshots:ramScreenshots.map(s=>s.label+" (RAM-only)"),limits:["Companion mocked for rendered UI QA","Does not certify native registration, OCR quality or translation semantics"]},null,2));
}finally{
  await browser?.close();fixture.kill();
  if(process.argv.includes("--ram-preview"))console.log("QA_RAM_IMAGES="+JSON.stringify(ramScreenshots));
}
