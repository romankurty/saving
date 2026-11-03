"""Discovery run 28: which sources can give MORE PRECISE prices? (leaflet hotspot links, Lidl product sitemap,
robots rules of shops/aggregators, Albert web data, Kaufland SK)."""
import gzip
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.robotparser

sys.path.insert(0, os.path.dirname(__file__))
import fetch_prices as F  # noqa: E402

API = "https://endpoints.leaflets.schwarz/v4"


def flyer_links(loc, sub, store=None, n=8):
    q = f"&store_id={store}" if store else ""
    r = F.get(f"{API}/overview?client_locale={urllib.parse.quote(loc, safe='')}{q}", as_json=True)
    if r is None:
        print("  overview failed", loc); return
    fl = [f for c in r.json().get("categories", []) for s in c.get("subcategories", []) if s.get("name") == sub for f in s.get("flyers", [])]
    if not fl:
        print("  no flyers", loc, sub); return
    f = fl[0]
    fr = F.get(f"{API}/flyer?flyer_identifier={urllib.parse.quote(f['id'])}{q}", as_json=True)
    fj = fr.json().get("flyer", {}) if fr is not None else {}
    print("  flyer keys:", list(fj.keys())[:30])
    print("  products field:", type(fj.get("products")).__name__, str(fj.get("products"))[:300])
    for pg in (fj.get("pages") or [])[:n]:
        links = pg.get("links") or []
        print(f"  p.{pg.get('number')} links={len(links)} sample={json.dumps(links[:3], ensure_ascii=False)[:500]}")


print("== A) Lidl CZ leaflet hotspots"); flyer_links("lidl/cs-CZ", "Akční letáky")
print("== B) Kaufland CZ leaflet hotspots"); flyer_links("kaufland/cs-CZ", "KDZ", 4310, n=4)

print("== C) Lidl product sitemap")
for base in ("https://www.lidl.cz", "https://www.lidl.sk"):
    lang = "CZ/cs" if base.endswith(".cz") else "SK/sk"
    r = F.get(f"{base}/p/export/{lang}/product_sitemap.xml.gz")
    if r is None:
        print("  ", base, "sitemap failed"); continue
    try:
        txt = gzip.decompress(r.content).decode("utf-8", "ignore")
    except Exception:
        txt = r.text
    locs = re.findall(r"<loc>([^<]+)</loc>", txt)
    food = [u for u in locs if re.search(r"vejce|maslo|kure|mlek|jogurt|syr|chleb|ryze|banan|vajc|mlieko|chlieb", F.norm(u))]
    print("  ", base, "product urls", len(locs), "food-like", len(food), food[:8])
    if locs:
        p = F.get((food or locs)[0])
        if p is not None:
            ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', p.text, re.S)
            print("   ld+json blocks", len(ld), (ld[0][:400] if ld else ""))

print("== D) robots rules")
for base, path in (("https://www.kaufland.cz", "/akcni-nabidka/aktualni-tyden.html"), ("https://www.kaufland.sk", "/akciova-ponuka/aktualny-tyzden.html"),
                   ("https://www.albert.cz", "/akce"), ("https://www.akcniceny.cz", "/"), ("https://www.kupi.cz", "/"), ("https://www.kupi.sk", "/"),
                   ("https://nakup.itesco.cz", "/groceries/cs-CZ/"), ("https://potravinydomov.itesco.sk", "/groceries/sk-SK/"), ("https://www.rohlik.cz", "/"),
                   ("https://www.kosik.cz", "/"), ("https://www.letaky.cz", "/")):
    try:
        r = F.session.get(base + "/robots.txt", timeout=20)
        rp = urllib.robotparser.RobotFileParser(); rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        ua_block = re.findall(r"(?im)^user-agent:\s*(.+)$", r.text)[:6]
        print(f"  {base}: robots {r.status_code}, can_fetch {path}: {rp.can_fetch(F.UA, base + path) if r.status_code == 200 else '-'}, agents {ua_block}")
    except Exception as e:
        print("  ", base, "ERR", str(e)[:100])

print("== E) Albert web data")
h = F.get("https://www.albert.cz/")
if h is not None:
    links = sorted(set(re.findall(r'href="(/[a-z0-9\-/]+)"', h.text)))
    print("  links:", [l for l in links if re.search(r"akc|nabid|produkt|letak|sleva|zlevn", l)][:30])
    nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h.text, re.S)
    print("  __NEXT_DATA__ size", len(nd.group(1)) if nd else 0)
for path in ("/akce", "/produkty", "/zlevnene-produkty", "/nabidka"):
    r = F.get("https://www.albert.cz" + path)
    if r is not None:
        nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        prices = len(re.findall(r'"price"', nd.group(1))) if nd else 0
        print(f"  {path}: {len(r.text)//1000} kB, next_data {len(nd.group(1))//1000 if nd else 0} kB, 'price' keys {prices}")

print("== F) Kaufland SK leaflets")
for q in ("", "&store_id=6670"):
    r = F.get(f"{API}/overview?client_locale=kaufland%2Fsk-SK{q}", as_json=True)
    print("  ", q or "(no store)", None if r is None else (r.json().get("message"), len(r.json().get("categories") or [])))
