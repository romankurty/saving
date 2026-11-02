"""Discovery run 14: Kaufland via the public Schwarz leaflet platform, Tesco open routes.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import json
import re
import time
import urllib.parse
import urllib.robotparser

import requests

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 3
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
_robots = {}


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        status, text = None, ""
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            status, text = r.status_code, r.text
            rp.parse(text.splitlines() if status == 200 and "<html" not in text[:300].lower() else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status)
        print(f"  robots {base}: {status} {[l for l in text.splitlines() if l.lower().startswith(('disallow', 'user-agent'))][:10] if '<html' not in text[:300].lower() else 'html'}")
        time.sleep(DELAY_S)
    rp, status = _robots[base]
    if status in (401, 403):
        return False
    return rp.can_fetch(UA, url)


def get(url, as_json=False, ok_any=False):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=40, headers={"Accept": "application/json"} if as_json else {})
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:180]} ({len(r.content)} B)")
    return r if (r.status_code == 200 or ok_any) else None


def c(o, n=800):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


print("=== 1. Lidl flyer meta (to learn the platform's parameter formats) ===")
lf = get("https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier=akcni-letak-od-ctvrtka-5-11-8-11-2026&region_id=0&region_code=0", as_json=True)
meta = {}
if lf is not None:
    f = lf.json().get("flyer", {})
    meta = {k: f.get(k) for k in ("id", "locale", "clientLocale", "apiCountryCode", "countryCode", "category", "subcategory", "regions")}
    print("  lidl meta:", c(meta, 900))

print("=== 2. Kaufland leaflet front-end: how it calls the platform ===")
k = get("https://leaflets.kaufland.com/cs-CZ")
js_url = None
if k is not None:
    m = re.search(r'src="(https://kaufland\.leaflets\.schwarz/assets/[^"]+\.js)"', k.text)
    js_url = m.group(1) if m else None
if js_url:
    j = get(js_url)
    if j is not None:
        t = j.text
        for kw in ("client_locale", "clientLocale", "overview", "flyer_identifier", "category_id", "endpoints.leaflets"):
            idx = [mm.start() for mm in re.finditer(re.escape(kw), t)][:3]
            for i in idx:
                print(f"  [{kw}] …{t[max(0, i - 160): i + 200]}…".replace("\n", " "))

print("=== 3. Overview attempts ===")
cands = []
cl = (meta.get("clientLocale") or "")
cands.append(f"https://endpoints.leaflets.schwarz/v4/overview?client_locale={urllib.parse.quote(cl)}") if cl else None
for v in ("kaufland-cz-cs", "kaufland_cz_cs", "kaufland-cs-CZ", "kaufland_cs_CZ", "cz-cs", "cs-cz-kaufland"):
    cands.append(f"https://endpoints.leaflets.schwarz/v4/overview?client_locale={v}")
if meta.get("category"):
    cands.append(f"https://endpoints.leaflets.schwarz/v4/overview?category_id={urllib.parse.quote(str(meta['category']))}")
for u in cands[:9]:
    r = get(u, as_json=True, ok_any=True)
    if r is None:
        continue
    body = r.text[:300].replace("\n", " ")
    print("   ->", body)
    if r.status_code == 200:
        try:
            jj = r.json()
            txt = json.dumps(jj, ensure_ascii=False)
            idents = sorted(set(re.findall(r'"(?:flyerIdentifier|identifier|slug)"\s*:\s*"([^"]+)"', txt)))
            print("   identifiers:", idents[:30])
        except Exception:  # noqa: BLE001
            pass

print("=== 4. Tesco open routes ===")
for u in ("https://www.tesco.cz/", "https://tesco.cz/", "https://www.itesco.cz/robots.txt"):
    r = get(u, ok_any=True)
    if r is not None:
        print("   body:", re.sub(r"\s+", " ", r.text)[:700])
