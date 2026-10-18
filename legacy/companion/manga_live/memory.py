"""Versioned, temporal SQLite memory. Content stays in the user's browser profile."""
import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from .errors import AppError, require
from .validation import identifier, location, text, number
from .terminology import term_record,grounded_proposals
from .linguistics import name_record
from .context_pack import validate_pack, root_source
from .summary_links import SummaryGraph, group_refs
from .expression import bind_expression
from .text_scope import story_regions

TTL = 86400
CACHE_LIMIT = 100 * 1024 * 1024
SPEAKER_BINDING_VERSION = "speaker-source-v1"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def bounded(rows, budget):
    """Conservative UTF-8 budget, not a claim of tokenizer-exact token counting."""
    result, used = [], 0
    for row in rows:
        size = len(encode(row).encode("utf-8"))
        if used + size <= budget * 3:
            result.append(row)
            used += size
    return result


def dialogue_source(source):
    """Retain temporal provenance even when an exported pack is imported again."""
    if isinstance(source,str):
        try:source=json.loads(source)
        except (TypeError,ValueError):return False
    for _ in range(24):
        if not isinstance(source,dict):return False
        if source.get("type")!="context-pack":return source.get("type")=="dialogue"
        source=source.get("original")
    # Over-nested provenance is not eligible for same-page retrieval.
    return True


def source_utterances(source):
    if isinstance(source,str):
        try:source=json.loads(source)
        except (TypeError,ValueError):return []
    for _ in range(24):
        if not isinstance(source,dict):return []
        if source.get("type")!="context-pack":
            values=source.get("utterances",[]) if source.get("type")=="dialogue" else []
            if not isinstance(values,list):return []
            return [{k:r[k] for k in ("ja","speaker","listener") if isinstance(r.get(k),str)}
                for r in values if isinstance(r,dict) and isinstance(r.get("ja"),str) and r["ja"]]
        source=source.get("original")
    return []


def prompt_fact(row):
    return {k:row[k] for k in ("kind","key","value","confirmed","locked","chapter","page")}


def known_forms(row):
    """Read only profiles validated by the same contracts as translation.

    Older/private imports may contain arbitrary JSON inside a fact's text.
    Preserve that text for review, but do not let a malformed name or canonical
    term become an identity hint or crash retrieval.
    """
    try:
        value = json.loads(row["value"])
        if not isinstance(value,dict):return None, []
        if row["kind"]=="character" and row["confirmed"] and value.get("type")=="name-forms":
            record = name_record(value["character"],value["forms"])
            return record["character"], [form["ja"] for form in record["forms"]]
        if row["kind"]=="glossary" and value.get("type")=="canonical-term":
            record = term_record(value["entity"],value["category"],value["ja"],value["vi"],
                value.get("aliases",[]),value.get("origin","user"))
            return record["entity"], [record["ja"], *[form["ja"] for form in record["aliases"]]]
    except (AppError,KeyError,TypeError,ValueError):pass
    return None, []


def retrieval_aliases(profiles, source_text, entities):
    """Bounded known names/terms, not invented Japanese word segmentation.

    The caller has already selected each record's version at the reading
    cutoff. A known role can retrieve its old name evidence even when Japanese
    omits the name. This selects evidence; it never asserts a new relationship.
    """
    result = set()
    for entity, forms in profiles.values():
        for alias in forms:
            if 2 <= len(alias) <= 80 and (alias in source_text or entity in entities):
                result.add(alias)
    return sorted(result, key=lambda alias: (-len(alias), alias))[:6]


def prompt_events(facts,summaries,read_utterances=source_utterances):
    """Unverified model paraphrases never become authoritative plot memory.

    Keep them for reader review/export, but use durable original utterances in
    inference. IDs/provenance stay in SQLite; quotes are necessary evidence,
    not database bookkeeping. Legacy generated entries without quotes are
    deliberately omitted until confirmed by a reader.
    """
    result=[];seen=set()
    for row in [*facts,*summaries]:
        is_summary="chapter_end" in row
        chapter,page=(row["chapter_end"],row["page_end"]) if is_summary else (row["chapter"],row["page"])
        if dialogue_source(row["source"]) and (is_summary or not row["confirmed"]):
            utterances=[]
            for item in read_utterances(row["source"]):
                key=(chapter,page,encode(item))
                if key not in seen:utterances.append(item);seen.add(key)
            if utterances:result.append({"kind":"dialogue-evidence","chapter":chapter,"page":page,"utterances":utterances})
        elif is_summary:
            result.append({k:row[k] for k in ("text","complete","chapter_start","chapter_end","page_end","kind")})
        else:result.append(prompt_fact(row))
    return result


