"""Price robot: reads public offer data for the household's items and writes data/prices.json.

Sources (personal, non-commercial use; one slow pass; honest User-Agent; robots.txt and blocks respected):
  Brno:     Lidl (lidl.cz offer pages), Billa (billa.cz product catalogue), Albert (leaflet text search)
  Kezmarok: Lidl (lidl.sk offer pages), Billa (billa.sk product catalogue)
Not covered (they block robots): Kaufland, Tesco, dm.
"""
import datetime as dt
import html as htmlmod
import json
import os
import re
import statistics
import sys
import time
import unicodedata
import urllib.parse
import urllib.robotparser

import requests

sys.path.insert(0, os.path.dirname(__file__))
from items_def import EUR_CZK, GROUP_ORDER, ITEMS, PET_EXC  # noqa: E402

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 1.5
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
_robots = {}
STATUS = {}


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- helpers
def norm(s):
    """Lowercase + strip accents, keeping string length (one output char per input char)."""
    out = []
    for ch in (s or ""):
        d = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in d if not unicodedata.combining(c)) or ch
        out.append(base[0].lower() if base else ch.lower())
    return "".join(out)


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        status = None
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            status = r.status_code
            rp.parse(r.text.splitlines() if status == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status)
        time.sleep(DELAY_S)
    rp, status = _robots[base]
    if status in (401, 403):
        return False
    return rp.can_fetch(UA, url)


def get(url, as_json=False):
    if not allowed(url):
        log(f"[SKIP robots/blocked] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30, headers={"Accept": "application/json"} if as_json else {})
    except Exception as e:  # noqa: BLE001
        log(f"[ERR] {url}: {e}")
        return None
    if r.status_code != 200:
        log(f"[{r.status_code}] {url}")
        return None
    return r


def num(s):
    s = str(s).replace("\xa0", " ").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


QTY_MULTI = re.compile(r"(\d+)\s*x\s*(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|ks)\b")
QTY_ONE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|ks|kus[uy]?|kusov|rol[ie]?|roliek|rolky|pcs|sacku|sacky|ubrousk\w*|obrusk\w*)\b")


def parse_qty(text):
    """Return (amount, base) with base in kg / l / ks, or None."""
    t = norm(text)
    m = QTY_MULTI.search(t)
    if m:
        n, v, u = int(m.group(1)), num(m.group(2)), m.group(3)
        if v:
            return _to_base(n * v, u)
    for m in QTY_ONE.finditer(t):
        v, u = num(m.group(1)), m.group(2)
        if v and v > 0:
            return _to_base(v, u)
    return None


def _to_base(v, u):
    if u == "g":
        return (v / 1000, "kg")
    if u == "kg":
        return (v, "kg")
    if u == "ml":
        return (v / 1000, "l")
    if u == "l":
        return (v, "l")
    return (v, "ks")


def convert(amount, base, item_unit):
    """Convert a pack amount into the item's unit (kg<->l treated 1:1 for foods)."""
    if amount is None:
        return None
    if base == item_unit:
        return amount
    if {base, item_unit} <= {"kg", "l"}:
        return amount
    return None


COMPILED = {it["id"]: (re.compile(it["inc"]), re.compile(it["exc"]) if it.get("exc") else None) for it in ITEMS}
ITEM = {it["id"]: it for it in ITEMS}


PET = re.compile(PET_EXC)


def match_items(name):
    t = norm(name)
    pet = bool(PET.search(t))
    out = []
    for iid, (inc, exc) in COMPILED.items():
        if pet and ITEM[iid]["group"] != "drugstore":
            continue
        if inc.search(t) and not (exc and exc.search(t)):
            out.append(iid)
    return out


def p25(values):
    v = sorted(x for x in values if x)
    if not v:
        return None
    if len(v) < 3:
        return v[0]
    k = (len(v) - 1) * 0.10
    f = int(k)
    return v[f] + (v[min(f + 1, len(v) - 1)] - v[f]) * (k - f)


