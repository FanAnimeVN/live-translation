// QA diagnostic only: intersecting text boxes flag risk, not glyph-mask truth.
// Never merge source text, shrink fonts or grant art-erasure permission here.
export function findLetteringBoxOverlaps(items,tolerance=0.5){
  if(!Array.isArray(items)||items.length>2048||!Number.isFinite(tolerance)||tolerance<0)
    throw new TypeError("Invalid lettering overlap inputs");
  const ids=new Set();
  for(const {id,rect} of items){
    if(typeof id!=="string"||!id||ids.has(id)||!rect||
      ![rect.x,rect.y,rect.width,rect.height].every(Number.isFinite)||rect.width<=0||rect.height<=0)
      throw new TypeError("Invalid or duplicate lettering box");
    ids.add(id);
  }
  const overlaps=[];
  for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){
    const a=items[i],b=items[j],r=a.rect,s=b.rect;
    const width=Math.min(r.x+r.width,s.x+s.width)-Math.max(r.x,s.x);
    const height=Math.min(r.y+r.height,s.y+s.height)-Math.max(r.y,s.y);
    if(width>tolerance&&height>tolerance)overlaps.push({ids:[a.id,b.id],width,height,
      minBoxFraction:width*height/Math.min(r.width*r.height,s.width*s.height)});
  }
  return overlaps;
}
