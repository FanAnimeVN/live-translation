/** Pure, bounded whole-word lettering; the caller measures the loaded font. */
export interface Lettering {fontSize:number;lineHeight:number;lines:string[];overflow:boolean}
type Measure=(text:string,fontSize:number)=>number;
const MIN_FONT=11,MAX_FONT=24,PADDING=3,LEADING=1.25;

function letteringUnits(paragraph:string,spelled=false):string[]{
  const value=paragraph.trim(),matches=[...value.matchAll(/\S+/gu)],units:string[]=[];
  const spelledGlyph=(token:string)=>/^["“‘「『(]*\p{L}[!?.,…:;”’"」』)]*$/u.test(token);
  for(let i=0;i<matches.length;){
    let unit=matches[i][0],end=matches[i].index!+unit.length,j=i+1;
    // Do not reflow a deliberately spelled word or replace its internal gaps.
    if(spelledGlyph(unit)){
      while(j<matches.length&&/\p{L}$/u.test(matches[j-1][0])&&spelledGlyph(matches[j][0])&&value.slice(end,matches[j].index)===" "){
        end=matches[j].index!+matches[j][0].length;j++;
      }
      if(j-i>=(spelled?2:3))unit=value.slice(matches[i].index,end);
      else {j=i+1;end=matches[i].index!+unit.length;}
    }
    const gap=i?value.slice(matches[i-1].index!+matches[i-1][0].length,matches[i].index):"";
    // Wide gaps, NBSP and tabs are authored pacing, not ordinary word spaces.
    if(i&&gap!==" ")units[units.length-1]+=gap+unit;else units.push(unit);
    i=j;
  }
  return units;
}

function wrap(words:string[],width:number,size:number,measure:Measure):string[]{
  // Normal dialogue is short. Bound the dynamic program for unusually long
  // model output rather than making scrolling/layout wait on quadratic work.
  if(words.length>120){
    const lines:string[]=[];let line="";
    for(const word of words){const next=line?line+" "+word:word;
      if(line&&measure(next,size)>width){lines.push(line);line=word;}else line=next;
    }
    if(line)lines.push(line);return lines;
  }
  const n=words.length,cost=new Array<number>(n+1).fill(Infinity),next=new Array<number>(n);
  cost[n]=0;
  for(let i=n-1;i>=0;i--){
    let line="";
    for(let j=i;j<n;j++){
      line+=(j===i?"":" ")+words[j];const used=measure(line,size);
      if(used>width&&j>i)break;
      // One overlong token remains intact and becomes explicit overflow.
      const slack=Math.max(0,width-used),last=j===n-1;
      const penalty=used>width?1e9:slack*slack*(last?0.75:1);
      const candidate=cost[j+1]+penalty+width*width*0.05;
      if(candidate<cost[i]){cost[i]=candidate;next[i]=j+1;}
    }
  }
  const lines:string[]=[];
  for(let i=0;i<n;){const end=next[i]??i+1;lines.push(words.slice(i,end).join(" "));i=end;}
  return lines;
}

export function fitLettering(text:string,width:number,height:number,measure:Measure,preferredSize=MAX_FONT,intent:{spelled?:boolean}={}):Lettering{
  if(!text.trim())return {fontSize:MIN_FONT,lineHeight:MIN_FONT*LEADING,lines:[],overflow:false};
  const valid=Number.isFinite(width)&&Number.isFinite(height)&&width>0&&height>0;
  const usableWidth=valid?Math.max(1,width-PADDING*2):1,usableHeight=valid?Math.max(0,height-PADDING*2):0;
  const paragraphs=text.replace(/\r\n?/g,"\n").split("\n");
  let result:Lettering={fontSize:MIN_FONT,lineHeight:MIN_FONT*LEADING,lines:[],overflow:true};
  const maximum=Number.isFinite(preferredSize)?Math.min(48,Math.max(MIN_FONT,Math.round(preferredSize))):MAX_FONT;
  for(let size=maximum;size>=MIN_FONT;size--){
    const cache=new Map<string,number>();
    const measured=(value:string)=>{let found=cache.get(value);if(found===undefined){found=measure(value,size);cache.set(value,found);}return found;};
    const lines=paragraphs.flatMap(paragraph=>{
      const words=letteringUnits(paragraph,!!intent.spelled);
      return words.length?wrap(words,usableWidth,size,measured):[""];
    });
    const lineHeight=size*LEADING;
    const overflow=!valid||lines.length*lineHeight>usableHeight+0.1||lines.some(line=>measured(line)>usableWidth+0.1);
    result={fontSize:size,lineHeight,lines,overflow};if(!overflow)break;
  }
  return result;
}
