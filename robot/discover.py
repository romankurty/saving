"""Discovery run 59: structure of Renault / Toyota / Skoda / Opel / Ford / Nissan stock pages, autobazar.sk."""
import re
import time
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9"})
RB = {}


def allowed(u):
    host = re.match(r"https?://[^/]+", u).group(0)
    if host not in RB:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = S.get(host + "/robots.txt", timeout=20)
            RB[host] = (r.status_code, rp)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                print("   robots", host, [l for l in r.text.splitlines() if l.strip()][:14])
        except Exception as e:  # noqa: BLE001
            RB[host] = (None, rp)
    st, rp = RB[host]
    return st == 404 or (st == 200 and rp.can_fetch(UA, u))


def show(u, pats=(r"€", r"api", r"\.json", r"graphql", r"__NEXT_DATA__|__NUXT__|window\.__|data-props|application/json")):
    ok = allowed(u)
    print(f"\n##### {u} allowed={ok}")
    if not ok:
        return ""
    time.sleep(1.0)
    try:
        r = S.get(u, timeout=30)
    except Exception as e:  # noqa: BLE001
        print("  ERR", e)
        return ""
    t = r.text
    print("  status", r.status_code, "final", r.url, "len", len(t))
    for p in pats:
        hits = [m.start() for m in re.finditer(p, t)][:3]
        for h in hits:
            print("  [", p[:12], "]", re.sub(r"\s+", " ", t[max(0, h - 160):h + 200])[:360])
    links = sorted(set(re.findall(r'href="([^"#]{8,})"', t)))
    print("  links sample", [l for l in links if re.search(r"detail|vozid|auto|model|car|offer|ponuk", l, re.I)][:20])
    return t


show("https://ihned.renault.sk/")
show("https://ihned.renault.sk/?filters=status:1&limit=10")
show("https://www.toyota.sk/nakup-a-ponuky/ponuka-dostupnych-vozidiel")
show("https://clg.skoda-auto.com/api/link?bid=654&culture=sk-SK&instanceName=SVK&pageGroup=Website&salesProgram=SVK&tool=StockAndUsedCars")
show("https://online.opel-ihned.sk/")
show("https://fordskladom.sk/category?car_state=nove&brand=Ford")
show("https://www.nissan.sk/vozidla/ponuky/zoznam-skladovych-vozidiel.html")
show("https://www.autobazar.sk/")
print("DONE")
