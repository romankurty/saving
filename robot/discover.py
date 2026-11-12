"""Discovery run 47: Stellantis 'nove-vozidla' listing card layout (Jeep/Fiat/Alfa) — where is the dealer?"""
import re
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"})
for base in ["https://jeep.skladovevozidla.sk/nove-vozidla/vysledky-hladania", "https://peugeot.skladovevozidla.sk/skladove-vozidla/vysledky-hladania"]:
    time.sleep(1.2)
    t = S.get(base, timeout=25).text
    links = [m.start() for m in re.finditer(r'href="https://[^"]*detail-vozidla/[^"]+"', t)]
    print("\n=====", base, "links", len(links))
    if len(links) > 3:
        a, b = links[1], links[3]
        seg = re.sub(r"\s+", " ", re.sub(r"<!--.*?-->", "", t[a - 2500: b + 200], flags=re.S))
        seg = re.sub(r' class="[^"]*"', "", seg)
        print(seg[:6000])
    time.sleep(1.2)
d = S.get("https://jeep.skladovevozidla.sk/nove-vozidla/detail-vozidla/jeep/avenger/suv/adventure-12t-100k-mt6-fwd/93940", timeout=25).text
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", " ", d, flags=re.S)))
for k in ["Predajca", "predajca", "s.r.o", "a.s.", "Kontakt"]:
    i = txt.find(k)
    if i >= 0:
        print("\nDETAIL", k, ":", txt[max(0, i - 200): i + 300])
print("DONE")
