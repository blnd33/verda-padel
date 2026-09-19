"""English source messages with Arabic interface translations."""
from pathlib import Path

TRANSLATIONS = {}
for row in (Path(__file__).parent/'locales.tsv').read_text(encoding='utf-8').splitlines():
    if row.strip() and not row.startswith('#'):
        key, ar = row.split('|',1)
        TRANSLATIONS[key] = {'ar':ar}

def translate(key,lang='en'):
    entry=TRANSLATIONS.get(key) or TRANSLATIONS.get(str(key).capitalize()) or TRANSLATIONS.get(str(key).replace('_',' ').capitalize()) or {}
    return entry.get(lang,key)
