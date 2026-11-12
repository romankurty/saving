"""Discovery run 52: where official stock pages state boot volume; robots of spec sites; Mazda condition fields."""
import json
import re
import time
import urllib.robotparser

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


PAT = re.compile(r"batožin|batozin|kufr|zavazadl|trunk|luggage|boot|objem", re.I)
for u in ["https://skladove-vozidla.dacia.sk/sandero-expression-eco-g-120-v93117/",
          "https://peugeot.skladovevozidla.sk/skladove-vozidla/detail-vozidla/peugeot/208/hatchback/peugeot-208-style-turbo-100-bvm6/118010",
          "https://skladove.hyundai.sk/ponuka/hyundai-i20/2818",
          "https://www.kiaihned.sk/vozidla/KNAB351B4TT494263/picanto-10-gdi-m5-silver",
          "https://www.mazdaihned.sk/Mazda/CX-30/kl6xz087/",
          "https://www.mitsubishi-motors.sk/nakup-vozidla/skladove-vozidla/zaujem-o-vozidlo/8260-mitsubishi-nov-asx-1-3-di-t-mild-hybrid/"]:
    st, t = get(u)
    tt = txt(re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S))
    hits = [tt[max(0, m.start() - 80):m.start() + 120] for m in PAT.finditer(tt)][:6]
    print("\n=====", st, u)
    for h in hits:
        print("   ", h)
    if "mazda" in u:
        m = re.search(r"condition=\d+[^\"]{0,400}", t)
        print("  mazda fields:", re.findall(r"\b(car_status|state_id|condition|tachometr|made_date|price|book_price|price_leasing)=([^,]+)", t)[:12])

st, t = get("https://www.autobazar.eu/detail-nove-auto/citroen-c3-max-pure-tech/AmWFvnpNQCL/")
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
if m:
    ad = json.loads(m.group(1))["props"]["pageProps"].get("advertisement", {})
    def walk(d, p=""):
        if isinstance(d, dict):
            for k, v in d.items():
                if re.search(r"trunk|luggage|boot|volume|kufr|batoz|capacity|seat|door|length|width", k, re.I):
                    print("  ab key", p + k, str(v)[:120])
                walk(v, p + k + ".")
        elif isinstance(d, list):
            for i, v in enumerate(d[:3]):
                walk(v, p + str(i) + ".")
    walk(ad)
    print("  ab top keys", sorted(ad.keys())[:80])

for site, paths in [("https://www.adac.de", ["/rund-ums-fahrzeug/autokatalog/marken-modelle/skoda/octavia/"]),
                    ("https://www.auto-data.net", ["/sk/skoda-octavia-combi-iv-generation-8159"]),
                    ("https://www.ultimatespecs.com", ["/car-specs/Skoda/"]),
                    ("https://www.auto-mobil.sk", ["/"]),
                    ("https://www.autoweek.nl", ["/"]),
                    ("https://www.autoevolution.com", ["/cars/"])]:
    rp = urllib.robotparser.RobotFileParser(site + "/robots.txt")
    try:
        rp.read()
        print("\nrobots", site, [(p, rp.can_fetch(UA, site + p)) for p in paths], "sitemaps", (rp.site_maps() or [])[:3])
    except Exception as e:  # noqa: BLE001
        print("robots", site, "error", e)
st, t = get("https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/skoda/octavia/")
print("\nadac", st, len(t), [txt(t[max(0, m.start() - 100):m.start() + 160]) for m in re.finditer(r"Kofferraum", t)][:4])
print("DONE")
