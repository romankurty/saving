"""Discovery run 56: Peugeot financing legal text (RPMN ~23 %?)."""
import re
import time

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA})


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S))).strip()


for u in ["https://peugeot.skladovevozidla.sk/skladove-vozidla/detail-vozidla/peugeot/208/hatchback/peugeot-208-style-turbo-100-bvm6/118010"]:
    time.sleep(1.2)
    t = S.get(u, timeout=30).text
    tt = txt(t)
    for m in list(re.finditer(r"RPMN|financ|mesačn|splátk|akontác|úver", tt, re.I))[:14]:
        print("  >", tt[max(0, m.start() - 300):m.start() + 500])
        print()
print("DONE")
