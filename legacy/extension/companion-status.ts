import type {Status} from "../shared/contracts";

function record(value:unknown):value is Record<string,unknown>{
  return value!==null&&typeof value==="object"&&!Array.isArray(value);
}
function flags(value:unknown){
  return record(value)&&Object.values(value).every(flag=>typeof flag==="boolean");
}
function nullableMetric(value:unknown){return value===null||(typeof value==="number"&&Number.isFinite(value)&&value>=0);}

// A truthy native reply is not proof of a usable library/settings response.
// Validate the fields consumed by the UI; never invent defaults or erase a
// reader's opt-out to make an older/incomplete companion look connected.
export function checkedStatus(value:unknown):Status{
  const settings=record(value)?value.settings:undefined;
  if(!record(value)||typeof value.version!=="string"||!record(settings)||
    !["offline","byok"].includes(String(settings.mode))||
    !["deepseek","gemini","openrouter"].includes(String(settings.provider))||
    !["paddle","opencv","cloud-page"].includes(String(settings.detector))||
    typeof settings.threads!=="number"||!Number.isInteger(settings.threads)||settings.threads<1||settings.threads>16||
    ["cloudConsent","metadataConsent","autoSummary"].some(key=>typeof settings[key]!=="boolean")||
    (settings.artCleanup!==undefined&&typeof settings.artCleanup!=="boolean")||
    (settings.cloudOcrConsent!==undefined&&typeof settings.cloudOcrConsent!=="boolean")||
    (settings.cloudPageOcrConsent!==undefined&&typeof settings.cloudPageOcrConsent!=="boolean")||
    (settings.summaryCloudConsent!==undefined&&typeof settings.summaryCloudConsent!=="boolean")||
    (settings.summaryBackend!==undefined&&!["local","cloud"].includes(String(settings.summaryBackend)))||
    (settings.summaryModel!==undefined&&(typeof settings.summaryModel!=="string"||settings.summaryModel.length<1||settings.summaryModel.length>80))||
    (settings.cloudOcrModel!==undefined&&(typeof settings.cloudOcrModel!=="string"||settings.cloudOcrModel.length<1||settings.cloudOcrModel.length>100))||
    (settings.ocr!==undefined&&!["manga","cloud-gemini"].includes(String(settings.ocr)))||
    ["deepseekModel","geminiModel","openrouterModel"].some(key=>typeof settings[key]!=="string")||
    !flags(value.models)||!flags(value.keys)||!Array.isArray(value.stories)||
    value.stories.some(story=>!record(story)||typeof story.id!=="string"||typeof story.title!=="string"||
      typeof story.version!=="number"||!Number.isFinite(story.version))||
    (value.engineWarm!==undefined&&typeof value.engineWarm!=="boolean")||
    (value.summaryUsageUnavailable!==undefined&&typeof value.summaryUsageUnavailable!=="boolean")||
    (value.runtimeBuild!==undefined&&(typeof value.runtimeBuild!=="string"||value.runtimeBuild.length!==75||!/^pkg-sha256:[a-f0-9]{64}$/.test(value.runtimeBuild)))||
    ["promptVersion","ocrVersion","layoutVersion","presentationVersion","scopeVersion","speakerBindingVersion","scheduleVersion","summaryVersion"].some(key=>
      value[key]!==undefined&&typeof value[key]!=="string")||
    (value.summaryUsage!==undefined&&(!Array.isArray(value.summaryUsage)||value.summaryUsage.length>10||value.summaryUsage.some(row=>
      !record(row)||typeof row.id!=="string"||typeof row.model!=="string"||typeof row.state!=="string"||
      typeof row.started!=="number"||!Number.isFinite(row.started)||
      (row.providerId!==undefined&&row.providerId!==null&&(typeof row.providerId!=="string"||!/^gen-[A-Za-z0-9._:-]{1,120}$/.test(row.providerId)))||
      ![row.costUsd,row.inputTokens,row.outputTokens].every(nullableMetric))))||
    (value.cloudModels!==undefined&&(!Array.isArray(value.cloudModels)||value.cloudModels.some(model=>
      !record(model)||!["deepseek","gemini","openrouter"].includes(String(model.provider))||
      typeof model.id!=="string"||typeof model.label!=="string"||typeof model.note!=="string")))){
    throw new Error("Companion trả dữ liệu không tương thích. Reload extension và kiểm tra bản companion; không cần xóa bộ nhớ hay key.");
  }
  return value as unknown as Status;
}

// Only the read-only status call has this UI deadline. Do not use a UI timeout
// to retry mutations or paid inference, and do not apply a reply after expiry.
export function loadStatus(transport:()=>Promise<unknown>,timeoutMs=15000):Promise<Status>{
  return new Promise((resolve,reject)=>{
    let settled=false;
    const timer=setTimeout(()=>{
      settled=true;
      reject(new Error("Chưa nhận được phản hồi từ companion sau 15 giây. Kiểm tra companion rồi bấm Kết nối lại; không có yêu cầu dịch nào được gửi."));
    },timeoutMs);
    Promise.resolve().then(transport).then(value=>{
      if(settled)return;
      settled=true;clearTimeout(timer);
      try{resolve(checkedStatus(value));}catch(error){reject(error);}
    },error=>{
      if(settled)return;
      settled=true;clearTimeout(timer);reject(error);
    });
  });
}
