"""Discovery run 3: find each chain's official offer pages and check whether prices are machine-readable.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import json
import re
import time
import urllib.parse
import urllib.robotparser
from collections import Counter

import requests
from bs4 import BeautifulSoup

UA = "saving-pricebot/0.1 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 4
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
_robots = {}


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        status = None
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            status = r.status_code
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status)
        time.sleep(DELAY_S)
    rp, status = _robots[base]
    if status in (401, 403):
        return False  # site refuses robots entirely
    return rp.can_fetch(UA, url) and rp.can_fetch("*", url)


def get(url):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url} -> {r.url} ({len(r.content)} B)")
    return r if r.status_code == 200 else None


def profile(r):
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    kc = len(re.findall(r"\d+[,.]\d{2}\s*(?:Kč|€)", html))
    ld = soup.find_all("script", type="application/ld+json")
    ld_types = Counter()
    for s in ld:
        try:
            data = json.loads(s.string or "{}")
            items = data if isinstance(data, list) else [data]
            for it in items:
                if isinstance(it, dict):
                    ld_types[str(it.get("@type"))] += 1
        except Exception:  # noqa: BLE001
            pass
    embedded = [s.get("id") or (s.get("type") or "") for s in soup.find_all("script") if s.get("id") or s.get("type") in ("application/json",)]
    big_json = sorted(((len(s.string or ""), s.get("id") or s.get("type") or "inline") for s in soup.find_all("script") if s.string and len(s.string) > 20000), reverse=True)[:4]
    cls = Counter(c for el in soup.find_all(class_=True) for c in el.get("class", []))
    price_cls = [c for c, _ in cls.most_common(400) if any(k in c.lower() for k in ("price", "cena", "product", "offer", "tile", "discount"))][:25]
    print(f"    price strings: {kc} | JSON-LD types: {dict(ld_types)} | big inline JSON: {big_json} | script ids: {embedded[:8]}")
    print(f"    price-ish classes: {price_cls}")


def offer_links(r, extra_keys=()):
    soup = BeautifulSoup(r.text, "html.parser")
    keys = ("akc", "slev", "nabid", "letak", "leták", "zlav", "aktual", "tyden", "týden") + tuple(extra_keys)
    out = []
    host = urllib.parse.urlsplit(r.url).netloc
    for a in soup.find_all("a", href=True):
        h = urllib.parse.urljoin(r.url, a["href"])
        t = (a.get_text(" ", strip=True) or "").lower()
        if urllib.parse.urlsplit(h).netloc.endswith(host.replace("www.", "")) and any(k in h.lower() or k in t for k in keys):
            out.append(h.split("#")[0])
    return list(dict.fromkeys(out))


CHAINS = {
    "lidl_cz": "https://www.lidl.cz/",
    "billa_cz": "https://www.billa.cz/",
    "albert_cz": "https://www.albert.cz/",
    "teta_cz": "https://www.tetadrogerie.cz/",
}

for name, home_url in CHAINS.items():
    print(f"=== {name} ===")
    home = get(home_url)
    if home is None:
        continue
    links = offer_links(home)
    print("  offer-ish links:", links[:15])
    for link in links[:3]:
        r = get(link)
        if r is not None:
            profile(r)

print("=== dm (app shell? look for API hosts) ===")
r = get("https://www.dm.cz/")
if r is not None:
    hosts = sorted(set(re.findall(r"https://[a-z0-9.-]+\.(?:dmtech|dm)\.[a-z]+", r.text)))
    print("  hosts referenced:", hosts[:15])

print("=== Kaufland / Tesco alternative official routes ===")
for url in ("https://leaflets.kaufland.com/", "https://www.itesco.cz/", "https://www.itesco.cz/akce/", "https://www.tesco.cz/"):
    r = get(url)
    if r is not None:
        profile(r)
        print("  offer-ish links:", offer_links(r)[:10])

print("=== Other CZ aggregators (check if robots welcome) ===")
for url in ("https://www.akcniceny.cz/", "https://www.letaky.cz/", "https://www.kompas-slev.cz/"):
    r = get(url)
    if r is not None:
        profile(r)

print("=== Kupino.sk offers (SK) ===")
for url in ("https://www.kupino.sk/akcie", "https://www.kupino.sk/lidl", "https://www.kupino.sk/obchody"):
    r = get(url)
    if r is not None:
        profile(r)
        soup = BeautifulSoup(r.text, "html.parser")
        hrefs = list(dict.fromkeys(a["href"] for a in soup.find_all("a", href=True)))
        print("  sample links:", [h for h in hrefs if any(k in h for k in ("akci", "sintra", "kategor", "hlad", "produkt"))][:25])
