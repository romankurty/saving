"""Discovery run 19: can Kaufland leaflet page images be read reliably with OCR? (feasibility only)

Personal, non-commercial use. A few requests, identifies itself honestly.
"""
import io
import re
import time

import pytesseract
import requests
from PIL import Image

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
session = requests.Session()
session.headers.update({"User-Agent": UA})

o = session.get("https://endpoints.leaflets.schwarz/v4/overview?client_locale=kaufland%2Fcs-CZ&store_id=4310", timeout=40).json()
fl = [f for cat in o.get("categories", []) for sub in cat.get("subcategories", []) if sub.get("name") in ("KDZ", "Hyper1") for f in sub.get("flyers", [])]
ident = fl[0]["id"]
f = session.get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={ident}&store_id=4310", timeout=40).json()["flyer"]
pages = f.get("pages") or []
want = ("máslo", "maslo", "vejce", "kuřecí", "vepřov", "eidam", "mozzarell", "šunka", "kefír", "rajčat", "okurk", "paprik", "banán", "jablk", "rýže", "těstovin")
picked = [pg for pg in pages if any(w in (pg.get("keyWords") or "").lower() for w in want)][:3]
print("pages with our items:", [pg.get("number") for pg in picked])
for pg in picked:
    time.sleep(3)
    img = Image.open(io.BytesIO(session.get(pg["zoom"], timeout=60).content)).convert("L")
    print(f"--- page {pg['number']} size {img.size}")
    txt = pytesseract.image_to_string(img, lang="ces", config="--psm 11")
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    hits = [l for l in lines if re.search(r"\d+[,.]\d{2}|kg|Kč|=", l)]
    print("   lines:", len(lines), "| price-ish:", len(hits))
    for l in lines[:70]:
        print("    ", l[:110])
