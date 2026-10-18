"""Bounded paid-attempt receipts, never dialogue, story IDs, keys or images."""
from contextlib import closing
import math
import re
import sqlite3
import time
import uuid

from .errors import AppError


class SummaryUsage:
    def __init__(self,path):
        self.path=path

    def begin(self,model):
        attempt=uuid.uuid4().hex
        try:
            with closing(sqlite3.connect(self.path,timeout=2)) as db,db:
                db.execute("CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,started REAL,model TEXT,state TEXT,cost REAL,input_tokens INTEGER,output_tokens INTEGER)")
                if "provider_id" not in {row[1] for row in db.execute("PRAGMA table_info(attempts)")}:
                    db.execute("ALTER TABLE attempts ADD COLUMN provider_id TEXT")
                db.execute("INSERT INTO attempts(id,started,model,state) VALUES(?,?,?,'sent')",(attempt,time.time(),model))
                db.execute("DELETE FROM attempts WHERE rowid NOT IN (SELECT rowid FROM attempts ORDER BY rowid DESC LIMIT 512)")
        except sqlite3.Error:
            raise AppError("USAGE_LEDGER","Không ghi được biên nhận chi phí. Chưa gửi request tóm tắt.") from None
        return attempt

    def finish(self,attempt,state,usage=None,provider_id=None):
        usage=usage if isinstance(usage,dict) else {}
        if not isinstance(provider_id,str) or not re.fullmatch(r"gen-[A-Za-z0-9._:-]{1,120}",provider_id):provider_id=None
        def metric(name):
            value=usage.get(name)
            return value if type(value) in (int,float) and math.isfinite(value) and value>=0 else None
        try:
            with closing(sqlite3.connect(self.path,timeout=2)) as db,db:
                db.execute("UPDATE attempts SET state=?,cost=?,input_tokens=?,output_tokens=?,provider_id=? WHERE id=?",
                           (state,metric("cost"),metric("prompt_tokens"),metric("completion_tokens"),provider_id,attempt))
        except sqlite3.Error:
            # The durable pre-I/O 'sent' receipt remains unknown, never $0.
            pass

    def recent(self):
        if not self.path.is_file():return []
        try:
            with closing(sqlite3.connect(self.path,timeout=2)) as db:
                db.row_factory=sqlite3.Row
                return [{"id":r["id"],"started":r["started"],"model":r["model"],"state":r["state"],
                         "costUsd":r["cost"],"inputTokens":r["input_tokens"],"outputTokens":r["output_tokens"],
                         "providerId":r["provider_id"] if "provider_id" in r.keys() else None}
                        for r in db.execute("SELECT * FROM attempts ORDER BY rowid DESC LIMIT 10")]
        except sqlite3.Error:
            raise AppError("USAGE_LEDGER","Chưa đọc được biên nhận tóm tắt; không suy ra chi phí bằng 0.") from None