def within_bounds(item, unit_price, currency):
    lo, hi = item["bounds"]
    czk = unit_price * (EUR_CZK if currency == "EUR" else 1)
    return lo <= czk <= hi


def offer(item_id, shop, city, currency, name, price, unit_price, pack, *, normal_price=None, normal_unit=None,
          min_qty=1, card=None, promo=False, valid_from=None, valid_to=None, weighted=False, source="", conf="high", url=None):
    it = ITEM[item_id]
    if unit_price is None or price is None or unit_price <= 0 or price <= 0:
        return None
    if not within_bounds(it, unit_price, currency):
        return None
    if normal_unit and normal_unit <= unit_price * 1.001:
        normal_unit = None if not promo else normal_unit
    return {
        "item": item_id, "shop": shop, "city": city, "name": name.strip()[:90], "price": round(price, 2),
        "unit_price": round(unit_price, 2), "pack": round(pack, 4) if pack else None, "weighted": bool(weighted),
        "normal_price": round(normal_price, 2) if normal_price else None,
        "normal_unit": round(normal_unit, 2) if normal_unit else None,
        "min_qty": int(min_qty or 1), "card": card, "promo": bool(promo),
        "valid_from": valid_from, "valid_to": valid_to, "source": source, "conf": conf, "url": url,
    }


# ---------------------------------------------------------------- Billa (CZ + SK): full product catalogue
def billa(city, base_url, terms_key, currency):
    shop = "billa"
    found, seen = [], set()
    ok_calls = 0
    for it in ITEMS:
        for term in it[terms_key]:
            r = get(f"{base_url}/api/product-discovery/products?page=0&pageSize=100&term={urllib.parse.quote(term)}", as_json=True)
            if r is None:
                continue
            ok_calls += 1
            try:
                results = r.json().get("results", [])
            except Exception:  # noqa: BLE001
                continue
            for p in results:
                name = p.get("name") or ""
                if it["id"] not in match_items(name):
                    continue
                key = (p.get("sku") or name, it["id"])
                if key in seen:
                    continue
                seen.add(key)
                pr = p.get("price") or {}
                reg = pr.get("regular") or {}
                loy = pr.get("loyalty") or {}
                use = loy if loy.get("value") else reg
                cur = use.get("value")
                if not cur:
                    continue
                cur = cur / 100
                per_std = (use.get("perStandardizedQuantity") or 0) / 100 or None
                bu = (pr.get("baseUnitShort") or "").lower()
                std = pr.get("standard") or {}
                if use is loy:
                    normal = (reg.get("value") or 0) / 100 or None
                    normal_std = (reg.get("perStandardizedQuantity") or 0) / 100 or None
                else:
                    normal = (std.get("value") or pr.get("crossed") or 0) / 100 or None
                    normal_std = (std.get("perStandardizedQuantity") or 0) / 100 or None
                promo = bool(p.get("inPromotion") or pr.get("crossed") or use is loy)
                min_qty = 1
                if use.get("promotionType") == "FROM" and (use.get("promotionQuantity") or 0) >= 2:
                    min_qty = int(use.get("promotionQuantity"))
                tags = [str(t).lower() for t in (use.get("tags") or [])]
                card = "Billa card" if (use is loy or any(k in t for t in tags for k in ("club", "klub", "card", "karta", "loyal"))) else None
                weighted = bool(p.get("weightArticle"))
                # pack size
                pack_amt = None
                vol = (p.get("volumeLabelShort") or "").lower()
                amt = num(p.get("amount")) if p.get("amount") else None
                if amt and vol in ("g", "kg", "ml", "l", "ks"):
                    pack_amt = _to_base(amt, vol)
                if not pack_amt:
                    pack_amt = parse_qty(name)
                pack = convert(pack_amt[0], pack_amt[1], it["unit"]) if pack_amt else None
                # unit price in item unit
                if it["unit"] == "ks":
                    if weighted:
                        continue
                    count = pack if pack else (pack_amt[0] if pack_amt and pack_amt[1] == "ks" else None)
                    if it.get("count_required") and not count:
                        continue
                    if bu == "ks" and per_std:
                        unit = per_std
                    elif count:
                        unit = cur / count
                    else:
                        unit = cur  # sold per piece
                        pack = 1
                    n_unit = (normal / count if (normal and count) else (normal if normal and not count else None))
                    if pack is None:
                        pack = count
                else:
                    if per_std and bu in ("kg", "l"):
                        unit = per_std
                    elif pack:
                        unit = cur / pack
                    else:
                        continue
                    n_unit = normal_std if normal_std else (unit * normal / cur if normal else None)
                    if weighted:
                        pack = None
                o = offer(it["id"], shop, city, currency, name, cur, unit, pack, normal_price=normal, normal_unit=n_unit,
                          min_qty=min_qty, card=card, promo=promo, weighted=weighted,
                          source=f"{base_url.split('//')[1]} catalogue", conf="high")
                if o:
                    found.append(o)
    STATUS[f"billa_{city}"] = {"status": "ok" if ok_calls else "error", "offers": len(found), "checked": NOW.isoformat(),
                               "note": "full catalogue: normal, promo and Billa card prices"}
    log(f"Billa {city}: {len(found)} matched products from {ok_calls} searches")
    return found


