"""Discovery run 54: ADAC generation pages - embedded version data with boot volume?"""
import json
import re
import time

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA})


def get(u):
    time.sleep(1.2)
    r = S.get(u, timeout=30)
    return r.status_code, r.text


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


st, sm = get("https://www.adac.de/sitemaps/sitemap-autokatalog.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
B = "https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/"
for bm in ["skoda/octavia", "kia/sportage", "dacia/sandero", "hyundai/i20", "toyota/corolla", "mg/zs"]:
    gens = sorted({u[len(B):].split("/")[2] for u in locs if u.startswith(B + bm + "/") and len(u[len(B):].strip("/").split("/")) >= 3})
    print("\n#####", bm, "generations", gens)
    if not gens:
        continue
    g = gens[-1]
    st, t = get(B + bm + "/" + g + "/")
    print("  gen page", g, st, len(t))
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", t, re.S)
    big = sorted(scripts, key=len, reverse=True)[:3]
    for sc in big:
        print("  script len", len(sc), sc[:160].replace("\n", " "))
    for m in list(re.finditer(r"trunkVolume", t))[:6]:
        print("   tv:", t[max(0, m.start() - 300):m.start() + 200].replace("\n", " ")[:500])
    vers = sorted({u for u in locs if u.startswith(B + bm + "/" + g + "/") and u.rstrip("/").split("/")[-1].isdigit()})
    print("  versions in sitemap", len(vers), vers[-3:])
    if bm in ("skoda/octavia", "kia/sportage") and vers:
        st, t2 = get(vers[-1])
        d = re.search(r'<meta name="description" content="([^"]+)"', t2)
        print("  ver", st, d.group(1)[:200] if d else None)
        for m in list(re.finditer(r"Kofferraumvolumen", t2))[:3]:
            print("    ", txt(t2[max(0, m.start() - 40):m.start() + 200])[:200])
        for m in list(re.finditer(r'"trunkVolume[^"]*"\s*:', t2))[:4]:
            print("    json", t2[m.start():m.start() + 80])
print("DONE")
