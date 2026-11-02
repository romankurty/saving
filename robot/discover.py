"""Discovery run 16: how the Kaufland leaflet front-end asks for regionalized flyers.

Personal, non-commercial use. One slow pass, identifies itself honestly.
"""
import json
import re
import time
import urllib.parse

import requests

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
session = requests.Session()
session.headers.update({"User-Agent": UA})


def get(url, accept_json=False):
    time.sleep(3)
    r = session.get(url, timeout=40, headers={"Accept": "application/json"} if accept_json else {})
    print(f"[{r.status_code}] {url[:170]} ({len(r.content)} B)")
    return r


k = get("https://leaflets.kaufland.com/cs-CZ")
m = re.search(r'src="(https://kaufland\.leaflets\.schwarz/assets/[^"]+\.js)"', k.text)
js = get(m.group(1)).text if m else ""
calls = sorted(set(re.findall(r'gN\(tf\(\),\s*"([a-z_/-]+)"', js)) | set(re.findall(r'const r="([a-z_/-]+)",i=new URLSearchParams', js)))
print("api names:", calls)
for kw in ("region", "store_id", "regional", "zip", "postal", "storeId", "regionCode"):
    hits = [mm.start() for mm in re.finditer(kw, js)][:4]
    for i in hits:
        print(f"  [{kw}] …{js[max(0, i - 220): i + 220]}…".replace("\n", " "))
print("--- strings with 'v4' or endpoint-like names ---")
print(sorted(set(re.findall(r'"((?:regions?|stores?|overview|flyers?|search|regionalized)[a-z_/-]*)"', js)))[:40])

for path in ("regions?client_locale=kaufland%2Fcs-CZ", "stores?client_locale=kaufland%2Fcs-CZ", "region?client_locale=kaufland%2Fcs-CZ",
             "overview?client_locale=kaufland%2Fcs-CZ&region_id=0&region_code=0"):
    r = get("https://endpoints.leaflets.schwarz/v4/" + path, accept_json=True)
    print("   ", r.text[:600].replace("\n", " "))
