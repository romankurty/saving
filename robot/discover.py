"""Discovery run 61: Renault + Opel detail pages."""
import re
import time

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9"})


def get(u):
    time.sleep(1.0)
    r = S.get(u, timeout=30)
    print(f"\n##### {u} -> {r.status_code} len {len(r.text)}")
    return r.text


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S))).strip()


sm = get("https://ihned.renault.sk/sitemap.xml")
cars = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if re.search(r"-v\d+/$", u) and "uzitkove" not in u]
print("renault car urls", len(cars), cars[:4])
for u in cars[:2]:
    t = get(u)
    print("  h1", [txt(x) for x in re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)][:2])
    for p in [r"pricelist_price", r"final-price", r"dealerName", r"\b(UU1|VF1|VF6|VF8)[A-HJ-NPR-Z0-9]{14}\b", r"perk-item", r"Batožin|batožin", r"km\b", r"predvádz|Predvádz"]:
        m = re.search(p, t)
        print("   ", p[:16], "->", re.sub(r"\s+", " ", t[max(0, m.start() - 120):m.start() + 220]) if m else None)

sm = get("https://online.opel-ihned.sk/sitemap.xml")
ou = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if "/vozidlo/" in u]
print("opel urls", len(ou))
for u in ou[:2]:
    t = get(u)
    tt = txt(t)
    print("  title", re.findall(r"<title>(.*?)</title>", t, re.S)[:1], [txt(x) for x in re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)][:2])
    for p in [r"€", r"VIN", r"[Pp]redajca|[Dd]ealer", r"km", r"Batožin", r"RPMN", r"hotovos", r"financ", r"ld\+json", r"og:title"]:
        for m in list(re.finditer(p, tt))[:2]:
            print("   tt", p[:10], "->", tt[max(0, m.start() - 150):m.start() + 200])
    for p in [r'"price"', r"application/ld\+json", r"data-price", r"dataLayer"]:
        m = re.search(p, t)
        print("   raw", p[:16], "->", re.sub(r"\s+", " ", t[max(0, m.start() - 100):m.start() + 400]) if m else None)
print("DONE")
