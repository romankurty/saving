"""Discovery run 60: Renault / Opel / Toyota / Skoda / Ford stock data endpoints."""
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
                print("   robots", host, r.status_code, [l for l in r.text.splitlines() if l.strip()][:12])
            else:
                print("   robots", host, r.status_code)
        except Exception as e:  # noqa: BLE001
            RB[host] = (None, rp)
            print("   robots", host, "ERR", e)
    st, rp = RB[host]
    return st == 404 or (st == 200 and rp.can_fetch(UA, u))


def get(u):
    if not allowed(u):
        print("  NOT ALLOWED", u)
        return ""
    time.sleep(1.0)
    try:
        r = S.get(u, timeout=30)
        print(f"  GET {u} -> {r.status_code} len {len(r.text)}")
        return r.text
    except Exception as e:  # noqa: BLE001
        print("  ERR", u, e)
        return ""


def ctx(t, pat, n=3, w=300):
    for m in list(re.finditer(pat, t))[:n]:
        print("    [", pat[:20], "]", re.sub(r"\s+", " ", t[max(0, m.start() - w // 2):m.start() + w]))


print("\n##### RENAULT")
t = get("https://ihned.renault.sk/sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", t)
print("  sitemap locs", len(locs), locs[:8], locs[-5:])
t = get("https://ihned.renault.sk/")
ctx(t, r"class=\"[^\"]*(?:car|vehicle|item|offer)[^\"]*\"", 4)
ctx(t, r"ajax|fetch\(|/api/|\.php", 5)

print("\n##### OPEL")
t = get("https://online.opel-ihned.sk/sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", t)
print("  sitemap locs", len(locs), locs[:8], locs[-5:])
t = get("https://online.opel-ihned.sk/?model_id%5B%5D=1509")
ctx(t, r"€", 6)
print("  links", sorted(set(l for l in re.findall(r'href="([^"#]+)"', t) if re.search(r"detail|vozidl|/auto|\d{4,}", l)))[:15])

print("\n##### TOYOTA")
t = get("https://www.toyota.sk/nakup-a-ponuky/ponuka-dostupnych-vozidiel")
ctx(t, r"stock|Stock|STOCK", 6, 400)
ctx(t, r"usc|USC|used-stock|new-stock|stockcar|stock-car", 4, 400)

print("\n##### SKODA")
t = get("https://www.skoda-auto.sk/apps/stock/?instancename=SVK&pagegroup=Website&salesprogram=SVK")
ctx(t, r"https://[a-z0-9.-]*(?:stock|api)[a-z0-9./-]*", 8, 260)
ctx(t, r"apiUrl|apiBase|endpoint|baseUrl", 6, 300)

print("\n##### FORD")
allowed("https://prevereneauto2.sellio.net/")
t = get("https://fordskladom.sk/category?car_state=nove&brand=Ford")
ctx(t, r"__NUXT__", 1, 2500)
js = sorted(set(re.findall(r'src="(/_nuxt/[^"]+\.js)"', t)))[:3]
print("  js", js)
print("DONE")
