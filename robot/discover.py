"""Discovery run 53: ADAC Autokatalog structure (boot volume per model)."""
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


st, t = get("https://www.adac.de/sitemap_index.xml")
sms = re.findall(r"<loc>([^<]+)</loc>", t)
print("index", st, len(sms), sms[:30])
auto = [s for s in sms if "auto" in s.lower() or "katalog" in s.lower() or "vehicle" in s.lower()]
print("auto sitemaps", auto[:20])
cand = []
for s in (auto or sms)[:6]:
    st, t2 = get(s)
    locs = re.findall(r"<loc>([^<]+)</loc>", t2)
    k = [u for u in locs if "autokatalog/marken-modelle" in u]
    print(" ", s, st, len(locs), "autokatalog", len(k), k[:8])
    cand += k
oc = [u for u in cand if "/skoda/octavia" in u][:10]
print("octavia urls", oc)
st, t = get("https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/skoda/octavia/")
links = sorted(set(re.findall(r'href="(/rund-ums-fahrzeug/autokatalog/marken-modelle/skoda/octavia/[^"#?]+)"', t)))
print("model page links", len(links), links[:25])
for u in (oc[-1:] or []) + ["https://www.adac.de" + l for l in links[:2]]:
    st, t = get(u)
    i = t.find("Kofferraum")
    print("\n=====", st, u, len(t), "Kofferraum at", i)
    for m in list(re.finditer(r"Kofferraum", t))[:5]:
        print("   ", txt(t[max(0, m.start() - 200):m.start() + 300])[:260])
    sub = sorted(set(re.findall(r'href="(/rund-ums-fahrzeug/autokatalog/marken-modelle/[^"#?]+)"', t)))
    print("  sublinks", len(sub), sub[:15])
print("DONE")
