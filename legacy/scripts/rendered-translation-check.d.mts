export function assertLetteredText(source:string,rendered:string,spelled?:boolean):void;
export function hasClassToken(value:string|undefined,token:string):boolean;
export function assertRenderedTranslations(
  regions:Array<{id:string;vi?:string;scope?:{action:string};expression?:{cues:string[]}}>,
  nodes:Array<{id:string;text:string;ariaLabel?:string}>
):void;
