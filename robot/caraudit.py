"""Independent audit of car offers: re-open a sample of offer pages and confirm the price and the dealer
really appear there. Separate code path from the parsers in carbot.py (plain text search on the live page).

Usage: python robot/caraudit.py            → audits auta/data/offers.json in place (adds "audit" per checked offer + summary)
       imported by carbot.py               → audit(offers) before writing
"""
import json
import os
import random
import re
import sys
import time
import unicodedata

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s.replace("\xa0", " ").replace(" ", " "))


def _page_text(html):
    html = re.sub(r"&nbsp;|&#160;", " ", html)
    return _norm(re.sub(r"<[^>]+>", " ", html))


def _price_forms(p):
    p = int(round(p))
    a = f"{p:,}".replace(",", " ")
    return {a, a.replace(" ", ""), a.replace(" ", "."), a.replace(" ", ",")}


def _dealer_ok(dealer, txt):
    if not dealer:
        return None
    words = [w for w in re.findall(r"[a-z0-9]{3,}", _norm(dealer)) if w not in ("s.r.o", "sro", "spol", "predajca", "autorizovany", "znaciek", "servis", "jazdene")]
    if not words:
        return None
    hits = sum(1 for w in words[:3] if w in txt)
    return hits >= min(2, len(words[:3]))


def audit(offers, n=40, get=None, log=print, seed=None):
    rnd = random.Random(seed)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9"})

    def _get(u):
        time.sleep(1.2)
        try:
            r = s.get(u, timeout=25)
            return r.text if r.status_code == 200 else None
        except Exception:  # noqa: BLE001
            return None
    get = get or _get
    # the offers people actually look at: cheapest per source, plus a random sample
    by_src = {}
    for o in offers:
        if o.get("auth") and not o.get("stale"):
            by_src.setdefault(o["src"], []).append(o)
    sample = []
    for src, lst in by_src.items():
        lst = sorted(lst, key=lambda o: o["price"])
        sample += lst[:2]
        rest = lst[2:]
        sample += rnd.sample(rest, min(len(rest), 2))
    rnd.shuffle(sample)
    sample = sample[:n]
    ok = fail = 0
    failed = []
    for o in sample:
        h = get(o["url"])
        if h is None:
            o["audit"] = "gone"
            fail += 1
            failed.append((o["src"], o["url"], "page not reachable / sold"))
            continue
        txt = _page_text(h)
        p_ok = any(f in txt for f in _price_forms(o["price"]))
        d_ok = _dealer_ok(o.get("dealer"), txt)
        if p_ok and d_ok is not False:
            o["audit"] = "ok"
            ok += 1
        else:
            o["audit"] = "fail"
            fail += 1
            failed.append((o["src"], o["url"], ("price " if not p_ok else "") + ("dealer" if d_ok is False else "")))
    log(f"audit: {ok} ok, {fail} not confirmed of {len(sample)}")
    for f in failed:
        log("   not confirmed:", *f)
    return {"checked": len(sample), "ok": ok, "failed": fail}


if __name__ == "__main__":
    path = os.path.join(ROOT, "auta", "data", "offers.json")
    data = json.load(open(path, encoding="utf-8"))
    res = audit(data["offers"], n=int(sys.argv[1]) if len(sys.argv) > 1 else 40)
    print(res)
