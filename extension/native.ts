import { HOST, type NativeReply } from "../shared/contracts";
import { TaskError } from "../shared/task-error";
import {nativeFailure,type NativeFailure,type NativeTransportDiagnostics} from "../shared/native-diagnostics";

type Pending={port:chrome.runtime.Port;resolve:(value:any)=>void;reject:(reason:Error)=>void;event?:(reply:NativeReply)=>void;timer:ReturnType<typeof setTimeout>};
export class NativeBridge {
  private port?:chrome.runtime.Port;
  private pending=new Map<string,Pending>();
  private ready?:Promise<void>;
  private profile="";
  private keepalive?:ReturnType<typeof setInterval>;
  private failure:NativeFailure="NONE";

  diagnostics():NativeTransportDiagnostics{
    return {host:HOST,state:this.keepalive?"ready":this.port?"connecting":"disconnected",
      failure:this.failure,pendingCalls:this.pending.size};
  }

  async connect() {
    if(this.ready) return this.ready;
    let connectionPort:chrome.runtime.Port|undefined;
    const attempt=(async()=>{
      this.failure="NONE";
      const stored=await chrome.storage.local.get("profileId");
      this.profile=typeof stored.profileId==="string"?stored.profileId:crypto.randomUUID();
      if(typeof stored.profileId!=="string") await chrome.storage.local.set({profileId:this.profile});
      const port=chrome.runtime.connectNative(HOST);connectionPort=port;this.port=port;
      port.onMessage.addListener((message:NativeReply)=>{
        if(this.port!==port) return;
        if(message?.v!==1||typeof message.id!=="string") return;
        const pending=this.pending.get(message.id);
        if(!pending||pending.port!==port) return;
        if(message.event){pending.event?.(message);return;}
        clearTimeout(pending.timer);this.pending.delete(message.id);
        if(message.ok) pending.resolve(message.result);
        else pending.reject(new TaskError(typeof message.error?.message==="string"?message.error.message:"Companion trả lỗi.",message.error?.code));
      });
      port.onDisconnect.addListener(()=>{
        const reason=chrome.runtime.lastError?.message??"Companion đã ngắt kết nối.";
        this.releasePort(port,reason);
      });
      await this.send("hello",{},undefined,10000);
      if(this.port!==port) throw new Error("Companion đã ngắt kết nối trong lúc khởi động.");
      this.keepalive=setInterval(()=>{
        if(this.port===port)void this.send("status",{},undefined,5000).catch(()=>{});
      },25000);
    })();
    this.ready=attempt;
    try{await attempt;}catch(error){
      if(connectionPort){
        this.releasePort(connectionPort,"Không hoàn tất kết nối companion.");
        // Closing this captured failed channel releases its native host.
        // Never disconnect a replacement opened while the old attempt ends.
        try{connectionPort.disconnect();}catch{/* Already disconnected. */}
      }
      if(this.ready===attempt)this.ready=undefined;
      throw error;
    }
  }
  private releasePort(port:chrome.runtime.Port,reason:string){
    for(const [id,p] of this.pending){
      if(p.port!==port)continue;
      clearTimeout(p.timer);this.pending.delete(id);p.reject(new Error(reason));
    }
    if(this.port!==port)return;
    this.failure=nativeFailure(reason);
    this.port=undefined;this.ready=undefined;
    if(this.keepalive)clearInterval(this.keepalive);
    this.keepalive=undefined;
  }
  private send(op:string,params:any,event?:Pending["event"],timeout=180000,id:string=crypto.randomUUID()) {
    return new Promise<any>((resolve,reject)=>{
      const port=this.port;
      if(!port){reject(new Error("Companion chưa kết nối. Thử lại."));return;}
      if(this.pending.has(id)){reject(new Error("Tác vụ đang chạy; không gửi trùng ID."));return;}
      const timer=setTimeout(()=>{
        if(this.pending.get(id)?.port!==port)return;
        this.pending.delete(id);
        try{port.postMessage({v:1,id:crypto.randomUUID(),profile:this.profile,op:"cancel",params:{id}});}catch{/* Closed channel. */}
        reject(new Error("Tác vụ quá thời gian. Chọn vùng nhỏ hơn hoặc thử lại."));
      },timeout);
      this.pending.set(id,{port,resolve,reject,event,timer});
      try{port.postMessage({v:1,id,profile:this.profile,op,params});}
      catch(error){clearTimeout(timer);this.pending.delete(id);reject(error);}
    });
  }
  async call(op:string,params:any={},event?:Pending["event"],id?:string) {
    await this.connect();return this.send(op,params,event,op==="pipeline"?240000:180000,id);
  }
  async image(imageId:string,dataUrl:string) {
    if(!/^data:image\/(?:png|jpeg|webp);base64,/.test(dataUrl)) throw new Error("Ảnh không hợp lệ.");
    const b64=dataUrl.substring(dataUrl.indexOf(",")+1);
    const bytes=atob(b64);
    if(bytes.length>8*1024*1024) throw new Error("Ảnh quá lớn. Chọn một vùng đang đọc.");
    await this.call("image.begin",{imageId,bytes:bytes.length});
    // Chunks stay below both native framing and MV3 message limits.
    for(let offset=0;offset<bytes.length;offset+=192*1024){
      await this.call("image.chunk",{imageId,offset,data:btoa(bytes.slice(offset,offset+192*1024))});
    }
  }
}
