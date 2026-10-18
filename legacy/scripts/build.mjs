import {build} from "esbuild";
import {mkdir,writeFile,copyFile} from "node:fs/promises";
import {readFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import {fileURLToPath} from "node:url";
import path from "node:path";
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const dest=path.join(root,"dist/extension");await mkdir(dest,{recursive:true});
const lettering=JSON.parse(await readFile(path.join(root,"extension/assets/font.lock.json"),"utf8"));
const fontBytes=await readFile(path.join(root,"extension/assets/PatrickHand-Regular.ttf"));
if(fontBytes.length!==lettering.bytes||createHash("sha256").update(fontBytes).digest("hex")!==lettering.sha256)
  throw new Error("Packaged lettering font does not match pinned checksum");
await mkdir(path.join(dest,"assets"),{recursive:true});
await Promise.all(["PatrickHand-Regular.ttf","OFL-PatrickHand.txt","font.lock.json"].map(file=>
  copyFile(path.join(root,"extension/assets",file),path.join(dest,"assets",file))));
await Promise.all([
  build({entryPoints:[path.join(root,"extension/background.ts")],outfile:path.join(dest,"background.js"),bundle:true,format:"esm",target:"chrome120",minify:true}),
  build({entryPoints:[path.join(root,"extension/content.ts")],outfile:path.join(dest,"content.js"),bundle:true,format:"iife",target:"chrome120",minify:true}),
  build({entryPoints:[path.join(root,"extension/ui.tsx")],outfile:path.join(dest,"ui.js"),bundle:true,format:"iife",target:"chrome120",minify:true})
]);
// A visible deterministic build identity, independent of the display/store
// version. Reload can now be distinguished from an old options document.
const bundleParts=await Promise.all(["background.js","content.js","ui.js","ui.css"].map(file=>readFile(path.join(dest,file))));
const buildId=createHash("sha256");for(const part of bundleParts)buildId.update(part);
const manifest={
  manifest_version:3,name:"Live translation · Nhật–Việt",version:"0.1.0",
  version_name:"0.1.0-dev."+buildId.digest("hex").slice(0,12),
  description:"Dịch vùng chữ tiếng Nhật trên màn hình với OCR local, overlay và bộ nhớ truyện riêng tư.",
  permissions:["activeTab","scripting","storage","nativeMessaging"],
  background:{service_worker:"background.js",type:"module"},
  action:{default_popup:"popup.html",default_title:"Live translation"},
  options_ui:{page:"options.html",open_in_tab:true},
  web_accessible_resources:[{resources:["assets/PatrickHand-Regular.ttf"],matches:["<all_urls>"],use_dynamic_url:true}],
  content_security_policy:{extension_pages:"script-src 'self'; object-src 'self'"}
};
await writeFile(path.join(dest,"manifest.json"),JSON.stringify(manifest,null,2));
const html='<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Live translation</title><link rel="stylesheet" href="ui.css"></head><body><div id="app"></div><script src="ui.js"></script></body></html>';
await Promise.all(["popup.html","options.html"].map(file=>writeFile(path.join(dest,file),html)));
console.log("Built dist/extension (Manifest V3)");
