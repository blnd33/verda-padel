"""Two currencies, never converted.

Every stored amount is an integer in the currency's smallest unit: whole dinar
for IQD, cents for USD. Totals are always kept per currency; nothing in the
system adds dollars to dinar.
"""
import re

CURRENCIES = ('IQD', 'USD')
DECIMALS = {'IQD': 0, 'USD': 2}
LABELS = {'IQD': 'Dinar (IQD)', 'USD': 'Dollar ($)'}


def check(currency):
    if currency not in CURRENCIES:
        from app.services.core import RuleError
        raise RuleError('Choose dinar or dollar.')
    return currency


def parse(value, currency, minimum=0, maximum=10**12):
    """Form text to minor units: '45.5' dollars -> 4550, '3000' dinar -> 3000."""
    from app.services.core import RuleError
    check(currency)
    text = str(value if value is not None else '').strip().replace(',', '')
    places = DECIMALS[currency]
    pattern = r'\d+' if not places else r'\d+(\.\d{1,%d})?|\.\d{1,%d}' % (places, places)
    if not re.fullmatch(pattern, text):
        raise RuleError('Enter a valid amount.' if places else 'Enter a whole dinar amount.')
    whole, _, fraction = text.partition('.')
    amount = int(whole or 0) * 10**places + int((fraction + '0' * places)[:places] or 0)
    if not minimum <= amount <= maximum:
        raise RuleError('The number is outside the allowed range.')
    return amount


def plain(amount, currency):
    """The number alone, grouped: 3,000 or 45.00."""
    places = DECIMALS.get(currency, 0)
    value = (amount or 0) / 10**places if places else int(amount or 0)
    return f'{value:,.{places}f}'


def fmt(amount, currency):
    """3,000 IQD or $45.00 (negative: −$45.00)."""
    amount = amount or 0
    if currency == 'USD':
        return ('−' if amount < 0 else '') + '$' + plain(abs(amount), 'USD')
    return plain(amount, 'IQD') + ' IQD'


def field_value(amount, currency):
    """Value for an <input>: no grouping, dollars with cents."""
    if amount is None:
        return ''
    places = DECIMALS.get(currency, 0)
    return f'{amount / 10**places:.{places}f}' if places else str(int(amount))


def zero():
    return {c: 0 for c in CURRENCIES}
