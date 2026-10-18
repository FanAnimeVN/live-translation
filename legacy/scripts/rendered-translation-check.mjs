// QA contract: source-bound IDs and exact wording, independent of DOM order.
import assert from "node:assert/strict";

export function hasClassToken(value,token){
  return typeof value==="string"&&value.split(/\s+/u).includes(token);
}

export function assertLetteredText(source,rendered,spelled=false){
  // Match the renderer's paragraph-edge trim/CRLF policy, not arbitrary
  // whitespace normalization. Only an ordinary inter-word ASCII space may
  // become a physical line break; explicit breaks/pacing stay exact.
  const reference=source.replace(/\r\n?/g,"\n").split("\n").map(p=>p.trim()).join("\n");
  const tokens=[...reference.matchAll(/\S+/gu)],protectedGaps=new Set();
  const glyph=token=>/^["“‘「『(]*\p{L}[!?.,…:;”’"」』)]*$/u.test(token);
  for(let i=0;i<tokens.length;){
    let j=i+1;
    if(glyph(tokens[i][0]))while(j<tokens.length&&/\p{L}$/u.test(tokens[j-1][0])&&glyph(tokens[j][0])&&
        reference.slice(tokens[j-1].index+tokens[j-1][0].length,tokens[j].index)===" ")j++;
    if(j-i>=(spelled?2:3))for(let k=i;k<j-1;k++)protectedGaps.add(tokens[k].index+tokens[k][0].length);
    i=j;
  }
  assert.equal(rendered.length,reference.length,"Lettering added or dropped source characters");
  for(let i=0;i<reference.length;i++){
    if(reference[i]===rendered[i])continue;
    const softWrap=reference[i]===" "&&rendered[i]==="\n"&&i>0&&i+1<reference.length&&
      !/\s/u.test(reference[i-1])&&!/\s/u.test(reference[i+1])&&!protectedGaps.has(i);
    assert(softWrap,"Lettering changed source wording, punctuation or deliberate pacing");
  }
}

export function assertRenderedTranslations(regions,nodes){
  const expected=regions.filter(r=>r.vi&&r.scope?.action!=="defer");
  assert.equal(nodes.length,expected.length,"Every completed translation must render once");
  const byId=new Map(expected.map(region=>[region.id,region]));
  assert.equal(byId.size,expected.length,"Native translation IDs must be unique");
  const seen=new Set();
  for(const node of nodes){
    assert(!seen.has(node.id),"Duplicate rendered translation ID");seen.add(node.id);
    const region=byId.get(node.id);assert(region,"Unknown or stale rendered translation ID");
    assert.equal(node.ariaLabel,"Xem và sửa bản dịch: "+region.vi,"Rendered wording must bind to its exact native ID");
    assertLetteredText(region.vi,node.text,region.expression?.cues.includes("spelled"));
  }
}
