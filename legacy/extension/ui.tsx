import React,{useEffect,useState,useRef,useMemo,useCallback} from "react";
import {createRoot} from "react-dom/client";
import {inferChapter,stableId,latestFactsAt,readerTargetSchema,type ReaderTarget,type Status,type ReaderConfig,type Settings,type Story,type CloudModelChoice} from "../shared/contracts";
import "./ui.css";
import {readContextPack,importContextPack,MAX_CONTEXT_PACK_BYTES} from "../shared/context-transfer";
import {MemoryFact,type TermView} from "./memory-fact";
import {checkedStatus,loadStatus} from "./companion-status";
import {loadNativeDiagnostics,type NativeDiagnostics} from "../shared/native-diagnostics";

async function call(op:string,params:any={}){
  const reply=await chrome.runtime.sendMessage({op,params});
  if(!reply?.ok)throw new Error(reply?.error??"Extension chưa phản hồi.");
  return reply.result;
}
type Pack={schema:number;story:Story;facts:any[];summaries:any[];
  summaryStatus?:{enabled:boolean;pending:number;failed:number;gap:number;done:number}};
function download(value:string,type:string,name:string){
  const url=URL.createObjectURL(new Blob([value],{type}));
  const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function CloudModelPicker({provider,value,choices,onChange}:{provider:Settings["provider"];value:string;
  choices:CloudModelChoice[];onChange:(value:string)=>void}){
  const [custom,setCustom]=useState(false);
  const available=choices.filter(choice=>choice.provider===provider);
  const selected=available.find(choice=>choice.id===value);
  const isCustom=custom||!selected;
  return <>
    <label>Model cloud<select aria-label="Model cloud" aria-describedby="cloud-model-note" value={isCustom?"__custom__":value} onChange={event=>{
      const id=event.currentTarget.value;setCustom(id==="__custom__");if(id!=="__custom__")onChange(id);
    }}>
      {available.map(choice=><option key={choice.id} value={choice.id}>{choice.label}</option>)}
      <option value="__custom__">Model ID tùy chỉnh</option>
    </select></label>
    {isCustom?<label>Model ID<input value={value} maxLength={80} onChange={event=>onChange(event.currentTarget.value)} autoComplete="off"/></label>:null}
    <p className="hint" id="cloud-model-note">{selected?.note??"Model tùy chỉnh chưa được kiểm chứng; adapter không tự đổi model khi có lỗi."}</p>
    <p className="muted">Danh sách là ứng viên kiểm thử, không phải cam kết chất lượng/tốc độ. Giá và route có thể thay đổi. Chọn hoặc lưu model không gọi API; áp dụng khi bắt đầu dịch lại.</p>
  </>;
}

function SummarySettings({settings,status,onChange}:{settings:Settings;status:Status;onChange:(settings:Settings)=>void}){
  if(status.summaryVersion!=="read-evidence-cloud-v1")return <>
    <p className="hint">Tóm tắt cloud cần cập nhật companion có capability read-evidence-cloud-v1. Không tự chuyển sang local.</p>
    {settings.summaryBackend!=="cloud"?<label className="check"><input type="checkbox" checked={settings.autoSummary}
      onChange={e=>onChange({...settings,autoSummary:e.currentTarget.checked})}/>Tóm tắt local sau khi tôi bấm Đã đọc và máy rảnh</label>:null}
  </>;
  const cloud=settings.summaryBackend==="cloud",eligible=settings.mode==="byok"&&settings.provider==="openrouter";
  return <fieldset aria-label="Bộ nhớ sự kiện">
    <legend>Bộ nhớ sự kiện · model độc lập với model dịch</legend>
    <label>Engine tóm tắt<select aria-label="Engine tóm tắt" value={settings.summaryBackend??"local"}
      onChange={e=>onChange({...settings,summaryBackend:e.currentTarget.value as "local"|"cloud",
        summaryModel:settings.summaryModel??"deepseek/deepseek-v4.1-flash",summaryCloudConsent:false,autoSummary:false})}>
      <option value="local">Local · model đã cài, không phí API</option>
      <option value="cloud" disabled={!eligible}>Cloud · BYOK OpenRouter, có phí riêng</option>
    </select></label>
    {cloud?<>
      <label>Model tóm tắt<select aria-label="Model tóm tắt" value={settings.summaryModel??"deepseek/deepseek-v4.1-flash"}
        onChange={e=>onChange({...settings,summaryModel:e.currentTarget.value,summaryCloudConsent:false})}>
        <option value="deepseek/deepseek-v4.1-flash">DeepSeek V4.1 Flash · snapshot tháng 9</option>
        <option value="anthropic/claude-haiku-5.5">Claude Haiku 5.5 · ứng viên</option>
      </select></label>
      <p className="hint">Gửi text Nhật và bản dịch của một trang đã bấm Đã đọc tới OpenRouter/nhà cung cấp, không gửi ảnh hay tra wiki. Thêm một lượt API tính phí ngoài lượt dịch; tối đa 900 token đầu ra/request. Giá phụ thuộc route và thời điểm, chưa có cam kết rẻ/nhanh nhất. Câu tóm tắt có thể sai, không tự xác nhận quan hệ hay speaker.</p>
      <label className="check"><input aria-label="Đồng ý phí tóm tắt cloud" type="checkbox" checked={settings.summaryCloudConsent??false}
        onChange={e=>onChange({...settings,summaryCloudConsent:e.currentTarget.checked})}/>Tôi đồng ý gửi thoại đã đọc để tóm tắt và chịu phí API riêng của model này.</label>
      <p className="hint">Lưu cấu hình không gọi API hoặc chạy backlog. Tự động chỉ áp dụng khi bạn bấm Đã đọc sau khi lưu, trong phiên companion hiện tại; lỗi không tự gửi lại. Đổi model/nhà cung cấp phải xác nhận lại. Hủy không đảm bảo nhà cung cấp hoàn phí request đã gửi.</p>
    </>:<p className="hint">Cần model tóm tắt local riêng, có thể chậm/tốn RAM. Hiện ưu tiên hoàn thiện cloud. Không tự tải model hay tự chuyển sang cloud.</p>}
    <label className="check"><input aria-label="Tóm tắt nền sau Đã đọc" type="checkbox" checked={settings.autoSummary}
      disabled={cloud&&(!eligible||!settings.cloudConsent||!settings.summaryCloudConsent)} onChange={e=>{
        const enabled=e.currentTarget.checked;
        if(enabled&&cloud&&!confirm("Bật tóm tắt nền có phí: mỗi lần bấm Đã đọc có thể gửi thêm một trang text tới model đã chọn khi máy rảnh. Không xử lý backlog; giá theo provider, chưa có trần chi phí tự động. Bạn có thể tắt trong Cài đặt. Đồng ý?"))return;
        onChange({...settings,autoSummary:enabled});
      }}/>{cloud?"Tóm tắt nền có phí cho trang tôi bấm Đã đọc sau khi lưu":"Tóm tắt local sau khi tôi bấm Đã đọc và máy rảnh"}</label>
    <p className="muted">Chỉ lưu đề xuất sự kiện ngắn cùng bằng chứng Nhật liên quan và mốc chapter/page, không coi lời hứa là hành động đã xảy ra. Bản diễn giải chưa được reader xác nhận không thay bằng chứng gốc trong context dịch.</p>
  </fieldset>;
}

function App(){
  const full=location.pathname.includes("options");
  const [status,setStatus]=useState<Status>(),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  const [connection,setConnection]=useState<"connecting"|"ready"|"error">("connecting");
  const [connectionError,setConnectionError]=useState("");
  const [extensionBuild]=useState(()=>chrome.runtime.getManifest?.().version_name??chrome.runtime.getManifest?.().version??"development");
  const connectionRevision=useRef(0);
  const diagnosticRevision=useRef(0);
  const [diagnostic,setDiagnostic]=useState<NativeDiagnostics>();
  const [diagnosticError,setDiagnosticError]=useState("");
  const [diagnosticLoading,setDiagnosticLoading]=useState(false);
  const [view,setView]=useState(()=>full&&location.hash==="#settings"?"settings":full?"library":"reader");
  const [title,setTitle]=useState(""),[storyId,setStoryId]=useState(""),[chapter,setChapter]=useState(1),[page,setPage]=useState(0);
  const [readerTarget,setReaderTarget]=useState<ReaderTarget>(),[readerTargetError,setReaderTargetError]=useState("");
  const [genre,setGenre]=useState(""),[autoScan,setAutoScan]=useState(true),[prefetch,setPrefetch]=useState(false),[active,setActive]=useState(false);
  const [recap,setRecap]=useState(""),[note,setNote]=useState(""),[keyName,setKeyName]=useState(""),[kind,setKind]=useState("character");
  const [apiKey,setApiKey]=useState(""),[pack,setPack]=useState<Pack>(),[metadata,setMetadata]=useState<any[]>([]);
  const [settings,setSettings]=useState<Settings>();
  const [naming,setNaming]=useState("natural"),[voiceSpeaker,setVoiceSpeaker]=useState(""),[voiceListener,setVoiceListener]=useState("");
  const [voiceSelf,setVoiceSelf]=useState(""),[voiceAddress,setVoiceAddress]=useState("");
  const [honorifics,setHonorifics]=useState("preserve"),[kinship,setKinship]=useState("preserve");
  const [nameId,setNameId]=useState(""),[familyJa,setFamilyJa]=useState(""),[familyReading,setFamilyReading]=useState("");
  const [givenJa,setGivenJa]=useState(""),[givenReading,setGivenReading]=useState("");
  const [termEntity,setTermEntity]=useState(""),[termJa,setTermJa]=useState(""),[termVi,setTermVi]=useState("");
  const [termCategory,setTermCategory]=useState("skill"),[termAliases,setTermAliases]=useState("");
  const [warming,setWarming]=useState(false),[engineReady,setEngineReady]=useState(false);
  const warmupPending=useRef(false);
  const [packLoading,setPackLoading]=useState(false),[memoryRefresh,setMemoryRefresh]=useState(0);
  const [visibleFacts,setVisibleFacts]=useState(10),[editProfile,setEditProfile]=useState(false);
  const [memoryFilter,setMemoryFilter]=useState("");
  const storySelection=useRef(0);
  const profileEditor=useRef<HTMLDetailsElement>(null);
  const refresh=useCallback(async()=>{
    const revision=++connectionRevision.current;
    diagnosticRevision.current++;setDiagnostic(undefined);setDiagnosticError("");setDiagnosticLoading(false);
    setConnection("connecting");setConnectionError("");
    try{
      const state=await loadStatus(()=>call("status"));
      if(revision!==connectionRevision.current)return;
      setStatus(state);setSettings(state.settings);setEngineReady(Boolean(state.engineWarm));setConnection("ready");
      return state;
    }catch(e){
      if(revision===connectionRevision.current){
        setConnectionError(e instanceof Error?e.message:"Companion chưa phản hồi.");setConnection("error");
        setStatus(undefined);setSettings(undefined);setEngineReady(false);
      }
      throw e;
    }
  },[]);
  async function diagnoseConnection(){
    const revision=++diagnosticRevision.current,connectionVersion=connectionRevision.current;
    setDiagnosticLoading(true);setDiagnosticError("");setDiagnostic(undefined);
    try{
      const value=await loadNativeDiagnostics(()=>call("diagnostics"));
      if(revision===diagnosticRevision.current&&connectionVersion===connectionRevision.current)setDiagnostic(value);
    }catch(e){
      if(revision===diagnosticRevision.current&&connectionVersion===connectionRevision.current)
        setDiagnosticError(e instanceof Error?e.message:"Chưa đọc được chẩn đoán.");
    }finally{if(revision===diagnosticRevision.current)setDiagnosticLoading(false);}
  }
  async function action(fn:()=>Promise<void>){
    setBusy(true);setError("");setMessage("");
    try{await fn();}catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  async function prepareEngine(){
    if(warmupPending.current)return;
    warmupPending.current=true;const revision=connectionRevision.current;
    setWarming(true);setError("");
    try{
      const result=await call("warmup");
      if(result?.ready!==true)throw new Error("Companion chưa xác nhận engine sẵn sàng.");
      if(revision===connectionRevision.current)setEngineReady(true);
    }catch(e){
      if(revision===connectionRevision.current){setEngineReady(false);setError("Không chuẩn bị được engine: "+(e instanceof Error?e.message:String(e)));}
    }finally{warmupPending.current=false;setWarming(false);}
  }
  useEffect(()=>{
    void refresh().then(state=>{
      if(!state)return;
      // Library/settings visits must not load heavyweight inference workers.
      // The reader popup still warms them while the title/chapter is confirmed.
      if(!full&&!state.engineWarm&&(state.models.ocr||state.settings.ocr==="cloud-gemini")&&
        (state.models.detector||state.settings.detector==="opencv")&&
        (state.settings.mode!=="offline"||state.models.translation||state.models["translation-lite"])){
        void prepareEngine();
      }
    }).catch(()=>{/* Persistent connection state is separate from action errors. */});
    void call("reader.info").then(info=>{
      setReaderTarget(readerTargetSchema.parse({tabId:info.tabId,url:info.url}));setReaderTargetError("");
      const saved=info.saved as ReaderConfig|undefined;
      setTitle(saved?.title??info.title??"");setStoryId(saved?.storyId??"");setGenre(saved?.genre??"");
      setChapter(inferChapter(info.url+" "+info.title)??saved?.at.chapter??1);
      setActive(Boolean(info.session));
    }).catch(()=>{
      setReaderTarget(undefined);
      setReaderTargetError("Chưa chọn được tab manga. Quay lại trang truyện rồi bấm biểu tượng Live translation để mở popup và bắt đầu dịch; trang Cài đặt không tự đoán tab trước đó.");
    });
    return()=>{connectionRevision.current++;diagnosticRevision.current++;};
  },[full,refresh]);
  async function chooseStory(story:Story){
    ++storySelection.current;
    setStoryId(story.id);setTitle(story.title);setGenre(story.genre??"");
    setPack(undefined);
    setVisibleFacts(10);setEditProfile(false);setMemoryFilter("");
    setTermEntity("");setTermJa("");setTermVi("");setTermAliases("");setTermCategory("skill");
    setVoiceSpeaker("");setVoiceListener("");setVoiceSelf("");setVoiceAddress("");
    setNameId("");setFamilyJa("");setFamilyReading("");setGivenJa("");setGivenReading("");
    setKeyName("");setNote("");setRecap("");setMetadata([]);
    setChapter(story.last_chapter??1);setPage(story.last_page??0);
    // Re-selecting the current story must reload too; otherwise clearing its
    // pack leaves an empty library with unchanged effect dependencies.
    setMemoryRefresh(value=>value+1);
  }
  useEffect(()=>{
    if(view!=="library"||!storyId){setPackLoading(false);return;}
    const selection=++storySelection.current,controller=new AbortController();
    setPackLoading(true);
    const timer=setTimeout(()=>{
      void readContextPack(call,storyId,{at:{chapter,page},signal:controller.signal}).then(data=>{
        if(selection===storySelection.current)setPack(data);
      }).catch(e=>{if(!controller.signal.aborted&&selection===storySelection.current)setError(e.message);})
        .finally(()=>{if(!controller.signal.aborted&&selection===storySelection.current)setPackLoading(false);});
    },120);
    return()=>{clearTimeout(timer);controller.abort();};
  },[view,storyId,chapter,page,memoryRefresh]);
  async function ensure(){
    const id=storyId||await stableId(title.trim().normalize("NFKC").toLowerCase());
    await call("story.ensure",{storyId:id,title:title.trim(),genre});setStoryId(id);return id;
  }
  const cutoff={chapter,page};
  // Show the saved runtime choice, never a draft from the settings form.
  const savedEngine=status?.settings;
  const savedCloudModel=savedEngine?.[savedEngine.provider+"Model" as "deepseekModel"|"geminiModel"|"openrouterModel"];
  const cloudSummary=savedEngine?.summaryBackend==="cloud";
  const summaryReady=cloudSummary?status?.summaryVersion==="read-evidence-cloud-v1"&&savedEngine?.mode==="byok"&&
    savedEngine.provider==="openrouter"&&savedEngine.cloudConsent&&savedEngine.summaryCloudConsent&&status?.keys.openrouter:status?.models.summarizer;
  const facts=useMemo(()=>latestFactsAt(pack?.facts??[],{chapter,page}),[pack,chapter,page]);
  const filteredFacts=useMemo(()=>{
    const query=memoryFilter.trim().toLocaleLowerCase();
    return query?facts.filter(f=>(f.key+" "+f.value).toLocaleLowerCase().includes(query)):facts;
  },[facts,memoryFilter]);
  const summaries=useMemo(()=>pack?.summaries.filter(s=>s.chapter_end<chapter||(s.chapter_end===chapter&&s.page_end<=page))??[],[pack,chapter,page]);
  const editTerm=useCallback((term:TermView)=>{
    setTermEntity(term.entity);setTermJa(term.ja);setTermVi(term.vi);setTermCategory(term.category);
    setTermAliases(term.aliases.map(a=>a.ja+" = "+a.vi).join("\n"));setEditProfile(true);
    requestAnimationFrame(()=>profileEditor.current?.scrollIntoView({block:"start"}));
  },[]);
  useEffect(()=>{
    const known=pack?.facts.filter(f=>f.kind==="style"&&(f.chapter<chapter||(f.chapter===chapter&&f.page<=page)))
      .sort((a,b)=>b.chapter-a.chapter||b.page-a.page)??[];
    setNaming(known.find(f=>f.key==="naming")?.value??"natural");
    setHonorifics(known.find(f=>f.key==="honorifics")?.value??"preserve");
    setKinship(known.find(f=>f.key==="kinship")?.value??"preserve");
  },[pack,chapter,page]);
  return <main className={full?"app wide":"app"}>
    <header><div><span className="eyebrow">NHẬT → VIỆT</span><h1>Live translation</h1></div>
      <span className="badge">{connection==="ready"?status?.settings.mode==="byok"?"Cloud BYOK":"Offline":connection==="error"?"Chưa kết nối":"Đang kết nối"}</span></header>
    <nav aria-label="Mục chính">
      {["reader","library","settings"].map((tab,index)=><button key={tab} className={view===tab?"selected":""}
        onClick={()=>{setView(tab);setError("");}}>{["Dịch ngay","Thư viện","Cài đặt"][index]}</button>)}
    </nav>
    {connection!=="ready"?<section className={connection==="error"?"connection alert":"connection notice"}
      role={connection==="error"?"alert":"status"} aria-busy={connection==="connecting"}>
      <h2>{connection==="error"?"Chưa kết nối được companion":"Đang kết nối companion…"}</h2>
      <p>{connection==="error"?connectionError:"Đang đọc cấu hình và thư viện trên máy. Chưa gọi API hay nạp model dịch."}</p>
      <p>Chưa tải được dữ liệu không có nghĩa thư viện trống. Không cần nhập lại key hay xóa bộ nhớ.</p>
      <button disabled={connection==="connecting"} onClick={()=>void refresh().catch(()=>{})}>Kết nối lại</button>
      {connection==="error"?<>
        <button disabled={diagnosticLoading} onClick={()=>void diagnoseConnection()}>{diagnosticLoading?"Đang đọc chẩn đoán…":"Chẩn đoán kết nối"}</button>
        <p className="hint">Kiểm tra đăng ký companion cho ID bên dưới. Chẩn đoán chỉ đọc trạng thái service worker, không gọi companion/API hoặc sửa đăng ký.</p>
        {diagnosticError?<p className="hint">{diagnosticError}</p>:null}
        {diagnostic?<div className="connection-diagnostic">
          <p>Trình duyệt báo: {diagnostic.browser==="edge"?"Microsoft Edge":diagnostic.browser==="chrome"?"Google Chrome":"Trình duyệt Chromium khác/chưa xác định"}. Host service worker gọi: <code>{diagnostic.host}</code>.</p>
          <label>Chẩn đoán kết nối · có thể sao chép<textarea aria-label="Chẩn đoán kết nối · có thể sao chép" readOnly rows={11} value={JSON.stringify(diagnostic,null,2)}/></label>
          <p className="hint">Bạn có thể sao chép ô này để gửi kiểm tra. Không chứa key, profile ID, tên/nội dung truyện hay URL đang đọc. Không tự gửi hoặc lưu lên server.</p>
        </div>:null}
      </>:null}
    </section>:null}
    {error?<div className="alert" role="alert">{error}</div>:null}
    {message?<div className="notice" role="status">{message}</div>:null}
    {view==="reader"&&connection==="ready"?<section>
      {readerTargetError?<p className="notice" role="note">{readerTargetError}</p>:null}
      <aside className="notice reader-engine" role="note" aria-label="Engine của phiên dịch">
        <strong>{savedEngine?.mode==="byok"?`Cloud BYOK · ${savedEngine.provider} · ${savedCloudModel}`:"Offline · CPU"}</strong>
        <p>{savedEngine?.mode==="offline"
          ?"Model local hiện có thể chậm hoặc lỗi đầu ra dù chỉ vài bóng. Lưu key không tự bật cloud."
          :!savedEngine?.cloudConsent?"Chưa cho phép gửi text/context. Xác nhận trong Cài đặt trước khi dịch cloud."
          :!status?.keys[savedEngine.provider]?"Chưa lưu key cho nhà cung cấp này. Kiểm tra Cài đặt trước khi dịch."
          :savedEngine.ocr==="cloud-gemini"?"OCR cloud thử nghiệm: gửi crop tới Gemini qua OpenRouter, sau đó gửi text/context tới model dịch đã chọn. Cả hai tính phí; không tự fallback. Cache hợp lệ không gọi lại model."
          :"Chỉ gửi text OCR và context đã chọn, không gửi ảnh. Lượt dịch mới dùng hạn mức API của bạn; cache hợp lệ không gọi lại model."}</p>
        <button disabled={busy} onClick={()=>{setView("settings");setError("");}}>{savedEngine?.mode==="offline"?"Cấu hình Cloud BYOK":"Xem cấu hình engine"}</button>
      </aside>
      <p className="hint" role="status">{warming?"Đang làm nóng model trong lúc bạn xác nhận context. Lần đầu có thể cần vài chục giây.":engineReady?"Engine đã nóng · sẵn sàng xử lý.":"Model sẽ nạp vào RAM ở lần dịch đầu."}</p>
      <div className="reader-prepare">
        <button disabled={busy||warming||engineReady} onClick={()=>void prepareEngine()}>
          {warming?"Đang chuẩn bị engine trên máy…":engineReady?"Engine đã sẵn sàng":"Chuẩn bị engine · không tốn credit"}
        </button>
        <p className="hint">Chỉ nạp engine trên máy; chưa gửi ảnh/text hoặc gọi API. Lần đầu có thể mất vài chục giây và dùng thêm RAM. Bạn có thể xác nhận context trong lúc chờ; request dịch mới vẫn có độ trễ mạng/model.</p>
      </div>
      <h2>Xác nhận ngữ cảnh</h2><p className="muted">Kiểm tra tên truyện và chapter trước khi dịch. Sự kiện sau mốc này sẽ không được đưa vào prompt.</p>
      <label>Hồ sơ truyện đã lưu<select value={storyId} onChange={event=>{
        const story=status?.stories.find(s=>s.id===event.target.value);
        if(story)void action(()=>chooseStory(story));else{storySelection.current++;setStoryId("");setPack(undefined);}
      }}><option value="">Tạo hồ sơ mới</option>{status?.stories.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
      <label>Tên truyện<input value={title} maxLength={300} onChange={e=>setTitle(e.target.value)} placeholder="Tên Nhật hoặc tên bạn sử dụng"/></label>
      <div className="row"><label>Chapter hiện tại<input type="number" min={0} step="0.5" value={chapter} onChange={e=>setChapter(Number(e.target.value))}/></label>
        <label>Trang bắt đầu<input type="number" min={0} value={page} onChange={e=>setPage(Number(e.target.value))}/></label></div>
      <label>Thể loại / giọng dịch<input value={genre} maxLength={150} onChange={e=>setGenre(e.target.value)} placeholder="Hài, đời thường; giọng gần gũi…"/></label>
      <details><summary>Bổ sung context ban đầu</summary>
        <p className="muted">Có thể bắt đầu giữa truyện. Nhập những điều bạn đã biết; recap chỉ có hiệu lực đến mốc đã xác nhận.</p>
        <label>Recap riêng tư<textarea rows={4} maxLength={6000} value={recap} onChange={e=>setRecap(e.target.value)} placeholder="Nhân vật, sự kiện đã đọc; tránh sự kiện tương lai."/></label>
        <button disabled={busy||!recap.trim()||!title.trim()} onClick={()=>void action(async()=>{
          const id=await ensure();await call("memory.recap",{storyId:id,title,at:cutoff,value:recap});setMessage("Đã lưu recap riêng của truyện.");
        })}>Lưu recap</button>
        <button disabled={busy||!settings?.metadataConsent||settings.mode==="offline"||!title.trim()} onClick={()=>void action(async()=>{
          setMetadata(await call("metadata.search",{title}));
        })}>Tra tên/alias (không lấy cốt truyện)</button>
        {metadata.map(m=><div className="metadata" key={m.qid}><span>{m.label} · {m.qid}</span>
          <button onClick={()=>void action(async()=>{const id=await ensure();await call("metadata.confirm",{storyId:id,metadata:m});setMessage("Đã xác nhận alias; không nhập thông tin cốt truyện.");})}>Đúng truyện này</button></div>)}
      </details>
      <label className="check"><input type="checkbox" checked={autoScan} onChange={e=>setAutoScan(e.target.checked)}/>Dịch ảnh đang nhìn khi cuộn</label>
      <label className="check"><input type="checkbox" checked={prefetch} onChange={e=>setPrefetch(e.target.checked)}/>Chuẩn bị tối đa 2 ảnh đã tải tiếp theo khi rảnh</label>
      {prefetch&&savedEngine?.mode==="byok"?<p className="hint">Chuẩn bị trước cũng gọi API tính phí cho ảnh chưa đọc nếu chưa có cache. Chỉ bắt đầu khi bạn bấm bật dịch; có thể tắt để tiết kiệm hạn mức.</p>:null}
      <p className="muted">Không tải chapter ẩn. Trang chuẩn bị trước chưa được coi là đã đọc.</p>
      <div className="primary-actions"><button className="primary" disabled={busy||!status||!title.trim()||!readerTarget} onClick={()=>void action(async()=>{
        // The background captures/verifies the reading tab before story.ensure.
        // Do not wait for another native request here and then choose a new tab.
        const id=storyId||await stableId(title.trim().normalize("NFKC").toLowerCase());
        await call("reader.start",{storyId:id,title:title.trim(),genre,at:cutoff,autoScan,prefetch,target:readerTarget});setStoryId(id);
        setActive(true);setMessage("Đã bật dịch. Quay lại trang đọc; dùng Chọn vùng cho canvas hoặc vùng chữ khó.");
      })}>{active?"Áp dụng ngữ cảnh & tiếp tục":"Bắt đầu dịch"}</button>
        {active?<button disabled={busy} onClick={()=>void action(async()=>{await call("reader.stop");setActive(false);setMessage("Đã dừng.");})}>Dừng</button>:null}</div>
      {active?<button disabled={busy} onClick={()=>void action(async()=>{await call("reader.region");window.close();})}>Kéo chọn vùng trên màn hình</button>:null}
      <p className="hint">Bấm bóng để sửa OCR/người nói. Alt+T xem gốc. “Đã đọc” lưu tiến độ; tóm tắt chỉ tự tạo nếu bạn bật trong Cài đặt.</p>
    </section>:null}
    {view==="library"&&connection==="ready"?<section>
      <h2>Thư viện của bạn</h2><p className="muted">Bộ nhớ riêng cho từng truyện, nằm trên máy này. Bạn có thể nhập cùng hồ sơ khi đổi website.</p>
      {!status?.stories.length?<div className="empty">Bật dịch và xác nhận truyện để tạo hồ sơ đầu tiên.</div>:null}
      <div className="stories">{status?.stories.map(story=><button className={storyId===story.id?"story selected":"story"} key={story.id}
        onClick={()=>void action(()=>chooseStory(story))}><strong>{story.title}</strong><span>{story.last_chapter!==undefined&&story.last_chapter!==null?"Đọc gần nhất: chap "+story.last_chapter:"Chưa đánh dấu đã đọc"}</span></button>)}</div>
      {storyId?<><h3>{title}</h3>
        {packLoading?<p className="hint" role="status">Đang nạp bộ nhớ đúng mốc đọc…</p>:null}
        <div className="row"><label>Mốc chapter cho context<input type="number" min={0} step="0.5" value={chapter} onChange={e=>setChapter(Number(e.target.value))}/></label>
          <label>Trang<input type="number" min={0} value={page} onChange={e=>setPage(Number(e.target.value))}/></label></div>
        <details ref={profileEditor} open={editProfile} onToggle={e=>setEditProfile(e.currentTarget.open)} className="profile-editor">
          <summary>Chỉnh xưng hô, danh xưng và thuật ngữ</summary>
          <p className="muted">Chỉ ghi quan hệ đã biết tại mốc đang đọc. Không tự suy cô/dì/chú/bác từ tuổi hoặc một hậu tố Nhật.</p>
          <div className="row"><label>ID người nói<input value={voiceSpeaker} onChange={e=>setVoiceSpeaker(e.target.value)} placeholder="em_trai"/></label>
            <label>ID người nghe<input value={voiceListener} onChange={e=>setVoiceListener(e.target.value)} placeholder="chi_gai"/></label></div>
          <div className="row"><label>Tự xưng<input value={voiceSelf} onChange={e=>setVoiceSelf(e.target.value)} placeholder="em" maxLength={40}/></label>
            <label>Gọi đối phương<input value={voiceAddress} onChange={e=>setVoiceAddress(e.target.value)} placeholder="chị" maxLength={40}/></label></div>
          <button disabled={busy||packLoading||!voiceSpeaker||!voiceListener||!voiceSelf||!voiceAddress} onClick={()=>void action(async()=>{
            await call("memory.voice",{storyId,speaker:voiceSpeaker,listener:voiceListener,self:voiceSelf,address:voiceAddress,at:cutoff});
            setMemoryRefresh(value=>value+1);setMessage("Đã khóa xưng hô có hướng; chiều ngược lại cần quy tắc riêng.");
          })}>Khóa xưng hô A → B</button>
          <label>Danh xưng Nhật<select value={honorifics} onChange={e=>setHonorifics(e.target.value)}>
            <option value="preserve">Giữ chất Nhật · -san, -kun, -chan, -sama, senpai</option>
            <option value="hybrid">Cân bằng · giữ khi mang ý nghĩa quan hệ / câu chuyện</option>
            <option value="localize">Việt hóa theo quan hệ đã xác nhận</option></select></label>
          <label>Gọi anh / chị trong thoại<select value={kinship} onChange={e=>setKinship(e.target.value)}>
            <option value="preserve">Giữ onii-chan, onee-chan… khi bản gốc dùng</option>
            <option value="natural">Dịch tự nhiên anh/chị theo bằng chứng</option></select></label>
          <p className="muted">Giữ cách gọi họ/tên của từng câu; không tự thêm hậu tố. Gọi tên không luôn có nghĩa yêu đương. Thông tin chỉ áp dụng từ mốc đã chọn.</p>
          <label>Phong cách tên kỹ năng / vật phẩm<select value={naming} onChange={e=>setNaming(e.target.value)}>
            <option value="natural">Tự nhiên, hiện đại</option><option value="fantasy">Fantasy / hành động · Hán–Việt có chọn lọc</option>
            <option value="historical">Cổ phong theo bối cảnh</option><option value="comedy">Hài, đời thường</option></select></label>
          <button disabled={busy||packLoading} onClick={()=>void action(async()=>{
            await Promise.all([call("memory.style",{storyId,key:"naming",style:naming,at:cutoff}),
              call("memory.style",{storyId,key:"honorifics",style:honorifics,at:cutoff}),
              call("memory.style",{storyId,key:"kinship",style:kinship,at:cutoff})]);
            setMemoryRefresh(value=>value+1);setMessage("Đã lưu danh xưng và phong cách tại mốc này. Glossary đã khóa luôn được ưu tiên.");
          })}>Lưu phong cách truyện</button>
          <details><summary>Cách đọc tên đã xác nhận</summary>
            <p className="muted">Tên kanji có nhiều cách đọc. Nhập khi có furigana hoặc nguồn xác nhận; AI không tự đổi họ thành tên để làm câu thân mật hơn.</p>
            <label>ID nhân vật<input value={nameId} onChange={e=>setNameId(e.target.value)} placeholder="tanaka_misaki" maxLength={128}/></label>
            <div className="row"><label>Họ Nhật<input value={familyJa} onChange={e=>setFamilyJa(e.target.value)} placeholder="田中" maxLength={80}/></label>
              <label>Cách đọc họ<input value={familyReading} onChange={e=>setFamilyReading(e.target.value)} placeholder="Tanaka" maxLength={100}/></label></div>
            <div className="row"><label>Tên Nhật<input value={givenJa} onChange={e=>setGivenJa(e.target.value)} placeholder="美咲" maxLength={80}/></label>
              <label>Cách đọc tên<input value={givenReading} onChange={e=>setGivenReading(e.target.value)} placeholder="Misaki" maxLength={100}/></label></div>
            <button disabled={busy||packLoading||!nameId||(!familyJa&&!givenJa)} onClick={()=>void action(async()=>{
              const forms=[familyJa?{ja:familyJa,reading:familyReading,role:"family"}:null,
                givenJa?{ja:givenJa,reading:givenReading,role:"given"}:null].filter(Boolean);
              await call("memory.name",{storyId,character:nameId,forms,at:cutoff});
              setMemoryRefresh(value=>value+1);setMessage("Đã khóa cách đọc. Cách gọi họ hay tên vẫn theo từng câu gốc.");
            })}>Lưu cách đọc tên</button>
          </details>
          <details open={Boolean(termEntity)}><summary>Tên cố định · bang hội, vũ khí, kỹ năng, biệt danh</summary>
            <p className="muted">Khóa tên theo thực thể, không theo một từ chung. Bản gốc đổi tên/biệt danh thì thêm cách gọi riêng; không tự gộp hai thực thể trùng tên.</p>
            <label>Loại tên<select value={termCategory} onChange={e=>setTermCategory(e.target.value)}>
              {[["skill","Kỹ năng"],["weapon","Vũ khí"],["guild","Bang hội"],["organization","Tổ chức"],["item","Vật phẩm"],["place","Địa danh"],["epithet","Biệt danh"],["other","Thuật ngữ riêng"]].map(([value,label])=><option key={value} value={value}>{label}</option>)}
            </select></label>
            <div className="row"><label>Tên trong bản gốc<input value={termJa} onChange={e=>setTermJa(e.target.value)} maxLength={100} placeholder="氷結結界"/></label>
              <label>Tên Việt cố định<input value={termVi} onChange={e=>setTermVi(e.target.value)} maxLength={120} placeholder="Băng Kết Kết Giới"/></label></div>
            <label>ID thực thể (để trống để tạo từ tên gốc)<input value={termEntity} onChange={e=>setTermEntity(e.target.value)} maxLength={128} placeholder="Copy ID khi sửa tên AI đã chốt"/></label>
            <label>Cách gọi khác đã xác nhận · mỗi dòng Nhật = Việt<textarea rows={2} value={termAliases} onChange={e=>setTermAliases(e.target.value)} maxLength={2000} placeholder="Tên viết tắt = Cách dịch viết tắt"/></label>
            <button disabled={busy||packLoading||!termJa.trim()||!termVi.trim()} onClick={()=>void action(async()=>{
              const aliases=termAliases.split("\n").filter(v=>v.trim()).map(line=>{
                const split=line.indexOf("=");if(split<1)throw new Error("Alias cần định dạng Nhật = Việt.");
                return {ja:line.slice(0,split).trim(),vi:line.slice(split+1).trim()};
              });
              await call("memory.term",{storyId,entity:termEntity||undefined,category:termCategory,ja:termJa.trim(),vi:termVi.trim(),aliases,at:cutoff});
              setMemoryRefresh(value=>value+1);setMessage("Đã khóa tên từ mốc này. Tên và cách gọi riêng được giữ nhất quán.");
            })}>Chốt & khóa tên</button>
          </details>
          <label>Loại<select value={kind} onChange={e=>setKind(e.target.value)}><option value="character">Nhân vật</option><option value="relationship">Xưng hô A → B</option><option value="glossary">Thuật ngữ</option><option value="note">Ghi chú</option></select></label>
          <label>ID / cặp có hướng<input value={keyName} onChange={e=>setKeyName(e.target.value)} placeholder="nana hoặc nana→owner"/></label>
          <label>Thông tin đã xác nhận<textarea rows={3} value={note} maxLength={1500} onChange={e=>setNote(e.target.value)} placeholder="Giọng nhân vật hoặc thuật ngữ: 氷結結界 = Băng Kết Kết Giới. Không tự thêm hiệu ứng kỹ năng."/></label>
          <button disabled={busy||packLoading||!keyName.trim()||!note.trim()} onClick={()=>void action(async()=>{
            await call("memory.fact",{storyId,title,kind,key:keyName,value:note,at:cutoff});
            setMemoryRefresh(value=>value+1);setNote("");setMessage("Đã khóa ghi chú của bạn tại mốc này.");
          })}>Lưu & khóa</button>
        </details>
        {!packLoading&&pack?<div className="memory-list" aria-label="Bộ nhớ ở mốc đang xem">
          <h3>Bộ nhớ ở mốc này ({facts.length})</h3>
          {facts.length>10?<label>Tìm trong bộ nhớ<input type="search" value={memoryFilter} maxLength={100}
            onChange={e=>{setMemoryFilter(e.target.value);setVisibleFacts(10);}} placeholder="Tên, cách gọi hoặc thuật ngữ…"/></label>:null}
          {!facts.length?<p className="muted">Chưa có ghi chú ở mốc này. Có thể bổ sung trong phần Chỉnh xưng hô.</p>:null}
          {facts.length>0&&!filteredFacts.length?<p className="muted">Không tìm thấy mục phù hợp tại mốc này.</p>:null}
          {filteredFacts.slice(0,visibleFacts).map(f=><MemoryFact key={f.id} fact={f} onEditTerm={editTerm} disabled={busy||packLoading}/>)}
          {filteredFacts.length>visibleFacts?<button onClick={()=>setVisibleFacts(count=>count+10)}>Xem thêm {Math.min(10,filteredFacts.length-visibleFacts)} mục</button>:null}
        </div>:null}
        <details><summary>Tóm tắt để đối chiếu ({summaries.length})</summary>
          <p className="muted">Tóm tắt AI có thể sai cách hiểu. Khi dịch tiếp, engine ưu tiên bằng chứng Nhật gốc thay vì tự coi diễn giải này là sự thật. Sửa recap nếu cần xác nhận.</p>
          {summaries.slice(-15).map(s=><div className="fact" key={s.id}><small>Chap {s.chapter_end} · {s.complete?"Phạm vi đầy đủ":"Phạm vi một phần"}</small><p>{s.text}</p></div>)}</details>
        {pack?.summaryStatus?<p className="hint" role="status">Tóm tắt tự động: {pack.summaryStatus.enabled?"bật":"tắt"} · {pack.summaryStatus.pending} trang chờ · {pack.summaryStatus.failed} lỗi.
          {pack.summaryStatus.gap?" "+pack.summaryStatus.gap+" trang hết cache nguồn; cần mở/dịch lại, không tự bịa phần thiếu.":""}</p>:null}
        {pack?.summaryStatus?.failed?<button disabled={busy} onClick={()=>void action(async()=>{
          const result=await call("memory.retry",{storyId});setMemoryRefresh(value=>value+1);
          setMessage("Đã đưa "+result.retried+" trang vào hàng đợi. "+(cloudSummary?"Bấm Tóm tắt một trang để xác nhận từng lượt cloud; không tự tính phí backlog.":"Bật tự động hoặc bấm Tóm tắt một trang."));
        })}>Thử lại tóm tắt lỗi</button>:null}
        <div className="row-actions">
          <button disabled={busy} onClick={()=>void action(async()=>{const value=await call("memory.markdown",{storyId,at:cutoff});download(value.markdown,"text/markdown",title+"-context.md");})}>Xuất Markdown theo mốc</button>
          <button disabled={busy} onClick={()=>void action(async()=>{
            if(!confirm("Hồ sơ đầy đủ có thể gồm thông tin ở các chapter sau mốc đang xem. Chỉ lưu riêng; không chia sẻ khi chưa có quyền. Tiếp tục?"))return;
            download(JSON.stringify(await readContextPack(call,storyId)),"application/json",title+"-private-context.json");
          })}>Xuất hồ sơ đầy đủ</button>
          <button disabled={busy||!pack?.summaryStatus?.pending||!summaryReady} onClick={()=>void action(async()=>{
            if(cloudSummary&&!confirm("Tóm tắt một trang đã đọc tới mốc đang xem bằng "+savedEngine?.summaryModel+"? Sẽ gửi text Nhật/bản dịch tới OpenRouter, tính thêm phí API; không gửi ảnh. Request đã gửi có thể vẫn tính phí nếu hủy. Tiếp tục?"))return;
            await call("summarize",{storyId,at:cutoff});setMemoryRefresh(value=>value+1);
            setMessage("Đã tóm tắt một trang đã đọc, không coi toàn chapter là hoàn tất.");
          })}>Tóm tắt một trang</button>
        </div>
        <details><summary>Xóa hồ sơ này</summary><p>Thao tác xóa toàn bộ context và cache của truyện trên máy.</p><button className="danger" onClick={()=>void action(async()=>{
          if(!confirm("Xóa toàn bộ bộ nhớ của "+title+"?"))return;
          await call("memory.delete",{storyId});setPack(undefined);setStoryId("");await refresh();
        })}>Xác nhận xóa</button></details>
      </>:null}
      <p className="muted">Nhập bổ sung không thay tiến độ đang đọc hoặc xưng hô đã khóa. Hồ sơ xung đột bị từ chối; dữ liệu hiện tại được giữ nguyên.</p>
      <label className="import">Nhập hồ sơ context riêng tư<input type="file" accept=".json" onChange={e=>{
        const file=e.target.files?.[0];if(!file)return;
        void action(async()=>{if(file.size>MAX_CONTEXT_PACK_BYTES)throw new Error("Hồ sơ quá lớn (tối đa 16 MB cho MVP).");
          await importContextPack(call,JSON.parse(await file.text()));await refresh();setMemoryRefresh(value=>value+1);setMessage("Đã nhập hồ sơ có mốc chapter.");});
      }}/></label>
    </section>:null}
    {view==="settings"&&connection==="ready"&&settings?<section>
      <h2>Cấu hình engine</h2>
      <label>Chế độ dịch<select aria-label="Chế độ dịch" value={settings.mode} onChange={e=>setSettings({...settings,mode:e.target.value as Settings["mode"],
        ...(status?.summaryVersion==="read-evidence-cloud-v1"&&e.target.value==="offline"?{summaryBackend:"local" as const,summaryCloudConsent:false,
          ...(settings.summaryBackend==="cloud"?{autoSummary:false}:{})}:{}),
        ocr:e.target.value==="offline"?"manga":settings.ocr,cloudOcrConsent:e.target.value==="offline"?false:settings.cloudOcrConsent,
        cloudConsent:e.target.value==="offline"?false:settings.cloudConsent,cloudPageOcrConsent:e.target.value==="offline"?false:settings.cloudPageOcrConsent,
        detector:e.target.value==="offline"?"paddle":settings.detector,metadataConsent:e.target.value==="offline"?false:settings.metadataConsent})}>
        <option value="offline">Offline · Hy-MT2 trên CPU</option><option value="byok">Cloud · dùng key của bạn</option></select></label>
      {settings.mode==="byok"?<>
        <label>Nhà cung cấp<select aria-label="Nhà cung cấp" value={settings.provider} onChange={e=>{setApiKey("");setSettings({...settings,provider:e.target.value as Settings["provider"],cloudConsent:false,cloudOcrConsent:false,cloudPageOcrConsent:false,detector:"paddle",ocr:"manga",
          ...(status?.summaryVersion==="read-evidence-cloud-v1"?{summaryBackend:"local" as const,summaryCloudConsent:false,
            ...(settings.summaryBackend==="cloud"?{autoSummary:false}:{})}:{})});}}>
          <option value="deepseek">DeepSeek trực tiếp</option><option value="gemini">Gemini trực tiếp</option><option value="openrouter">OpenRouter · nhiều model</option></select></label>
        <CloudModelPicker key={settings.provider} provider={settings.provider} choices={status?.cloudModels??[]}
          value={settings[settings.provider+"Model" as "deepseekModel"|"geminiModel"|"openrouterModel"]}
          onChange={model=>setSettings({...settings,[settings.provider+"Model"]:model,cloudConsent:false})}/>
        <label className="check"><input type="checkbox" checked={settings.cloudConsent} onChange={e=>setSettings({...settings,cloudConsent:e.target.checked,
          ...(status?.summaryVersion==="read-evidence-cloud-v1"&&!e.target.checked?{summaryCloudConsent:false}:{})})}/>Cho phép gửi text OCR và context đã chọn · API tính phí theo model/hạn mức của tôi</label>
        {settings.provider==="openrouter"?<fieldset>
          <legend>OCR cloud · thử nghiệm, chưa khuyến nghị thay mặc định</legend>
          <label>Nhận chữ<select aria-label="Nhận chữ" value={settings.ocr??"manga"} onChange={e=>setSettings({...settings,ocr:e.target.value as Settings["ocr"],cloudOcrConsent:false})}>
            <option value="manga">manga-ocr · giữ ảnh trên máy</option><option value="cloud-gemini">Gemini Flash-Lite · gửi crop có tính phí</option></select></label>
          {settings.ocr==="cloud-gemini"?<>
            <label>Model OCR cloud<select aria-label="Model OCR cloud" value={settings.cloudOcrModel??"google/gemini-3.5-flash-lite"} onChange={e=>setSettings({...settings,cloudOcrModel:e.target.value,cloudOcrConsent:false})}>
              {(status?.cloudModels??[]).filter(choice=>["anthropic/claude-haiku-5.5","google/gemini-3.5-flash-lite","qwen/qwen3.8-flash"].includes(choice.id)).map(choice=><option key={choice.id} value={choice.id}>{choice.label}</option>)}
            </select></label>
            <p className="hint">Chỉ gửi crop vùng đọc, không gửi cả thư viện hay tra cốt truyện. Detector vẫn local. Thêm một lượt API trước dịch, có thể chậm hơn OCR local khi máy đã nóng; chưa chứng minh model nào tốt hơn trên toàn bộ manga thật. OCR và dịch có thể tính phí riêng; giá nhà cung cấp có thể đổi.</p>
            <label className="check"><input aria-label="Xác nhận gửi crop OCR có tính phí" type="checkbox" checked={settings.cloudOcrConsent??false}
              onChange={e=>setSettings({...settings,cloudOcrConsent:e.currentTarget.checked})}/>Tôi đồng ý gửi crop qua OpenRouter/Vertex để OCR và chịu phí API, rồi mới dịch text. Không tự đổi model hoặc gửi lại khi lỗi.</label>
            <p className="hint">Lưu cấu hình chưa gửi ảnh hay tính phí. Chỉ bắt đầu khi bạn bấm dịch. Crop quá lớn bị từ chối, không tự giảm chất lượng ảnh.</p>
          </>:null}
        </fieldset>:null}
        <label className="check"><input type="checkbox" checked={settings.metadataConsent} onChange={e=>setSettings({...settings,metadataConsent:e.target.checked})}/>Cho phép tra tên manga qua Wikidata khi tôi bấm Tra tên</label>
        <label>API key · {status?.keys[settings.provider]?"đã có trong Windows Vault":"chưa lưu"}<input type="password" autoComplete="off" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="Key chỉ được gửi vào companion local"/></label>
        <button disabled={busy||!apiKey} onClick={()=>void action(async()=>{await call("key.set",{provider:settings.provider,key:apiKey});setApiKey("");setStatus(checkedStatus(await call("status")));setMessage("Đã lưu key vào Windows Vault. Bấm Lưu cấu hình để áp dụng chế độ/model đang chọn; chưa gọi API.");})}>Lưu key</button>
        <button disabled={busy} onClick={()=>void action(async()=>{await call("key.delete",{provider:settings.provider});setStatus(checkedStatus(await call("status")));})}>Xóa key nhà cung cấp</button>
      </>:null}
      <label>Detector<select value={settings.detector} onChange={e=>setSettings({...settings,detector:e.target.value as Settings["detector"]})}>
        <option value="paddle">PP-OCRv5 mobile (mặc định)</option><option value="opencv">OpenCV thử nghiệm (kém tin cậy hơn)</option>
        {settings.mode==="byok"&&settings.provider==="openrouter"?<option value="cloud-page">Cloud page proposals · gửi cả trang (thử nghiệm)</option>:null}</select></label>
      {settings.detector==="cloud-page"?<>
        <p className="hint">Detector cloud gửi ảnh trang hiện tại qua OpenRouter để tìm thêm vùng chữ. Đây là lượt API riêng, có thể tốn phí và chậm hơn; các box chỉ là đề xuất review, không tự xóa nền hoặc ghi memory.</p>
        <label className="check"><input aria-label="Xác nhận gửi toàn trang có tính phí" type="checkbox" checked={settings.cloudPageOcrConsent??false}
          onChange={e=>setSettings({...settings,cloudPageOcrConsent:e.currentTarget.checked})}/>Tôi đồng ý gửi toàn bộ ảnh trang cho detector cloud và chịu chi phí phát sinh.</label>
      </>:null}
      <label>Luồng CPU<input type="number" min={1} max={16} value={settings.threads} onChange={e=>setSettings({...settings,threads:Number(e.target.value)})}/></label>
      {status?<SummarySettings settings={settings} status={status} onChange={setSettings}/>:null}
      {status?.summaryUsageUnavailable?<p className="hint" role="note">Chưa đọc được biên nhận chi phí tóm tắt. Companion vẫn kết nối; không suy ra chi phí bằng 0. Không gửi lượt tóm tắt mới nếu chưa ghi được biên nhận.</p>:null}
      {status?.summaryUsage?.length?<details><summary>Biên nhận tóm tắt cloud gần đây</summary>
        <p className="hint">Tối đa 10 lượt gần đây, không phải tổng hóa đơn hay giới hạn chi phí. Không lưu text/key trong biên nhận. “Chưa biết” không có nghĩa miễn phí; đối soát với nhà cung cấp.</p>
        {status.summaryUsage.map(row=><p className="hint" key={row.id}>{row.model} · {new Date(row.started*1000).toLocaleString()} · {row.costUsd===null?"Chi phí chưa biết":row.costUsd.toFixed(6)+" USD"} · {row.state==="received"?"Đã nhận phản hồi":"Chưa đối soát"}</p>)}
      </details>:null}
      <label className="check"><input type="checkbox" checked={settings.artCleanup??true} onChange={e=>{const enabled=e.currentTarget.checked;setSettings(current=>current?{...current,artCleanup:enabled}:current);}}/>Hòa chữ vào tranh · local, thử nghiệm</label>
      <p className="hint">Mặc định bật cho vùng nhỏ đủ rõ. Không thêm token/credit, không gửi ảnh lên mạng; có thêm xử lý CPU và có thể làm mềm chi tiết dưới chữ. Vùng không chắc giữ tranh gốc. Áp dụng khi bật dịch lại, dùng lại bản dịch đã cache. Alt+T để xem nguyên bản; bạn có thể tắt bất kỳ lúc nào.</p>
      <button className="primary" disabled={busy||(settings.summaryBackend==="cloud"&&(status?.summaryVersion!=="read-evidence-cloud-v1"||!settings.cloudConsent||!settings.summaryCloudConsent))||(settings.ocr==="cloud-gemini"&&(!settings.cloudConsent||!settings.cloudOcrConsent))||(settings.detector==="cloud-page"&&(!settings.cloudConsent||!settings.cloudPageOcrConsent))} onClick={()=>void action(async()=>{await call("settings",settings);await refresh();setMessage("Đã lưu. Thay đổi luồng CPU áp dụng sau khi companion khởi động lại. Chưa gửi tác vụ dịch; bật dịch lại để dùng cấu hình mới.");})}>Lưu cấu hình</button>
      <div className="models"><h3>Model local</h3>{Object.entries(status?.models??{}).map(([name,ready])=><div key={name}><span>{name}</span><span className={ready?"ready":"missing"}>{ready?"Đã cài":"Chưa cài"}</span></div>)}</div>
      <p className="muted">Lần chạy đầu tải model vào RAM sẽ chậm hơn. Key cloud phải có hạn mức. Offline không tự chuyển cloud.</p>
      <details className="runtime-details"><summary>Kết nối và phiên bản runtime</summary>
        <p>Companion đã phản hồi. Đây là kiểm tra kết nối, không phải chứng nhận chất lượng OCR/dịch.</p>
        <dl>{[["Companion",status?.version],["Mã runtime",status?.runtimeBuild??"Companion chưa báo mã runtime"],["Prompt",status?.promptVersion],["OCR",status?.ocrVersion],
          ["Dàn chữ",status?.presentationVersion??status?.layoutVersion],["Phân loại chữ",status?.scopeVersion],["Binding xưng hô",status?.speakerBindingVersion]].map(([label,value])=>
          <React.Fragment key={label}><dt>{label}</dt><dd>{value??"Companion chưa báo"}</dd></React.Fragment>)}</dl>
      </details>
    </section>:null}
    <footer>{busy?"Đang xử lý…":"Dữ liệu ảnh chỉ dùng trong RAM · context lưu riêng trên máy"}
      {!full?<button onClick={()=>void chrome.runtime.openOptionsPage()}>Mở thư viện đầy đủ</button>:null}
      <small>Build extension: {extensionBuild}</small>
      <small>ID extension: {chrome.runtime.id}</small></footer>
  </main>;
}

createRoot(document.getElementById("app")!).render(<App/>);
