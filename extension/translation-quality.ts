/** Editorial hint for a name, never a translation correction or error gate. */
export function repeatedNameWord(value:string):string|undefined {
  const words=[...value.matchAll(/[\p{L}\p{M}]+/gu)];
  for(let index=1;index<words.length;index++){
    const previous=words[index-1],current=words[index];
    if(previous[0].length<2||!/^[\s]+$/.test(value.slice(previous.index!+previous[0].length,current.index)))continue;
    if(previous[0].normalize("NFKC").toLocaleLowerCase("vi")===current[0].normalize("NFKC").toLocaleLowerCase("vi"))return previous[0];
  }
}

export function nameReviewNote(value:string):string|undefined {
  const word=repeatedNameWord(value);
  return word?`Tên có âm “${word}” lặp. Có thể là chủ ý của tên gốc; bạn có thể giữ nguyên hoặc sửa cho dễ đọc. Không tự đổi tên đã chốt.`:undefined;
}
