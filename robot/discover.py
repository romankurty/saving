"""Discovery run 41: data structure of official SK stock platforms + autobazar.eu new cars."""
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


def robots(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in RB:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = S.get(base + "/robots.txt", timeout=20)
            st = r.status_code
            rp.parse(r.text.splitlines() if st == 200 else [])
            dis = [l.strip() for l in r.text.splitlines() if l.lower().startswith(("disallow", "user-agent", "crawl-delay", "sitemap"))][:12] if st == 200 else []
        except Exception as e:  # noqa: BLE001
            st, dis = f"ERR {type(e).__name__}", []
        RB[base] = (rp, st, dis)
        print(f"\n### {base}  robots={st}  {' | '.join(dis)}")
    rp, st, _ = RB[base]
    return rp.can_fetch(UA, url) if st == 200 else (st == 404)


def walk(o, path="", out=None, depth=0):
    """find arrays of dicts that look like car offers (have price-ish keys)"""
    out = [] if out is None else out
    if depth > 9:
        return out
    if isinstance(o, list) and o and isinstance(o[0], dict):
        keys = set().union(*[set(x.keys()) for x in o[:3] if isinstance(x, dict)])
        if any(re.search(r"price|cena|amount", k, re.I) for k in keys):
            out.append((path, len(o), sorted(keys)[:40], o[0]))
        for i, x in enumerate(o[:2]):
            walk(x, f"{path}[{i}]", out, depth + 1)
    elif isinstance(o, dict):
        for k, v in o.items():
            walk(v, f"{path}.{k}", out, depth + 1)
    return out


def probe(url, show=1500):
    if not robots(url):
        print(f"  BLOCKED by robots: {url}")
        return None
    try:
        r = S.get(url, timeout=25, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"  ERR {url}: {type(e).__name__}")
        return None
    t = r.text or ""
    print(f"  {r.status_code} {url} -> {r.url[:100]} | {len(t)//1024} kB {r.headers.get('content-type','')[:30]}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
    if m:
        try:
            j = json.loads(m.group(1))
            for path, n, keys, first in walk(j)[:4]:
                print(f"     NEXT array {path} n={n} keys={keys}")
                print("       first:", json.dumps(first, ensure_ascii=False)[:show])
        except Exception as e:  # noqa: BLE001
            print("     NEXT parse err", e)
    for ld in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', t, re.S)[:2]:
        print("     LD:", re.sub(r"\s+", " ", ld)[:500])
    apis = sorted(set(re.findall(r'["\'](/?(?:api|_next/data|wp-json)[^"\'\s]{2,120})["\']', t)))[:10]
    if apis:
        print("     api-ish:", apis)
    xs = sorted(set(re.findall(r'https?://[a-z0-9.-]+/[^"\'\s<>]{0,40}(?:api|graphql|search|json)[^"\'\s<>]{0,60}', t)))[:8]
    if xs:
        print("     ext:", xs)
    if not m:
        txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"\s+", " ", txt)
        i = txt.find("€")
        print("     text@€:", txt[max(0, i - 400): i + 400] if i >= 0 else txt[:300])
    time.sleep(1.2)
    return r


for u in [
    "https://www.autobazar.eu/vysledky-nove-auta/",
    "https://www.autobazar.eu/vysledky-nove-auta/?page=2",
    "https://www.autobazar.eu/detail-nove-auto/peugeot-3008-business-hybrid-145k-e-dcs6/AmF_toQd7UB/",
    "https://www.autovia.sk/",
    "https://skladove.hyundai.sk/ponuky/model/i30/_sort/cheapest", "https://skladove.hyundai.sk/ponuka/hyundai-i30/6091",
    "https://skladovevozidla.citroen.sk/skladove-vozidla", "https://skladovevozidla.citroen.sk/jazdene-a-predvadzacie-vozidla",
    "https://peugeot.skladovevozidla.sk/", "https://opel.skladovevozidla.sk/", "https://jeep.skladovevozidla.sk/", "https://fiat.skladovevozidla.sk/",
    "https://skladovevozidla.peugeot.sk/", "https://skladovevozidla.opel.sk/",
    "https://www.kiaihned.sk/", "https://www.mazdaihned.sk/",
    "https://skladove-vozidla.dacia.sk/?filters=status:1&limit=10", "https://skladove-vozidla.renault.sk/",
    "https://fordskladom.sk/category?car_state=nove&brand=Ford",
    "https://skladove-vozidla.vw.sk/", "https://skladove-vozidla.audi.sk/", "https://skladove-vozidla.cupraofficial.sk/", "https://skladove-vozidla.skoda.sk/",
    "https://www.mitsubishi-motors.sk/nakup-vozidla/skladove-vozidla/", "https://www.nissan.sk/vozidla/ponuky/zoznam-skladovych-vozidiel.html",
    "https://www.autobazar.sk/", "https://www.mgmotor.eu/sk-SK", "https://www.toyota.sk/nakup-a-ponuky/akciove-ponuky",
]:
    probe(u)
print("\nDONE")
