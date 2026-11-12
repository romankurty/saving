"""Discovery run 50: Mazda detail pages that did not parse + Cebia guide list."""
import re
import time
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA})


def get(u):
    time.sleep(1.2)
    r = S.get(u, timeout=25)
    return r.status_code, r.text


st, sm = get("https://www.mazdaihned.sk/sitemap.xml")
urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if re.search(r"/Mazda/[^/]+/[a-z0-9]+/$", u)]
print("mazda urls", len(urls))
models = {}
for u in urls:
    models.setdefault(u.split("/")[4], []).append(u)
print({k: len(v) for k, v in models.items()})
for k, v in list(models.items())[:6]:
    if k in ("CX-6e", "MX-5", "6e"):
        continue
    st, t = get(v[0])
    print("\n=====", st, v[0], len(t))
    for pat in [r"model-price", r'"price"', r"og:title", r"predan", r"rezerv", r"€", r"seller"]:
        i = t.find(pat) if pat != "€" else t.find("€")
        print("  ", pat, i, repr(t[max(0, i - 160):i + 160]) if i >= 0 else "")

rp = urllib.robotparser.RobotFileParser("https://www.cebia.cz/robots.txt")
rp.read()
print("\ncebia sitemaps", rp.site_maps())
for smu in (rp.site_maps() or [])[:3]:
    st, t = get(smu)
    locs = re.findall(r"<loc>([^<]+)</loc>", t)
    print(smu, st, len(locs), locs[:5])
    kuf = [u for u in locs if "objem-kufru" in u]
    print("  objem-kufru", len(kuf), kuf[:40])
    subs = [u for u in locs if u.endswith(".xml")]
    for s2 in subs[:6]:
        st, t2 = get(s2)
        l2 = re.findall(r"<loc>([^<]+)</loc>", t2)
        k2 = [u for u in l2 if "objem-kufru" in u]
        print("  sub", s2, st, len(l2), "objem-kufru", len(k2), k2[:60])
print("DONE")
