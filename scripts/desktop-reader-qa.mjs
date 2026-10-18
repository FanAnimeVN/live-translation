// Desktop React reader setup only; mocked native boundary, no keys/API/models.
import {chromium} from "playwright";
import {fileURLToPath} from "node:url";
import path from "node:path";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const i=process.argv.indexOf("--edge-executable");
const browser=await chromium.launch({...(i>=0?{executablePath:process.argv[i+1]}:{channel:"msedge"}),headless:true});
const images=[];
try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  page.setDefaultTimeout(5000);
  page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
  const origin="http://127.0.0.1:65303";
  for(const [file,type] of [["options.html","text/html"],["ui.js","application/javascript"],["ui.css","text/css"]])
    await page.route(origin+"/"+file,route=>route.fulfill({path:path.join(root,"dist/extension",file),contentType:type}));
  await page.addInitScript(()=>{
    window.__qaCalls=[];window.__qaWarmFail=true;
    window.chrome={runtime:{id:"a".repeat(32),getManifest:()=>({version:"qa"}),async sendMessage({op,params}){
      window.__qaCalls.push({op,params});let result={};
      if(op==="status")result={version:"qa",settings:{mode:"byok",provider:"openrouter",ocr:"cloud-gemini",detector:"paddle",threads:4,
        cloudConsent:true,cloudOcrConsent:true,metadataConsent:false,autoSummary:false,artCleanup:true,
        openrouterModel:"deepseek/deepseek-v4.1-flash",deepseekModel:"deepseek-flash",geminiModel:"gemini-3.5-flash-lite"},
        models:{ocr:false,detector:true},keys:{openrouter:true},stories:[],engineWarm:false};
      if(op==="reader.info"){
        if(sessionStorage.getItem("qaNoTarget"))return {ok:false,error:"Chọn tab manga trước khi dịch."};
        result={tabId:12,title:"Trang tự tạo",url:"http://127.0.0.1:65303/chapter/1"};
      }
      if(op==="warmup"){
        await new Promise(resolve=>setTimeout(resolve,250));
        if(window.__qaWarmFail)return {ok:false,error:"Engine QA chưa sẵn sàng"};
        result={ready:true,warmup_ms:250};
      }
      return {ok:true,result};
    }}};
  });
  await page.goto(origin+"/options.html");
  assert.equal(await page.title(),"Live translation");await page.getByRole("heading",{name:"Thư viện của bạn"}).waitFor();
  await page.getByRole("button",{name:"Dịch ngay",exact:true}).click();
  await page.getByRole("heading",{name:"Xác nhận ngữ cảnh"}).waitFor();
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>c.op==="warmup")),false);
  const prepare=page.getByRole("button",{name:"Chuẩn bị engine · không tốn credit",exact:true});
  await prepare.click();
  await page.getByText("Đang chuẩn bị engine trên máy…",{exact:true}).waitFor();
  assert(await page.getByRole("button",{name:"Đang chuẩn bị engine trên máy…",exact:true}).isDisabled());
  await page.getByRole("alert").filter({hasText:"Engine QA chưa sẵn sàng"}).waitFor();
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="warmup").length),1);
  assert(await prepare.isEnabled(),"Failed warmup must permit explicit retry, not auto-repeat");
  await page.evaluate(()=>window.__qaWarmFail=false);await prepare.click();
  const ready=page.getByRole("button",{name:"Engine đã sẵn sàng",exact:true});await ready.waitFor();assert(await ready.isDisabled());
  await page.getByText(/Chỉ nạp engine trên máy/).waitFor();
  assert.equal(await page.evaluate(()=>window.__qaCalls.filter(c=>c.op==="warmup").length),2);
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>["image","pipeline","translate","metadata.search","reader.start","settings"].includes(c.op))),false);
  assert.equal(await page.locator("vite-error-overlay,nextjs-portal").count(),0);assert.deepEqual(errors,[]);
  images.push({label:"desktop-prepared-reader",mimeType:"image/jpeg",data:(await page.screenshot({type:"jpeg",quality:80})).toString("base64")});
  await page.evaluate(()=>window.__qaCalls=[]);
  await page.getByRole("button",{name:"Bắt đầu dịch",exact:true}).click();
  await page.getByRole("status").filter({hasText:"Đã bật dịch. Quay lại trang đọc"}).waitFor();
  const startCalls=await page.evaluate(()=>window.__qaCalls);
  assert.deepEqual(startCalls.map(c=>c.op),["reader.start"],"Start must capture the current tab in the background before waiting for any story.ensure call");
  assert.equal(startCalls[0].params.title,"Trang tự tạo");assert(startCalls[0].params.storyId);
  assert.deepEqual(startCalls[0].params.target,{tabId:12,url:"http://127.0.0.1:65303/chapter/1"});
  await page.evaluate(()=>sessionStorage.setItem("qaNoTarget","1"));await page.reload();
  await page.getByRole("heading",{name:"Thư viện của bạn"}).waitFor();
  await page.getByRole("button",{name:"Dịch ngay",exact:true}).click();
  await page.getByText(/Chưa chọn được tab manga/).waitFor();
  await page.getByRole("textbox",{name:"Tên truyện",exact:true}).fill("Tên tự nhập");
  assert(await page.getByRole("button",{name:"Bắt đầu dịch",exact:true}).isDisabled(),"A manually entered title is not evidence of a readable tab");
  assert.equal(await page.evaluate(()=>window.__qaCalls.some(c=>["warmup","reader.start","story.ensure","image","pipeline","translate"].includes(c.op))),false);
  assert.deepEqual(errors,[]);
  images.push({label:"desktop-no-reading-target",mimeType:"image/jpeg",data:(await page.screenshot({type:"jpeg",quality:80})).toString("base64")});
  console.log(JSON.stringify({passed:true,viewport:"1280x900",url:page.url(),browser:"isolated Edge; Browser plugin not available",
    checks:["identity/nonblank","no framework overlay","console clean","no automatic preparation in options",
      "explicit warmup, disabled duplicate button","failure + explicit retry","no image/text/settings/paid request","ready status",
      "start uses a single target-capturing operation","missing reading target explained, no guessed tab, start disabled"],
    limitations:["Mocked native boundary; not personal-profile connection or live latency proof"]},null,2));
}finally{await browser.close();if(process.argv.includes("--ram-preview"))console.log("QA_RAM_IMAGES="+JSON.stringify(images));}
