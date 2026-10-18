"""Opt-in Wikidata identity lookup: labels/aliases only; never plot/wiki scraping."""
import json
import urllib.parse
import urllib.request
from .errors import AppError,require
from .validation import text


class Metadata:
    def __init__(self,config):
        self.config=config

    def search(self,title):
        require(self.config.values["mode"]!="offline" and self.config.values["metadataConsent"],
                "OFFLINE","Tra metadata mạng đang tắt. Bạn vẫn có thể xác nhận tên truyện và nhập recap.")
        title=text(title,150)
        query=urllib.parse.urlencode({"action":"wbsearchentities","search":title,"language":"ja",
                                     "uselang":"en","limit":5,"format":"json"})
        req=urllib.request.Request("https://www.wikidata.org/w/api.php?"+query,
                                  headers={"User-Agent":"MangaLive/0.1 (local user initiated metadata lookup)"})
        try:
            with urllib.request.urlopen(req,timeout=10) as response:
                raw=response.read(100001)
                require(len(raw)<=100000,"METADATA_SIZE")
                data=json.loads(raw)
            # Entity descriptions may contain premise/spoilers; do not expose them.
            return [{"qid":item["id"],"label":item.get("label",title),
                     "aliases":[title,item.get("label",title)],"source":"https://www.wikidata.org/wiki/"+item["id"],
                     "license":"CC0","scope":"identity-only"} for item in data.get("search",[])[:5]]
        except (OSError,ValueError,KeyError):
            raise AppError("METADATA","Không tra được metadata. Có thể xác nhận thủ công và dịch ngay.")