# ---------------------------------------------------------------- Lidl (CZ + SK): weekly offer pages
def lidl(city, base_url, currency):
    shop = "lidl"
    home = get(base_url + "/")
    if home is None:
        STATUS[f"lidl_{city}"] = {"status": "error", "offers": 0, "note": "homepage not reachable"}
        return []
    pages = list(dict.fromkeys(re.findall(r'href="(/c/[a-z0-9-]+/a\d+)"', home.text)))
    log(f"Lidl {city}: {len(pages)} offer pages")
    found, seen = [], set()
    for path in pages[:30]:
        r = get(base_url + path)
        if r is None:
            continue
        for raw in re.findall(r'data-grid-data="([^"]+)"', r.text):
            try:
                d = json.loads(htmlmod.unescape(raw))
            except Exception:  # noqa: BLE001
                continue
            d = d[0] if isinstance(d, list) and d else d
            if not isinstance(d, dict):
                continue
            name = d.get("fullTitle") or d.get("title") or ""
            ids = match_items(name)
            if not ids:
                continue
            pid = d.get("productId") or name
            pobj = d.get("price") or {}
            price = pobj.get("price")
            lp = d.get("lidlPlus") or []
            lp_obj = (lp[0].get("price") or {}) if lp and isinstance(lp[0], dict) else {}
            lp_price = lp_obj.get("price")
            base_txt = ((pobj.get("basePrice") or {}).get("text") or (lp_obj.get("basePrice") or {}).get("text") or "")
            pack_txt = ((pobj.get("packaging") or {}).get("text") or (lp_obj.get("packaging") or {}).get("text") or "")
            old = pobj.get("oldPrice") or (pobj.get("discount") or {}).get("deletedPrice") or None
            # validity
            vf = vt = None
            badges = ((d.get("stockAvailability") or {}).get("badgeInfoV2")) or []
            spans = [(b.get("validFrom"), b.get("validUntil")) for b in badges if isinstance(b, dict) and b.get("validUntil")]
            if spans:
                now_ts = NOW.timestamp()
                current = [s for s in spans if s[1] >= now_ts]
                if current:
                    s = min(current, key=lambda x: x[0] or 0)
                    vf = dt.datetime.fromtimestamp(s[0], dt.timezone.utc).isoformat() if s[0] else None
                    vt = dt.datetime.fromtimestamp(s[1], dt.timezone.utc).isoformat()
                else:
                    continue  # all spans in the past
            elif pobj.get("endDate"):
                vt = pobj.get("endDate")
                vf = pobj.get("startDate")
                try:
                    if dt.datetime.fromisoformat(vt.replace("Z", "+00:00")) < NOW:
                        continue
                except Exception:  # noqa: BLE001
                    pass
            eff = lp_price or price
            if not eff:
                continue
            card = "Lidl Plus" if lp_price else None
            normal = price if (lp_price and price and price > lp_price) else (old if old and old > eff else None)
            m = re.search(r"1\s*(kg|l)\s*=\s*(\d[\d\s]*,\d{2})", norm(base_txt))
            for iid in ids:
                it = ITEM[iid]
                if (pid, iid) in seen:
                    continue
                seen.add((pid, iid))
                weighted = False
                pack = None
                if m and it["unit"] in ("kg", "l"):
                    per = num(m.group(2))
                    ref_price = price or lp_price
                    unit = per * (eff / ref_price) if ref_price else per
                    q = parse_qty(pack_txt) or parse_qty(name)
                    pack = convert(q[0], q[1], it["unit"]) if q else (eff / unit if unit else None)
                else:
                    q = parse_qty(pack_txt) or parse_qty(base_txt) or parse_qty(name)
                    nb = norm(base_txt + " " + pack_txt)
                    if not q and re.search(r"\b1\s*kg\b|za\s*kg|cena za 1 kg", nb) and it["unit"] == "kg":
                        unit, pack, weighted = eff, None, True
                    elif q:
                        pack = convert(q[0], q[1], it["unit"])
                        if pack is None and it["unit"] == "ks" and not it.get("count_required"):
                            pack = 1
                        if not pack:
                            continue
                        unit = eff / pack
                    elif it["unit"] == "ks" and not it.get("count_required"):
                        pack, unit = 1, eff
                    else:
                        continue
                n_unit = (unit * normal / eff) if normal else None
                o = offer(iid, shop, city, currency, name, eff, unit, pack, normal_price=normal, normal_unit=n_unit,
                          card=card, promo=True, valid_from=vf, valid_to=vt, weighted=weighted,
                          source=f"{base_url.split('//')[1]} offers", conf="high",
                          url=base_url + (d.get("canonicalUrl") or ""))
                if o:
                    found.append(o)
    STATUS[f"lidl_{city}"] = {"status": "ok", "offers": len(found), "checked": NOW.isoformat(), "note": "weekly offers incl. Lidl Plus prices"}
    log(f"Lidl {city}: {len(found)} matched offers")
    return found


