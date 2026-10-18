import { z } from "zod";

// MV3 forbids dynamic evaluation, including Zod's caught capability probe.
// Configure before constructing any object schema in every extension realm;
// keep normal validation/refinements without weakening the extension CSP.
z.config({ jitless: true });

export const idSchema = z.string().regex(/^[\w.:-]{1,128}$/);
export const locationSchema = z.object({ chapter: z.number().finite().min(0).max(1000000), page: z.number().int().min(0).max(100000) });
export type ReadingLocation = z.infer<typeof locationSchema>;
const regionBoxSchema=z.tuple([z.number().finite().nonnegative(),z.number().finite().nonnegative(),z.number().finite().positive(),z.number().finite().positive()]);
export const expressionSchema=z.object({v:z.literal(1),sourceHash:z.string().regex(/^[a-f0-9]{64}$/),
  cues:z.array(z.enum(["spelled","segmented","elongated","paused","stutter","uppercase"])).min(1).max(6)}).strict();
export const scopeSchema=z.object({v:z.literal(1),key:idSchema,group:idSchema,
  role:z.enum(["dialogue","thought","narration","scene_text","editorial","sfx","unknown"]),
  action:z.enum(["translate","defer"]),reason:z.enum(["unclassified","editorial_marker","editorial_candidate","visual_review","reader"]),
  memory:z.boolean()}).strict().refine(value=>!value.memory||
    (value.action==="translate"&&value.role!=="editorial"&&value.role!=="sfx"&&value.reason!=="visual_review"),"Unverified or secondary text cannot be plot memory");
const legacyCropPartitionSchema=z.object({source_ids:z.array(idSchema).min(2).max(2),orientation:z.enum(["vertical","horizontal"]),
  seam:z.number().int().nonnegative(),blank_band:z.tuple([z.number().int().nonnegative(),z.number().int().nonnegative()]),
  source_ink_coverage_preserved:z.literal(true),erasure_permitted:z.literal(false)}).strict();
const containsBox=(outer:number[],inner:number[])=>inner[0]>=outer[0]&&inner[1]>=outer[1]&&
  inner[0]+inner[2]<=outer[0]+outer[2]&&inner[1]+inner[3]<=outer[1]+outer[3];
const parentCropFrameSchema=z.object({source_ids:z.array(idSchema).min(2).max(64),
  reason:z.literal("group_parent_longitudinal_frame"),orientation:z.enum(["vertical","horizontal"]),
  parent_source_bbox:regionBoxSchema,parent_inference_crop:regionBoxSchema,
  source_members_preserved:z.literal(true),erasure_permitted:z.literal(false)}).strict().refine(value=>
    new Set(value.source_ids).size===value.source_ids.length&&containsBox(value.parent_source_bbox,value.parent_inference_crop),
    "Parent inference framing must retain unique sources and stay inside source bounds");
