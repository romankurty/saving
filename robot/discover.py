"""Discovery run 40: Slovak new / stock / demo car sources. Robots rules + what each page offers."""
import re
import time
import urllib.parse
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.5"})
RB = {}


def robots(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in RB:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = S.get(base + "/robots.txt", timeout=20)
            st = r.status_code
            rp.parse(r.text.splitlines() if st == 200 else [])
            dis = [l.strip() for l in r.text.splitlines() if l.lower().startswith(("disallow", "user-agent", "crawl-delay"))][:14] if st == 200 else []
        except Exception as e:  # noqa: BLE001
            st, dis = f"ERR {type(e).__name__}", []
            rp.parse([])
        RB[base] = (rp, st, dis)
        print(f"\n### {base}  robots={st}  rules: {' | '.join(dis)}")
    rp, st, _ = RB[base]
    return rp.can_fetch(UA, url) if st == 200 else (st == 404)


KEY = re.compile(r'href="([^"]*(?:sklad|predvadz|predvádz|akci|cenn|stock|nove-aut|nove_voz|novych|ponuka|offer|vyhlad)[^"]*)"', re.I)


def probe(url):
    ok = robots(url)
    if not ok:
        print(f"  BLOCKED by robots: {url}")
        return
    try:
        r = S.get(url, timeout=25, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"  ERR {url}: {type(e).__name__}")
        return
    t = r.text or ""
    links = sorted(set(KEY.findall(t)))[:12]
    print(f"  {r.status_code} {url} -> {r.url[:90]} | {len(t)//1024} kB {r.headers.get('content-type','')[:25]} | ldjson={t.count('application/ld+json')} next={'__NEXT_DATA__' in t} nuxt={'__NUXT__' in t} eur={t.count('€')} api={len(set(re.findall(r'https?://[^\"\\s]*api[^\"\\s]{0,60}', t)))}")
    for l in links:
        print("     ·", l[:120])
    time.sleep(1.2)


URLS = [
    "https://www.autobazar.eu/", "https://www.autobazar.eu/vysledky-nove-auta/", "https://www.autobazar.eu/en/detail-nove-auto/skoda-kamiq-selection-15-tsi/Ab1nyVQzjK8",
    "https://skladove-vozidla.seat.sk/", "https://skladove-vozidla.skoda-auto.sk/", "https://skladove-vozidla.volkswagen.sk/", "https://skladove-vozidla.cupra.sk/",
    "https://www.skoda-auto.sk/", "https://www.skoda-auto.sk/modely/skladove-vozidla", "https://webapps.skoda-auto.sk/Cenniky-a-katalogy/cenniky/Skoda_Scala-FL_cennik.pdf",
    "https://www.hyundai.sk/", "https://www.hyundai.com/sk/", "https://www.kia.com/sk/", "https://www.kia.sk/",
    "https://www.toyota.sk/", "https://www.dacia.sk/", "https://www.renault.sk/", "https://www.volkswagen.sk/",
    "https://www.peugeot.sk/", "https://www.citroen.sk/", "https://www.opel.sk/", "https://www.ford.sk/", "https://www.mazda.sk/",
    "https://www.suzuki.sk/", "https://auto.suzuki.sk/", "https://www.mgmotor.sk/", "https://www.mg.sk/", "https://www.nissan.sk/", "https://www.mitsubishi-motors.sk/",
    "https://www.fiat.sk/", "https://www.seat.sk/", "https://www.cupraofficial.sk/", "https://www.byd.com/sk/", "https://www.honda.sk/", "https://www.jeep.sk/",
    "https://www.autopalace.sk/skladove-vozidla/typy_nove/", "https://www.finalcd.sk/ponuka/nove_vozidla/", "https://autocentrum.sk/auta-skladom/nove-auta-skladom/",
    "https://auto-impex.sk/", "https://www.autotest.sk/najvacsie-zlavy-na-nove-auta-na-slovensku-top-10-skladovych-aut-z-kazdej-znacky/",
]
for u in URLS:
    probe(u)
print("\nDONE")
