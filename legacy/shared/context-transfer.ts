import type {ReadingLocation,Story} from "./contracts";

export const MAX_CONTEXT_PACK_BYTES=16*1024*1024;
type Rpc=(op:string,params:Record<string,unknown>)=>Promise<any>;
export interface ContextPack {
  schema:1;story:Story;facts:any[];summaries:any[];
  progress?:{last_chapter:number;last_page:number;furthest_chapter:number}|null;
  summaryStatus?:{enabled:boolean;pending:number;failed:number;gap:number;done:number};
}

function checkAbort(signal?:AbortSignal){
  if(signal?.aborted)throw new DOMException("Đã hủy tải hồ sơ cũ.","AbortError");
}

export async function readContextPack(rpc:Rpc,storyId:string,options:{at?:ReadingLocation;signal?:AbortSignal}={}):Promise<ContextPack>{
  let cursor:unknown=null,pack:ContextPack|undefined,version:number|undefined,snapshotId:string|undefined,bytes=0;
  const cursors=new Set<string>(),factIds=new Set<string>(),summaryIds=new Set<string>();
  for(let page=0;page<10000;page++){
    checkAbort(options.signal);
    const part=await rpc("memory.export.page",{storyId,cursor,...(options.at?{at:options.at}:{})});
    checkAbort(options.signal);
    if(part?.schema!==1||part.story?.id!==storyId||typeof part.story?.title!=="string"||
       !Number.isInteger(part.snapshotVersion)||typeof part.snapshotId!=="string"||!part.snapshotId||
       !Array.isArray(part.facts)||!Array.isArray(part.summaries))
      throw new Error("Companion trả phần hồ sơ không hợp lệ.");
    if(version!==undefined&&(version!==part.snapshotVersion||snapshotId!==part.snapshotId))throw new Error("Hồ sơ hoặc tiến độ vừa đổi. Hãy tải lại.");
    version=part.snapshotVersion;snapshotId=part.snapshotId;
    const partBytes=new TextEncoder().encode(JSON.stringify(part)).length;
    if(partBytes>160000||(bytes+=partBytes)>MAX_CONTEXT_PACK_BYTES)
      throw new Error("Hồ sơ vượt giới hạn chuyển 16 MB của bản MVP; dữ liệu gốc không bị thay đổi.");
    if(!pack)pack={schema:1,story:part.story,progress:part.progress,facts:[],summaries:[],summaryStatus:part.summaryStatus};
    for(const [records,ids,target] of [[part.facts,factIds,pack.facts],[part.summaries,summaryIds,pack.summaries]] as const){
      for(const record of records){
        if(typeof record?.id!=="string"||ids.has(record.id))throw new Error("Phần hồ sơ bị trùng hoặc thiếu ID.");
        ids.add(record.id);target.push(record);
      }
    }
    if(part.next===null)return pack;
    if(!part.next||part.facts.length+part.summaries.length===0)throw new Error("Không có tiến độ khi tải hồ sơ.");
    const key=JSON.stringify(part.next);
    if(cursors.has(key))throw new Error("Cursor hồ sơ bị lặp. Không ghép dữ liệu chưa đầy đủ.");
    cursors.add(key);cursor=part.next;
  }
  throw new Error("Quá nhiều phần context; không xuất hồ sơ thiếu.");
}

export async function importContextPack(rpc:Rpc,pack:unknown):Promise<{storyId:string}>{
  const data=new TextEncoder().encode(JSON.stringify(pack));
  if(data.length===0||data.length>MAX_CONTEXT_PACK_BYTES)throw new Error("Hồ sơ context tối đa 16 MB.");
  const digest=await crypto.subtle.digest("SHA-256",data);
  const sha256=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,"0")).join("");
  const transferId=crypto.randomUUID();let begun=false,committed=false;
  try{
    await rpc("context.begin",{transferId,bytes:data.length,sha256});begun=true;
    for(let offset=0;offset<data.length;offset+=128*1024){
      let binary="";
      for(const byte of data.subarray(offset,offset+128*1024))binary+=String.fromCharCode(byte);
      await rpc("context.chunk",{transferId,offset,data:btoa(binary)});
    }
    const result=await rpc("context.commit",{transferId});committed=true;return result;
  }finally{
    if(begun&&!committed)await rpc("context.cancel",{transferId}).catch(()=>{});
  }
}