export const regionSchema = z.object({
  id: idSchema, bbox: regionBoxSchema,
  balloon:z.object({textBox:regionBoxSchema,background:z.string().regex(/^#[a-fA-F0-9]{6}$/),
    ink:z.string().regex(/^#[a-fA-F0-9]{6}$/).optional(),sourceFontPx:z.number().finite().min(8).max(160).optional(),
    erasePolygons:z.array(z.array(z.tuple([z.number().finite().nonnegative(),z.number().finite().nonnegative()])).min(3).max(64)).max(128).optional()}).optional(),
  polygon: z.array(z.tuple([z.number(),z.number()])).optional(),
  ja: z.string().max(3000), vi: z.string().max(5000).optional(),
  expression:expressionSchema.optional(),
  scope:scopeSchema.optional(),
  type: z.string().optional(), overlay: z.enum(["white","label"]).default("label"),
  speaker: z.string().optional(), listener: z.string().optional(), review: z.boolean().optional(),
  speakerBindingReview:z.boolean().optional(),
  reviewReasons:z.array(z.enum(["repetition","length","detector_low_score","quote_balance","layout_fragment","layout_cluster","visual_low_signal","visual_punctuation_support","ocr_crop_partition","cloud_ocr_uncertain","cloud_page_proposal","ocr_empty"])).max(12).optional(),
  ocrCropBox:regionBoxSchema.optional(),
  ocrPartition:z.array(z.union([legacyCropPartitionSchema,parentCropFrameSchema])).max(2).optional(),
  ambiguous: z.boolean().optional(), order: z.number().optional()
}).refine(value=>(value.ocrPartition??[]).every(record=>!("reason" in record)||
  (record.source_ids.includes(value.id)&&!!value.ocrCropBox&&containsBox(record.parent_inference_crop,value.ocrCropBox)&&
   (record.orientation==="vertical"?value.ocrCropBox[1]===record.parent_inference_crop[1]&&value.ocrCropBox[3]===record.parent_inference_crop[3]:
    value.ocrCropBox[0]===record.parent_inference_crop[0]&&value.ocrCropBox[2]===record.parent_inference_crop[2]))),
  "Inherited inference crop must match its parent frame and captured source").refine(value=>!value.reviewReasons?.some(reason=>reason==="visual_low_signal"||reason==="visual_punctuation_support"||reason==="cloud_ocr_uncertain"||reason==="cloud_page_proposal"||reason==="ocr_empty")||!value.scope?.memory||
  value.scope.reason==="reader","Weak source cannot implicitly become plot memory");
export type Region = z.infer<typeof regionSchema>;
// This contract is transport-only; never part of Region/story/cache exports.
export const renderPatchSchema=z.object({
  revision:idSchema,width:z.number().int().positive().max(8000),height:z.number().int().positive().max(8000),
  patch:z.object({regionId:idSchema,bbox:regionBoxSchema,
    textBox:regionBoxSchema.optional(),
    dataUrl:z.string().max(512*1024+22).regex(/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/),
    ink:z.string().regex(/^#[a-fA-F0-9]{6}$/),stroke:z.string().regex(/^#[a-fA-F0-9]{6}$/),
    sourceFontPx:z.number().finite().min(8).max(160),method:z.literal("opencv-telea-v1")})
}).superRefine((value,ctx)=>{
  if(value.patch.dataUrl.slice(22).length%4!==0)
    ctx.addIssue({code:"custom",message:"Invalid base64 padding"});
  const [x,y,w,h]=value.patch.bbox;
  if(x+w>value.width||y+h>value.height||w*h>200000)
    ctx.addIssue({code:"custom",message:"Patch outside bounded source image"});
  if(value.patch.textBox){const [tx,ty,tw,th]=value.patch.textBox;
    if(tx+tw>value.width||ty+th>value.height||tw*th>200000)
      ctx.addIssue({code:"custom",message:"Lettering outside bounded source image"});
  }
});
export type RenderPatch=z.infer<typeof renderPatchSchema>["patch"];
export const readerConfigSchema = z.object({
  storyId:idSchema,title:z.string().trim().min(1).max(300),at:locationSchema,
  genre:z.string().max(150).default(""),autoScan:z.boolean().default(true),
  prefetch:z.boolean().default(false)
});
export type ReaderConfig = z.infer<typeof readerConfigSchema>;
// Ephemeral UI target, never saved in ReaderConfig or story memory. A popup
// confirming chapter 1 must not start a different URL that became active later.
export const readerTargetSchema=z.object({tabId:z.number().int().positive(),
  url:z.string().max(8192).regex(/^(https?:\/\/|file:\/\/)/)}).strict();
export type ReaderTarget=z.infer<typeof readerTargetSchema>;
export const readerStartSchema=readerConfigSchema.extend({target:readerTargetSchema});
export interface NativeReply { v:1; id:string; ok?:boolean; event?:string; result?:any; error?:{code:string;message:string} }
export interface Settings {
  mode:"offline"|"byok";provider:"deepseek"|"gemini"|"openrouter";cloudConsent:boolean;
  metadataConsent:boolean;autoSummary:boolean;threads:number;detector:"paddle"|"opencv"|"cloud-page";
  cloudPageOcrConsent?:boolean;
  summaryBackend?:"local"|"cloud";summaryModel?:string;summaryCloudConsent?:boolean;
  ocr:"manga"|"cloud-gemini";cloudOcrConsent?:boolean;cloudOcrModel?:string;showSfx:boolean;ocrBatch:number;artCleanup:boolean;geminiModel:string;deepseekModel:string;openrouterModel:string;
}
export interface Story { id:string;title:string;version:number;last_chapter?:number;last_page?:number;furthest_chapter?:number;genre?:string;aliases?:string;metadata?:string }
export interface CloudModelChoice {provider:Settings["provider"];id:string;label:string;note:string}
export interface SummaryReceipt {id:string;started:number;model:string;state:string;
  costUsd:number|null;inputTokens:number|null;outputTokens:number|null;providerId?:string|null}
export interface Status {version:string;settings:Settings;keys:Record<string,boolean>;models:Record<string,boolean>;stories:Story[];engineWarm?:boolean;
  runtimeBuild?:string;
  promptVersion?:string;ocrVersion?:string;layoutVersion?:string;presentationVersion?:string;scopeVersion?:string;
  speakerBindingVersion?:string;
  scheduleVersion?:string;
  summaryVersion?:string;summaryUsage?:SummaryReceipt[];summaryUsageUnavailable?:boolean;
  cloudModels?:CloudModelChoice[];cloudCatalogVersion?:string}
export const HOST = "vn.mangalive.companion";

export function latestFactsAt<T extends {kind:string;key:string;chapter:number;page:number}>(facts:T[],at:ReadingLocation):T[]{
  // Export order is chronological. For equal cutoffs the last reader revision
  // wins; historical locks remain stored, not repeated as contradictory UI rows.
  const candidates=facts.filter(f=>f.chapter<at.chapter||(f.chapter===at.chapter&&f.page<=at.page))
    .reverse().sort((a,b)=>b.chapter-a.chapter||b.page-a.page);
  const seen=new Set<string>();
  return candidates.filter(f=>{const key=JSON.stringify([f.kind,f.key]);if(seen.has(key))return false;seen.add(key);return true;});
}

export async function stableId(value:string,prefix="s"):Promise<string> {
  const hash=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(value));
  return prefix+Array.from(new Uint8Array(hash).slice(0,16),v=>v.toString(16).padStart(2,"0")).join("");
}

export function inferChapter(value:string):number|undefined {
  const match=value.match(/(?:chapter|chap(?:ter)?|ch|第|話)[\s._/-]*(\d+(?:\.\d+)?)/i)
    ?? value.match(/(\d+(?:\.\d+)?)\s*話/);
  if(!match) return undefined;
  const chapter=Number(match[1]);
  return chapter>=0&&chapter<1000000?chapter:undefined;
}
