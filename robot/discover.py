"""Discovery run 49: Cebia table layouts."""
import re
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"})
for u in ["https://www.cebia.cz/pruvodce/objem-kufru-kia-ceed", "https://www.cebia.cz/pruvodce/objem-kufru-hyundai-i30", "https://www.cebia.cz/pruvodce/objem-kufru-skoda-octavia", "https://www.cebia.cz/pruvodce/objem-kufru-peugeot-208", "https://www.cebia.cz/pruvodce/objem-kufru-skoda-fabia"]:
    time.sleep(1.2)
    r = S.get(u, timeout=25)
    print("\n=====", r.status_code, u)
    for i, tab in enumerate(re.findall(r"<table.*?</table>", r.text, re.S)[:2]):
        rows = re.findall(r"<tr.*?</tr>", tab, re.S)
        print(" table", i, "rows", len(rows))
        for tr in rows[:5]:
            print("   ", [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)])
    h = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", r.text, re.S)[:8]
    print(" headings:", [re.sub(r"<[^>]+>", "", x).strip()[:60] for x in h])
print("DONE")
