"""Validate local summary dependencies without trusting a group's claimed cutoff."""
from .context_pack import root_source
from .errors import require
from .validation import identifier


def group_refs(row):
    refs = root_source(row["source"]).get("summary_ids")
    require(isinstance(refs, list) and 0 < len(refs) <= 1000, "EVIDENCE")
    for ref in refs:
        identifier(ref)
    require(len(set(refs)) == len(refs), "EVIDENCE")
    return refs


class SummaryGraph:
    """The lookup must return only valid rows belonging to the same story.

    Check each edge's temporal range even when a child has already been checked.
    Bound recursion and work so a malformed private import cannot exhaust the
    host. The graph lives for one database snapshot/transaction, not globally.
    """
    def __init__(self, lookup):
        self.lookup = lookup
        self.checked = set()
        self.visiting = set()
        self.visits = 0

    def prompt_rows(self, row):
        """Follow AI rollups to original evidence, never to invented root quotes.

        Complete means source coverage, NOT semantic verification. An explicit
        reader-supplied group is usable as a reader assertion; dialogue groups
        must use their validated child evidence. Validation bounds traversal.
        """
        self.validate(row)
        stack, seen = [row], set()
        while stack:
            current = stack.pop()
            if current["id"] in seen:
                continue
            seen.add(current["id"])
            if current["kind"] == "group" and root_source(current["source"])["type"] == "dialogue":
                for ref in reversed(group_refs(current)):
                    child = self.lookup(ref)
                    require(child is not None, "EVIDENCE")
                    stack.append(child)
            else:
                yield current

    def validate(self, row, depth=0):
        if row["kind"] != "group":
            return
        rid = row["id"]
        require(depth < 64 and rid not in self.visiting, "EVIDENCE",
                "Liên kết tóm tắt bị vòng lặp hoặc lồng quá sâu.")
        if rid in self.checked:
            return
        self.visits += 1
        require(self.visits <= 10000 and row["complete"] == 1, "EVIDENCE")
        self.visiting.add(rid)
        try:
            for ref in group_refs(row):
                child = self.lookup(ref)
                require(child is not None and child["complete"] == 1, "EVIDENCE",
                        "Nhóm tóm tắt thiếu nguồn đầy đủ; không tự coi là lịch sử đã đọc.")
                require(row["chapter_start"] <= child["chapter_start"] <= child["chapter_end"] <= row["chapter_end"]
                        and (child["chapter_end"] < row["chapter_end"] or child["page_end"] <= row["page_end"]),
                        "EVIDENCE", "Nguồn tóm tắt vượt mốc chapter/trang của nhóm; có nguy cơ spoiler.")
                self.validate(child, depth + 1)
            self.checked.add(rid)
        finally:
            self.visiting.remove(rid)
