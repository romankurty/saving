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
VERSION = 2  # bump when the reading rules change, so cached results are re-read
FACTOR = {"1kg": 1.0, "100g": 10.0, "1l": 1.0, "100ml": 10.0, "1ks": 1.0}


def ocr_lines(img, pytesseract, min_conf=30, digit_conf=30, scale=1.0, tag=0):
    d = pytesseract.image_to_data(img, lang="ces", config="--psm 11", output_type=pytesseract.Output.DICT)
    lines = {}
    for i, w in enumerate(d["text"]):
        w = (w or "").strip()
        c = int(float(d["conf"][i]))
        if not w or c < (digit_conf if re.fullmatch(r"[\d,.]+", w) else min_conf):
            continue
        for k in ("left", "top", "width", "height"):
            d[k][i] = int(d[k][i] / scale)
        key = (tag, d["block_num"][i], d["par_num"][i], d["line_num"][i])
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


# words that mean "not the plain product" (flavoured snack, ready meal, fish fingers ...): reject the whole block
BAD_FOOD = re.compile(r"prichut|ochucen|prsty|predsmaz|obalovan|chips|chipsy|brambur|lupink|tycink|krekr|pomazank|polevk|hotove jidlo|omack|"
                      r"dresink|nuget|nugget|burger|plnen|knedl|pizza|tortill|susenk|oplat|cokolad")
SPLIT_RE = re.compile(r"(?<![\d,.])(\d{1,3})\s+(\d{2})(?![\d%,.])")
ENDINGS = ("90", "99", "49", "50", "40", "80", "00", "70", "60", "30", "20", "10", "95", "59", "69", "79", "89", "39", "29", "19", "09")
TOL = 0.03


def _price_candidates(block):
    """All plausible shelf prices printed in a product block (incl. big '99' + small '90' superscript pairs)."""
    out = []
    for L in block:
        nt = L["text"].replace("\u00a0", " ")
        if UNIT_RE.search(nt.lower()) or UNIT_RE2.search(nt.lower()):
            continue
        out += [float(a + "." + b) for a, b in MONEY_RE.findall(nt)]
        out += [int(x) / 100 for x in INT_PRICE_RE.findall(nt) if x.endswith(ENDINGS)]
        out += [float(a + "." + b) for a, b in SPLIT_RE.findall(nt) if b in ENDINGS]
    # superscript pairs: big integer followed (right, top-aligned) by a smaller 2-digit number
    ints = [L for L in block if re.fullmatch(r"\d{1,4}", L["text"].strip(" ,.-"))]
    for A in ints:
        for B in ints:
            if B is A:
                continue
            a, b = A["text"].strip(" ,.-"), B["text"].strip(" ,.-")
            if len(b) == 2 and B["h"] < A["h"] * 0.85 and -0.3 * A["h"] <= B["x0"] - A["x1"] <= 0.8 * A["h"] and abs(B["y0"] - A["y0"]) <= 0.45 * A["h"]:
                out.append(float(a + "." + b))
    return out


GENERIC = {"nuts"}  # a more specific item (e.g. Brazil nuts) wins over the generic one


def page_passes(img, pytesseract, Image):
    """Two OCR passes per page (tested on real leaflets: each finds prices the other misses):
    the page as published, and a 2x enlarged copy where small print is easier to read."""
    W, H = img.size
    yield ocr_lines(img, pytesseract)
    yield ocr_lines(img.resize((W * 2, H * 2), Image.LANCZOS), pytesseract, digit_conf=0, scale=2.0)


