// Rendered React library/settings QA in an isolated headless browser.
// Native transport and summary generation are mocked, explicitly not E2E proof.
import {chromium} from "playwright";
import {mkdir} from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output=process.env.MANGALIVE_QA_OUTPUT??path.join(os.tmpdir(),"mangalive-options-qa");await mkdir(output,{recursive:true});
const edgeArg=process.argv.indexOf("--edge-executable");
const browser=await chromium.launch({...(edgeArg>=0?{executablePath:process.argv[edgeArg+1]}:{channel:"msedge"}),headless:true});
const ramImages=[];
async function capture(page,label){ramImages.push({label,mimeType:"image/jpeg",data:(await page.screenshot({type:"jpeg",quality:75})).toString("base64")});}
try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("console",msg=>{if(msg.type()==="error")errors.push(msg.text());});
  const origin="http://127.0.0.1:65303";
  for(const [file,type] of [["options.html","text/html"],["popup.html","text/html"],["ui.js","application/javascript"],["ui.css","text/css"]])
    await page.route(origin+"/"+file,route=>route.fulfill({path:path.join(root,"dist/extension",file),contentType:type}));
  await page.addInitScript(()=>{
    window.__qaCalls=[];
    const story={id:"qa-memory",title:"Bộ nhớ mẫu",genre:"fantasy",last_chapter:5,last_page:2,version:2};
    const other={id:"other",title:"Bộ nhớ khác",last_chapter:1,last_page:0,version:1};
    const settings={mode:"offline",ocr:"manga",cloudOcrConsent:false,cloudConsent:false,metadataConsent:false,autoSummary:false,artCleanup:true,threads:4,detector:"paddle",provider:"openrouter",
      openrouterModel:"deepseek/deepseek-v4.1-flash",deepseekModel:"deepseek-flash",geminiModel:"gemini-3.5-flash-lite"};
    const keys={};
    const cloudModels=[{provider:"openrouter",id:"deepseek/deepseek-v4.1-flash",label:"DeepSeek V4.1 Flash",note:"Mặc định beta tạm thời"},
      {provider:"openrouter",id:"anthropic/claude-haiku-5.5",label:"Claude Haiku 5.5",note:"Ứng viên mới"},
      {provider:"gemini",id:"gemini-3.5-flash-lite",label:"Gemini Flash-Lite trực tiếp",note:"Thinking minimal"}];
    const summaryStatus={enabled:false,pending:1,failed:1,gap:1,done:0};window.__qaSummaryQueue=summaryStatus;
    const term=value=>JSON.stringify({type:"canonical-term",entity:"ice",category:"skill",ja:"氷結結界",vi:value,aliases:[],origin:"user"});
    const pack={schema:1,story,summaryStatus,facts:[
      {id:"old",kind:"glossary",key:"ice",value:term("Tên cũ"),chapter:1,page:0,confirmed:1},
      {id:"current",kind:"glossary",key:"ice",value:term("Băng Kết Kết Giới"),chapter:1,page:0,confirmed:1},
      {id:"future",kind:"note",key:"secret",value:"SPOILER_QA_ONLY",chapter:80,page:0,confirmed:1}],summaries:[]};
    window.chrome={runtime:{id:"qa-extension",async sendMessage(message){
      window.__qaCalls.push(message);
      let result={};
      if(message.op==="status")result={version:"qa",settings,cloudModels,
        layoutVersion:"balloon-mask-v20-source-footprint-corners",presentationVersion:"balloon-mask-v21-actual-source-support",
        summaryVersion:window.__qaLegacySummary?undefined:"read-evidence-cloud-v1",
        summaryUsage:[],summaryUsageUnavailable:window.__qaUsageUnavailable??false,
        models:{ocr:true,detector:true,translation:true,summarizer:!window.__qaNoLocalSummary},keys,stories:[story,other],engineWarm:false};
      if(message.op==="key.set")keys[message.params.provider]=true;
      if(message.op==="key.delete")keys[message.params.provider]=false;
      if(message.op==="settings"){Object.assign(settings,message.params);result=settings;}
      if(message.op==="warmup")result={ready:true};
      if(message.op==="reader.info")result={tabId:12,url:"http://127.0.0.1:65303/chapter/5",title:story.title};
      if(message.op==="memory.export.page"){
        const params=message.params;
        const selected=params.storyId===other.id?{schema:1,story:other,summaryStatus,facts:[
          {id:"other-note",kind:"note",key:"note",value:"OTHER_STORY_CURRENT",chapter:1,page:0,confirmed:1}],summaries:[]}:pack;
        const at=params.at;
        const eligible=selected.facts.filter(f=>!at||f.chapter<at.chapter||(f.chapter===at.chapter&&f.page<=at.page));
        const offset=params.cursor?.offset??0;
        result={...selected,snapshotVersion:selected.story.version,snapshotId:"qa-snapshot-"+selected.story.id+"-"+selected.story.version,
          facts:eligible.slice(offset,offset+64),
          next:offset+64<eligible.length?{offset:offset+64}:null,
          summaries:offset+64<eligible.length?[]:selected.summaries.filter(s=>!at||s.chapter_end<at.chapter||(s.chapter_end===at.chapter&&s.page_end<=at.page))};
        if(params.storyId===story.id&&window.__slowOld)await new Promise(resolve=>setTimeout(resolve,450));
      }
      if(message.op==="context.begin")window.__upload={...message.params,data:""};
      if(message.op==="context.chunk"){
        const decoded=atob(message.params.data);if(message.params.offset!==window.__upload.data.length)throw new Error("QA offset mismatch");
        window.__upload.data+=decoded;
      }
      if(message.op==="context.commit"){
        const bytes=Uint8Array.from(window.__upload.data,c=>c.charCodeAt(0));
        if(bytes.length!==window.__upload.bytes)throw new Error("QA import size mismatch");
        const digest=await crypto.subtle.digest("SHA-256",bytes);
        if(Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,"0")).join("")!==window.__upload.sha256)throw new Error("QA hash mismatch");
        const incoming=JSON.parse(new TextDecoder().decode(bytes));pack.facts.push(...incoming.facts);story.version++;
        window.__upload=undefined;result={storyId:story.id};
      }
      if(message.op==="context.cancel")window.__upload=undefined;
      if(message.op==="memory.retry"){result={retried:summaryStatus.failed};summaryStatus.pending+=summaryStatus.failed;summaryStatus.failed=0;}
      if(message.op==="summarize"){
        summaryStatus.pending--;summaryStatus.done++;
        pack.summaries.push({id:"summary-"+summaryStatus.done,chapter_end:5,page_end:1,complete:0,text:"Tóm tắt một trang đã đọc."});
      }
      return {ok:true,result:JSON.parse(JSON.stringify(result))};
    }}};
  });
  await page.goto(origin+"/options.html#settings");
  await page.getByRole("heading",{name:"Cấu hình engine"}).waitFor();
  await page.locator(".runtime-details > summary").click();
  await page.locator(".runtime-details").getByText("balloon-mask-v21-actual-source-support",{exact:true}).waitFor();
  assert.equal(await page.locator(".runtime-details").getByText("balloon-mask-v20-source-footprint-corners",{exact:true}).count(),0,
    "Dàn chữ must show the actual presentation capability, not a source-cache compatibility version");
  await page.locator(".runtime-details").scrollIntoViewIfNeeded();await capture(page,"runtime-presentation-desktop");
  await page.locator(".runtime-details > summary").click();
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>["settings","warmup","image","reader.start"].includes(c.op)).length),0,
    "Opening model recovery configuration must not load models, change backend or charge a request");
  await page.goto(origin+"/options.html");
  assert.equal(await page.title(),"Live translation");await page.getByRole("heading",{name:"Thư viện của bạn"}).waitFor();
  await page.getByRole("button",{name:/Bộ nhớ mẫu/}).click();
  await page.getByText(/1 trang chờ · 1 lỗi/).waitFor();
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>c.op==="warmup")),false,
    "Opening a cold library must not load OCR/LLM workers");
  await page.getByRole("button",{name:"Dịch ngay",exact:true}).click();
  const engineNote=page.getByRole("note",{name:"Engine của phiên dịch"});
  assert.match(await engineNote.innerText(),/Offline.*CPU/);
  assert.match(await engineNote.innerText(),/Lưu key không tự bật cloud/);
  const beforeEngineHelp=await page.evaluate(()=>window.__qaCalls.length);
  await page.getByRole("button",{name:"Cấu hình Cloud BYOK",exact:true}).click();
  await page.getByRole("heading",{name:"Cấu hình engine"}).waitFor();
  assert.equal(await page.evaluate(start=>window.__qaCalls.slice(start).some(c=>["settings","warmup","image","reader.start"].includes(c.op)),beforeEngineHelp),false,
    "Opening cloud help must not change the saved offline mode, load models or charge");
  await page.getByRole("button",{name:"Thư viện",exact:true}).click();
  assert.equal(await page.getByText("SPOILER_QA_ONLY").count(),0);
  assert.equal(await page.getByText(/Tên cũ/).count(),0);
  assert.equal(await page.locator(".profile-editor").getAttribute("open"),null);
  await page.getByRole("button",{name:"Sửa tên / thêm alias"}).click();
  assert.equal(await page.getByLabel("Tên Việt cố định").inputValue(),"Băng Kết Kết Giới");
  assert(await page.getByRole("note").filter({hasText:"âm “Kết” lặp"}).isVisible());
  await page.locator(".profile-editor > summary").click();
  await page.getByRole("button",{name:"Thử lại tóm tắt lỗi"}).click();
  await page.getByText(/2 trang chờ · 0 lỗi/).waitFor();
  assert.equal(await page.getByRole("button",{name:"Thử lại tóm tắt lỗi"}).count(),0);
  await page.getByRole("button",{name:"Tóm tắt một trang",exact:true}).click();
  await page.getByText(/Đã tóm tắt một trang đã đọc/).waitFor();
  const summaryCall=await page.evaluate(()=>window.__qaCalls.find(c=>c.op==="summarize"));
  assert.equal(summaryCall.params.storyId,"qa-memory");assert.deepEqual(summaryCall.params.at,{chapter:5,page:2});
  await page.getByRole("button",{name:"Tóm tắt một trang",exact:true}).click();
  await page.getByText(/0 trang chờ · 0 lỗi/).waitFor();
  assert(await page.getByRole("button",{name:"Tóm tắt một trang",exact:true}).isDisabled());
  // Profiles larger than the previous 550KB cap are chunked, never sent as a
  // single native message. The actual companion's atomic import is unit-tested.
  const large={schema:1,story:{id:"qa-memory",title:"Bộ nhớ mẫu"},summaries:[],facts:Array.from({length:900},(_,i)=>({
    id:"import-"+i,kind:"note",key:"import-"+i,value:"Nhật Việt 日本語 ".repeat(65),chapter:1,page:0,confirmed:1,locked:1,source:'{"type":"user"}'}))};
  const raw=Buffer.from(JSON.stringify(large));assert(raw.length>550000);
  await page.locator('input[type="file"]').setInputFiles({name:"private-qa-context.json",mimeType:"application/json",buffer:raw});
  await page.getByText("Đã nhập hồ sơ có mốc chapter.").waitFor();
  await page.waitForFunction(()=>window.__qaCalls.filter(c=>c.op==="memory.export.page").some(c=>c.params.cursor?.offset>=800));
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>c.op==="memory.get"||c.op==="memory.import")),false);
  const imported=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="context.chunk"));
  assert(imported.length>1);
  assert(imported.every(c=>Buffer.byteLength(JSON.stringify(c))<200000));
  await page.locator(".memory-list .fact").first().waitFor();
  assert.equal(await page.locator(".memory-list .fact").count(),10);
  const longNote=page.locator(".memory-list .fact-body").first();
  assert.equal(await longNote.getAttribute("open"),null);
  const collapsedHeight=(await longNote.boundingBox()).height;
  await longNote.locator("summary").click();
  assert((await longNote.boundingBox()).height>collapsedHeight);
  await longNote.locator("summary").click();
  await page.getByRole("button",{name:"Xem thêm 10 mục",exact:true}).click();
  assert.equal(await page.locator(".memory-list .fact").count(),20);
  await page.getByLabel("Tìm trong bộ nhớ").fill("Băng Kết Kết Giới");
  assert.equal(await page.locator(".memory-list .fact").count(),1);
  await page.getByLabel("Tìm trong bộ nhớ").fill("NOT_FOUND_QA");
  await page.getByText("Không tìm thấy mục phù hợp tại mốc này.").waitFor();
  await page.getByLabel("Tìm trong bộ nhớ").fill("");
  assert.equal(await page.locator(".memory-list .fact").count(),10);
  await page.evaluate(()=>scrollTo(0,0));
  await capture(page,"library-summary-desktop");
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>scrollTo(0,0));
  await capture(page,"library-summary-mobile");
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),"Mobile horizontal overflow");
  // A later cutoff actually refetches. Then switch stories while that reply is
  // deliberately late; neither data nor errors may overwrite the new profile.
  await page.evaluate(()=>{window.__slowOld=true;});
  const before=await page.evaluate(()=>window.__qaCalls.length);
  await page.getByLabel("Mốc chapter cho context").fill("6");
  await page.waitForFunction(before=>window.__qaCalls.slice(before).some(c=>c.op==="memory.export.page"&&c.params.at.chapter===6),before);
  await page.getByRole("button",{name:/Bộ nhớ khác/}).click();
  await page.getByText("OTHER_STORY_CURRENT").waitFor();
  await page.waitForTimeout(600);
  assert.equal(await page.getByText("OTHER_STORY_CURRENT").count(),1);
  assert.equal(await page.getByText(/import-899/).count(),0);
  assert.equal(await page.getByRole("alert").count(),0);
  assert.equal(await page.getByLabel("Tên Việt cố định").inputValue(),"");
  assert.equal(await page.locator(".profile-editor").getAttribute("open"),null);
  await page.evaluate(()=>scrollTo(0,0));
  await capture(page,"library-switched-mobile");
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>c.op==="warmup")),false);
  await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
  const cleanup=page.getByLabel("Hòa chữ vào tranh · local, thử nghiệm");
  assert.equal(await cleanup.isChecked(),true);
  await cleanup.scrollIntoViewIfNeeded();
  await capture(page,"settings-local-default");
  await cleanup.uncheck();
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  await page.getByText(/Đã lưu. Thay đổi luồng CPU/).waitFor();
  assert.equal(await cleanup.isChecked(),false);
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="settings").at(-1).params.artCleanup),false);
  await capture(page,"settings-local-optout");
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>c.op==="image"||c.op==="pipeline")),false,"Toggling cleanup must not start a paid translation");
  const beforeCloud=await page.evaluate(()=>window.__qaCalls.length);
  await page.getByLabel("Chế độ dịch",{exact:true}).selectOption("byok");
  await page.getByLabel("Model cloud",{exact:true}).selectOption("anthropic/claude-haiku-5.5");
  const consent=page.getByLabel(/Cho phép gửi text OCR/);
  assert.equal(await consent.isChecked(),false);
  await consent.check();
  await page.getByLabel(/API key/).fill("QA-only-fake-key");
  await page.getByRole("button",{name:"Lưu key",exact:true}).click();
  await page.getByText(/Bấm Lưu cấu hình để áp dụng/).waitFor();
  assert.equal(await page.getByLabel("Chế độ dịch",{exact:true}).inputValue(),"byok","Saving key must preserve the draft mode");
  assert.equal(await page.getByLabel("Model cloud",{exact:true}).inputValue(),"anthropic/claude-haiku-5.5");
  assert.equal(await page.getByLabel(/API key/).inputValue(),"");
  assert.equal(await consent.isChecked(),true);
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  await page.getByText(/Đã lưu. Thay đổi luồng CPU/).waitFor();
  const selectedCloud=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="settings").at(-1).params);
  assert.equal(selectedCloud.openrouterModel,"anthropic/claude-haiku-5.5");assert.equal(selectedCloud.cloudConsent,true);
  await page.getByLabel("Model cloud",{exact:true}).selectOption("__custom__");
  await page.getByLabel("Model ID",{exact:true}).fill("reader/custom-model");
  assert.equal(await consent.isChecked(),false);
  await page.getByLabel("Nhà cung cấp",{exact:true}).selectOption("gemini");
  assert.equal(await page.getByLabel("Model cloud",{exact:true}).inputValue(),"gemini-3.5-flash-lite");
  assert.equal(await consent.isChecked(),false);
  assert.equal(await page.evaluate(start=>window.__qaCalls.slice(start).some(c=>["warmup","image","pipeline","translate","summarize"].includes(c.op)),beforeCloud),false);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),"Cloud controls overflow on mobile");
  await page.getByLabel("Nhà cung cấp",{exact:true}).selectOption("openrouter");
  const beforeVision=await page.evaluate(()=>window.__qaCalls.length);
  await page.getByLabel("Nhận chữ",{exact:true}).selectOption("cloud-gemini");
  assert.equal(await page.getByLabel("Xác nhận gửi crop OCR có tính phí",{exact:true}).isChecked(),false);
  assert.equal(await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).isDisabled(),true);
  await consent.check();
  await page.getByLabel("Xác nhận gửi crop OCR có tính phí",{exact:true}).check();
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  await page.getByText(/Đã lưu. Thay đổi luồng CPU/).waitFor();
  const savedVision=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="settings").at(-1).params);
  assert.equal(savedVision.ocr,"cloud-gemini");assert.equal(savedVision.cloudOcrConsent,true);
  assert.equal(await page.evaluate(start=>window.__qaCalls.slice(start).some(c=>["image","pipeline","translate","warmup"].includes(c.op)),beforeVision),false);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),"Cloud image consent overflows mobile");
  await page.getByLabel("Nhận chữ",{exact:true}).scrollIntoViewIfNeeded();
  await capture(page,"cloud-image-consent-mobile");
  await page.getByRole("button",{name:"Dịch ngay",exact:true}).click();
  assert.match(await page.getByRole("note",{name:"Engine của phiên dịch"}).innerText(),/gửi crop tới Gemini/);
  await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
  await page.getByLabel("Chế độ dịch",{exact:true}).selectOption("offline");
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  const savedOffline=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="settings").at(-1).params);
  assert.equal(savedOffline.ocr,"manga");assert.equal(savedOffline.cloudOcrConsent,false);
  await page.getByLabel("Chế độ dịch",{exact:true}).selectOption("byok");
  assert.equal(await page.getByLabel("Nhận chữ",{exact:true}).inputValue(),"manga");
  await page.getByLabel("Model cloud",{exact:true}).scrollIntoViewIfNeeded();
  await capture(page,"cloud-models-mobile");
  await page.setViewportSize({width:1280,height:900});
  await page.getByLabel("Chế độ dịch",{exact:true}).scrollIntoViewIfNeeded();
  await capture(page,"cloud-models-desktop");
  const beforeSummarySetup=await page.evaluate(()=>window.__qaCalls.length);
  await page.getByLabel("Engine tóm tắt",{exact:true}).selectOption("cloud");
  const summaryConsent=page.getByLabel("Đồng ý phí tóm tắt cloud",{exact:true});
  assert.equal(await summaryConsent.isChecked(),false);
  assert.equal(await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).isDisabled(),true);
  await page.getByLabel(/Cho phép gửi text OCR/).check();await summaryConsent.check();
  await page.getByLabel("Model tóm tắt",{exact:true}).selectOption("anthropic/claude-haiku-5.5");
  assert.equal(await summaryConsent.isChecked(),false,"A summary-model change requires new consent");
  await summaryConsent.check();
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  await page.getByText(/Đã lưu. Thay đổi luồng CPU/).waitFor();
  assert.equal(await page.evaluate(start=>window.__qaCalls.slice(start).some(c=>c.op==="summarize"),beforeSummarySetup),false);
  await page.getByLabel("Engine tóm tắt",{exact:true}).scrollIntoViewIfNeeded();await capture(page,"cloud-summary-desktop");
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),"Summary consent overflows");
  await capture(page,"cloud-summary-mobile");
  await page.evaluate(()=>{window.__qaNoLocalSummary=true;window.__qaSummaryQueue.pending=1;});
  // Re-read status after a key operation, with no local summary model installed.
  await page.getByLabel(/API key/).fill("QA-only-fake-key");
  await page.getByRole("button",{name:"Lưu key",exact:true}).click();
  await page.getByText(/Bấm Lưu cấu hình để áp dụng/).waitFor();
  await page.getByRole("button",{name:"Thư viện",exact:true}).click();
  await page.getByRole("button",{name:/Bộ nhớ khác/}).click();
  await page.getByText(/1 trang chờ/).waitFor();
  const manualSummary=page.getByRole("button",{name:"Tóm tắt một trang",exact:true});
  assert.equal(await manualSummary.isEnabled(),true,"Consented cloud summaries do not require a local model");
  let accepted=false;page.on("dialog",dialog=>accepted?dialog.accept():dialog.dismiss());
  const beforeManual=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="summarize").length);
  await manualSummary.click();
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="summarize").length),beforeManual);
  accepted=true;await manualSummary.click();await page.getByText(/Đã tóm tắt một trang đã đọc/).waitFor();
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="summarize").length),beforeManual+1);
  await page.getByText(/0 trang chờ/).waitFor();
  assert.equal(await manualSummary.isDisabled(),true);
  await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
  await page.getByLabel("Chế độ dịch",{exact:true}).selectOption("offline");
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  const summaryOffline=await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="settings").at(-1).params);
  assert.equal(summaryOffline.summaryBackend,"local");assert.equal(summaryOffline.summaryCloudConsent,false);
  await page.evaluate(()=>{window.__qaLegacySummary=true;window.__qaUsageUnavailable=true;});
  await page.getByLabel("Chế độ dịch",{exact:true}).selectOption("byok");
  await page.getByLabel(/API key/).fill("QA-only-fake-key");
  await page.getByRole("button",{name:"Lưu key",exact:true}).click();
  await page.getByText(/Tóm tắt cloud cần cập nhật companion/).waitFor();
  await page.getByRole("note").filter({hasText:/Chưa đọc được biên nhận chi phí/}).waitFor();
  assert.equal(await page.getByLabel("Engine tóm tắt",{exact:true}).count(),0);
  assert.equal(await page.getByLabel(/Tóm tắt local sau khi tôi bấm/).count(),1);
  await page.goto(origin+"/popup.html");
  await page.waitForFunction(()=>window.__qaCalls.some(c=>c.op==="warmup"));
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="warmup").length),1,
    "Reader popup must retain one opportunistic warmup");
  // A document navigation resets this mock account. Set an explicit saved
  // cloud choice in the new popup, then leave a DIFFERENT draft unsaved.
  await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
  await page.getByLabel("Chế độ dịch",{exact:true}).selectOption("byok");
  await page.getByLabel("Model cloud",{exact:true}).selectOption("anthropic/claude-haiku-5.5");
  await page.getByLabel(/Cho phép gửi text OCR/).check();
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  await page.getByText(/Đã lưu. Thay đổi luồng CPU/).waitFor();
  await page.getByLabel("Model cloud",{exact:true}).selectOption("__custom__");
  await page.getByLabel("Model ID",{exact:true}).fill("reader/custom-model");
  await page.getByRole("button",{name:"Dịch ngay",exact:true}).click();
  const savedEngine=page.getByRole("note",{name:"Engine của phiên dịch"});
  assert.match(await savedEngine.innerText(),/Cloud BYOK.*openrouter.*anthropic\/claude-haiku-5.5/);
  assert.doesNotMatch(await savedEngine.innerText(),/reader\/custom-model/,
    "Reader must show the SAVED model, never an unsaved settings draft");
  await page.getByRole("checkbox",{name:/Chuẩn bị tối đa 2 ảnh/}).check();
  await page.getByText(/Chuẩn bị trước cũng gọi API tính phí/).waitFor();
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>["image","reader.start"].includes(c.op))),false);
  await page.evaluate(()=>scrollTo(0,0));
  await capture(page,"reader-cloud-mode-desktop");
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>scrollTo(0,0));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),"Saved engine identity overflows on mobile");
  await capture(page,"reader-cloud-mode-mobile");
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,url:origin+"/options.html",browser_plugin:"Browser plugin not available",
    checks:["identity/nonblank","console health","current name only","no future facts shown","summary retry scoped to selected story",
      "manual summary cutoff","disabled when queue empty","390px no overflow","large chunked UTF-8 import/export",
      "cutoff refetch","late old-story response cannot overwrite new story","editor opens selected canonical term",
      "long notes expand/collapse without losing content","10-record paging and local search","new story clears old editor fields",
      "cold library does not warm heavy engines; reader popup warms once",
      "free local art cleanup default-on; explicit opt-out saved without triggering translation",
      "cloud picker preserves key-save draft; per-model/provider consent; custom IDs; saving has no paid calls",
      "image upload requires separate consent, saving never charges, offline restores local OCR",
      "summary model has separate consent; saving cannot summarize backlog; manual paid action can be declined",
      "cloud summary works without local weights; offline revokes consent; empty queue disables action",
      "first-viewport screenshots on desktop/mobile"],screenshots:"RAM only",
    limits:["Mocked native responses; not installed extension or model-quality proof"]},null,2));
  if(process.argv.includes("--ram-preview"))console.log("QA_RAM_IMAGES="+JSON.stringify(ramImages.filter(r=>r.label==="cloud-summary-desktop"||r.label==="cloud-summary-mobile"||r.label==="runtime-presentation-desktop")));
}finally{await browser.close();}
