"""Discovery run 23: does 2x upscaling read more Kaufland prices (store 4310)?"""
import io
import os
import sys
import time
import urllib.parse
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import pytesseract  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402

import fetch_prices as F  # noqa: E402
import kaufland_ocr as K  # noqa: E402
from items_def import ITEMS  # noqa: E402

r = F.get("https://endpoints.leaflets.schwarz/v4/overview?client_locale=kaufland%2Fcs-CZ&store_id=4310", as_json=True)
fl = [f for c in r.json()["categories"] for s in c.get("subcategories", []) if s.get("name") == "KDZ" for f in s.get("flyers", [])
      if (f.get("offerEndDate") or "9") >= F.TODAY]
fl.sort(key=lambda f: f.get("offerStartDate") or "")
f = fl[0]
fr = F.get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={urllib.parse.quote(f['id'])}&store_id=4310", as_json=True)
pages = fr.json()["flyer"]["pages"]
stems = sorted({F.norm(t).split()[0][:6] for it in ITEMS for t in it["cz"] if t})
pick = [pg for pg in pages if pg.get("number") in (2, 7, 10, 12, 13, 15, 21, 24, 25, 36, 40, 47)]
print("page keys:", list(pages[0].keys()))
print("urls:", {k: v for k, v in pages[0].items() if isinstance(v, str) and v.startswith("http")})
print("flyer", f.get("offerStartDate"), len(pick), "pages")
tot = Counter()
union = {}
t_base = t_best = 0.0
for pg in pick:
    ir = F.get(pg.get("zoom") or pg.get("image"))
    if ir is None:
        continue
    img = Image.open(io.BytesIO(ir.content)).convert("L")
    W = img.size[0]
    a = time.time()
    got_b, _ = K.read_page(img, pytesseract, F.match_items, F.parse_qty, F.convert, F.norm, F.ITEM, W, lines=K.page_lines(img, pytesseract, "base"))
    b = time.time()
    up = img.resize((W * 2, img.size[1] * 2), Image.LANCZOS)
    got_x, dbg = K.read_page(img, pytesseract, F.match_items, F.parse_qty, F.convert, F.norm, F.ITEM, W,
                             lines=K.ocr_lines(up, pytesseract, digit_conf=0, scale=2.0))
    tot.update(d[0] for d in dbg)
    for d in dbg:
        if d[0] in ("unverified", "OK"):
            print("    ", str(d)[:230])
    c = time.time()
    t_base += b - a
    t_best += c - b
    tot["base"] += len(got_b)
    tot["best"] += len(got_x)
    for g in got_b + got_x:
        union[(g[0], g[3])] = (pg.get("number"),) + g
    print(f"p.{pg.get('number')}: base {len(got_b)} best {len(got_x)}  ({b - a:.1f}s / {c - b:.1f}s)  W={W}")
print("TOTAL", dict(tot), f"time base {t_base:.0f}s best {t_best:.0f}s")
print("=== ALL VERIFIED (union) ===")
for k, v in sorted(union.items()):
    pgn, iid, name, price, unit, pack, card = v
    print(f"  p.{pgn} {iid:<14} {unit:>8}/{F.ITEM[iid]['unit']}  {price} for {pack}  | {name[:70]}")
