"""Discovery run 30: why are most Lidl leaflet prices 'unverified'? (debug samples, CZ)"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import pytesseract  # noqa: E402
from PIL import Image  # noqa: E402

import fetch_prices as F  # noqa: E402
import kaufland_ocr as K  # noqa: E402
from items_def import ITEMS  # noqa: E402

g = lambda url, raw=False: F.get(url, as_json=not raw)  # noqa: E731
deps = dict(pytesseract=pytesseract, Image=Image, match_items=F.match_items, parse_qty=F.parse_qty, convert=F.convert, norm=F.norm, ITEM=F.ITEM, offer=F.offer)
fl = K.list_flyers(g, "lidl/cs-CZ", ("Akční letáky",), F.TODAY)
fl = [x for x in fl if (x[1].get("offerStartDate") or "") <= F.TODAY][:2]
offs, dbg = K.scan_flyers(g, fl, "lidl", "brno", "CZK", [it["cz"] for it in ITEMS], deps, max_pages=14, delay=0.3, label="Lidl")
print("verified:", [(o["item"], o["unit_price"], o["price"], o["pack"], o["name"][:40]) for o in offs])
print("status counts:", Counter(d[1] for d in dbg))
for st, n in (("unverified", 25), ("excluded", 8), ("ambiguous", 5), ("nomatch", 25)):
    print("===", st)
    for d in [d for d in dbg if d[1] == st][:n]:
        print("  ", str(d)[:260])
