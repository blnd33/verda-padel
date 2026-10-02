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


# 12-hour clock everywhere a time of day is shown. Durations (elapsed timers)
# are not clock times and stay as H:MM:SS.
MERIDIEM = {'en': ('AM', 'PM'), 'ar': ('ص', 'م')}


def meridiem(hour, lang='en'):
    am, pm = MERIDIEM.get(lang, MERIDIEM['en'])
    return am if int(hour) % 24 < 12 else pm


def hour12(hour):
    return int(hour) % 12 or 12


def clock(hour, minute=0, lang='en', short=False):
    """8 PM / 8:30 PM (short) or 8:00 PM; Arabic uses ص / م."""
    minutes = '' if short and not minute else f':{int(minute):02d}'
    return f'{hour12(hour)}{minutes} {meridiem(hour, lang)}'


def clock_of(value, lang='en', date=False):
    """A localised datetime as a 12-hour clock, optionally prefixed with its date."""
    text = clock(value.hour, value.minute, lang)
    return f'{value:%Y-%m-%d} {text}' if date else text
