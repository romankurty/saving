"""Discovery run 8: Lidl search API, Teta action products, dm sources, Albert leaflet dates, Kaufland leaflet data.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import html as htmlmod
import json
import re
import time
import urllib.parse
import urllib.robotparser
from collections import Counter

import requests
from bs4 import BeautifulSoup

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 3
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
_robots = {}


def robots(base):
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        status, text = None, ""
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            status, text = r.status_code, r.text
            rp.parse(text.splitlines() if status == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status, text)
        time.sleep(DELAY_S)
    return _robots[base]


def allowed(url):
    p = urllib.parse.urlsplit(url)
    rp, status, _ = robots(f"{p.scheme}://{p.netloc}")
    if status in (401, 403):
        return False
    return rp.can_fetch(UA, url)


def get(url, as_json=False):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30, headers={"Accept": "application/json"} if as_json else {})
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:170]} ({len(r.content)} B, {r.headers.get('content-type')})")
    return r if r.status_code == 200 else None


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


def unflatten_nuxt(payload):
    memo = {}

    def res(i, depth=0):
        if not isinstance(i, int) or i < 0 or i >= len(payload):
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


print("=== 1. Lidl search API (all current Lidl products with prices?) ===")
_, st, txt = robots("https://www.lidl.cz")
print("  robots disallow lines:", [l for l in txt.splitlines() if l.lower().startswith("disallow")][:20])
for url in ("https://www.lidl.cz/q/api/search?q=m%C3%A1slo&locale=cs_CZ&assortment=CZ&version=v2.0.0",
            "https://www.lidl.cz/q/api/search?q=maslo&fetchsize=48&locale=cs_CZ&assortment=CZ&version=2.1.0",
            "https://www.lidl.cz/q/query/potraviny"):
    r = get(url, as_json="api" in url)
    if r is None:
        continue
    if "json" in (r.headers.get("content-type") or ""):
        j = r.json()
        print("   keys:", list(j.keys())[:15] if isinstance(j, dict) else type(j))
        items = j.get("items") or []
        print("   items:", len(items), "| numFound:", j.get("numFound"))
        for it in items[:4]:
            g = (it.get("gridbox") or {}).get("data") or {}
            print("    -", g.get("fullTitle"), "|", c(g.get("price"), 250), "| lidlPlus:", c(g.get("lidlPlus"), 160), "| cat:", g.get("category"))
    else:
        tiles = re.findall(r'data-grid-data="([^"]+)"', r.text)
        print("   tiles:", len(tiles))

print("=== 2. Teta action products ===")
for url in ("https://www.tetadrogerie.cz/akce", "https://www.tetadrogerie.cz/akce?page=2"):
    r = get(url)
    if r is None:
        continue
    s = BeautifulSoup(r.text, "html.parser").find("script", id="__NUXT_DATA__")
    data = unflatten_nuxt(json.loads(s.string))
    d = (data or {}).get("data") if isinstance(data, dict) else None
    keys = list(d.keys()) if isinstance(d, dict) else []
    print("  data keys:", [k[:80] for k in keys][:20])
    for k in keys:
        if "actions?" in k:
            v = d[k]
            print("  ", k[:90], "->", type(v).__name__, list(v.keys())[:10] if isinstance(v, dict) else len(v))
            members = v.get("hydra:member") if isinstance(v, dict) else v
            if isinstance(v, dict):
                print("   total:", v.get("hydra:totalItems") or v.get("totalItems"))
                for kk, vv in v.items():
                    if isinstance(vv, list) and vv and isinstance(vv[0], dict):
                        members = vv
            if isinstance(members, list):
                print("   members:", len(members))
                for m in members[:2]:
                    print("   member:", c(m, 1800))

print("=== 3. dm ===")
_, st, txt = robots("https://www.dm.cz")
print("  dm robots:", st, [l for l in txt.splitlines() if l.strip()][:40])
for base in ("https://content.services.dmtech.com", "https://product-search.services.dmtech.com"):
    _, st2, txt2 = robots(base)
    print(f"  {base} robots:", st2, txt2[:300].replace("\n", " | "))
r = get("https://www.dm.cz/sitemap.xml")
if r is not None:
    locs = re.findall(r"<loc>([^<]+)</loc>", r.text)
    print("  sitemap locs:", locs[:15])

print("=== 4. Albert leaflet dates ===")
r = get("https://www.albert.cz/aktualni-letaky")
if r is not None:
    for slug in sorted(set(re.findall(r"letaky\.albert\.cz/([a-z0-9_]+)", r.text)))[:4]:
        i = r.text.find(slug)
        ctx = r.text[max(0, i - 900): i + 400]
        print(f"  --- {slug} ---")
        print("  ", re.sub(r"\s+", " ", ctx)[-1300:])
    soup = BeautifulSoup(r.text, "html.parser")
    nd = soup.find("script", id="__NEXT_DATA__")
    if nd:
        txtj = nd.string
        for m in re.finditer(r'"(validFrom|validTo|validityFrom|validityTo|dateFrom|dateTo|startDate|endDate|from|to)"\s*:\s*"([^"]{8,30})"', txtj):
            print("   date field:", m.group(1), m.group(2))
            break
        keys = Counter(re.findall(r'"([a-zA-Z]*(?:[Vv]alid|[Dd]ate)[a-zA-Z]*)"\s*:', txtj))
        print("   date-like keys:", keys.most_common(15))

print("=== 5. Kaufland leaflet platform ===")
for base in ("https://leaflets.kaufland.com", "https://kaufland.leaflets.schwarz", "https://endpoints.leaflets.schwarz"):
    _, st3, t3 = robots(base)
    print(f"  robots {base}: {st3} {t3[:200]!r}")
k = get("https://leaflets.kaufland.com/cs-CZ")
if k is not None:
    js_urls = re.findall(r'src="([^"]+\.js)"', k.text)
    for ju in js_urls[:2]:
        j = get(ju)
        if j is not None:
            print("   endpoint paths:", sorted(set(re.findall(r"/v\d/[a-zA-Z_/-]{3,40}", j.text)))[:30])
            print("   params:", sorted(set(re.findall(r"[?&]([a-z_]{3,30})=", j.text)))[:30])
            print("   flyer-ish strings:", sorted(set(re.findall(r"[\"'`](flyer[a-zA-Z_]*|overview[a-zA-Z_]*)[\"'`]", j.text)))[:20])
for url in ("https://endpoints.leaflets.schwarz/v4/overview?country=cz&brand=kaufland&locale=cs-CZ",
            "https://endpoints.leaflets.schwarz/v4/flyers?country_code=CZ&brand=kaufland",
            "https://endpoints.leaflets.schwarz/v4/overview?client=kaufland&country=CZ"):
    r = get(url, as_json=True)
    if r is not None:
        print("   ", r.text[:500].replace("\n", " "))
