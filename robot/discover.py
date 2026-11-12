"""Discovery run 43: listing formats + pagination + seller fields."""
import json
import re
import time
import urllib.parse
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.5"})
RB = {}


def ok(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in RB:
        rp = urllib.robotparser.RobotFileParser()
        r = S.get(base + "/robots.txt", timeout=20)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        RB[base] = (rp, r.status_code)
    rp, st = RB[base]
    return rp.can_fetch(UA, url) if st == 200 else st == 404


def get(url):
    if not ok(url):
        print("BLOCKED", url)
        return ""
    time.sleep(1.2)
    try:
        r = S.get(url, timeout=25)
        print(f"\n===== {r.status_code} {url} ({len(r.text)//1024} kB)")
        return r.text
    except Exception as e:  # noqa: BLE001
        print("ERR", url, e)
        return ""


def nxt(t):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
    return json.loads(m.group(1)) if m else {}


def snip(t, pat, n=1, w=1500):
    for m in list(re.finditer(pat, t))[:n]:
        print("  …" + re.sub(r"\s+", " ", t[max(0, m.start() - w // 4): m.start() + w]) + "…")


# autobazar: all keys, filter object, price filter attempt, detail advertisement object
t = get("https://www.autobazar.eu/vysledky-nove-auta/?category=30900")
pp = nxt(t).get("props", {}).get("pageProps", {})
rec = pp["initialRecords"]["data"][0]
print("ALL KEYS:", sorted(rec.keys()))
print("filter:", json.dumps(pp.get("filter"), ensure_ascii=False)[:1500])
print("newCarsQuery:", json.dumps(pp.get("newCarsQuery"), ensure_ascii=False)[:800])
print("total:", pp["initialRecords"]["total"], "maxPage:", pp.get("maxPage"))
print("conditions:", sorted({(r.get("condition"), r.get("mileage") is not None and r.get("mileage") > 100) for r in pp["initialRecords"]["data"]}))
print("subjectTypes:", sorted({r.get("userSubjectType") for r in pp["initialRecords"]["data"]}))
for q in ["?category=30900&priceTo=20000", "?category=30900&price-to=20000", "?category=30900&cenaDo=20000", "?category=30900&priceFrom=0&priceTo=20000&sort=price"]:
    tt = get("https://www.autobazar.eu/vysledky-nove-auta/" + q)
    p2 = nxt(tt).get("props", {}).get("pageProps", {})
    ds = p2.get("initialRecords", {}).get("data", [])
    print("  ", q, "total", p2.get("initialRecords", {}).get("total"), "prices", [d.get("finalPrice") for d in ds[:8]])
d = get("https://www.autobazar.eu/detail-nove-auto/peugeot-3008-business-hybrid-145k-e-dcs6/AmF_toQd7UB/")
adv = nxt(d).get("props", {}).get("pageProps", {}).get("advertisement", {})
print("ADV KEYS:", sorted(adv.keys()) if isinstance(adv, dict) else type(adv))
for k in ("user", "seller", "company", "dealer", "contact", "client", "subject"):
    if isinstance(adv, dict) and k in adv:
        print("  ", k, json.dumps(adv[k], ensure_ascii=False)[:900])
print("  adv sample:", json.dumps({k: v for k, v in adv.items() if not isinstance(v, (list, dict))}, ensure_ascii=False)[:1500] if isinstance(adv, dict) else "")

# Kia listing (Inertia/Livewire?)
t = get("https://www.kiaihned.sk/vozidla?model=K4")
m = re.search(r'data-page="([^"]+)"', t)
if m:
    import html
    pg = json.loads(html.unescape(m.group(1)))
    print("KIA page props:", list(pg.get("props", {}).keys()))
    print(json.dumps(pg.get("props"), ensure_ascii=False)[:2500])
else:
    snip(t, r"€", 2, 1200)
    print("kia api-ish:", sorted(set(re.findall(r'["\'](/api/[^"\']+|/vozidla[^"\']*\?[^"\']*page[^"\']*)["\']', t)))[:10])

# Hyundai listing pagination
t = get("https://skladove.hyundai.sk/ponuky/_sort/cheapest")
print("hyundai found:", re.findall(r"Nájdených vozidiel:\s*(\d+)", t), "cards:", len(re.findall(r'class="o-bx__header__name__title', t)))
print("hy paging:", sorted(set(re.findall(r'(?:href|data-url|data-href)="([^"]*(?:strana|page|ponuky/[^"]*\d)[^"]*)"', t)))[:10])
snip(t, r"o-bx__spec__list", 1, 1600)
t2 = get("https://skladove.hyundai.sk/ponuky/_sort/cheapest/_page/2")
print("page2 cards:", len(re.findall(r'class="o-bx__header__name__title', t2)))
t3 = get("https://skladove.hyundai.sk/ponuky/_sort/cheapest?page=2")
print("page=2 cards:", len(re.findall(r'class="o-bx__header__name__title', t3)), re.findall(r'href="/ponuka/[^"]+"', t3)[:3])

# Stellantis listing cards + pagination
t = get("https://peugeot.skladovevozidla.sk/skladove-vozidla/vysledky-hladania")
print("pg cards:", len(re.findall(r"detail-vozidla", t)), "paging:", sorted(set(re.findall(r'href="([^"]*page=\d+[^"]*)"', t)))[:6])
snip(t, r"EUR s DPH", 1, 2200)
t = get("https://peugeot.skladovevozidla.sk/skladove-vozidla/vysledky-hladania?page=2")
print("pg2 cards:", len(re.findall(r"detail-vozidla", t)))

# Dacia detail
t = get("https://skladove-vozidla.dacia.sk/jogger-expression-tce-110-7-miest-v83974/")
snip(t, r"€", 3, 900)
print("dacia VIN:", re.findall(r"[A-HJ-NPR-Z0-9]{17}", t)[:3])

# Mazda listing pages
t = get("https://www.mazdaihned.sk/")
print("mazda cards:", len(re.findall(r"stock-list-item-content", t)), "paging:", sorted(set(re.findall(r'href="([^"]*(?:page|strana|first=)[^"]*)"', t)))[:6])

# Mitsubishi
t = get("https://www.mitsubishi-motors.sk/nakup-vozidla/skladove-vozidla/")
snip(t, r"zaujem-o-vozidlo/\d+", 2, 1300)
print("\nDONE")