def read_page(img, pytesseract, match_items, parse_qty, convert, norm, ITEM, W, lines=None):
    """Return verified offers [(item_id, name, price, unit_price, pack, card)] and a debug list.

    Rules (precision first): the item name must be in the 6 lines nearest to the printed unit price, exactly one of our
    items may match, the block must not contain "flavoured / processed" words, and price / pack size must reproduce the
    printed unit price within 3 %."""
    lines = lines if lines is not None else ocr_lines(img, pytesseract)
    found, debug = [], []
    for U in lines:
        t = norm(U["text"]).replace("\u00a0", " ")
        m = UNIT_RE.search(t) or UNIT_RE2.search(t)
        if not m:
            continue
        base = m.group(1).replace(" ", "")
        unit = float(m.group(2) + "." + m.group(3)) * FACTOR.get(base, 1.0)
        near = [L for L in lines if L is not U and abs(L["cx"] - U["cx"]) < 0.22 * W and -0.22 * W < (U["cy"] - L["cy"]) < 0.05 * W]
        near.sort(key=lambda L: abs(U["cy"] - L["cy"]) + 0.6 * abs(U["cx"] - L["cx"]))
        block = near[:14]
        order = lambda ls: sorted(ls, key=lambda L: (L["y0"], L["x0"]))  # noqa: E731
        # product names are printed above (or level with) their unit price, never below it
        name_text = " ".join(L["text"] for L in order([L for L in near if L["cy"] <= U["cy"] + 0.6 * U["h"]][:6]))
        text = " ".join(L["text"] for L in order(block))
        ids = match_items(name_text)
        if len(ids) > 1:
            ids = [i for i in ids if i not in GENERIC] or ids
        if not ids:
            debug.append(("nomatch", unit, name_text[:100]))
            continue
        if len(ids) > 1:
            debug.append(("ambiguous", ids, unit, name_text[:100]))
            continue
        iid = ids[0]
        it = ITEM[iid]
        if it["group"] != "drugstore" and BAD_FOOD.search(norm(text)):
            debug.append(("excluded", iid, unit, text[:100]))
            continue
        # pack size: on the unit-price line itself (outside the "=1 kg .." part) or the nearest line with a quantity
        packs = []
        q0 = parse_qty(t[:m.start()] + " " + t[m.end():])
        if q0:
            packs.append(q0)
        for L in block:
            nt = norm(L["text"])
            if UNIT_RE.search(nt) or UNIT_RE2.search(nt):
                continue
            q = parse_qty(L["text"])
            if q:
                packs.append(q)
                if len(packs) >= 3:
                    break
        prices = _price_candidates(block)
        card = "Kaufland Card" if re.search(r"kaufland\s*card|s\s*kartou", norm(text)) else None
        verified = None
        for pq in packs:
            pk = convert(pq[0], pq[1], it["unit"])
            if not pk:
                continue
            for p in prices:
                if p > 0 and abs(p / pk - unit) / unit <= TOL:
                    verified = (p, pk)
                    break
            if verified:
                break
        if verified:
            found.append((iid, name_text[:80], verified[0], unit, verified[1], card))
            debug.append(("OK", iid, unit, verified, text[:100]))
        else:
            debug.append(("unverified", iid, unit, packs[:2], prices[:6], text[:100]))
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
    # main food leaflet (KDZ) + hypermarket supplement (Hyper1), each once
    chosen = {}
    for sub, f in flyers:
        chosen.setdefault((sub, f.get("offerStartDate"), f.get("offerEndDate")), f)
    offers, leaflets, debug_all = [], [], []
    stems = sorted({deps["norm"](t).split()[0][:6] for terms in items_terms for t in terms if t})
    for (sub, vf, vt), f in sorted(chosen.items(), key=lambda x: (x[0][1] or "", x[0][0])):
        leaflets.append({"id": f.get("id"), "title": f.get("title"), "from": vf, "to": vt, "url": f.get("flyerUrlAbsolute")})
        fr = session_get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={urllib.parse.quote(f['id'])}&store_id={store_id}")
        if fr is None:
            continue
        pages = fr.json().get("flyer", {}).get("pages") or []
        pick = [pg for pg in pages if any(s in deps["norm"](pg.get("keyWords") or "") for s in stems)][:max_pages]
        log(f"Kaufland {sub} {vf}–{vt}: reading {len(pick)} of {len(pages)} pages")
        for pg in pick:
            time.sleep(delay)
            ir = session_get(pg.get("zoom") or pg.get("image"), raw=True)
            if ir is None:
                continue
            img = Image.open(io.BytesIO(ir.content)).convert("L")
            got, dbg, seen_pg = [], [], set()
            for lines in page_passes(img, pytesseract, Image):
                g, d = read_page(img, pytesseract, deps["match_items"], deps["parse_qty"], deps["convert"], deps["norm"], deps["ITEM"],
                                 img.size[0], lines=lines)
                dbg += d
                for x in g:
                    if (x[0], x[3]) not in seen_pg:
                        seen_pg.add((x[0], x[3]))
                        got.append(x)
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
