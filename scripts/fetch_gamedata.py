"""Download JP and candidate TW skill data from public GitHub repositories."""
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'raw'
SOURCES = {
    'jp': 'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/master/jp/gamedata/excel/',
    'tw': 'https://raw.githubusercontent.com/arkntools/arknights-data-tw-for-maa/main/',
}
TABLES = ('character_table.json', 'skill_table.json', 'char_patch_table.json')


def main():
    manifest = {'downloaded_at_utc': datetime.now(timezone.utc).isoformat(), 'files': {}}
    for region, base_url in SOURCES.items():
        folder = OUT / region
        folder.mkdir(parents=True, exist_ok=True)
        for filename in TABLES:
            url = base_url + filename
            print('Downloading:', url, flush=True)
            request = urllib.request.Request(url, headers={'User-Agent': 'Arknights-JP-Translator/0.1'})
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    data = response.read()
                json.loads(data.decode('utf-8-sig'))
            except Exception as exc:
                raise RuntimeError(f'Cannot download {url}: {exc}') from exc
            (folder / filename).write_bytes(data)
            manifest['files'][f'{region}/{filename}'] = {
                'url': url, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)
            }
            print('Saved', len(data), 'bytes')
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Done:', OUT)


if __name__ == '__main__':
    main()
