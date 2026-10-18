export interface LetteringBox {id:string;rect:{x:number;y:number;width:number;height:number}}
export interface LetteringOverlap {ids:[string,string];width:number;height:number;minBoxFraction:number}
export function findLetteringBoxOverlaps(items:LetteringBox[],tolerance?:number):LetteringOverlap[];
