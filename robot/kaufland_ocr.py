"""Kaufland (Brno Královo Pole, store 4310) leaflet reader.

The leaflet platform publishes page images but no product-price data. This module reads the images with OCR and
keeps ONLY self-verified prices: a product name that matches one of our items, its printed unit price
("=1 kg 99,60" / "=100 g 4,47") AND a main price + pack size whose ratio agrees with that unit price (±6 %).
Anything that cannot be verified is dropped, so a misread can't drive a decision.
"""
import io
import re
import time
import urllib.parse

UNIT_RE = re.compile(r"=\s*(1\s*kg|100\s*g|1\s*l|100\s*ml|1\s*ks)\s*[:=]?\s*(\d{1,4})\s*[,.]\s*(\d{2})")
UNIT_RE2 = re.compile(r"(1\s*kg|100\s*g|1\s*l|100\s*ml)\s*=\s*(\d{1,4})\s*[,.]\s*(\d{2})")
MONEY_RE = re.compile(r"(?<![\d,.=])(\d{1,4})\s*[,.]\s*(\d{2})(?![\d%])")
INT_PRICE_RE = re.compile(r"(?<![\d,.])(\d{3,5})(?![\d%,.])")
FACTOR = {"1kg": 1.0, "100g": 10.0, "1l": 1.0, "100ml": 10.0, "1ks": 1.0}


def ocr_lines(img, pytesseract):
    d = pytesseract.image_to_data(img, lang="ces", config="--psm 11", output_type=pytesseract.Output.DICT)
    lines = {}
    for i, w in enumerate(d["text"]):
        w = (w or "").strip()
        if not w or int(float(d["conf"][i])) < 30:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        x, y, ww, hh = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        L = lines.setdefault(key, {"words": [], "x0": x, "y0": y, "x1": x + ww, "y1": y + hh})
        L["words"].append(w)
        L["x0"], L["y0"] = min(L["x0"], x), min(L["y0"], y)
        L["x1"], L["y1"] = max(L["x1"], x + ww), max(L["y1"], y + hh)
    out = []
    for L in lines.values():
        L["text"] = " ".join(L["words"])
        L["cx"], L["cy"] = (L["x0"] + L["x1"]) / 2, (L["y0"] + L["y1"]) / 2
        L["h"] = L["y1"] - L["y0"]
        out.append(L)
    return out


def read_page(img, pytesseract, match_items, parse_qty, convert, norm, ITEM, W):
    """Return verified offers [(item_id, name, price, unit_price, pack, card)] and a debug list."""
    lines = ocr_lines(img, pytesseract)
    found, debug = [], []
    for U in lines:
        t = norm(U["text"]).replace(" ", " ")
        m = UNIT_RE.search(t) or UNIT_RE2.search(t)
        if not m:
            continue
        base = m.group(1).replace(" ", "")
        unit = float(m.group(2) + "." + m.group(3)) * FACTOR.get(base, 1.0)
        # product block: lines above / around the unit-price line, same column
        near = [L for L in lines if L is not U and abs(L["cx"] - U["cx"]) < 0.22 * W and -0.22 * W < (U["cy"] - L["cy"]) < 0.05 * W]
        near.sort(key=lambda L: abs(U["cy"] - L["cy"]) + 0.6 * abs(U["cx"] - L["cx"]))
        block = near[:14]
        text = " ".join(L["text"] for L in sorted(block, key=lambda L: (L["y0"], L["x0"])))
        ids = match_items(text)
        if not ids:
            debug.append(("nomatch", unit, text[:120]))
            continue
        # pack size (nearest line with a quantity) and main price candidates
        pack_q = None
        for L in block:
            q = parse_qty(L["text"])
            if q and not UNIT_RE.search(norm(L["text"])):
                pack_q = q
                break
        prices = []
        for L in block:
            nt = norm(L["text"])
            if UNIT_RE.search(nt) or UNIT_RE2.search(nt):
                continue
            prices += [float(a + "." + b) for a, b in MONEY_RE.findall(L["text"].replace(" ", " "))]
            prices += [int(x) / 100 for x in INT_PRICE_RE.findall(L["text"]) if x.endswith(("90", "99", "49", "50", "40", "80", "00"))]
        card = "Kaufland Card" if re.search(r"kaufland\s*card|s\s*kartou", norm(text)) else None
        for iid in ids:
            it = ITEM[iid]
            verified = None
            if pack_q:
                pk = convert(pack_q[0], pack_q[1], it["unit"])
                if pk:
                    for p in prices:
                        if p > 0 and abs(p / pk - unit) / unit <= 0.06:
                            verified = (p, pk)
                            break
            if verified:
                found.append((iid, text[:80], verified[0], unit, verified[1], card))
                debug.append(("OK", iid, unit, verified, text[:100]))
            else:
                debug.append(("unverified", iid, unit, pack_q, prices[:6], text[:100]))
    return found, debug


