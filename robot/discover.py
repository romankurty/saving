"""Discovery run 58: price-history fields on autobazar; more brand stock sites; second portal."""
import json
import re
import time
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9"})


def get(u):
    time.sleep(1.0)
    try:
        r = S.get(u, timeout=25)
        return r.status_code, r.text, r.url
    except Exception as e:  # noqa: BLE001
        return None, str(e), u


# 1) autobazar: which fields carry dates / previous prices
st, t, _ = get("https://www.autobazar.eu/vysledky-nove-auta/?category=30900&priceFrom=14000&priceTo=15000")
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
recs = json.loads(m.group(1))["props"]["pageProps"]["initialRecords"]["data"] if m else []
if recs:
    r0 = recs[0]
    print("LISTING KEYS", sorted(r0.keys()))
    for k, v in r0.items():
        if re.search(r"price|date|time|created|updated|publish|history|discount|old|top|renew", k, re.I):
            print("  ", k, json.dumps(v, ensure_ascii=False)[:200])
    url = "https://www.autobazar.eu" + (r0.get("url") or r0.get("detailUrl") or "")
    print("detail url field", {k: v for k, v in r0.items() if isinstance(v, str) and "/detail" in v})
    du = next((v for v in r0.values() if isinstance(v, str) and "/detail" in v), None)
    if du:
        st, t2, _ = get(du if du.startswith("http") else "https://www.autobazar.eu" + du)
        m2 = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t2, re.S)
        if m2:
            pp = json.loads(m2.group(1))["props"]["pageProps"]
            ad = pp.get("advertisement", {})
            print("DETAIL KEYS", sorted(ad.keys()))
            for k, v in ad.items():
                if re.search(r"price|date|time|created|updated|publish|history|discount|old|renew", k, re.I):
                    print("  ", k, json.dumps(v, ensure_ascii=False)[:300])
            print("pageProps keys", sorted(pp.keys()))
            s = json.dumps(pp, ensure_ascii=False)
            for mm in list(re.finditer(r"priceHistor|histor|zmena ceny|zníž", s, re.I))[:5]:
                print("   hist ctx:", s[max(0, mm.start() - 150):mm.start() + 250])

# 2) brand sites: robots + links to stock pages
sites = ["https://www.renault.sk", "https://skladove-vozidla.renault.sk", "https://www.skoda-auto.sk", "https://www.toyota.sk", "https://www.opel.sk",
         "https://opel.skladovevozidla.sk", "https://www.ford.sk", "https://www.nissan.sk", "https://www.mgmotor.sk", "https://www.mgmotor.eu/sk-SK",
         "https://www.byd.com/sk", "https://www.honda.sk", "https://www.mercedes-benz.sk", "https://www.volvocars.com/sk", "https://www.bmw.sk",
         "https://www.seat.sk", "https://www.cupraofficial.sk", "https://www.mini.sk", "https://www.subaru.sk", "https://www.omodajaecoo.sk",
         "https://www.leapmotor.sk", "https://www.lexus.sk", "https://www.jaguar.sk", "https://www.porsche.sk",
         "https://www.autovia.sk", "https://www.autoscout24.sk", "https://www.sauto.cz", "https://www.autobazar.sk", "https://www.mobile.de"]
for base in sites:
    host = re.match(r"https://[^/]+", base).group(0)
    rp = urllib.robotparser.RobotFileParser()
    st, rt, _ = get(host + "/robots.txt")
    if st == 200:
        rp.parse(rt.splitlines())
    ok = (st == 404) or (st == 200 and rp.can_fetch(UA, base + "/"))
    st2, t, final = get(base + "/") if ok else (None, "", base)
    links = sorted(set(l for l in re.findall(r'href="([^"]+)"', t) if re.search(r"sklad|ihned|ihneď|stock|predvadz|na-predaj|dostupn|ready|okamzit", l, re.I)))[:12]
    print(f"\n## {base} robots={st} allowed={ok} home={st2} final={final}")
    print("   ", links)
    if st == 200:
        dis = [l for l in rt.splitlines() if l.lower().startswith(("disallow", "user-agent"))][:10]
        print("    robots:", dis)
print("DONE")
