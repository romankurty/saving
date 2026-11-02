"""Discovery run 21: accuracy test of the stricter Kaufland leaflet reader (store 4310)."""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import pytesseract  # noqa: E402
from PIL import Image  # noqa: E402

import fetch_prices as F  # noqa: E402
import kaufland_ocr as K  # noqa: E402
from items_def import ITEMS  # noqa: E402


def sget(url, raw=False):
    return F.get(url, as_json=not raw)


deps = dict(pytesseract=pytesseract, Image=Image, match_items=F.match_items, parse_qty=F.parse_qty, convert=F.convert,
            norm=F.norm, ITEM=F.ITEM, offer=F.offer)
terms = [it["cz"] for it in ITEMS]
offers, leaflets, dbg = K.kaufland_offers(sget, 4310, F.TODAY, terms, deps, max_pages=30, delay=0.5)
print("leaflets:", leaflets)
print("debug status counts:", Counter(d[1] for d in dbg))
print("=== VERIFIED OFFERS ===")
for o in offers:
    print(f"  {o['item']:<14} {o['unit_price']:>8} Kč/{F.ITEM[o['item']]['unit']}  price {o['price']} pack {o['pack']}  card={o['card']}  | {o['name'][:70]}")
for st, n in (("excluded", 12), ("ambiguous", 8), ("unverified", 25)):
    print(f"=== sample {st} ===")
    for d in [d for d in dbg if d[1] == st][:n]:
        print("  ", str(d)[:300])