def kaufland_offers(session_get, store_id, today, items_terms, deps, max_pages=40, delay=1.0, log=print):
    """deps: dict with pytesseract, Image, match_items, parse_qty, convert, norm, ITEM, offer."""
    pytesseract, Image = deps["pytesseract"], deps["Image"]
    r = session_get(f"https://endpoints.leaflets.schwarz/v4/overview?client_locale=kaufland%2Fcs-CZ&store_id={store_id}")
    if r is None:
        return [], [], []
    flyers = []
    for cat in r.json().get("categories", []):
        for sub in cat.get("subcategories", []):
            if sub.get("name") not in ("Hyper1", "KDZ"):
                continue
            for f in sub.get("flyers", []):
                if (f.get("offerEndDate") or "9999") >= today:
                    flyers.append((sub.get("name"), f))
    # one flyer per date range, prefer the hypermarket edition
    chosen = {}
    for sub, f in sorted(flyers, key=lambda x: 0 if x[0] == "Hyper1" else 1):
        chosen.setdefault((f.get("offerStartDate"), f.get("offerEndDate")), f)
    offers, leaflets, debug_all = [], [], []
    stems = sorted({deps["norm"](t).split()[0][:6] for terms in items_terms for t in terms if t})
    for (vf, vt), f in sorted(chosen.items()):
        leaflets.append({"title": f.get("title"), "from": vf, "to": vt, "url": f.get("flyerUrlAbsolute")})
        fr = session_get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={urllib.parse.quote(f['id'])}&store_id={store_id}")
        if fr is None:
            continue
        pages = fr.json().get("flyer", {}).get("pages") or []
        pick = [pg for pg in pages if any(s in deps["norm"](pg.get("keyWords") or "") for s in stems)][:max_pages]
        log(f"Kaufland {vf}–{vt}: {len(pick)} of {len(pages)} pages with our items")
        for pg in pick:
            time.sleep(delay)
            ir = session_get(pg.get("zoom") or pg.get("image"), raw=True)
            if ir is None:
                continue
            img = Image.open(io.BytesIO(ir.content)).convert("L")
            got, dbg = read_page(img, pytesseract, deps["match_items"], deps["parse_qty"], deps["convert"], deps["norm"], deps["ITEM"], img.size[0])
            debug_all += [(pg.get("number"),) + d for d in dbg]
            for iid, name, price, unit, pack, card in got:
                o = deps["offer"](iid, "kaufland", "brno", "CZK", name, price, unit, pack, card=card, promo=True,
                                  valid_from=vf + "T00:00:00+01:00" if vf else None, valid_to=vt + "T23:59:59+01:00" if vt else None,
                                  source=f"Kaufland leaflet p.{pg.get('number')} (scan, verified)", conf="med", url=f.get("flyerUrlAbsolute"))
                if o:
                    offers.append(o)
    # de-duplicate (same item + unit price)
    seen, uniq = set(), []
    for o in offers:
        k = (o["item"], o["unit_price"], o["valid_from"])
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    return uniq, leaflets, debug_all
