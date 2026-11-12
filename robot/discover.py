"""Discovery run 55: ADAC generation page Apollo state - versions + boot?"""
import json
import re
import time
from collections import Counter

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA})


def get(u):
    time.sleep(1.2)
    r = S.get(u, timeout=30)
    return r.status_code, r.text


B = "https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/"
for g in ["skoda/octavia/4generation-facelift/", "kia/sportage/nq5-facelift/"]:
    st, t = get(B + g)
    m = re.search(r"window.__APOLLO_STATE__=(\{.*?\});?\s*</script>", t, re.S)
    print("\n#####", g, st, bool(m))
    if not m:
        continue
    try:
        d = json.loads(m.group(1))
    except Exception as e:  # noqa: BLE001
        print("json err", e, m.group(1)[-200:])
        continue
    print(" typenames", Counter(v.get("__typename") for v in d.values() if isinstance(v, dict)).most_common(20))
    shown = set()
    for k, v in d.items():
        tn = v.get("__typename") if isinstance(v, dict) else None
        if tn and tn not in shown:
            shown.add(tn)
            print("  ", k, json.dumps(v, ensure_ascii=False)[:700])
    s = json.dumps(d, ensure_ascii=False)
    for mm in list(re.finditer(r"trunk|Kofferraum", s, re.I))[:8]:
        print("   trunk ctx:", s[max(0, mm.start() - 200):mm.start() + 200])
    h = re.search(r'window.__staticRouterHydrationData = JSON.parse\("(.*?)"\);', t, re.S)
    if h:
        hd = json.loads(json.loads('"' + h.group(1) + '"'))
        print(" hydration", json.dumps(hd, ensure_ascii=False)[:1500])
print("DONE")
