"""Discovery run 42: exact fields (seller, VIN, list price, discount, instalments) per source."""
import json
import re
import time
import urllib.parse
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.5"})
RB = {}


def ok(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in RB:
        rp = urllib.robotparser.RobotFileParser()
        r = S.get(base + "/robots.txt", timeout=20)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        RB[base] = (rp, r.status_code)
    rp, st = RB[base]
    return rp.can_fetch(UA, url) if st == 200 else st == 404


def get(url):
    if not ok(url):
        print("BLOCKED", url)
        return ""
    time.sleep(1.2)
    try:
        r = S.get(url, timeout=25)
        print(f"\n===== {r.status_code} {url} ({len(r.text)//1024} kB)")
        return r.text
    except Exception as e:  # noqa: BLE001
        print("ERR", url, e)
        return ""


def nxt(t):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
    return json.loads(m.group(1)) if m else {}


def snip(t, pat, n=2, w=900):
    for m in list(re.finditer(pat, t))[:n]:
        s = t[max(0, m.start() - w // 3): m.start() + w]
        print("  …" + re.sub(r"\s+", " ", s) + "…")


# --- autobazar.eu
t = get("https://www.autobazar.eu/vysledky-nove-auta/")
j = nxt(t)
pp = j.get("props", {}).get("pageProps", {})
print("pageProps keys:", list(pp.keys()))
ir = pp.get("initialRecords", {})
print("initialRecords keys:", list(ir.keys()), {k: ir[k] for k in ir if k != "data"})
print("RECORD:", json.dumps(ir.get("data", [{}])[0], ensure_ascii=False)[:3500])
hrefs = sorted(set(re.findall(r'href="(/vysledky-nove-auta/[^"]+)"', t)))
print("filter hrefs:", hrefs[:25])
q = j.get("query") or {}
print("query:", q, "page:", j.get("page"))
d = get("https://www.autobazar.eu/detail-nove-auto/peugeot-3008-business-hybrid-145k-e-dcs6/AmF_toQd7UB/")
dj = nxt(d)
dpp = dj.get("props", {}).get("pageProps", {})
print("detail pageProps keys:", list(dpp.keys()))
txt = json.dumps(dpp, ensure_ascii=False)
for k in ["vin", "VIN", "seller", "dealer", "company", "user", "ico", "advertiser", "contact"]:
    for m in list(re.finditer(r'"([^"]*%s[^"]*)"\s*:\s*("[^"]{0,80}"|\{[^{}]{0,300}\}|\d+|null|true|false)' % k, txt))[:3]:
        print("   ", m.group(0)[:300])

# --- Hyundai official
t = get("https://skladove.hyundai.sk/ponuky/model/i30/_sort/cheapest")
snip(t, r"/ponuka/hyundai-", 2, 1400)
print("pagination:", sorted(set(re.findall(r'href="([^"]*(?:page|strana|_page)[^"]*)"', t)))[:8])
t = get("https://skladove.hyundai.sk/ponuka/hyundai-i30/6091")
snip(t, r"Akciová ponuka", 1, 2500)
print("VIN:", re.findall(r"VIN[^<]{0,40}<[^>]*>[^<]{0,40}", t)[:3])

# --- Stellantis platform
t = get("https://peugeot.skladovevozidla.sk/skladove-vozidla")
snip(t, r"EUR s DPH", 1, 1800)
print("detail links:", sorted(set(re.findall(r'href="(https?://peugeot\.skladovevozidla\.sk/[^"]*detail-vozidla[^"]*)"', t)))[:5])
sm = get("https://peugeot.skladovevozidla.sk/sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
print("sitemap locs:", len(locs), locs[:3], [l for l in locs if "detail" in l][:3])
det = [l for l in locs if "detail-vozidla" in l]
if det:
    t = get(det[0])
    snip(t, r"EUR s DPH", 2, 1500)
    print("VIN:", re.findall(r"VIN[^<]{0,30}(?:<[^>]*>\s*){0,3}[A-HJ-NPR-Z0-9]{17}", t)[:2])
    snip(t, r"[Ss]plátk|RPMN|akontác", 2, 900)

# --- Kia official
sm = get("https://kiaihned.sk/sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
print("kia sitemap:", len(locs), locs[:5])
veh = [l for l in locs if "/vozidla/" in l]
print("vehicle urls:", len(veh), veh[:3])
if veh:
    t = get(veh[0])
    snip(t, r"€", 2, 1500)
    snip(t, r"[Ss]plátk|RPMN|akontác|[Ff]inanc", 2, 700)
    print("ldjson:", [re.sub(r"\s+", " ", x)[:700] for x in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', t, re.S)][:2])

# --- Mazda official
sm = get("https://www.mazdaihned.sk/sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
print("mazda sitemap:", len(locs), locs[:5])
veh = [l for l in locs if "/Mazda/" in l]
if veh:
    t = get(veh[0])
    snip(t, r"Cena s DPH", 1, 1500)

# --- Dacia official
sm = get("https://skladove-vozidla.dacia.sk/sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
print("dacia sitemap:", len(locs), locs[:6])
t = get("https://skladove-vozidla.dacia.sk/?filters=status:1&limit=10")
snip(t, r"€", 3, 900)
print("dacia links:", sorted(set(re.findall(r'href="([^"]*(?:vozidl|vehicle|detail)[^"]*)"', t)))[:8])

# --- Mitsubishi official
t = get("https://www.mitsubishi-motors.sk/nakup-vozidla/skladove-vozidla/")
snip(t, r"zaujem-o-vozidlo", 1, 1500)

# --- Škoda + Toyota authorised dealer lists
for u in ["https://www.skoda-auto.sk/predajcovia", "https://www.skoda-auto.sk/vyhladavanie-predajcu", "https://www.toyota.sk/predajne-a-servisne-miesta",
          "https://www.skoda-auto.sk/ponuka/akcie", "https://www.skoda-auto.sk/ponuka/financovanie"]:
    t = get(u)
    tx = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S)
    print("  text:", re.sub(r"\s+", " ", tx)[:900])
print("\nDONE")