# ---------------------------------------------------------------- Albert (CZ): leaflet text search
STOP_WORDS = {"neporazitelne", "mimoradne", "bez", "aplikace", "aplikaci", "akce", "novinka", "top", "cena", "sleva", "jen", "pouze", "kc", "bal", "ks", "cca", "vybrane", "druhy", "celku", "baleni"}


def parse_albert(text, term, item):
    """Extract offers for `term` from one leaflet page's text."""
    out = []
    t = norm(text)
    nterm = norm(term)
    first_word = nterm.split()[0]
    for m in re.finditer(re.escape(first_word), t):
        i = m.start()
        # product name: capitalised words before the term + text up to the first bullet
        words = text[max(0, i - 60):i].split()

        def nameish(w):
            wn = norm(w).strip(".,–-")
            return w[:1].isalpha() and not any(ch.isdigit() for ch in w) and not (w.isupper() and len(w) > 2) \
                and wn not in STOP_WORDS and len(wn) > 1

        prefix = []
        k = len(words) - 1
        while k >= 0 and len(prefix) < 4:
            w = words[k]
            if not nameish(w):
                break
            if w[:1].isupper():
                prefix.insert(0, w)
                k -= 1
                continue
            # lowercase word: keep only if a capitalised name word sits right before it (e.g. "Česká chuť")
            if k - 1 >= 0 and nameish(words[k - 1]) and words[k - 1][:1].isupper():
                prefix[0:0] = [words[k - 1], w]
                k -= 2
                continue
            break
        end_name = text.find("•", i)
        if end_name == -1 or end_name - i > 45:
            continue
        name = (" ".join(prefix) + " " + text[i:end_name]).strip()
        name = re.split(r"\s\d{1,4},\d{2}\s*/|\s\d{1,4},-", name)[0].strip(" –-/")
        window = text[i:i + 240]
        wn = norm(window)
        if item["id"] not in match_items(name + " " + window[:80]):
            continue
        unit_any = [um.span() for um in re.finditer(r"(1\s*kg|100\s*g|1\s*l|100\s*ml|1\s*ks|10\s*ks)\s*(?:=|od)\s*(\d{1,4}),(\d{2})\s*Kč", window)]
        def in_unit(p0):
            return any(a <= p0 < b for a, b in unit_any)
        cands = [(pm.start(), num(pm.group(1) + "." + pm.group(2)), "kc") for pm in re.finditer(r"(\d{1,4}),(\d{2})\s*Kč", window) if not in_unit(pm.start())]
        cands += [(bm.start(), num(bm.group(1) + "." + bm.group(2)), "big") for bm in re.finditer(r"(?<![\d,.])(\d{1,4}) (\d{2})(?![\d,%])", window) if not in_unit(bm.start())]
        cands.sort()
        if not cands:
            continue
        pos, price, _kind = cands[0]
        if not price:
            continue
        unit_m = None
        for um in re.finditer(r"(1\s*kg|100\s*g|1\s*l|100\s*ml|1\s*ks|10\s*ks)\s*(?:=|od)\s*(\d{1,4}),(\d{2})\s*Kč", window[:pos + 2]):
            unit_m = um
        unit_span = unit_m.span() if unit_m else (-1, -1)
        old = None
        after = window[pos:pos + 30]
        om = re.search(r"Kč\s+(\d{1,4}),(\d{2})", after)
        if om:
            old = num(om.group(1) + "." + om.group(2))
        else:
            om2 = list(re.finditer(r"(\d{1,4}),-", window[:pos]))
            if om2:
                old = num(om2[-1].group(1))
        tail = wn[pos:pos + 90]
        card = "Albert app" if re.search(r"s aplikac|s albert", tail) and "bez aplikac" not in tail else None
        attrs = window[:pos]
        q = None
        for qm in QTY_ONE.finditer(norm(attrs)):
            if unit_m and unit_span[0] <= qm.start() < unit_span[1]:
                continue
            q = _to_base(num(qm.group(1)), qm.group(2))
            break
        mq = QTY_MULTI.search(norm(attrs))
        if mq:
            q = _to_base(int(mq.group(1)) * num(mq.group(2)), mq.group(3))
        unit = None
        conf = "med"
        if unit_m:
            per = num(unit_m.group(2) + "." + unit_m.group(3))
            base = norm(unit_m.group(1)).replace(" ", "")
            factor = {"1kg": 1, "100g": 10, "1l": 1, "100ml": 10, "1ks": 1, "10ks": 0.1}.get(base, 1)
            unit = per * factor
        pack = convert(q[0], q[1], item["unit"]) if q else None
        if item["unit"] == "ks":
            if pack is None:
                if item.get("count_required"):
                    continue
                pack = 1
            calc = price / pack
            if unit and abs(calc - unit) / unit > 0.25:
                conf = "low"
            unit = calc
        else:
            if pack:
                calc = price / pack
                if unit:
                    conf = "high" if abs(calc - unit) / unit <= 0.15 else "low"
                    if conf == "low":
                        continue
                unit = unit or calc
            elif unit:
                pack = price / unit
        if not unit:
            continue
        weighted = bool(q and q[0] == 1 and q[1] == "kg" and item["unit"] == "kg")
        normal_unit = unit * old / price if old and old > price else None
        out.append(dict(name=name, price=price, unit=unit, pack=None if weighted else pack, old=old if old and old > price else None,
                        normal_unit=normal_unit, card=card, conf=conf, weighted=weighted))
    return out


