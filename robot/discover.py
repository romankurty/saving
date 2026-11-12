"""Discovery run 48: why Cebia boot-space pages give no table."""
import re
import time
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8"})
r = S.get("https://www.cebia.cz/robots.txt", timeout=20)
print("robots", r.status_code, r.text[:800])
rp = urllib.robotparser.RobotFileParser()
rp.parse(r.text.splitlines())
for u in ["https://www.cebia.cz/pruvodce/objem-kufru-dacia-duster", "https://www.cebia.cz/pruvodce/objem-kufru-skoda-octavia", "https://www.cebia.cz/pruvodce/objem-kufru-kia-ceed"]:
    print("can_fetch", rp.can_fetch(UA, u), u)
    time.sleep(1.2)
    t = S.get(u, timeout=25)
    print(t.status_code, len(t.text), "table" in t.text, t.text.count("<table"), t.headers.get("content-type"))
    i = t.text.find("517") if "duster" in u else t.text.find("litr")
    print(re.sub(r"\s+", " ", t.text[max(0, i - 1500): i + 800]))
print("DONE")