class Memory:
    def __init__(self, path, clock=time.time):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.depth = 0
        self.clock = clock
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA secure_delete=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        require(version <= 4, "DB_VERSION", "Dữ liệu được tạo bởi bản mới hơn. Không tự hạ cấp.")
        if version == 0:
            self.db.executescript("""
              CREATE TABLE stories(id TEXT PRIMARY KEY,title TEXT NOT NULL,aliases TEXT NOT NULL DEFAULT '[]',version INTEGER NOT NULL DEFAULT 1);
              CREATE TABLE facts(id TEXT PRIMARY KEY,story TEXT REFERENCES stories(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,chapter REAL NOT NULL,page INTEGER NOT NULL,
                source TEXT NOT NULL,confirmed INTEGER NOT NULL,locked INTEGER NOT NULL,valid INTEGER NOT NULL DEFAULT 1);
              CREATE INDEX facts_time ON facts(story,chapter,page,valid);
              CREATE VIRTUAL TABLE facts_fts USING fts5(id UNINDEXED,value,tokenize='unicode61');
              CREATE TRIGGER fact_add AFTER INSERT ON facts BEGIN INSERT INTO facts_fts(id,value) VALUES(new.id,new.value); END;
              CREATE TRIGGER fact_del AFTER DELETE ON facts BEGIN DELETE FROM facts_fts WHERE id=old.id; END;
              CREATE TRIGGER fact_update AFTER UPDATE ON facts BEGIN DELETE FROM facts_fts WHERE id=old.id; INSERT INTO facts_fts(id,value) VALUES(new.id,new.value); END;
              CREATE TABLE summaries(id TEXT PRIMARY KEY,story TEXT REFERENCES stories(id) ON DELETE CASCADE,
                chapter_start REAL NOT NULL,chapter_end REAL NOT NULL,page_end INTEGER NOT NULL,
                kind TEXT NOT NULL,text TEXT NOT NULL,complete INTEGER NOT NULL,source TEXT NOT NULL,valid INTEGER NOT NULL DEFAULT 1);
              CREATE INDEX summary_time ON summaries(story,chapter_end,page_end,valid);
              CREATE TABLE cache(key TEXT PRIMARY KEY,story TEXT REFERENCES stories(id) ON DELETE CASCADE,
                chapter REAL NOT NULL,page INTEGER NOT NULL,payload TEXT NOT NULL,bytes INTEGER NOT NULL,expires REAL NOT NULL,accessed REAL NOT NULL);
              CREATE TABLE pages(story TEXT REFERENCES stories(id) ON DELETE CASCADE,id TEXT NOT NULL,
                chapter REAL NOT NULL,page INTEGER NOT NULL,revision TEXT NOT NULL,regions TEXT NOT NULL,
                state TEXT NOT NULL,expires REAL NOT NULL,PRIMARY KEY(story,id));
              CREATE TABLE jobs(id TEXT PRIMARY KEY,story TEXT REFERENCES stories(id) ON DELETE CASCADE,
                page_id TEXT NOT NULL,revision TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',expires REAL NOT NULL);
              CREATE TABLE speakers(story TEXT REFERENCES stories(id) ON DELETE CASCADE,page_id TEXT NOT NULL,region_id TEXT NOT NULL,
                speaker TEXT NOT NULL,listener TEXT NOT NULL,chapter REAL NOT NULL,page INTEGER NOT NULL,
                PRIMARY KEY(story,page_id,region_id));
              PRAGMA user_version=1;
            """)
            self.db.commit()
        if version < 2:
            self.db.executescript("""
              ALTER TABLE stories ADD COLUMN genre TEXT NOT NULL DEFAULT '';
              ALTER TABLE stories ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}';
              CREATE TABLE progress(story TEXT PRIMARY KEY REFERENCES stories(id) ON DELETE CASCADE,
                last_chapter REAL NOT NULL,last_page INTEGER NOT NULL,furthest_chapter REAL NOT NULL,
                updated REAL NOT NULL);
              PRAGMA user_version=2;
            """)
            self.db.commit()
        if version < 3:
            # Ordinal legacy rows contain no image/crop/revision evidence. Do
            # not attach them to today's page by guessing during migration.
            # Keep them intact for explicit reader re-confirmation instead.
            # executescript does not create a transaction itself. Include
            # BEGIN in the script and let the connection roll back on error,
            # so a failed migration can be retried without partial tables.
            with self.db:
                self.db.executescript("""
                  BEGIN IMMEDIATE;
                  CREATE TABLE speaker_bindings(story TEXT REFERENCES stories(id) ON DELETE CASCADE,
                    page_id TEXT NOT NULL,source_key TEXT NOT NULL,region_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,listener TEXT NOT NULL,chapter REAL NOT NULL,page INTEGER NOT NULL,
                    PRIMARY KEY(story,page_id,source_key,chapter,page));
                  PRAGMA user_version=3;
                  COMMIT;
                """)
        if version < 4:
            with self.db:
                self.db.executescript("""
                  BEGIN IMMEDIATE;
                  CREATE TABLE speaker_legacy(story TEXT REFERENCES stories(id) ON DELETE CASCADE,
                    page_id TEXT NOT NULL,region_id TEXT NOT NULL,speaker TEXT NOT NULL,listener TEXT NOT NULL,
                    chapter REAL NOT NULL,page INTEGER NOT NULL,
                    PRIMARY KEY(story,page_id,region_id,speaker,listener,chapter,page));
                  INSERT INTO speaker_legacy SELECT * FROM speakers;
                  PRAGMA user_version=4;
                  COMMIT;
                """)
        self.prune()

    @contextmanager
    def transaction(self):
        with self.lock:
            outer = self.depth == 0
            self.depth += 1
            try:
                yield self.db
                if outer:
                    self.db.commit()
            except Exception:
                if outer:
                    self.db.rollback()
                raise
            finally:
                self.depth -= 1

    def close(self):
        with self.lock:
            self.db.close()

    def ensure_story(self, story, title, genre=None):
        identifier(story)
        text(title, 300)
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO stories(id,title) VALUES(?,?)", (story, title))
            if genre is not None:
                text(genre,150,empty=True)
                db.execute("UPDATE stories SET genre=?,version=version+1 WHERE id=? AND genre<>?",(genre,story,genre))

    def version(self, story):
        with self.lock:
            row = self.db.execute("SELECT version FROM stories WHERE id=?", (story,)).fetchone()
            require(row is not None, "STORY", "Chưa có hồ sơ truyện.")
            return row[0]

    @contextmanager
    def at_version(self, story, expected):
        """Short compare-and-use guard, never held over model/OCR/cleanup work.

        This is not a transaction: a reentrant publication callback's reader
        edit must not be rolled back with a stale task. Writers may advance
        their own expected revision while holding the guard. Publications
        separately check again after their callback before continuing.
        """
        with self.lock:
            require(self.version(story)==expected,"STALE_CONTEXT",
                    "Ngữ cảnh vừa đổi; dịch lại trang để dùng lựa chọn mới.")
            yield

    def list_stories(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("""SELECT s.*,p.last_chapter,p.last_page,p.furthest_chapter
                FROM stories s LEFT JOIN progress p ON s.id=p.story ORDER BY COALESCE(p.updated,0) DESC,s.title""")]

    def fact(self, story, kind, key, value, at, source, confirmed=True, locked=True, fact_id=None):
        identifier(story)
        require(kind in ("character", "relationship", "glossary", "event", "note", "style"))
        text(key, 160)
        text(value, 1500)
        at = location(at)
        require(type(confirmed) is bool and type(locked) is bool)
        require(isinstance(source, dict) and len(encode(source)) < 10000)
        require(source.get("type") in ("user", "dialogue", "context-pack", "metadata"), "EVIDENCE")
        fact_id = identifier(fact_id or uuid.uuid4().hex)
        with self.transaction() as db:
            old = db.execute("SELECT locked,story FROM facts WHERE id=?", (fact_id,)).fetchone()
            require(old is None or (not old[0] and old[1] == story), "LOCKED", "Ghi chú đã khóa không được AI ghi đè.")
            db.execute("INSERT OR REPLACE INTO facts VALUES(?,?,?,?,?,?,?,?,?,?,1)",
                       (fact_id, story, kind, key, value, at["chapter"], at["page"], encode(source), int(confirmed), int(locked)))
            db.execute("UPDATE stories SET version=version+1 WHERE id=?", (story,))
        return fact_id

    def summary(self, story, start, end, page, value, source, complete=False, kind="chapter", summary_id=None):
        identifier(story); number(start); location({"chapter":end,"page":page})
        require(start <= end and type(complete) is bool)
        require(kind in ("chapter", "group", "recap"))
        text(value, 6000)
        require(isinstance(source, dict) and bool(source.get("type")), "EVIDENCE")
        sid = identifier(summary_id or uuid.uuid4().hex)
        with self.transaction() as db:
            owner = db.execute("SELECT story FROM summaries WHERE id=?", (sid,)).fetchone()
            require(owner is None or owner[0] == story, "CONTEXT_CONFLICT")
            if kind == "group":
                self._summary_graph(story).validate({"id": sid, "kind": kind, "chapter_start": start,
                    "chapter_end": end, "page_end": page, "source": source, "complete": complete})
            db.execute("INSERT OR REPLACE INTO summaries VALUES(?,?,?,?,?,?,?,?,?,1)",
                       (sid, story, start, end, page, kind, value, int(complete), encode(source)))
            db.execute("UPDATE stories SET version=version+1 WHERE id=?", (story,))
        return sid

    def _summary_graph(self, story):
        # A graph belongs to this locked snapshot. Shared leaves are queried
        # once even when many recent groups refer to the same old evidence.
        loaded = {}
        def lookup(ref):
            if ref not in loaded:
                row = self.db.execute("SELECT * FROM summaries WHERE story=? AND id=? AND valid=1", (story, ref)).fetchone()
                loaded[ref] = dict(row) if row else None
            return loaded[ref]
        return SummaryGraph(lookup)

    def context(self, story, at, source_text="", page_id="", entities=()):
        at = location(at)
        c, p = at["chapter"], at["page"]
        with self.lock:
            quote_cache = {}
            def quotes(source):
                # Database sources are encoded strings. Scope this cache to
                # the locked snapshot so OCR corrections/imports cannot leave
                # stale evidence across requests or reading cutoffs.
                if not isinstance(source,str):return source_utterances(source)
                if source not in quote_cache:quote_cache[source]=source_utterances(source)
                return quote_cache[source]
            version = self.version(story)
            facts = [dict(r) for r in self.db.execute("""SELECT * FROM facts WHERE story=? AND valid=1
                AND (chapter<? OR (chapter=? AND page<=?)) ORDER BY chapter DESC,page DESC,rowid DESC""", (story, c, c, p))]
            # Latest knowledge of each key at the reading cutoff, not globally latest.
            unique, seen = [], set()
            for row in facts:
                if row["chapter"]==c and row["page"]==p and row["kind"] in ("event","note","character","relationship") and dialogue_source(row["source"]):
                    continue
                if (row["kind"], row["key"]) not in seen:
                    unique.append(row)
                    seen.add((row["kind"], row["key"]))
            # FTS is a relevance hint only; the temporal filter above is always authoritative.
            terms = re.findall(r"[\w\u3040-\u30ff\u4e00-\u9fff]{2,20}", source_text)[:12]
            profiles = {row["id"]:known_forms(row) for row in unique if row["kind"] in ("character","glossary")}
            aliases = retrieval_aliases(profiles, source_text, entities)
            search_terms = [*terms, *aliases]
            hits = set()
            if terms:
                query = " OR ".join('"' + t.replace('"', '') + '"' for t in terms)
                hits = {r[0] for r in self.db.execute("SELECT id FROM facts_fts WHERE facts_fts MATCH ? LIMIT 30", (query,))}
            relevance_scores = {}
            def relevance(row):
                if row["id"] in relevance_scores:return relevance_scores[row["id"]]
                pair=row["key"].split("→")
                explicit=bool(entities) and (row["key"] in entities or (len(pair)==2 and all(x in entities for x in pair)))
                matched=row["key"] in source_text or row["id"] in hits or (bool(search_terms) and any(
                    term in item["ja"] for item in quotes(row["source"]) for term in search_terms))
                if row["id"] in profiles:
                    matched = matched or any(alias in source_text for alias in profiles[row["id"]][1])
                score=(not explicit,not matched,not row["locked"],-row["chapter"],-row["page"])
                relevance_scores[row["id"]]=score
                return score
            unique.sort(key=relevance)
            summaries = [dict(r) for r in self.db.execute("""SELECT * FROM summaries WHERE story=? AND valid=1
                AND (chapter_end<? OR (chapter_end=? AND page_end<=?)) ORDER BY chapter_end DESC,page_end DESC LIMIT 20""", (story, c, c, p))]
            if aliases:
                # unicode61 does not segment an unspaced Japanese sentence into
                # name tokens. Literal, parameterized evidence lookup supplements
                # recent context; no wiki/vector service or future records.
                match = " OR ".join("instr(source,?)>0" for _ in aliases)
                related = self.db.execute("""SELECT * FROM summaries WHERE story=? AND valid=1 AND kind<>'group'
                    AND (chapter_end<? OR (chapter_end=? AND page_end<=?)) AND (""" + match +
                    ") ORDER BY chapter_end DESC,page_end DESC LIMIT 24", (story, c, c, p, *aliases))
                summaries.extend(dict(row) for row in related if any(alias in item["ja"]
                    for item in quotes(row["source"]) for alias in aliases))
            summaries=[r for r in summaries if not (r["chapter_end"]==c and r["page_end"]==p and dialogue_source(r["source"]))]
            graph = self._summary_graph(story)
            eligible, summary_seen = [], set()
            for row in summaries:
                try: evidence_rows = list(graph.prompt_rows(row))
                except AppError: continue  # Legacy broken links are reviewable, never prompt facts.
                for evidence in evidence_rows:
                    if evidence["id"] not in summary_seen:
                        eligible.append(evidence); summary_seen.add(evidence["id"])
            # A group's claimed end is not the time at which each child fact
            # became known. Keep original cutoffs and prioritize recent leaves.
            summaries = sorted(eligible, key=lambda row: (
                not (bool(aliases) and any(alias in item["ja"] for item in quotes(row["source"]) for alias in aliases)),
                -row["chapter_end"], -row["page_end"]))
            # Rank facts and original summary evidence together before the
            # shared event budget. Otherwise unrelated large reader notes can
            # consume that budget before a relevant old quote is considered.
            def event_rank(row):
                is_summary = "chapter_end" in row
                if is_summary:
                    related = bool(search_terms) and any(term in item["ja"] for item in quotes(row["source"]) for term in search_terms)
                    if not dialogue_source(row["source"]):
                        related = related or any(term in row["text"] for term in search_terms)
                    reader = not dialogue_source(row["source"])
                    chapter,page = row["chapter_end"],row["page_end"]
                else:
                    related = not all(relevance(row)[:2])
                    if row["confirmed"]:
                        related = related or any(term in row["value"] for term in search_terms)
                    reader = bool(row["confirmed"] and row["locked"])
                    chapter,page = row["chapter"],row["page"]
                return (not related,not reader,-chapter,-page)
            event_rows = sorted([*[r for r in unique if r["kind"] in ("event","note")],*summaries],key=event_rank)
            recent = list(self.db.execute("""SELECT chapter,page,regions FROM pages WHERE story=?
                AND expires>? AND state='read' AND (chapter<? OR (chapter=? AND page<?))
                ORDER BY chapter DESC,page DESC LIMIT 2""", (story, self.clock(), c, c, p)))
            # Apply scope before projection. Source geometry, cleanup receipts
            # and review diagnostics stay in the page record; they are not
            # dialogue and must not consume its model-input byte allowance.
            recent_dialogue = [{**{key:r[key] for key in ("id","ja","vi","speaker","listener","type") if key in r},
                               "chapter":page["chapter"],"page":page["page"]}
                for page in reversed(recent) for r in story_regions(json.loads(page["regions"]))][-18:]
            # Spend the byte allowance on newest complete utterances first,
            # then present the survivors in their original reading order.
            recent_dialogue = list(reversed(bounded(reversed(recent_dialogue),500)))
            selected = {
                "story": dict(self.db.execute("SELECT title,genre,aliases FROM stories WHERE id=?",(story,)).fetchone()),
                "characters": bounded([prompt_fact(r) for r in unique if r["kind"] in ("character", "relationship")], 500),
                # SQL selects newest pages first; dialogue must reach the
                # translator oldest-to-newest. Truncate only after restoring
                # that order, otherwise an older page displaces recent replies.
                "recent_dialogue": recent_dialogue,
                "events": bounded(prompt_events(event_rows,[],read_utterances=quotes),500),
                # Evidence stays in SQLite, not repeated in the prompt budget.
                "glossary": bounded([{k:r[k] for k in ("key","value","confirmed","locked","chapter","page")}
                    for r in unique if r["kind"] == "glossary"], 500),
                "styles":bounded([{k:r[k] for k in ("key","value","confirmed","chapter","page")}
                    for r in unique if r["kind"]=="style" and r["key"] in ("naming","honorifics","kinship")],150),
            }
            fingerprint = digest(selected)
            return {"version": version, "fingerprint": fingerprint, "cutoff": at, "data": selected}

    def cache_get(self, key):
        with self.transaction() as db:
            row = db.execute("SELECT payload FROM cache WHERE key=? AND expires>?", (key, self.clock())).fetchone()
            if row:
                db.execute("UPDATE cache SET accessed=? WHERE key=?", (self.clock(), key))
                return json.loads(row[0])

    def cache_put(self, key, story, at, payload):
        encoded = encode(payload)
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?,?,?,?)", (key, story, at["chapter"], at["page"], encoded,
                       len(encoded.encode()), self.clock() + TTL, self.clock()))
        self.prune()

    def save_page(self, story, page_id, at, revision, regions, state="processed"):
        require(state in ("processed", "displayed", "read"))
        with self.transaction() as db:
            old = db.execute("SELECT state,revision FROM pages WHERE story=? AND id=?", (story, page_id)).fetchone()
            rank = {"processed": 0, "displayed": 1, "read": 2}
            if old and old[1] == revision and rank[old[0]] > rank[state]:
                state = old[0]
            db.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?,?,?)", (story, page_id, at["chapter"], at["page"], revision,
                       encode(regions), state, self.clock() + TTL))

    def page(self, story, page_id, revision):
        with self.lock:
            row=self.db.execute("SELECT * FROM pages WHERE story=? AND id=? AND expires>?",
                                (story,page_id,self.clock())).fetchone()
            require(row and row["revision"]==revision,"STALE","Trang đã đổi; không sửa kết quả cũ.")
            return {**dict(row),"regions":json.loads(row["regions"])}

    def correct_region(self, story, page_id, at, revision, region):
        with self.transaction():
            page=self.page(story,page_id,revision)
            require(any(r["id"]==region["id"] for r in page["regions"]),"STALE")
            require(page["chapter"]==at["chapter"] and page["page"]==at["page"],"STALE")
            self.invalidate(story,at,page_id,keep_page=True)
            regions=[bind_expression({**r,**region}) if r["id"]==region["id"] else r for r in page["regions"]]
            self.save_page(story,page_id,at,revision,regions,state="displayed")

    def canonical_term(self, story, entity, category, ja, vi, aliases, at):
        entity=entity or "term-"+digest([story,ja])[:24]
        record=term_record(entity,category,ja,vi,aliases)
        # An explicit user correction creates a temporal revision. It never
        # rewrites an earlier reader's cutoff or mutates the previous lock.
        return self.fact(story,"glossary",entity,encode(record),at,{"type":"user"},True,True)

    def confirm_term(self, story, page_id, revision, entity, at, vi=None):
        with self.transaction():
            page=self.page(story,page_id,revision)
            require(page["chapter"]==at["chapter"] and page["page"]==at["page"],"STALE")
            row=self.db.execute("SELECT * FROM facts WHERE story=? AND kind='glossary' AND key=? AND valid=1 "
                "AND (chapter<? OR (chapter=? AND page<=?)) ORDER BY chapter DESC,page DESC,rowid DESC LIMIT 1",
                (story,entity,at["chapter"],at["chapter"],at["page"])).fetchone()
            require(row is not None,"TERM","Tên này không còn trong context của trang.")
            record=json.loads(row["value"])
            require(record.get("type")=="canonical-term" and any(record["ja"] in r["ja"] for r in page["regions"]),"EVIDENCE")
            new_vi=text(vi,120) if vi is not None else record["vi"]
            self.canonical_term(story,entity,record["category"],record["ja"],new_vi,record.get("aliases",[]),at)
            return {**record,"vi":new_vi,"origin":"user","changed":new_vi!=record["vi"]}

    def accept_terms(self, story, at, page_id, proposals):
        accepted=[]
        with self.transaction():
            # Query the full temporal glossary; prompt budgets must not cause a
            # second lock for an existing term that was not retrieved.
            rows=self.db.execute("SELECT key,value FROM facts WHERE story=? AND kind='glossary' AND valid=1 "
                "AND (chapter<? OR (chapter=? AND page<=?)) ORDER BY chapter DESC,page DESC,rowid DESC",
                (story,at["chapter"],at["chapter"],at["page"])).fetchall()
            sources=set();seen=set()
            for row in rows:
                if row["key"] in seen:continue
                seen.add(row["key"]);sources.add(row["key"])
                try:
                    record=json.loads(row["value"])
                    if isinstance(record,dict) and record.get("type")=="canonical-term":
                        sources.add(record["ja"]);sources.update(a["ja"] for a in record.get("aliases",[]))
                except (ValueError,KeyError,TypeError):pass
            for proposal in proposals:
                if proposal["ja"] in sources:continue
                entity="term-"+digest([story,proposal["ja"]])[:24]
                record=term_record(entity,proposal["category"],proposal["ja"],proposal["vi"],origin="auto")
                self.fact(story,"glossary",entity,encode(record),at,
                    {"type":"dialogue","page_id":page_id,"region_ids":[proposal["region_id"]]},False,True)
                sources.add(proposal["ja"]);accepted.append(record)
        return accepted

    def mark_read(self, story, page_id, revision):
        with self.transaction() as db:
            row = db.execute("SELECT revision,expires FROM pages WHERE story=? AND id=?", (story, page_id)).fetchone()
            require(row and row[0] == revision and row[1]>self.clock(), "STALE", "Trang đã đổi hoặc hết cache; dịch lại trước khi lưu tiến độ.")
            db.execute("UPDATE pages SET state='read' WHERE story=? AND id=?", (story, page_id))
            at=db.execute("SELECT chapter,page FROM pages WHERE story=? AND id=?",(story,page_id)).fetchone()
            db.execute("""INSERT INTO progress VALUES(?,?,?,?,?) ON CONFLICT(story) DO UPDATE SET
                last_chapter=excluded.last_chapter,last_page=excluded.last_page,
                furthest_chapter=MAX(progress.furthest_chapter,excluded.furthest_chapter),updated=excluded.updated""",
                (story,at["chapter"],at["page"],at["chapter"],self.clock()))
            db.execute("""INSERT INTO jobs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                state=CASE WHEN jobs.state IN ('failed','gap') THEN 'pending' ELSE jobs.state END,
                expires=excluded.expires""", (digest([story, page_id, revision]), story, page_id,
                       revision, "pending", row[1]))
            return digest([story, page_id, revision])

    def next_job(self,story=None,at=None,job_ids=None):
        clause,params="",[self.clock(),self.clock()]
        if job_ids is not None:
            require(isinstance(job_ids,(list,tuple)) and len(job_ids)<=64,"SUMMARY_JOBS")
            if not job_ids:return None
            permitted=[identifier(value) for value in job_ids]
            clause+=" AND j.id IN ("+",".join("?" for _ in permitted)+")"
            params.extend(permitted)
        if story is not None:
            clause+=" AND j.story=?";params.append(identifier(story))
        if at is not None:
            at=location(at)
            clause+=" AND (p.chapter<? OR (p.chapter=? AND p.page<=?))"
            params.extend([at["chapter"],at["chapter"],at["page"]])
        with self.lock:
            row = self.db.execute("""SELECT j.*,p.chapter,p.page,p.regions FROM jobs j JOIN pages p
                ON j.story=p.story AND j.page_id=p.id AND j.revision=p.revision
                WHERE j.state='pending' AND j.expires>? AND p.expires>? AND p.state='read'"""+
                clause+" ORDER BY j.rowid LIMIT 1",params).fetchone()
            if not row:return None
            job=dict(row)
            # Keep the full source stamp separate from the filtered model
            # input. A change to a deferred region still invalidates this job.
            job["sourceDigest"]=digest(json.loads(job["regions"]))
            job["regions"]=encode(story_regions(json.loads(job["regions"])))
            return job

    def fail_job(self,job):
        with self.transaction() as db:
            db.execute("UPDATE jobs SET state='failed' WHERE id=? AND state='pending'",(job["id"],))

    def summary_status(self,story):
        self.prune()
        with self.lock:
            counts={state:0 for state in ("pending","failed","gap","done")}
            counts.update({r[0]:r[1] for r in self.db.execute("SELECT state,COUNT(*) FROM jobs WHERE story=? GROUP BY state",(identifier(story),))})
            return counts

    def retry_jobs(self,story):
        self.prune()
        with self.transaction() as db:
            return db.execute("""UPDATE jobs SET state='pending' WHERE story=? AND state='failed' AND expires>?
                AND EXISTS(SELECT 1 FROM pages p WHERE p.story=jobs.story AND p.id=jobs.page_id
                AND p.revision=jobs.revision AND p.expires>? AND p.state='read')""",
                (identifier(story),self.clock(),self.clock())).rowcount

    def finish_job(self, job, raw):
        """Only validated evidence references can propose unconfirmed facts."""
        require(isinstance(raw, dict) and isinstance(raw.get("facts", []), list))
        value = text(raw.get("summary"), 1200)
        regions = json.loads(job["regions"])
        ids = {r["id"] for r in regions}
        def utterances(evidence):
            return [{"id":r["id"],"ja":r["ja"],"speaker":r.get("speaker","unknown"),"listener":r.get("listener","unknown")}
                for r in regions if r["id"] in evidence]
        proposals = raw.get("facts", [])
        require(len(proposals) <= 8)
        for proposal in proposals:
            require(isinstance(proposal, dict))
            text(proposal.get("text"), 250)
            evidence = proposal.get("evidence_ids")
            require(isinstance(evidence, list) and evidence and set(evidence) <= ids, "EVIDENCE")
        with self.transaction() as db:
            page = db.execute("SELECT revision FROM pages WHERE story=? AND id=?", (job["story"], job["page_id"])).fetchone()
            require(page and page[0] == job["revision"], "STALE")
            current=db.execute("SELECT j.state,p.regions FROM jobs j JOIN pages p ON j.story=p.story AND j.page_id=p.id WHERE j.id=?",(job["id"],)).fetchone()
            require(current and current["state"]=="pending" and
                    digest(json.loads(current["regions"]))==job.get("sourceDigest",digest(regions)),"STALE")
            # Per-page summary is partial; chapter completion cannot be inferred from scrolling.
            sid = digest([job["story"], job["page_id"], job["revision"], "summary"])
            # Cloud event memory is not a permanent transcript of the page.
            # Facts below retain the cited JA evidence once. Unverified prose
            # stays review-only and never replaces source evidence in prompts.
            summary_source={"type":"dialogue","page_id":job["page_id"]}
            if raw.get("_summaryPolicy")=="selected-events-v1":
                summary_source.update(region_ids=sorted({item for proposal in proposals for item in proposal["evidence_ids"]}),
                                      policy="selected-events-v1")
            else:summary_source.update(region_ids=sorted(ids),utterances=utterances(ids))
            self.summary(job["story"], job["chapter"], job["chapter"], job["page"], value,
                         summary_source, summary_id=sid)
            for proposal in proposals:
                fid = digest([sid, proposal["text"]])
                self.fact(job["story"], "event", fid, proposal["text"], {"chapter": job["chapter"], "page": job["page"]},
                          {"type": "dialogue", "page_id": job["page_id"], "region_ids": proposal["evidence_ids"],"utterances":utterances(proposal["evidence_ids"])},
                          confirmed=False, locked=False, fact_id=fid)
            self.accept_terms(job["story"],{"chapter":job["chapter"],"page":job["page"]},job["page_id"],
                grounded_proposals(raw,regions,regions))
            db.execute("UPDATE jobs SET state='done' WHERE id=?", (job["id"],))

    def invalidate(self, story, at, page_id=None, keep_page=False):
        """Conservative dependency invalidation after a source/voice correction."""
        with self.transaction() as db:
            db.execute("DELETE FROM cache WHERE story=?", (story,))
            db.execute("UPDATE summaries SET valid=0 WHERE story=? AND chapter_end>=?", (story, at["chapter"]))
            db.execute("UPDATE facts SET valid=0 WHERE story=? AND locked=0 AND chapter>=?", (story, at["chapter"]))
            if page_id:
                if keep_page:
                    db.execute("UPDATE pages SET state='displayed' WHERE story=? AND id=?", (story, page_id))
                    # Auto names grounded in a corrected page need revalidation.
                    db.execute("UPDATE facts SET valid=0 WHERE story=? AND kind='glossary' AND confirmed=0 "
                               "AND json_extract(source,'$.page_id')=?",(story,page_id))
                else:
                    db.execute("DELETE FROM pages WHERE story=? AND id=?", (story, page_id))
                db.execute("DELETE FROM jobs WHERE story=? AND page_id=?", (story, page_id))
            db.execute("UPDATE stories SET version=version+1 WHERE id=?", (story,))

    def speaker(self, story, page_id, region_id, source_key=None, at=None):
        """Read one binding; production always supplies source key + cutoff.

        The three-argument form only reads preserved legacy data. It is not
        safe for inference because region IDs are presentation ordinals.
        """
        with self.lock:
            if at is not None:
                at=location(at)
                if source_key is not None:
                    identifier(source_key)
                    row=self.db.execute("SELECT speaker,listener FROM speaker_bindings "
                        "WHERE story=? AND page_id=? AND source_key=? AND "
                        "(chapter<? OR (chapter=? AND page<=?)) ORDER BY chapter DESC,page DESC LIMIT 1",
                        (story,page_id,source_key,at["chapter"],at["chapter"],at["page"])).fetchone()
                    if row:return {**dict(row),"speakerBindingReview":False}
                # Review history, not just the latest reused ordinal. A later
                # choice must not hide an earlier eligible re-confirmation
                # notice; neither record grants source/speaker authority.
                review_args=(story,page_id,region_id,at["chapter"],at["chapter"],at["page"])
                legacy=self.db.execute("SELECT 1 FROM speaker_legacy WHERE story=? AND page_id=? AND region_id=? "
                    "AND (chapter<? OR (chapter=? AND page<=?)) UNION ALL "
                    "SELECT 1 FROM speakers WHERE story=? AND page_id=? AND region_id=? "
                    "AND (chapter<? OR (chapter=? AND page<=?)) LIMIT 1",review_args*2).fetchone()
                return {"speaker":"unknown","listener":"unknown","speakerBindingReview":bool(legacy)}
            row = self.db.execute("SELECT speaker,listener FROM speakers WHERE story=? AND page_id=? AND region_id=?", (story, page_id, region_id)).fetchone()
            return dict(row) if row else {"speaker": "unknown", "listener": "unknown"}

    def bind_speakers(self, story, page_id, at, regions):
        """Resolve a complete current layout, never re-key it by read order.

        Source keys already bind captured image bytes + crop geometry through
        the stable scope-key namespace. OCR wording and policy versions are
        intentionally absent. Duplicate source boxes are ambiguous, not two
        independently confirmed speakers. No images or text are persisted.
        """
        require(isinstance(regions,list) and len(regions)<=64,"SPEAKER_SOURCE")
        ids=[identifier(r["id"]) for r in regions]
        require(len(set(ids))==len(ids),"SPEAKER_SOURCE")
        keys=[r.get("scope",{}).get("key") for r in regions]
        counts=Counter(k for k in keys if isinstance(k,str))
        with self.lock:
            return {region_id:self.speaker(story,page_id,region_id,
                identifier(key) if isinstance(key,str) and counts[key]==1 else None,at)
                for region_id,key in zip(ids,keys)}

    def set_speaker(self, story, page_id, region_id, speaker, listener, at, revision=None):
        for value in (story, page_id, region_id, speaker, listener):
            identifier(value)
        at = location(at)
        with self.transaction() as db:
            saved=db.execute("SELECT * FROM pages WHERE story=? AND id=? AND expires>?",
                (story,page_id,self.clock())).fetchone()
            if revision is not None:
                identifier(revision)
                require(saved is not None and saved["revision"]==revision and
                    (saved["chapter"],saved["page"])==(at["chapter"],at["page"]),"STALE",
                    "Trang đã đổi; không sửa người nói của kết quả cũ.")
            regions=json.loads(saved["regions"]) if saved is not None else []
            target=next((r for r in regions if r["id"]==region_id),None)
            key=target.get("scope",{}).get("key") if target else None
            bound=(isinstance(key,str) and sum(r.get("scope",{}).get("key")==key for r in regions)==1 and
                (saved["chapter"],saved["page"])==(at["chapter"],at["page"]))
            if revision is not None:
                require(bound,"SPEAKER_SOURCE","Dịch lại trang để xác nhận người nói trên vùng nguồn hiện tại.")
            if bound:
                identifier(key)
                db.execute("INSERT OR REPLACE INTO speaker_bindings VALUES(?,?,?,?,?,?,?,?)",
                    (story,page_id,key,region_id,speaker,listener,at["chapter"],at["page"]))
            # Reusing an ordinal for a newly confirmed source must not erase
            # the old unanchored choice. History is review data, never authority
            # to infer a source/speaker. All records cascade with story deletion.
            db.execute("INSERT OR IGNORE INTO speaker_legacy SELECT * FROM speakers "
                "WHERE story=? AND page_id=? AND region_id=?",(story,page_id,region_id))
            if not bound:
                db.execute("INSERT OR IGNORE INTO speaker_legacy VALUES(?,?,?,?,?,?,?)",
                    (story,page_id,region_id,speaker,listener,at["chapter"],at["page"]))
            db.execute("INSERT OR REPLACE INTO speakers VALUES(?,?,?,?,?,?,?)", (story, page_id, region_id, speaker, listener, at["chapter"], at["page"]))
            # Speaker identity and the dependent-context revision are one
            # reader edit. No task may observe a new pair at the old version.
            self.invalidate(story, at, page_id, keep_page=True)

    def export(self, story):
        with self.lock:
            meta = self.db.execute("SELECT * FROM stories WHERE id=?", (story,)).fetchone()
            require(meta is not None)
            return {"schema": 1, "story": dict(meta), "progress":self._export_progress(story), "facts": [dict(r) for r in self.db.execute("SELECT * FROM facts WHERE story=? AND valid=1 ORDER BY chapter,page,rowid", (story,))],
                    "summaries": [dict(r) for r in self.db.execute("SELECT * FROM summaries WHERE story=? AND valid=1 ORDER BY chapter_end,page_end,rowid", (story,))]}

    def _export_progress(self, story):
        row=self.db.execute("SELECT last_chapter,last_page,furthest_chapter FROM progress WHERE story=?",(story,)).fetchone()
        return dict(row) if row else None

    def export_page(self,story,cursor=None,at=None,byte_budget=128*1024):
        """Bounded coherent transfer; never assemble the full history in a frame.

        Offset cursors are valid only for this exact story/version/cutoff. A
        concurrent correction aborts transfer instead of mixing two histories.
        This is admin/export I/O, not the short interactive retrieval path.
        """
        identifier(story);at=location(at) if at is not None else None
        require(type(byte_budget) is int and 1024<=byte_budget<=128*1024)
        with self.lock:
            meta=self.db.execute("SELECT * FROM stories WHERE id=?",(story,)).fetchone()
            require(meta is not None,"STORY")
            version=meta["version"];section=0;offset=0
            progress=self._export_progress(story);snapshot_id=digest([dict(meta),progress])
            if cursor is not None:
                require(isinstance(cursor,dict) and cursor.get("story")==story and cursor.get("at")==at,"CONTEXT_CURSOR")
                require(cursor.get("version")==version,"STALE_CONTEXT","Hồ sơ vừa đổi; tải lại để không ghép dữ liệu cũ và mới.")
                require(cursor.get("snapshotId")==snapshot_id,"STALE_CONTEXT","Tiến độ đọc vừa đổi; tải lại hồ sơ đầy đủ.")
                section,offset=cursor.get("section"),cursor.get("offset")
                require(type(section) is int and section in (0,1) and type(offset) is int and 0<=offset<=1000000,"CONTEXT_CURSOR")
            result={"schema":1,"story":dict(meta),"progress":progress,"snapshotVersion":version,"snapshotId":snapshot_id,
                    "facts":[],"summaries":[],"next":None}
            graph = self._summary_graph(story) if at is not None else None
            used=len(encode(result).encode())+512  # Cursor + status/framing headroom.
            require(used<byte_budget,"CONTEXT_SIZE")
            for current in range(section,2):
                name,time_col,page_col=("facts","chapter","page") if current==0 else ("summaries","chapter_end","page_end")
                count=offset if current==section else 0
                clause="";args=[story]
                if at is not None:
                    clause=f" AND ({time_col}<? OR ({time_col}=? AND {page_col}<=?))"
                    args.extend([at["chapter"],at["chapter"],at["page"]])
                while True:
                    rows=self.db.execute(f"SELECT * FROM {name} WHERE story=? AND valid=1"+clause+
                        f" ORDER BY {time_col},{page_col},rowid LIMIT 128 OFFSET ?",[*args,count]).fetchall()
                    for row in rows:
                        record=dict(row);size=len(encode(record).encode())+1
                        if current == 1 and graph is not None:
                            try: graph.validate(record)
                            except AppError:
                                count += 1
                                continue
                        if used+size>byte_budget:
                            require(bool(result["facts"] or result["summaries"]),"CONTEXT_RECORD_SIZE",
                                    "Một mục context quá lớn để chuyển an toàn. Không cắt hoặc xóa dữ liệu gốc.")
                            result["next"]={"story":story,"version":version,"snapshotId":snapshot_id,"at":at,"section":current,"offset":count}
                            return result
                        result[name].append(record);used+=size;count+=1
                    if len(rows)<128:break
            return result

    def import_pack(self, pack):
        checked=validate_pack(pack);meta=checked["story"];sid=meta["id"]
        # Private import is additive, atomic and idempotent. It is not permission
        # to replace an existing reader lock, title, genre or resume position.
        with self.transaction() as db:
            protected={}
            for row in db.execute("SELECT * FROM facts WHERE story=? AND valid=1 AND confirmed=1 AND locked=1 ORDER BY chapter DESC,page DESC,rowid DESC",(sid,)):
                protected.setdefault((row["kind"],row["key"]),[]).append(dict(row))
            self.ensure_story(sid,meta["title"])
            old=dict(db.execute("SELECT * FROM stories WHERE id=?",(sid,)).fetchone())
            merged_aliases=list(dict.fromkeys([*json.loads(old["aliases"]),*meta.get("aliases",[])]))
            require(len(merged_aliases)<=30,"CONTEXT_PACK")
            old_metadata=json.loads(old["metadata"]);new_metadata=meta.get("metadata",{})
            require(not (old_metadata and new_metadata) or old_metadata.get("qid")==new_metadata.get("qid"),
                    "CONTEXT_CONFLICT","Hai hồ sơ có định danh truyện khác nhau. Không tự gộp bộ nhớ.")
            genre=old["genre"] or meta.get("genre","");aliases=encode(merged_aliases);metadata=encode(old_metadata or new_metadata)
            if (genre,aliases,metadata)!=(old["genre"],old["aliases"],old["metadata"]):
                db.execute("UPDATE stories SET genre=?,aliases=?,metadata=?,version=version+1 WHERE id=?",(genre,aliases,metadata,sid))

            def signature(row, fields):
                def canonical(key):
                    if key in ("confirmed","locked","complete"):return bool(row[key])
                    if key in ("chapter","chapter_start","chapter_end"):return float(row[key])
                    return row[key]
                return digest([*[canonical(key) for key in fields],root_source(row["source"])])

            def record_id(table,row):
                rid=row.get("id") or digest([sid,table,row])
                owner=db.execute(f"SELECT story FROM {table} WHERE id=?",(rid,)).fetchone()
                return digest(["private-context",sid,table,rid]) if owner and owner[0]!=sid else rid

            def unused_id(table, record):
                rid = record_id(table, record)
                require(db.execute(f"SELECT 1 FROM {table} WHERE id=?", (rid,)).fetchone() is None,
                        "CONTEXT_CONFLICT", "Một ID trong hồ sơ đã có nội dung khác. Dữ liệu hiện tại được giữ nguyên.")
                return rid

            fields = ("kind", "key", "value", "chapter", "page", "confirmed", "locked")
            existing = {signature(dict(r), fields) for r in db.execute("SELECT * FROM facts WHERE story=? AND valid=1", (sid,))}
            for record in checked["facts"]:
                sig = signature(record, fields)
                if sig in existing: continue
                rid = unused_id("facts", record)
                lock = next((r for r in protected.get((record["kind"], record["key"]), []) if
                             (record["chapter"], record["page"]) >= (r["chapter"], r["page"])), None)
                if lock:
                    require(record["value"] == lock["value"] and record["confirmed"] and record["locked"],
                            "CONTEXT_CONFLICT", "Hồ sơ nhập xung đột với ghi chú/xưng hô bạn đã khóa. Chỉnh trong Thư viện nếu muốn đổi.")
                self.fact(sid, record["kind"], record["key"], record["value"],
                          {"chapter": record["chapter"], "page": record["page"]}, record["source"],
                          record["confirmed"], record["locked"], fact_id=rid)
                existing.add(sig)

            fields = ("chapter_start", "chapter_end", "page_end", "kind", "text", "complete")
            existing = {signature(dict(r), fields): r["id"] for r in db.execute("SELECT * FROM summaries WHERE story=? AND valid=1", (sid,))}
            incoming = {r["id"]: r for r in checked["summaries"] if "id" in r}
            resolved, visiting = {}, set()

            def put_summary(record, depth=0):
                key = record.get("id") or digest([sid, "summaries", record])
                require(depth < 64 and key not in visiting, "EVIDENCE", "Liên kết tóm tắt bị vòng lặp hoặc lồng quá sâu.")
                if key in resolved: return resolved[key]
                visiting.add(key)
                try:
                    value = record
                    if record["kind"] == "group":
                        refs = [put_summary(incoming[ref], depth + 1) if ref in incoming else ref for ref in group_refs(record)]
                        value = {**record, "source": {"type": "context-pack", "original":
                                 {**root_source(record["source"]), "summary_ids": refs}}}
                    sig = signature(value, fields)
                    rid = existing.get(sig)
                    if rid is not None and value["kind"] == "group":
                        self._summary_graph(sid).validate({**value, "id": rid})
                    if rid is None:
                        rid = unused_id("summaries", value)
                        self.summary(sid, value["chapter_start"], value["chapter_end"], value["page_end"], value["text"],
                                     value["source"], value["complete"], value["kind"], summary_id=rid)
                        existing[sig] = rid
                    resolved[key] = rid
                    return rid
                finally:
                    visiting.remove(key)

            for record in checked["summaries"]: put_summary(record)
            progress=checked["progress"]
            if progress:
                current=db.execute("SELECT * FROM progress WHERE story=?",(sid,)).fetchone()
                if current is None:
                    db.execute("INSERT INTO progress VALUES(?,?,?,?,?)",(sid,progress["last_chapter"],progress["last_page"],progress["furthest_chapter"],self.clock()))
                elif progress["furthest_chapter"]>current["furthest_chapter"]:
                    db.execute("UPDATE progress SET furthest_chapter=? WHERE story=?",(progress["furthest_chapter"],sid))
        return sid

    def delete_story(self, story):
        with self.transaction() as db:
            db.execute("DELETE FROM stories WHERE id=?", (story,))
        with self.lock:
            self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def prune(self):
        with self.transaction() as db:
            now = self.clock()
            db.execute("DELETE FROM cache WHERE expires<=?", (now,))
            db.execute("UPDATE jobs SET state='gap' WHERE expires<=? AND state IN ('pending','failed')", (now,))
            db.execute("DELETE FROM pages WHERE expires<=?", (now,))
            total = db.execute("SELECT COALESCE(SUM(bytes),0) FROM cache").fetchone()[0]
            for row in db.execute("SELECT key,bytes FROM cache ORDER BY accessed").fetchall():
                if total <= CACHE_LIMIT:
                    break
                db.execute("DELETE FROM cache WHERE key=?", (row[0],))
                total -= row[1]
            # Source page cache shares the same 100 MB ceiling with translation cache.
            total += db.execute("SELECT COALESCE(SUM(length(CAST(regions AS BLOB))),0) FROM pages").fetchone()[0]
            for row in db.execute("SELECT story,id,length(CAST(regions AS BLOB)) FROM pages ORDER BY expires").fetchall():
                if total <= CACHE_LIMIT:
                    break
                db.execute("UPDATE jobs SET state='gap' WHERE story=? AND page_id=? AND state='pending'", (row[0], row[1]))
                db.execute("DELETE FROM pages WHERE story=? AND id=?", (row[0], row[1]))
                total -= row[2]

    def confirm_metadata(self,story,metadata):
        require(isinstance(metadata,dict) and len(encode(metadata))<8000)
        require(bool(re.fullmatch(r"Q\d{1,12}",metadata.get("qid",""))))
        aliases=metadata.get("aliases",[])
        require(isinstance(aliases,list) and len(aliases)<=30 and all(isinstance(v,str) and len(v)<300 for v in aliases))
        with self.transaction() as db:
            db.execute("UPDATE stories SET aliases=?,metadata=?,version=version+1 WHERE id=?",
                       (encode(aliases),encode(metadata),story))

    def markdown(self,story,at):
        snapshot=self.context(story,at)
        return context_markdown(snapshot["data"]),snapshot


