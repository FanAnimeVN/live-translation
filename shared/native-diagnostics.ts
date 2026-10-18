// Public transport metadata only. Never include profile IDs, source URLs,
// settings, keys, text, memories, prompts, stack traces or raw provider errors.
export type NativeFailure="NONE"|"NATIVE_HOST_NOT_FOUND"|"NATIVE_ACCESS_DENIED"|"NATIVE_START_FAILED"|"NATIVE_DISCONNECTED";
export type NativeTransportDiagnostics={host:string;state:"disconnected"|"connecting"|"ready";failure:NativeFailure;pendingCalls:number};
export type NativeDiagnostics=NativeTransportDiagnostics&{v:1;browser:"edge"|"chrome"|"other";extensionId:string;manifestBuild:string};

export function nativeFailure(reason:string):NativeFailure{
  if(reason==="Specified native messaging host not found."||reason==="Native messaging host host name is not registered.")return "NATIVE_HOST_NOT_FOUND";
  if(reason==="Access to the specified native messaging host is forbidden.")return "NATIVE_ACCESS_DENIED";
  if(reason==="Failed to start native messaging host.")return "NATIVE_START_FAILED";
  return "NATIVE_DISCONNECTED";
}
export function nativeBrowser(userAgent:string):NativeDiagnostics["browser"]{
  if(/\bEdg\//.test(userAgent))return "edge";
  if(/\bChrome\//.test(userAgent)&&!/\b(?:OPR|Brave)\//.test(userAgent))return "chrome";
  return "other";
}
export function checkedNativeDiagnostics(value:unknown):NativeDiagnostics{
  const r=value as Partial<NativeDiagnostics>|null;
  if(!r||typeof r!=="object"||r.v!==1||typeof r.host!=="string"||
    !/^[a-z0-9_]+(?:\.[a-z0-9_]+)+$/.test(r.host)||r.host.length>100||
    !["edge","chrome","other"].includes(String(r.browser))||
    !["disconnected","connecting","ready"].includes(String(r.state))||
    !["NONE","NATIVE_HOST_NOT_FOUND","NATIVE_ACCESS_DENIED","NATIVE_START_FAILED","NATIVE_DISCONNECTED"].includes(String(r.failure))||
    typeof r.pendingCalls!=="number"||!Number.isInteger(r.pendingCalls)||r.pendingCalls<0||r.pendingCalls>1024||
    typeof r.extensionId!=="string"||!/^[a-p]{32}$/.test(r.extensionId)||
    typeof r.manifestBuild!=="string"||!/^[A-Za-z0-9._-]{1,100}$/.test(r.manifestBuild))
    throw new Error("Service worker chưa trả chẩn đoán tương thích. Reload extension và mở lại Cài đặt; không cần xóa dữ liệu.");
  // Copy only this allowlist, even if a future transport accidentally adds data.
  return {v:1,browser:r.browser!,host:r.host,state:r.state!,failure:r.failure!,pendingCalls:r.pendingCalls,
    extensionId:r.extensionId,manifestBuild:r.manifestBuild};
}
export function loadNativeDiagnostics(transport:()=>Promise<unknown>,timeoutMs=5000):Promise<NativeDiagnostics>{
  return new Promise((resolve,reject)=>{
    let settled=false;
    const timer=setTimeout(()=>{settled=true;reject(new Error("Service worker chưa trả chẩn đoán sau 5 giây. Chưa gọi companion hoặc API."));},timeoutMs);
    Promise.resolve().then(transport).then(value=>{
      if(settled)return;settled=true;clearTimeout(timer);
      try{resolve(checkedNativeDiagnostics(value));}catch(error){reject(error);}
    },error=>{if(settled)return;settled=true;clearTimeout(timer);reject(error);});
  });
}
