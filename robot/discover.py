"""Discovery run 51: Mazda price block + Cebia guide index."""
import re
import time

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA})


def get(u):
    time.sleep(1.2)
    r = S.get(u, timeout=25)
    return r.status_code, r.text


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


for u in ["https://www.mazdaihned.sk/Mazda/CX-30/kl6xz087/", "https://www.mazdaihned.sk/Mazda/CX-30/mmpfjys0kzg/", "https://www.mazdaihned.sk/Mazda/CX-5/"]:
    st, t = get(u)
    print("\n=====", st, u)
    i = t.find('class="sale"')
    print("  SALE:", txt(t[i:i + 5000])[:900] if i >= 0 else None)
    for k in ["369", "poplat", "registr", "financ", "leasing", "mesa", "RPMN", "zľava", "zlava", "akci"]:
        j = t.find(k)
        print("  ", k, j, txt(t[max(0, j - 250):j + 250])[:300] if j >= 0 else "")

for u in ["https://www.cebia.cz/pruvodce", "https://www.cebia.cz/pruvodce/", "https://www.cebia.cz/pruvodce?page=2", "https://www.cebia.cz/sitemap.xml"]:
    st, t = get(u)
    links = sorted(set(re.findall(r'href="([^"]*objem-kufru[^"]*)"', t)))
    print("\n=====", st, u, len(t), "objem-kufru links", len(links), links[:50])
    print("  pager:", sorted(set(re.findall(r'href="([^"]*(?:page|strana|stranka)=\d+[^"]*)"', t)))[:10])
    print("  locs:", len(re.findall(r"<loc>", t)), re.findall(r"<loc>([^<]+)</loc>", t)[:8])
print("DONE")