def context_markdown(data):
    """Readable compact model input; database IDs/evidence remain in SQLite."""
    story=data.get("story",{})
    lines=["# Story context",f"Title: {story.get('title','')}",f"Genre/style: {story.get('genre','')}",
           "Only knowledge at the current reading cutoff is included."]
    for heading,key in (("Characters and directed address","characters"),("Glossary","glossary"),("Story style","styles"),
                        ("Known events (unconfirmed entries remain uncertain)","events")):
        values=data.get(key,[])
        if values:
            lines.append("## "+heading)
            for value in values:
                if value.get("kind")=="dialogue-evidence":
                    lines.append(f"- [Original utterances only; ch {value['chapter']}, page {value['page']}; not proof of completed actions]")
                    for item in value["utterances"]:
                        lines.append("  "+encode(item))
                    continue
                mark="confirmed" if value.get("confirmed",value.get("complete",False)) else "uncertain/partial"
                content=value.get("value",value.get("text",""))
                lines.append(f"- [{mark}; ch {value.get('chapter',value.get('chapter_end',0))}] {value.get('key','')}: {content}")
    recent=data.get("recent_dialogue",[])
    if recent:
        lines.append("## Recent dialogue")
        for item in recent:
            lines.append(f"- {item.get('speaker','unknown')}: {item.get('ja','')} => {item.get('vi','')}")
    return "\n".join(lines)
