"""Discovery run 45: Dacia + Mazda official stock detail pages (price, list price, dealer, VIN, km)."""
import re
import time

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9"})


def get(u):
    time.sleep(1.2)
    r = S.get(u, timeout=25)
    print(f"\n===== {r.status_code} {u} ({len(r.text)//1024} kB)")
    return r.text


def snip(t, pat, n=3, w=700):
    for m in list(re.finditer(pat, t))[:n]:
        print("  …" + re.sub(r"\s+", " ", t[max(0, m.start() - w // 3): m.start() + w]) + "…")


sm = get("https://skladove-vozidla.dacia.sk/sitemap.xml")
locs = [l for l in re.findall(r"<loc>([^<]+)</loc>", sm) if re.search(r"-v\d+/$", l)]
print("dacia vehicles:", len(locs))
for u in locs[:2]:
    t = get(u)
    print("h1:", re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)[:2])
    snip(t, r"€", 6, 500)
    snip(t, r"(?i)predajca|dealer|autorizovan", 2, 500)
    print("VIN:", re.findall(r"\b[A-HJ-NPR-Z0-9]{17}\b", t)[:2], "km:", re.findall(r"(\d[\d  ]*)\s*km", t)[:3])
sm = get("https://www.mazdaihned.sk/sitemap.xml")
locs = [l for l in re.findall(r"<loc>([^<]+)</loc>", sm) if "/Mazda/" in l]
print("mazda vehicles:", len(locs))
for u in locs[:2]:
    t = get(u)
    print("h1:", re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)[:2])
    snip(t, r"Cena s DPH|ZĽAVA|Cenníková|€", 6, 500)
    print("VIN:", re.findall(r"\b[A-HJ-NPR-Z0-9]{17}\b", t)[:2], "km:", re.findall(r"(\d[\d  ]*)\s*km", t)[:3])
print("DONE")
