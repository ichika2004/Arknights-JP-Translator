"""Roguelike collectible name lookup with topic-aware ambiguity protection."""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def normalize(text: Any) -> str:
    normalized = unicodedata.normalize('NFKC', str(text or '')).casefold()
    return re.sub(r'[\s「」『』“”"\'・･。、，,.:：!！?？（）()\[\]【】]', '', normalized)


class RogueMatcher:
    def __init__(self, database_path='data/generated/rogue_collectibles.json'):
        with Path(database_path).open(encoding='utf-8') as f:
            database = json.load(f)
        rows = database.values() if isinstance(database, dict) else database
        self.records = []
        for row in rows:
            name = normalize(row.get('name_jp'))
            if name:
                self.records.append((name, row))
        self.topics = sorted({record['topic_id'] for _, record in self.records})

    @staticmethod
    def _format(record: dict, score: float) -> dict:
        return {
            'score': round(score, 4),
            'topic_id': record['topic_id'],
            'item_id': record['item_id'],
            'name_jp': record.get('name_jp', ''),
            'name_tw': record.get('name_tw', ''),
            'effect_tw': (record.get('usage_tw') or record.get('description_tw') or record.get('short_usage_tw') or ''),
        }

    def _rank(self, text, topic_id=None):
        query = normalize(text)
        if not query:
            return []
        if topic_id is not None and topic_id not in self.topics:
            return []
        ranked = []
        for name, record in self.records:
            if topic_id is not None and record['topic_id'] != topic_id:
                continue
            score = 1.0 if query == name else SequenceMatcher(None, query, name).ratio()
            ranked.append(self._format(record, score))
        ranked.sort(key=lambda x: (-x['score'], x['topic_id'], x['item_id']))
        return ranked

    def search(self, text, topic_id=None, limit=5):
        return self._rank(text, topic_id)[:max(0, int(limit))]

    def resolve(self, text, topic_id=None, threshold=0.85, min_margin=0.04):
        """Return matched / ambiguous / not_found with no unsafe auto-pick.

        If multiple top-scoring records share the same translation and effect,
        those records may be treated as equivalent. A separate close second
        spelling produces ambiguous, including within a selected topic.
        """
        results = self._rank(text, topic_id)
        if not results or results[0]['score'] < threshold:
            return {'status': 'not_found', 'result': None, 'candidates': results[:5]}

        best_score = results[0]['score']
        # All equal-best records, not an arbitrary limit of 20.
        tied = [r for r in results if abs(r['score'] - best_score) < 0.0000001]
        rest = [r for r in results if abs(r['score'] - best_score) >= 0.0000001]
        if best_score < 1.0 and rest and best_score - rest[0]['score'] < min_margin:
            return {'status': 'ambiguous', 'reason': 'close_match', 'result': None,
                    'candidates': results[:10]}

        translations = {(r['name_tw'], r['effect_tw']) for r in tied}
        if len(translations) > 1:
            return {'status': 'ambiguous', 'reason': 'different_effects',
                    'result': None, 'candidates': tied}

        output = {'status': 'matched', 'result': tied[0],
                  'shared_across_topics': len({r['topic_id'] for r in tied}) > 1,
                  'matched_topics': sorted({r['topic_id'] for r in tied})}
        return output
