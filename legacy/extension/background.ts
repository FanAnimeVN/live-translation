import { NativeBridge } from "./native";
import { TaskError } from "../shared/task-error";
import { readerStartSchema, idSchema, locationSchema, type NativeReply, type ReaderConfig } from "../shared/contracts";
import {nativeBrowser} from "../shared/native-diagnostics";

const bridge=new NativeBridge();
const sessions=new Map<number,{config:ReaderConfig;url:string;jobs:Set<string>}>();
const captures=new Map<number,number>();
const contentOps=new Set(["image","cancel","retranslate","memory.read","speaker.set","term.confirm","reader.settings"]);
const adminOps=new Set(["status","warmup","settings","key.set","key.delete","story.ensure","memory.get","memory.fact",
  "memory.export.page","context.begin","context.chunk","context.commit","context.cancel",
  "memory.recap","memory.voice","memory.style","memory.name","memory.term","memory.delete","memory.import","memory.markdown","memory.retry","summarize","metadata.search","metadata.confirm"]);
const isUi=(sender:chrome.runtime.MessageSender)=>{
  const root=chrome.runtime.getURL("");
  // Options pages legitimately have sender.tab when open_in_tab is true.
  // Match owned UI documents, not arbitrary documents or extension subframes.
  return (sender.frameId===undefined||sender.frameId===0)&&
    ["popup.html","options.html"].some(page=>sender.url===root+page||sender.url===root+page+"#settings");
};

async function currentTab(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id||!tab.url||!/^https?:|^file:/.test(tab.url)) throw new Error("Mở một trang đọc truyện trước.");
  return tab;
}
async function start(config:unknown){
  const checked=readerStartSchema.safeParse(config);
  if(!checked.success){
    if(checked.error.issues.some(issue=>issue.path[0]==="target"))
      throw new Error("Chưa xác định được trang đọc. Đóng rồi mở lại popup trên trang manga để xác nhận ngữ cảnh.");
    throw checked.error;
  }
  const {target,...parsed}=checked.data;
  // Capture the user's chosen page before a cold native connection can wait.
  // Never follow a newly active tab with an already-confirmed story/cutoff.
  const tab=await currentTab(),url=tab.url!;
  if(tab.id!==target.tabId||url!==target.url)throw new Error("Tab hoặc trang đọc đã đổi. Mở lại popup trên trang manga và xác nhận ngữ cảnh.");
  const verifyTarget=async()=>{
    let current:chrome.tabs.Tab;
    try{current=await chrome.tabs.get(tab.id!);}catch{throw new Error("Trang đọc đã đóng. Mở lại trang và xác nhận ngữ cảnh.");}
    if(current.url!==url||current.active===false)throw new Error("Tab hoặc trang đọc đã đổi. Quay lại trang cần dịch và xác nhận ngữ cảnh.");
  };
  await bridge.call("story.ensure",{storyId:parsed.storyId,title:parsed.title,genre:parsed.genre});
  await verifyTarget();
  const old=sessions.get(tab.id!);
  if(old) for(const id of old.jobs) await bridge.call("cancel",{id}).catch(()=>{});
  await verifyTarget();
  await chrome.scripting.executeScript({target:{tabId:tab.id!},files:["content.js"]});
  await verifyTarget();
  const session={config:parsed,url,jobs:new Set<string>()};sessions.set(tab.id!,session);
  try{
    const reply=await chrome.tabs.sendMessage(tab.id!,{type:"start",expectedUrl:url,config:parsed});
    if(reply?.started!==true)throw new Error("Trang đọc chưa xác nhận bắt đầu. Mở lại popup trên trang manga rồi thử lại.");
    await chrome.storage.local.set({["reader:"+new URL(url).hostname]:parsed});
  }catch(error){if(sessions.get(tab.id!)===session)sessions.delete(tab.id!);throw error;}
  return {started:true,tabId:tab.id};
}

chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  void (async()=>{
    if(sender.id!==chrome.runtime.id||!message||typeof message!=="object") throw new Error("Nguồn gửi không hợp lệ.");
    if(isUi(sender)){
      if(message.op==="diagnostics"){
        // This stays in the service worker: no hello, model loading, Vault,
        // database, permission changes or cloud request, even while disconnected.
        const manifest=chrome.runtime.getManifest();
        return {v:1,...bridge.diagnostics(),browser:nativeBrowser(navigator.userAgent),
          extensionId:chrome.runtime.id,manifestBuild:manifest.version_name??manifest.version};
      }
      if(message.op==="reader.info"){
        const tab=await currentTab();
        const host=new URL(tab.url!).hostname;
        const stored=await chrome.storage.local.get("reader:"+host);
        return {tabId:tab.id,title:tab.title,url:tab.url,saved:stored["reader:"+host],session:sessions.get(tab.id!)?.config};
      }
      if(message.op==="reader.start") return start(message.params);
      if(message.op==="reader.stop"){
        const tab=await currentTab();const session=sessions.get(tab.id!);
        if(session) for(const id of session.jobs) await bridge.call("cancel",{id}).catch(()=>{});
        sessions.delete(tab.id!);await chrome.tabs.sendMessage(tab.id!,{type:"stop"}).catch(()=>{});
        return {};
      }
      if(message.op==="reader.region"){
        const tab=await currentTab();if(!sessions.has(tab.id!)) throw new Error("Bật phiên dịch trước.");
        await chrome.tabs.sendMessage(tab.id!,{type:"select"});return {};
      }
      if(!adminOps.has(message.op)) throw new Error("Tác vụ không được phép.");
      return bridge.call(message.op,message.params??{});
    }
    const tabId=sender.tab?.id;
    const session=tabId!==undefined?sessions.get(tabId):undefined;
    if(!session||sender.frameId!==0||sender.url!==session.url||!contentOps.has(message.op)) throw new Error("Phiên đọc đã đổi.");
    if(message.op==="reader.settings"){
      await chrome.tabs.create({url:chrome.runtime.getURL("options.html")+"#settings"});
      return {};
    }
    const params=message.params??{};
    if(message.op==="cancel"){
      if(!session.jobs.has(params.id)) return {};
      return bridge.call("cancel",{id:params.id});
    }
    if(params.storyId!==session.config.storyId) throw new Error("Sai hồ sơ truyện.");
    locationSchema.parse(params.at);
    if(params.at.chapter!==session.config.at.chapter) throw new Error("Chapter đã đổi; xác nhận lại.");
    if(message.op!=="image") return bridge.call(message.op,params);
    idSchema.parse(params.id);idSchema.parse(params.pageId);idSchema.parse(params.revision);
    if(session.jobs.size>=2) throw new Error("Đang xử lý trang trước. Chờ một chút.");
    session.jobs.add(params.id);
    const url=session.url;
    try{
      let dataUrl=params.dataUrl;
      if(params.capture){
        const tab=await chrome.tabs.get(tabId!);
        if(!tab.active||tab.url!==url) throw new Error("Quay lại tab đang đọc trước khi chụp.");
        const previous=captures.get(tabId!)??0;
        const delay=Math.max(0,550-(Date.now()-previous));
        if(delay) await new Promise(resolve=>setTimeout(resolve,delay));
        captures.set(tabId!,Date.now());
        dataUrl=await chrome.tabs.captureVisibleTab(tab.windowId,{format:"png"});
        // The content script crops screenshot in RAM, using its observed viewport transform.
        const cropped=await chrome.tabs.sendMessage(tabId!,{type:"crop",id:params.id,dataUrl,rect:params.capture.rect,
          viewport:params.capture.viewport,epoch:params.capture.epoch});
        if(!cropped?.dataUrl) throw new Error("Trang đã cuộn/đổi. Chọn lại vùng.");
        dataUrl=cropped.dataUrl;
      }
      if(typeof dataUrl!=="string") throw new Error("Thiếu ảnh.");
      await bridge.image(params.id,dataUrl);
      const result=await bridge.call("pipeline",{...params,imageId:params.id,dataUrl:undefined,capture:undefined},
        (reply:NativeReply)=>{
          if(sessions.get(tabId!)!==session) return;
          void chrome.tabs.sendMessage(tabId!,{type:"result",id:params.id,event:reply.event,result:reply.result}).catch(()=>{});
        },params.id);
      if(sessions.get(tabId!)!==session) throw new Error("Trang đã đổi.");
      return result;
    }finally{session.jobs.delete(params.id);}
  })().then(result=>sendResponse({ok:true,result}),error=>sendResponse({ok:false,
    error:error instanceof Error?error.message:"Tác vụ lỗi.",...(error instanceof TaskError&&error.code?{code:error.code}:{})}));
  return true;
});

chrome.tabs.onRemoved.addListener(id=>{
  const session=sessions.get(id);if(session) for(const job of session.jobs) void bridge.call("cancel",{id:job}).catch(()=>{});
  sessions.delete(id);captures.delete(id);
});
chrome.tabs.onUpdated.addListener((id,change)=>{
  if(!change.url) return;
  const session=sessions.get(id);
  if(session&&change.url!==session.url){
    for(const job of session.jobs) void bridge.call("cancel",{id:job}).catch(()=>{});
    sessions.delete(id);
    void chrome.tabs.sendMessage(id,{type:"stop",reason:"Chapter/trang đã đổi. Bấm extension để xác nhận và tiếp tục."}).catch(()=>{});
  }
});
