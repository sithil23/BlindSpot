import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def normalize_barcode(code):
    code = str(code).strip()
    if not (6 <= len(code) <= 18 and code.isascii() and code.isdigit()):
        raise ValueError('Enter a numeric food barcode (6–18 digits)')
    return code


def extract_food(code, payload):
    if not isinstance(payload, dict) or payload.get('status') != 1:
        return None
    product = payload.get('product') or {}
    nutrients = product.get('nutriments') or {}
    label = (product.get('product_name') or product.get('product_name_en') or '').strip()
    if not label:
        return None
    values = {}
    for src, dest in [('energy-kcal_100g','energy_kcal'),('proteins_100g','protein_g'),
                      ('carbohydrates_100g','carbs_g'),('fat_100g','fat_g')]:
        try:
            raw = nutrients[src]
            n = float(raw)
            if not math.isfinite(n) or n < 0 or n > 10000:
                return None
        except (ValueError, TypeError, KeyError):
            return None
        values[dest] = n
    return {'barcode': code, 'label': label[:120], 'serving_basis':'100 g / 100 ml', **values}


def lookup_food(barcode, opener=None):
    code = normalize_barcode(barcode)
    url = f'https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=code,product_name,product_name_en,nutriments'
    req = Request(url, headers={'User-Agent': 'BLINDSPOT-Demo/0.27 (https://sbmc.space)', 'Accept':'application/json'})
    try:
        response = (opener or urlopen)(req, timeout=12)
        with response as stream:
            payload = json.load(stream)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, UnicodeError) as exc:
        raise LookupError('Food database unavailable. Try again or add the food label manually.') from exc
    return extract_food(code, payload)
