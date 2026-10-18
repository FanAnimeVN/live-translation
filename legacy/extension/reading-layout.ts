/** Presentation-only collision detection. Never changes OCR/source ownership. */
export function conflictedLetteringIds(items:ReadonlyArray<{id:string;box:ReadonlyArray<number>}>):Set<string>{
  const seen=new Set<string>();
  for(const {id,box} of items){
    if(!id||seen.has(id)||box.length!==4||!box.every(Number.isFinite)||box[2]<=0||box[3]<=0)
      throw new Error("Invalid or duplicate lettering geometry");
    seen.add(id);
  }
  const conflicts=new Set<string>();
  for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){
    const a=items[i],b=items[j];
    if(Math.min(a.box[0]+a.box[2],b.box[0]+b.box[2])>Math.max(a.box[0],b.box[0])&&
       Math.min(a.box[1]+a.box[3],b.box[1]+b.box[3])>Math.max(a.box[1],b.box[1])){
      conflicts.add(a.id);conflicts.add(b.id);
    }
  }
  return conflicts;
}
