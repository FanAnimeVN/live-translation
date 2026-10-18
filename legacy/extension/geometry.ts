export interface Box {x:number;y:number;width:number;height:number}

function offset(value:string,free:number){
  if(value.endsWith("%"))return Number.parseFloat(value)/100*free;
  if(value.endsWith("px"))return Number.parseFloat(value);
  if(value==="left"||value==="top")return 0;
  if(value==="right"||value==="bottom")return free;
  return free/2;
}

/** CSS object-fit geometry; source pixels may extend beyond the content box. */
export function fittedImage(box:Box,naturalWidth:number,naturalHeight:number,fit:string,position:string):Box{
  if(fit==="fill")return box;
  let scale=fit==="cover"?Math.max(box.width/naturalWidth,box.height/naturalHeight)
    :fit==="none"?1:Math.min(box.width/naturalWidth,box.height/naturalHeight);
  if(fit==="scale-down")scale=Math.min(1,scale);
  const width=naturalWidth*scale,height=naturalHeight*scale;
  const values=position.trim().split(/\s+/);
  return {x:box.x+offset(values[0]??"50%",box.width-width),
    y:box.y+offset(values[1]??"50%",box.height-height),width,height};
}

export function regionBox(bbox:number[],source:Box,width:number,height:number):Box{
  const [x,y,w,h]=bbox;
  return {x:source.x+x/width*source.width,y:source.y+y/height*source.height,
    width:w/width*source.width,height:h/height*source.height};
}

export function intersect(a:Box,b:Box):Box{
  const x=Math.max(a.x,b.x),y=Math.max(a.y,b.y);
  return {x,y,width:Math.max(0,Math.min(a.x+a.width,b.x+b.width)-x),
    height:Math.max(0,Math.min(a.y+a.height,b.y+b.height)-y)};
}
