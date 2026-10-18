from pathlib import Path
from arknights_translator.rogue_unified_index import build

if __name__ == '__main__':
    paths, report = build(Path.cwd())
    for path in paths.values():
        print('Saved', path)
    print('Total records:',report['total_records'])
    print('Categories:',report['categories'])
    print('Term hits:',report['term_hits_total'])
    print('Missing TW names:',report['missing_tw_name_by_group'])