def albert():
    page = get("https://www.albert.cz/aktualni-letaky")
    if page is None:
        STATUS["albert_brno"] = {"status": "error", "offers": 0, "note": "leaflet list not reachable"}
        return [], []
    leaflets = []
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page.text, re.S)
    if m:
        try:
            nd = json.loads(m.group(1))
        except Exception:  # noqa: BLE001
            nd = None
        stack = [nd]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if o.get("viewUrl") and o.get("validityEndDate"):
                    slug = o["viewUrl"].rstrip("/").split("/")[-1]
                    vf = vt = None
                    try:
                        d1 = dt.datetime.strptime(o.get("validityStartDateFormatted", ""), "%d.%m.%Y")
                        vf = d1.strftime("%Y-%m-%dT00:00:00+01:00")
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        d2 = dt.datetime.strptime(o["validityEndDate"], "%d/%m/%Y %H:%M:%S")
                        vt = d2.strftime("%Y-%m-%dT%H:%M:%S+01:00")
                    except Exception:  # noqa: BLE001
                        pass
                    leaflets.append({"slug": slug, "valid_from": vf, "valid_to": vt, "type": o.get("documentType"),
                                     "location": o.get("locationType"), "title": o.get("title")})
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
    uniq = {}
    for l in leaflets:
        uniq.setdefault(l["slug"], l)
    leaflets = list(uniq.values())
    log(f"Albert leaflets: {leaflets}")
    current = [l for l in leaflets if not l["valid_to"] or l["valid_to"][:10] >= TODAY]
    sm = [l["slug"] for l in current if l.get("location") == "SUPERMARKET"]
    hm = [l["slug"] for l in current if l.get("location") != "SUPERMARKET"]
    ordered = (sorted(sm, key=lambda x: (0 if "letak" in x else 1, x)) or sorted(hm, key=lambda x: (0 if "letak" in x else 1, x)))[:3]
    found, seen = [], set()
    for slug in ordered:
        lf = next((l for l in leaflets if l["slug"] == slug), {})
        for it in ITEMS:
            for term in it["cz"]:
                r = get(f"https://letaky.albert.cz/{slug}/search?q={urllib.parse.quote(term)}", as_json=True)
                if r is None:
                    continue
                try:
                    hits = r.json().get("hits", [])
                except Exception:  # noqa: BLE001
                    continue
                for h in hits:
                    f = h.get("fields") or {}
                    for o in parse_albert(f.get("contents") or "", term, it):
                        key = (it["id"], norm(o["name"]), o["price"])
                        if key in seen:
                            continue
                        seen.add(key)
                        rec = offer(it["id"], "albert", "brno", "CZK", o["name"], o["price"], o["unit"], o["pack"],
                                    normal_price=o["old"], normal_unit=o["normal_unit"], card=o["card"], promo=True,
                                    valid_from=lf.get("valid_from"), valid_to=lf.get("valid_to"), weighted=o["weighted"],
                                    source=f"Albert leaflet {slug} p.{f.get('page_number')}", conf=o["conf"],
                                    url=f"https://letaky.albert.cz/{slug}/page/{f.get('page_number')}")
                        if rec:
                            found.append(rec)
    STATUS["albert_brno"] = {"status": "ok" if ordered else "error", "offers": len(found), "checked": NOW.isoformat(),
                             "note": "leaflet offers incl. Albert app prices, read from leaflet text: " + ", ".join(ordered)}
    log(f"Albert: {len(found)} matched offers from {len(ordered)} leaflets")
    return found, leaflets


