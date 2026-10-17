"""Conservative multilingual character-name matching (many IDs can share a name)."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher


def normalize(value):
    s = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s・·「」『』【】\[\]()（）'’`\-‐‑–—]", "", s)


def build_aliases(characters, name_db=None):
    """Returns normalized alias -> sorted list of character IDs."""
    name_db = name_db or {}
    aliases = defaultdict(set)
    for cid, char in characters.items():
        extra = name_db.get(cid) or {}
        for field in ("name_jp", "name_en", "name_zh_tw", "name_zh_tw_candidate"):
            for obj in (char, extra):
                alias = normalize(obj.get(field))
                if len(alias) >= 2:
                    aliases[alias].add(cid)
        alias = normalize(cid)
        if alias:
            aliases[alias].add(cid)
    return {k: sorted(v) for k, v in aliases.items()}


def rank_names(lines, characters, name_db=None, min_score=0.84, min_gap=0.07, topk=5):
    """Return {character_id, status, score, candidates, matched_alias}.

    status: matched, ambiguous, weak, empty. Similarity scores aren't probabilities.
    If one alias maps to multiple IDs, return ambiguous, never select arbitrarily.
    """
    aliases = build_aliases(characters, name_db)
    observed = [normalize(x) for x in lines if normalize(x)]
    if not observed:
        return dict(character_id=None, status="empty", score=0.0, candidates=[], matched_alias=None)
    by_id = {}
    best_alias = {}
    for alias, ids in aliases.items():
        for obs in observed:
            if obs == alias:
                score = 1.0
            elif len(obs) >= 2 and alias in obs and len(obs) <= len(alias) + 5:
                score = 0.92
            elif len(obs) >= 2 and len(obs) <= 64:
                score = SequenceMatcher(None, alias, obs).ratio()
            else:
                continue
            for cid in ids:
                if score > by_id.get(cid, -1):
                    by_id[cid] = score
                    best_alias[cid] = alias
    ranked = sorted(by_id.items(), key=lambda p: (-p[1], p[0]))
    candidates = [dict(character_id=cid, score=round(score, 4), matched_alias=best_alias[cid]) for cid, score in ranked[:topk]]
    if not ranked or ranked[0][1] < min_score:
        status = "weak"
        chosen = None
    elif len(ranked) > 1 and ranked[0][1] - ranked[1][1] < min_gap:
        status = "ambiguous"
        chosen = None
    else:
        status = "matched"
        chosen = ranked[0][0]
    return dict(character_id=chosen, status=status, score=round(ranked[0][1], 4) if ranked else 0.0,
                candidates=candidates, matched_alias=best_alias.get(ranked[0][0]) if ranked else None)


def match_names(lines, characters, min_score=0.83, min_gap=0.07, name_db=None):
    """Backward-compatible tuple API used by Phase 4 GUI."""
    result = rank_names(lines, characters, name_db, min_score=min_score, min_gap=min_gap, topk=3)
    top = [(x["character_id"], x["score"]) for x in result["candidates"]]
    return result["character_id"], result["score"], top
