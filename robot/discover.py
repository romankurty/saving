"""Discovery run 62: Skoda stock app + Toyota available-cars page: where does the car list come from?"""
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
            print("   robots", host, r.status_code, [l for l in r.text.splitlines() if l.strip()][:8] if r.status_code == 200 else "")
        except Exception:  # noqa: BLE001
            RB[host] = (None, rp)
    st, rp = RB[host]
    return st == 404 or (st == 200 and rp.can_fetch(UA, u))


def get(u):
    if not allowed(u):
        print("  NOT ALLOWED", u)
        return ""
    time.sleep(1.0)
    try:
        r = S.get(u, timeout=30)
        print(f"  GET {u[:140]} -> {r.status_code} len {len(r.text)}")
        return r.text if r.status_code == 200 else ""
    except Exception as e:  # noqa: BLE001
        print("  ERR", e)
        return ""


def urls_in(t):
    return sorted(set(re.findall(r"https?://[a-zA-Z0-9.-]+(?:/[a-zA-Z0-9._~%/{}:-]*)?", t)))


print("\n##### SKODA")
t = get("https://www.skoda-auto.sk/apps/stock/?instancename=SVK&pagegroup=Website&salesprogram=SVK")
scripts = sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', t)))
print("  scripts", scripts[:30])
mods = sorted(set(re.findall(r'data-module="([^"]+)"', t)))
print("  modules", mods)
for m in re.finditer(r'data-props="([^"]{0,4000})', t):
    p = m.group(1).replace("&quot;", '"')
    if re.search(r"stock|Stock|api|Api", p):
        print("  props:", p[:1500])
for u in [u for u in urls_in(t) if re.search(r"stock|api|graphql|sdrive|vehicle", u, re.I)][:25]:
    print("   url", u)
for sc in [s for s in scripts if re.search(r"stock|app|main|bundle", s, re.I)][:4]:
    js = get(sc if sc.startswith("http") else "https://www.skoda-auto.sk" + sc)
    for u in [u for u in urls_in(js) if re.search(r"stock|api|vehicle|search", u, re.I)][:20]:
        print("   js url", u)

print("\n##### TOYOTA")
t = get("https://www.toyota.sk/nakup-a-ponuky/ponuka-dostupnych-vozidiel")
for m in re.finditer(r'<div[^>]+class="[^"]*(?:usc|stock|car-filter|vehicle)[^"]*"[^>]*>', t, re.I):
    print("  div", m.group(0)[:400])
for m in re.finditer(r'"(?:apiUrl|uscUrl|uscApi|stockApi|uscEnv|uscBaseUrl|uscApiUrl|vehicleApi)"\s*:\s*"([^"]+)"', t):
    print("  cfg", m.group(0)[:300])
for u in [u for u in urls_in(t) if re.search(r"usc|stock|vehicle|search|api", u, re.I)][:30]:
    print("   url", u)
print("DONE")
