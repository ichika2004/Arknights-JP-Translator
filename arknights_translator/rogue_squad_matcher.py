"""Conservative squad-name resolver. No version guessed from name alone."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def normalize(value):
    value = unicodedata.normalize('NFKC', str(value or '')).lower()
    return re.sub(r'[\s「」『』“”"\'・]', '', value)


class SquadMatcher:
    def __init__(self, path='data/generated/rogue_starting_squads.json'):
        with Path(path).open(encoding='utf-8') as f:
            rows = json.load(f)
        self.rows = list(rows.values())

    def resolve(self, text, topic_id=None, threshold=0.87, gap=0.08):
        query = normalize(text)
        if len(query) < 3:
            return {'status': 'not_found', 'candidates': []}
        scored = []
        for row in self.rows:
            if topic_id is not None and row['topic_id'] != topic_id:
                continue
            name = normalize(row.get('name_jp'))
            if not name:
                continue
            score = SequenceMatcher(None, query, name).ratio()
            scored.append((score, row))
        if not scored:
            return {'status': 'not_found', 'candidates': []}
        best_score = max(x[0] for x in scored)
        if best_score < threshold:
            return {'status': 'not_found', 'candidates': []}
        # Check competing *names*, not repeated versions of the same name.
        other_names = [score for score, row in scored if normalize(row['name_jp']) != normalize(max(scored, key=lambda x: x[0])[1]['name_jp'])]
        if other_names and best_score - max(other_names) < gap:
            return {'status': 'uncertain_name', 'candidates': []}
        winners = [dict(row, similarity=round(score, 4)) for score, row in scored if abs(score-best_score) < 1e-8]
        effects = {(row.get('name_tw'), row.get('effect_tw')) for row in winners}
        if len(effects) > 1:
            return {'status': 'ambiguous_variant', 'name_tw': winners[0].get('name_tw'), 'candidates': winners}
        return {'status': 'matched', 'result': winners[0], 'same_effect_records': len(winners)}