# ---------------------------------------------------------------- Teta (CZ drugstore): e-shop category pages
TETA_SLUGS = {
    "toilet_paper": ["toaletni-papir"],
    "wet_wipes": ["vlhcene-toaletni-papiry", "vlhcene-ubrousky"],
    "toothpaste": ["zubni-pasty"],
    "shampoo": ["sampony"],
    "shower_gel": ["sprchove-gely-a-oleje"],
    "dish_soap": ["rucni-myti-nadobi"],
}


def unflatten_nuxt(payload):
    memo = {}

    def res(i, depth=0):
        if not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= len(payload):
            return i
        if i in memo:
            return memo[i]
        if depth > 80:
            return None
        v = payload[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef"):
                out = res(v[1], depth + 1) if len(v) > 1 else None
            elif v and isinstance(v[0], str) and v[0] in ("Set", "Map", "Date", "RegExp", "BigInt", "null", "undefined", "NaN"):
                out = v[1] if v[0] == "Date" and len(v) > 1 else None
            else:
                out = []
                memo[i] = out
                out.extend(res(x, depth + 1) for x in v)
                return out
        elif isinstance(v, dict):
            out = {}
            memo[i] = out
            for k, x in v.items():
                out[k] = res(x, depth + 1)
            return out
        else:
            out = v
        memo[i] = out
        return out

    return res(0)


def teta():
    found, seen = [], set()
    ok_pages = 0
    for iid, slugs in TETA_SLUGS.items():
        it = ITEM[iid]
        for slug in slugs:
            for page_no in (1, 2, 3):
                url = f"https://www.tetadrogerie.cz/eshop/produkty/{slug}" + (f"?page={page_no}" if page_no > 1 else "")
                r = get(url)
                if r is None:
                    break
                m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
                if not m:
                    break
                try:
                    data = unflatten_nuxt(json.loads(m.group(1)))
                except Exception:  # noqa: BLE001
                    break
                ok_pages += 1
                prods, stack, new = [], [data], 0
                while stack:
                    o = stack.pop()
                    if isinstance(o, dict):
                        if "name" in o and "price" in o and "code" in o and isinstance(o.get("price"), (int, float)):
                            prods.append(o)
                            continue
                        stack.extend(o.values())
                    elif isinstance(o, list):
                        stack.extend(o)
                for p in prods:
                    name = p.get("name") or ""
                    if (p.get("code"), iid) in seen:
                        continue
                    seen.add((p.get("code"), iid))
                    new += 1
                    if iid not in match_items(name) or p.get("isStockAvailable") is False:
                        continue
                    price = p["price"] / 100
                    orig = (p.get("originalPrice") or 0) / 100 or None
                    q = parse_qty(name)
                    pack = convert(q[0], q[1], it["unit"]) if q else None
                    if it["unit"] == "ks" and not pack:
                        continue
                    if not pack:
                        up = ((p.get("bbyPrices") or {}).get("unit_price") or {})
                        if str(up.get("unit")).upper() in ("L", "KG") and up.get("number"):
                            unit = up["number"]
                            pack = price / unit
                        else:
                            continue
                    unit = price / pack
                    promo = bool(orig and orig > price)
                    o = offer(iid, "teta", "brno", "CZK", name, price, unit, pack,
                              normal_price=orig if promo else None, normal_unit=(unit * orig / price) if promo else None,
                              promo=promo, source="tetadrogerie.cz e-shop", conf="high",
                              url=f"https://www.tetadrogerie.cz/eshop/produkt/{p.get('slug')}" if p.get("slug") else None)
                    if o:
                        found.append(o)
                if new == 0:
                    break  # page parameter ignored or no more products
    STATUS["teta_brno"] = {"status": "ok" if ok_pages else "error", "offers": len(found), "checked": NOW.isoformat(),
                           "note": "e-shop prices for drugstore items"}
    log(f"Teta: {len(found)} matched products from {ok_pages} pages")
    return found


# ---------------------------------------------------------------- history, usual prices, output
def load(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def main():
    all_offers = []
    all_offers += lidl("brno", "https://www.lidl.cz", "CZK")
    all_offers += billa("brno", "https://www.billa.cz", "cz", "CZK")
    alb, leaflets = albert()
    all_offers += alb
    all_offers += lidl("kezmarok", "https://www.lidl.sk", "EUR")
    all_offers += billa("kezmarok", "https://www.billa.sk", "skt", "EUR")
    all_offers += teta()
    notes = {"kaufland": "blocks robots on its website; leaflet only as images",
             "tesco": "blocks robots on all its websites",
             "dm": "its robots rules forbid reading product data",
             "sintra": "no online prices"}
    for name in ("kaufland_brno", "tesco_brno", "dm_brno", "kaufland_kezmarok", "tesco_kezmarok", "sintra_kezmarok"):
        STATUS.setdefault(name, {"status": "not covered", "offers": 0, "note": notes[name.split("_")[0]]})

    hist_path = os.path.join(ROOT, "data", "history.json")
    history = load(hist_path, {})
    cities = {}
    for city, currency, shops in (("brno", "CZK", ["lidl", "billa", "albert"]), ("kezmarok", "EUR", ["lidl", "billa"])):
        items_out = {}
        ch = history.setdefault(city, {})
        for it in ITEMS:
            offs = [o for o in all_offers if o["city"] == city and o["item"] == it["id"]]
            offs.sort(key=lambda o: o["unit_price"])
            # history: best unit price per shop today + normal price observations
            ih = ch.setdefault(it["id"], {})
            for shop in shops + (["teta"] if city == "brno" else []):
                so = [o for o in offs if o["shop"] == shop]
                if not so:
                    continue
                best = so[0]
                normals = [o["normal_unit"] for o in so if o.get("normal_unit")] + \
                          [o["unit_price"] for o in so if not o["promo"]]
                normals = [p25(normals)] if normals else []
                rows = [r for r in ih.get(shop, []) if r[0] != TODAY]
                rows.append([TODAY, best["unit_price"], round(statistics.median(normals), 2) if normals else None])
                ih[shop] = rows[-150:]
            # usual (normal) unit price: median of normal observations today + last 60 days
            cutoff = (NOW.date() - dt.timedelta(days=60)).isoformat()
            # usual = everyday price of the cheaper acceptable products (25th percentile of regular prices)
            obs = [o["normal_unit"] for o in offs if o.get("normal_unit") and o.get("conf") != "low"]
            obs += [o["unit_price"] for o in offs if not o["promo"]]
            for rows in ih.values():
                obs += [r[2] for r in rows if r[2] and r[0] >= cutoff]
            usual = round(p25(obs), 2) if obs else None
            per_shop = {}
            for o in offs:
                per_shop.setdefault(o["shop"], [])
                if len(per_shop[o["shop"]]) < 5:
                    per_shop[o["shop"]].append(o)
            items_out[it["id"]] = {"usual": usual, "offers": [o for s in per_shop.values() for o in s]}
        cities[city] = {
            "currency": currency,
            "covered": shops,
            "uncovered": ["kaufland", "tesco"] if city == "brno" else ["kaufland", "tesco", "sintra"],
            "drug_covered": ["lidl", "billa", "albert", "teta"] if city == "brno" else ["lidl", "billa"],
            "drug_uncovered": ["dm"] if city == "brno" else [],
            "items": items_out,
        }

    out = {
        "generated": NOW.isoformat(),
        "eur_czk": EUR_CZK,
        "sources": STATUS,
        "albert_leaflets": leaflets,
        "cities": cities,
    }
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "prices.json"), "w") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    with open(hist_path, "w") as fh:
        json.dump(history, fh, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(os.path.join(ROOT, "config"), exist_ok=True)
    with open(os.path.join(ROOT, "config", "items.json"), "w") as fh:
        json.dump({"groups": GROUP_ORDER, "eur_czk": EUR_CZK,
                   "items": [{k: v for k, v in it.items() if k not in ("inc", "exc")} for it in ITEMS]},
                  fh, ensure_ascii=False, indent=1)

    # summary for the log
    log("\n=== SUMMARY ===")
    log(json.dumps(STATUS, ensure_ascii=False, indent=1))
    for city in cities:
        log(f"\n--- {city} ---")
        for it in ITEMS:
            d = cities[city]["items"][it["id"]]
            best = {}
            for o in d["offers"]:
                if o["shop"] not in best:
                    best[o["shop"]] = o
            parts = [f"{s}:{o['unit_price']}{'*' if o['promo'] else ''}{'[' + o['card'] + ']' if o['card'] else ''} ({o['name'][:38]})" for s, o in best.items()]
            log(f"{it['id']:<15} usual={d['usual']} | " + " | ".join(parts))


if __name__ == "__main__":
    main()
