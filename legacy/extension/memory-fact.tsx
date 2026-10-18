import React,{memo} from "react";
import {nameReviewNote} from "./translation-quality";

export interface TermView {
  type:"canonical-term";entity:string;category:string;ja:string;vi:string;
  aliases:{ja:string;vi:string}[];
}

interface Props {fact:any;onEditTerm:(term:TermView)=>void;disabled:boolean}

export const MemoryFact=memo(function MemoryFact({fact,onEditTerm,disabled}:Props){
  let term:TermView|undefined,body:string=fact.value;
  try{
    const value=JSON.parse(fact.value);
    if(value.type==="canonical-term"&&typeof value.ja==="string"&&typeof value.vi==="string"&&
       typeof value.entity==="string"&&typeof value.category==="string"&&Array.isArray(value.aliases)&&
       value.aliases.every((alias:any)=>typeof alias?.ja==="string"&&typeof alias.vi==="string")){
      term=value;body=value.aliases.map((alias:{ja:string;vi:string})=>alias.ja+" → "+alias.vi).join("; ");
    }else if(fact.kind==="relationship"&&typeof value.self==="string"&&typeof value.address==="string"){
      body="Tự xưng “"+value.self+"”, gọi đối phương “"+value.address+"”.";
    }else if(value.type==="name-forms"&&Array.isArray(value.forms)){
      body=value.forms.map((form:{ja:string;reading:string})=>form.ja+" → "+form.reading).join("; ");
    }
  }catch{/* Plain reader notes remain plain text. */}
  const preview=body.replace(/\s+/g," ");
  const nameNote=term?nameReviewNote(term.vi):undefined;
  return <article className="fact" aria-label={term?term.ja:fact.key}>
    <strong>{term?term.ja+" → "+term.vi:fact.key}</strong>
    {preview.length>180?<details className="fact-body"><summary>{preview.slice(0,150)}… · Xem đầy đủ</summary><p>{body}</p></details>
      :body?<p>{body}</p>:null}
    <small>Chap {fact.chapter} · {fact.confirmed?"Đã xác nhận":"AI chọn, chưa kiểm chứng"}</small>
    {nameNote?<p className="name-review" role="note">{nameNote}</p>:null}
    {term?<button disabled={disabled} onClick={()=>onEditTerm(term!)}>Sửa tên / thêm alias</button>:null}
  </article>;
});
