"""Neighbour-aware request boundaries, never semantic grouping or source edits.

Only existing, pixel-validated crop partition relations influence scheduling.
Do not infer speaker/utterance/erasure ownership from them. Keep the original
request count and first-request ceiling; later requests are bounded to six
source IDs. This supplies adjacent source context without another API call.
"""
from functools import lru_cache

SCHEDULE_VERSION = "translation-schedule-v1-seam-neighbours"
MAX_BATCH = 6


def schedule_regions(regions, first=4, partition_evidence=()):
    if type(first) is not int or first not in (2, 4) or not isinstance(regions, list) or len(regions) > 64:
        raise ValueError("Bounded source scheduling required")
    baseline = [regions[:first], *[regions[i:i+4] for i in range(first, len(regions), 4)]]
    if not regions or not isinstance(partition_evidence, (list, tuple)) or len(partition_evidence) > 64:
        return baseline
    ids = [row.get("id") if isinstance(row, dict) else None for row in regions]
    if any(not isinstance(ident, str) or not ident for ident in ids) or len(set(ids)) != len(ids):
        return baseline
    positions = {ident: index for index, ident in enumerate(ids)}
    forbidden = set()
    for evidence in partition_evidence:
        if not isinstance(evidence, dict):
            continue
        members = evidence.get("source_ids")
        if (not isinstance(members, list) or len(members) != 2 or len({ident for ident in members if isinstance(ident, str)}) != 2
                or any(not isinstance(ident, str) or ident not in positions for ident in members)
                or evidence.get("source_ink_coverage_preserved") is not True
                or evidence.get("erasure_permitted") is not False
                or evidence.get("orientation") not in ("vertical", "horizontal")):
            continue
        lower, upper = sorted(positions[ident] for ident in members)
        forbidden.update(range(lower+1, upper+1))
    if not forbidden or not any(sum(map(len, baseline[:i])) in forbidden for i in range(1, len(baseline))):
        return baseline
    requests = len(baseline)
    targets = [sum(map(len, baseline[:i+1])) for i in range(requests)]

    @lru_cache(maxsize=None)
    def solve(start, depth):
        if depth == requests:
            return (0, 0, 0, ()) if start == len(regions) else None
        remaining = requests-depth-1
        cap = first if depth == 0 else MAX_BATCH
        options = []
        for end in range(start+1, min(len(regions), start+cap)+1):
            tail_size = len(regions)-end
            if not remaining <= tail_size <= remaining*MAX_BATCH:
                continue
            tail = solve(end, depth+1)
            if tail is None:
                continue
            options.append((int(end in forbidden)+tail[0], abs(end-targets[depth])+tail[1],
                            max(end-start, tail[2]), (-end, *tail[3])))
        return min(options) if options else None

    best = solve(0, 0)
    if best is None:
        return baseline
    # A new arrangement must actually reduce cuts, not merely reshuffle IDs.
    old_cuts = sum(boundary in forbidden for boundary in targets[:-1])
    if best[0] >= old_cuts:
        return baseline
    result = []
    start = 0
    for negative_end in best[3]:
        end = -negative_end
        result.append(regions[start:end])
        start = end
    return result
