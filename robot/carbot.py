"""Car offer robot — Slovak market, new + stock + demo passenger cars.

Personal, non-commercial use. One slow pass per run, honest User-Agent, robots.txt respected
(a site that forbids robots or can't be reached is skipped and reported as not covered).

Sources
  official brand stock sites (importer platforms — authorised dealers only):
    Kia (kiaihned.sk), Hyundai (skladove.hyundai.sk), Stellantis platform (Peugeot, Citroën, Fiat,
    Jeep, Alfa Romeo, DS), Mitsubishi (mitsubishi-motors.sk)
  autobazar.eu new-car section: every brand, with the portal's own "authorised dealer" check per brand

Double check
  * same VIN on an official site and on autobazar.eu → "2 sources", prices compared
  * seller must be an authorised dealer of that brand (official site, or autobazar.eu's authorisation)
  * price sanity: discount vs. list price must be plausible; implausible offers are dropped

Output: auta/data/offers.json (+ auta/data/history.json for first-seen dates and price drops)
"""
import datetime as dt
import html as H
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.robotparser

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
DELAY = 1.2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "auta", "data")
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
PRICE_CAP = 50000          # keep offers up to this price (the app filters the budget)
DETAIL_BUDGET = 420        # max detail pages per run (conditions, financing, VIN) — cached between runs
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.5"})
RB = {}
STATUS = {}


def log(*a):
    print(*a, flush=True)


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in RB:
        rp = urllib.robotparser.RobotFileParser()
        st = None
        for _ in range(3):
            try:
                r = S.get(base + "/robots.txt", timeout=20)
                st = r.status_code
                if st in (200, 404):
                    rp.parse(r.text.splitlines() if st == 200 else [])
                    break
            except Exception:  # noqa: BLE001
                st = None
            time.sleep(10)
        RB[base] = (rp, st)
    rp, st = RB[base]
    if st == 404:
        return True
    return st == 200 and rp.can_fetch(UA, url)


def get(url, tries=2):
    if not allowed(url):
        log("  robots: not allowed", url)
        return None
    for i in range(tries):
        time.sleep(DELAY)
        try:
            r = S.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
            log("  HTTP", r.status_code, url)
            if r.status_code in (403, 404, 410):
                return None
        except Exception as e:  # noqa: BLE001
            log("  ERR", type(e).__name__, url)
        time.sleep(5 * (i + 1))
    return None


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def num(s):
    """'24 230 €' → 24230 ; '19 390,50' → 19390.5"""
    if s is None:
        return None
    s = H.unescape(str(s)).replace("\xa0", " ").replace(" ", " ")
    m = re.search(r"\d[\d ]*(?:[.,]\d{1,2})?", s)
    if not m:
        return None
    t = m.group(0).replace(" ", "")
    if re.search(r"[.,]\d{1,2}$", t):
        t = t[:-3].replace(".", "").replace(",", "") + "." + t[-2:] if len(t) > 3 and t[-3] in ".," else t.replace(",", ".")
    else:
        t = t.replace(".", "").replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def text(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h or "", flags=re.S)
    h = re.sub(r"<!--.*?-->", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


BODY = [("estate", r"kombi|combi|sw\b|sportswagon|touring|variant|avant|estate|break|tourer"), ("mpv", r"mpv|van\b|jogger|7 miest|7-miest|rifter|berlingo|doblo|tourneo|traveller|spacetourer|caddy|zafira|combo"),
        ("suv", r"suv|crossover|terenn|4x4|off-road"), ("hatch", r"hatchback|hatch|liftback|mestsk|\bhb\b"), ("sedan", r"sedan|limuz"), ("coupe", r"kup[eé]|coupe|kabri|cabrio|roadster|spider|fastback")]
FUEL = [("phev", r"plug-?in|phev"), ("ev", r"elektro|electric|\bev\b|e-tech electric|bev|100% elektr"), ("hybrid", r"hybrid|hev|e-tech|e-hybrid|hibrid"), ("lpg", r"lpg|cng"), ("diesel", r"diesel|nafta|tdi|crdi|hdi|dci|bluehdi|mjet|multijet|ecoblue"), ("petrol", r"benz[ií]n|tsi|tfsi|t-gdi|gdi|puretech|tce|mpi|ecoboost|turbo|benzine")]


def classify(table, s, default=None):
    n = norm(s)
    for k, pat in table:
        if re.search(pat, n):
            return k
    return default


def mild(s):
    return bool(re.search(r"mild|mhev|48v", norm(s)))


MODEL_BODY = {
    "hyundai": {"i10": "hatch", "i20": "hatch", "i30": "hatch", "bayon": "suv", "kona": "suv", "tucson": "suv", "santa fe": "suv", "ioniq 5": "suv", "ioniq 6": "sedan", "ioniq 9": "suv", "inster": "hatch", "staria": "mpv"},
    "kia": {"picanto": "hatch", "stonic": "suv", "ceed": "hatch", "xceed": "suv", "k4": "hatch", "seltos": "suv", "sportage": "suv", "niro": "suv", "sorento": "suv", "ev2": "suv", "ev3": "suv", "ev4": "hatch", "ev5": "suv", "ev6": "suv", "ev9": "suv"},
    "mitsubishi": {"asx": "suv", "colt": "hatch", "space": "hatch", "eclipse": "suv", "outlander": "suv", "grandis": "suv"},
    "peugeot": {"208": "hatch", "2008": "suv", "308": "hatch", "3008": "suv", "408": "hatch", "5008": "suv", "rifter": "mpv"},
    "citroen": {"c3 aircross": "suv", "c3": "hatch", "c4 x": "hatch", "c4": "hatch", "c5 aircross": "suv", "c5 x": "estate", "berlingo": "mpv"},
    "fiat": {"500": "hatch", "500c": "coupe", "600": "suv", "grande panda": "hatch", "panda": "hatch", "tipo": "hatch", "doblo": "mpv"},
    "jeep": {"avenger": "suv", "compass": "suv", "renegade": "suv"}, "alfa romeo": {"junior": "suv", "tonale": "suv", "stelvio": "suv", "giulia": "sedan"},
    "skoda": {"fabia": "hatch", "scala": "hatch", "kamiq": "suv", "octavia": "hatch", "karoq": "suv", "kodiaq": "suv", "superb": "sedan", "elroq": "suv", "enyaq": "suv", "epiq": "suv"},
    "volkswagen": {"polo": "hatch", "golf": "hatch", "t-cross": "suv", "taigo": "suv", "t-roc": "suv", "tiguan": "suv", "id.3": "hatch", "id.4": "suv", "id.5": "suv", "id.7": "sedan", "passat": "estate", "touran": "mpv"},
    "seat": {"ibiza": "hatch", "arona": "suv", "leon": "hatch", "ateca": "suv", "tarraco": "suv"}, "cupra": {"formentor": "suv", "born": "hatch", "leon": "hatch", "terramar": "suv", "tavascan": "suv"},
    "toyota": {"aygo": "hatch", "yaris cross": "suv", "yaris": "hatch", "corolla cross": "suv", "corolla": "hatch", "c-hr": "suv", "rav4": "suv", "bz4x": "suv", "urban cruiser": "suv", "proace city verso": "mpv"},
    "dacia": {"sandero": "hatch", "duster": "suv", "jogger": "mpv", "bigster": "suv", "spring": "hatch", "logan": "sedan"},
    "renault": {"clio": "hatch", "captur": "suv", "symbioz": "suv", "austral": "suv", "arkana": "suv", "megane": "suv", "rafale": "suv", "scenic": "suv", "5": "hatch", "4": "suv", "espace": "suv"},
    "opel": {"corsa": "hatch", "frontera": "suv", "mokka": "suv", "astra": "hatch", "grandland": "suv", "zafira": "mpv"},
    "ford": {"puma": "suv", "focus": "hatch", "kuga": "suv", "explorer": "suv", "capri": "suv", "mustang mach-e": "suv", "tourneo": "mpv"},
    "suzuki": {"swift": "hatch", "ignis": "hatch", "vitara": "suv", "s-cross": "suv", "across": "suv", "swace": "estate", "jimny": "suv"},
    "mazda": {"2": "hatch", "3": "hatch", "cx-3": "suv", "cx-30": "suv", "cx-5": "suv", "cx-60": "suv", "cx-80": "suv", "mx-30": "suv", "cx-6e": "suv", "6e": "sedan"},
    "mg": {"mg3": "hatch", "3": "hatch", "zs": "suv", "hs": "suv", "mg4": "hatch", "4": "hatch", "mg5": "estate", "s5": "suv"}, "nissan": {"micra": "hatch", "juke": "suv", "qashqai": "suv", "x-trail": "suv", "ariya": "suv", "leaf": "hatch"},
    "honda": {"jazz": "hatch", "civic": "hatch", "hr-v": "suv", "zr-v": "suv", "cr-v": "suv"}, "byd": {"dolphin": "hatch", "atto 2": "suv", "atto 3": "suv", "seal u": "suv", "seal": "sedan", "sealion": "suv"},
}
NOT_CAR = r"topolino|\bami\b|rocks-e|furgon|\bvan\b|cargo|pv5|uzitkov|úžitkov|chassis|valn[ií]k|boxer|jumper|ducato|kasten|podvozok|pick-?up|l200|ranger"


def body_of(brand, model, title, default=None):
    t = norm(title)
    if re.search(r"\bsw\b|kombi|combi|sportswagon|sports ?wagon|touring|variant|estate|tourer|\bst\b", t):
        return "estate"
    m = MODEL_BODY.get(norm(brand), {})
    for k in sorted(m, key=len, reverse=True):
        if norm(model).startswith(k) or (" " + k + " ") in (" " + t + " "):
            return m[k]
    return classify(BODY, title, default)


COND_PAT = [("fin", r"(?:plat[ií]|cena|zvyhodnen\w*|bonus)[^.]{0,80}(?:financovan|uver|leasing|lizing)|pri financovan|v pripade financovan|s financovan|financovanim cez|cez \w+ finance|hyundai finance|kia finance|skoda financial|easy financovan"),
            ("tradein", r"vykup|protiuct|stare za nove|bonus za vymenu|vymenn\w+ bonus"),
            ("company", r"\bico\b|podnikatel|odpocet dph|pre firmy|fleet|bez dph"), ("insurance", r"povinn\w+ havarijn|s havarijnym poisten")]


def conditions(s):
    n = norm(s)
    return [k for k, p in COND_PAT if re.search(p, n)]


def fin_from_text(s):
    """Pull financing terms out of a Slovak legal line: monthly, down %, months, last payment, RPMN, total paid."""
    n = H.unescape(s or "").replace("\xa0", " ")
    f = {}
    m = re.search(r"akont[áa]ci\w*\s*(?:vo v[ýy][šs]ke\s*)?(\d+(?:[.,]\d+)?)\s*%", n)
    if m:
        f["down_pct"] = float(m.group(1).replace(",", "."))
    m = re.search(r"(\d{2,3})\s*mesiac", n)
    if m:
        f["months"] = int(m.group(1))
    m = re.search(r"(?:Prv[ýy]ch\s*\d+\s*spl[áa]tok je vo v[ýy][šs]ke|mesa[čc]n[áa] spl[áa]tka(?: je)?(?: vo v[ýy][šs]ke)?|spl[áa]tka od)\s*([\d  .,]+)\s*€", n, re.I)
    if m:
        f["monthly"] = num(m.group(1))
    m = re.search(r"[Pp]osledn[áa] (?:navý[šs]en[áa] )?spl[áa]tka je vo v[ýy][šs]ke\s*([\d  .,]+)\s*€", n)
    if m:
        f["last"] = num(m.group(1))
    m = re.search(r"RPMN[^0-9]{0,30}(\d+(?:[.,]\d+)?)\s*%", n)
    if m:
        f["rpmn"] = float(m.group(1).replace(",", "."))
    m = re.search(r"[ÚU]rokov[áa] sadzba(?: je)?:?\s*(\d+(?:[.,]\d+)?)\s*%", n)
    if m:
        f["rate"] = float(m.group(1).replace(",", "."))
    m = re.search(r"celkov[áa] (?:čiastka|suma|splatn[áa] suma)[^0-9€.]{0,90}?(?:zaplati\w*|splati\w*|uhradi\w*)[^0-9€]{0,80}?([\d  .,]{4,})\s*€", n, re.I)
    if m:
        f["total"] = num(m.group(1))
    m = re.search(r"havarijn\w+ poisten\w+ je vo v[ýy][šs]ke\s*([\d  .,]+)\s*€", n)
    if m:
        f["ins_month"] = num(m.group(1))
    m = re.search(r"poisten\w+ finan[čc]nej straty je vo v[ýy][šs]ke\s*([\d  .,]+)\s*€", n)
    if m:
        f["pfs_month"] = num(m.group(1))
    return f


# ---------------------------------------------------------------- state
def load(name, default):
    try:
        with open(os.path.join(OUT, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


PREV = load("offers.json", {})
HIST = load("history.json", {})          # id -> {first, low, prices:[[date, price]]}
CACHE = load("details.json", {})         # id -> {price, fetched, vin, dealer, cond, fin, text}
OFFERS = []
detail_used = 0


def detail_due(oid, price):
    c = CACHE.get(oid)
    if not c:
        return True
    if c.get("price") != price:
        return True
    return (NOW.date() - dt.date.fromisoformat(c.get("fetched", "2000-01-01"))).days >= 7


def add(o):
    if not o.get("price") or o["price"] < 3000 or o["price"] > PRICE_CAP or not o.get("brand"):
        return
    if re.search(NOT_CAR, norm(o.get("title", "") + " " + (o.get("model") or "") + " " + (o.get("body") or ""))):
        return  # quadricycles and commercial vans are not family cars
    if not o.get("body") or o["body"] == "other":
        o["body"] = body_of(o["brand"], o.get("model") or "", o.get("title", ""), o.get("body"))
    if o.get("list") and o["list"] < o["price"]:
        o["list"] = None
    o["checked"] = NOW.isoformat(timespec="minutes")
    OFFERS.append(o)


# ---------------------------------------------------------------- Kia (official)
def kia():
    key = "kia"
    seen = set()
    for demo in (0, 1):
        for page in range(1, 200):
            q = f"https://www.kiaihned.sk/vozidla?{'predvadzacie=1&' if demo else ''}strana={page}" if page > 1 else f"https://www.kiaihned.sk/vozidla{'?predvadzacie=1' if demo else ''}"
            t = get(q)
            if not t:
                if page == 1 and not demo:
                    STATUS[key] = ("blocked", 0)
                    return
                break
            cards = re.split(r'<a class="flex flex-col items-center justify-center[^"]*" href="', t)[1:]
            new = 0
            for c in cards:
                m = re.match(r"(https://www\.kiaihned\.sk/vozidla/([A-HJ-NPR-Z0-9]{17})/[^\"]+)\"", c)
                if not m or m.group(2) in seen:
                    continue
                url, vin = m.group(1), m.group(2)
                seen.add(vin)
                new += 1
                title = H.unescape((re.search(r'alt="([^"]+)"', c) or [None, ""])[1])
                price = num((re.search(r'title-md font-kia-bold[^>]*>\s*([\d  .,]+)\s*€', c) or [None, None])[1])
                lst = num((re.search(r"line-through\">\(([\d  .,]+)\s*€\)", c) or [None, None])[1])
                monthly = num((re.search(r"od\s*([\d  .,]+)\s*€/mes", c) or [None, None])[1])
                dealer = H.unescape((re.search(r'description-md text-kia-100">\s*([^<]+?)\s*</p>\s*<p class="inline-flex', c) or [None, ""])[1])
                city = H.unescape((re.search(r"icon-pin[^>]*></i><span>([^<,]+)", c) or [None, ""])[1]).strip()
                if re.search(r"vyber si", norm(city)):
                    city = ""
                    dealer = "Sklad importéra Kia (vyberieš si predajcu)" if re.search(r"importer", norm(dealer)) else dealer
                tags = text(c)
                mm = re.match(r"Kia\s+(.+?)\s+(?:HB|SW|\d)", title + " 0")
                model_name = (mm.group(1) if mm else re.sub(r"^Kia\s+", "", title).split(" ")[0]).title().replace("Xceed", "XCeed").replace("Ev", "EV")
                model_name = re.sub(r"\s+(Hev|Phev|Hybrid|Plug-In.*)$", "", model_name, flags=re.I)
                add({"id": "kia:" + vin, "src": "kia", "off": True, "url": url, "brand": "Kia", "model": model_name, "title": title,
                     "body": body_of("Kia", model_name, title), "fuel": classify(FUEL, title, "petrol"), "mhev": mild(title),
                     "gear": "auto" if re.search(r"\b(a\d|dct\d?|\d?dct|at\d?|amt\d?|ivt|e-?cvt)\b", norm(title)) or re.search(r"\bev\d", norm(title)) else "man",
                     "cond": "demo" if demo else "new", "price": price, "list": lst, "monthly": monthly, "zero_rate": "0% úrok" in tags,
                     "dealer": dealer, "city": city, "auth": True, "vin": vin})
            if new == 0:
                break
    STATUS[key] = ("ok", len(seen))
    log("Kia:", len(seen))


def kia_details(limit=80):
    """official financing calculation (all costs, RPMN, total paid) for the cheapest Kia offers (cached)"""
    global detail_used
    used = 0
    for o in sorted([o for o in OFFERS if o["src"] == "kia"], key=lambda o: o["price"]):
        c = CACHE.get(o["id"])
        if used < limit and detail_used < DETAIL_BUDGET and detail_due(o["id"], o["price"]) and o["price"] <= 35000:
            t = get(o["url"])
            used += 1
            detail_used += 1
            if t:
                t2 = t.replace("\\/", "/")
                legal = (re.search(r'"legal_line":"(.*?)"\}', t2) or [None, ""])[1]
                try:
                    legal = json.loads('"' + legal + '"')
                except Exception:  # noqa: BLE001
                    pass
                yr = (re.search(r'"(?:model_year|year|production_year)":"?(\d{4})', t2) or [None, None])[1]
                c = {"price": o["price"], "fetched": TODAY, "fin": fin_from_text(legal), "year": yr}
                CACHE[o["id"]] = c
        if c:
            if c.get("fin"):
                o["fin"] = c["fin"]
            o["year"] = o.get("year") or c.get("year")


# ---------------------------------------------------------------- Hyundai (official)
def hyundai():
    key = "hyundai"
    n = 0
    for page in range(1, 60):
        t = get(f"https://skladove.hyundai.sk/ponuky/_sort/cheapest?strona={page}&na-strone=24")
        if not t:
            if page == 1:
                STATUS[key] = ("blocked", 0)
                return
            break
        cards = t.split('<div class="o-bx">')[1:]
        if not cards:
            break
        stop = False
        for c in cards:
            m = re.search(r'href="(/ponuka/hyundai-([a-z0-9-]+)/(\d+))"', c)
            if not m:
                continue
            model = H.unescape((re.search(r'o-bx__header__name__title[^>]*>\s*([^<]+?)\s*</a>', c) or [None, ""])[1]).replace("Hyundai ", "")
            trim = H.unescape((re.search(r'o-bx__header__name__subtitle">\s*([^<]+?)\s*</span>', c) or [None, ""])[1])
            city = H.unescape((re.search(r'h-icon-map-marker"></i><span>([^<]+)</span>', c) or [None, ""])[1])
            tag = text((re.search(r'o-bx__header__tag">(.*?)</div>', c, re.S) or [None, ""])[1])
            old = num((re.search(r'text-line-through">([^<]+)<', c) or [None, None])[1])
            pr = num((re.search(r'<strong class="text-primary">([^<]+)', c) or [None, None])[1])
            low30 = num((re.search(r"posledných 30 dní:\s*<em>([^<]+)</em>", c) or [None, None])[1])
            monthly = num((re.search(r"([\d  .,]+)\s*€(?:&nbsp;|\s)*<small>s DPH/mes", c) or [None, None])[1])
            spec = dict((text(a), text(b)) for a, b in re.findall(r"<small>(.*?)</small>\s*<span[^>]*>(.*?)</span>", c, re.S))
            ft = text((re.search(r'o-bx__footer__tags">(.*?)</div>', c, re.S) or [None, ""])[1])
            if pr and pr > PRICE_CAP:
                stop = True
            oid = "hy:" + m.group(3)
            o = {"id": oid, "src": "hyundai", "off": True, "url": "https://skladove.hyundai.sk" + m.group(1), "brand": "Hyundai", "model": model, "title": f"Hyundai {model} {trim}",
                 "body": body_of("Hyundai", model, trim + " " + model), "fuel": classify(FUEL, spec.get("Druh paliva", "") + " " + trim, "petrol"), "mhev": mild(trim),
                 "gear": "man" if "Manu" in spec.get("Prevodovka", "") else "auto", "kw": num(spec.get("Výkon")),
                 "cond": "demo" if re.search(r"PREDV|JAZD", tag.upper()) else "new", "price": pr, "list": old, "low30": low30, "monthly": monthly,
                 "dealer": None, "city": city, "auth": True, "flags": ["company"] if "Odpočet DPH" in ft and False else []}
            add(o)
            n += 1
        if stop:
            break
    STATUS[key] = ("ok", n)
    log("Hyundai:", n)


def hyundai_details(limit=60):
    global detail_used
    used = 0
    cand = sorted([o for o in OFFERS if o["src"] == "hyundai"], key=lambda o: o["price"])
    for o in cand:
        c = CACHE.get(o["id"])
        if used < limit and detail_used < DETAIL_BUDGET and detail_due(o["id"], o["price"]):
            t = get(o["url"])
            detail_used += 1
            used += 1
            if t:
                desc = text((re.search(r'vdp__description__content">(.*?)</div>', t, re.S) or [None, ""])[1])
                dealer = text((re.search(r"(?:Predajca|Dealer)</dt>\s*<dd>(.*?)</dd>", t, re.S) or [None, ""])[1])
                if not dealer:
                    dealer = text((re.search(r'vdp__dealer[^>]*>.*?<(?:h\d|strong)[^>]*>(.*?)</', t, re.S) or [None, ""])[1])
                vin = (re.search(r"VIN</dt>\s*<dd>\s*([A-HJ-NPR-Z0-9]{17})", t) or [None, None])[1]
                yr = (re.search(r"Rok výroby</dt>\s*<dd>\s*(\d{4})", t) or [None, None])[1]
                km = num((re.search(r"(?:Najazden|Stav tachometra)[^<]*</dt>\s*<dd>([^<]+)", t) or [None, None])[1])
                c = {"price": o["price"], "fetched": TODAY, "dealer": dealer[:80], "vin": vin, "cond": conditions(desc), "year": yr, "km": km, "text": desc[:600]}
                CACHE[o["id"]] = c
        if c:
            o["dealer"] = re.sub(r"^Predajca\s+", "", o.get("dealer") or c.get("dealer") or "") or None
            o["vin"] = c.get("vin")
            o["flags"] = sorted(set(o.get("flags", []) + c.get("cond", [])))
            o["year"] = c.get("year")
            o["km"] = c.get("km")


# ---------------------------------------------------------------- Stellantis platform (official)
STELL = [("Peugeot", "https://peugeot.skladovevozidla.sk", ["skladove-vozidla", "jazdene-vozidla"]),
         ("Citroën", "https://skladovevozidla.citroen.sk", ["skladove-vozidla", "jazdene-a-predvadzacie-vozidla"]),
         ("Fiat", "https://fiat.skladovevozidla.sk", ["nove-vozidla", "jazdene-a-predvadzacie-vozidla"]),
         ("Jeep", "https://jeep.skladovevozidla.sk", ["nove-vozidla", "jazdene-a-predvadzacie-vozidla"]),
         ("Alfa Romeo", "https://alfaromeo.skladovevozidla.sk", ["nove-vozidla", "jazdene-a-predvadzacie-vozidla"]),
         ("DS", "https://skladovevozidla.dsautomobiles.sk", ["skladove-vozidla", "jazdene-a-predvadzacie-vozidla"])]


def stellantis():
    for brand, base, sections in STELL:
        key = "st_" + norm(brand).replace(" ", "")
        seen = set()
        for sec in sections:
            for page in range(1, 60):
                t = get(f"{base}/{sec}/vysledky-hladania?page={page}")
                if t is None:
                    if page == 1 and sec == sections[0]:
                        STATUS[key] = ("blocked", 0)
                    break
                links = list(dict.fromkeys(re.findall(r'href="(' + re.escape(base) + r'/[^"]*detail-vozidla/[^"]+/(\d+))"', t)))
                new = [l for l in links if l[1] not in seen]
                if not new:
                    break
                for url, did in new:
                    seen.add(did)
                    i = t.find(url)
                    c = t[max(0, i - 3500): i + 3000]
                    # the card around the first link: dealer line, old price, price, monthly, financing price, fuel, kW
                    path = url.split("/detail-vozidla/")[1].split("/")
                    model, body_s, slug = (path[1] if len(path) > 1 else ""), (path[2] if len(path) > 2 else ""), (path[3] if len(path) > 3 else "")
                    seg = c[c.rfind("fa-location-dot") if "fa-location-dot" in c[:3600] else 0:]
                    dealer_line = text((re.search(r"fa-location-dot[^>]*></i>(.*?)</div>", c, re.S) or [None, ""])[1])
                    old = num((re.search(r"old-price[^>]*>\s*([\d  .]+)\s*EUR", seg) or [None, None])[1])
                    pr = num((re.search(re.escape(url) + r'"[^>]*>\s*<span[^>]*>\s*([\d  .]+)\s*EUR', c) or [None, None])[1])
                    after = c[c.find(url):]
                    monthly = num((re.search(r"Mesačná splátka od:.*?>\s*([\d  .,]+)\s*€", after, re.S) or [None, None])[1])
                    finp = num((re.search(r"Cena pri financov\w+:.*?>\s*([\d  .,]+)\s*€", after, re.S) or [None, None])[1])
                    kw = num((re.search(r"(\d{2,3})\s*kW", after) or [None, None])[1])
                    km = num((re.search(r"([\d  .]+)\s*km\b", after[:2500]) or [None, None])[1])
                    fuel_s = text((re.search(r'list-fuel"></span>.*?<span class="whitespace-nowrap">(.*?)</span>', after, re.S) or [None, ""])[1])
                    if body_s in ("uzitkove", "nakladne"):
                        continue
                    words = [w for w in slug.split("-") if w and norm(w) not in (norm(brand), norm(model), "peugeot", "citroen", "fiat", "jeep", "alfa", "romeo", "ds")]
                    title = f"{brand} {model.replace('-', ' ').upper() if len(model) <= 4 else model.replace('-', ' ').title()} " + " ".join(w.upper() if re.match(r"^[a-z]{1,4}\d*$", w) and len(w) <= 4 else w for w in words)
                    demo = "predvadz" in sec or "jazden" in sec
                    if demo and (km is None or km > 15000):
                        continue  # used car, not demo
                    if pr is None and finp:
                        pr = finp
                    cash = pr
                    flags = []
                    if finp and pr and finp < pr - 1:
                        flags.append("fin_cheaper")
                    add({"id": f"st:{key}:{did}", "src": key, "off": True, "url": url, "brand": brand, "model": model.replace("-", " ").upper() if len(model) <= 4 else model.replace("-", " ").title(),
                         "title": title, "body": classify(BODY, body_s + " " + slug, None), "fuel": classify(FUEL, fuel_s + " " + slug, "petrol"), "mhev": mild(slug),
                         "gear": "auto" if re.search(r"eat\d|edcs|dct|edct|at\d|\bat\b|automat|cvt", norm(slug)) else "man", "kw": kw, "km": km,
                         "cond": "demo" if demo else "new", "price": cash, "list": old, "fin_price": finp if finp and pr and finp < pr - 1 else None, "monthly": monthly,
                         "dealer": re.split(r",", dealer_line)[0].strip() or None, "city": (dealer_line.split(",")[-1].strip() if "," in dealer_line else None), "auth": True, "flags": flags})
        STATUS[key] = ("ok", len(seen))
        log(brand, len(seen))


def stellantis_details(limit=70):
    """VIN + financing legal line for the cheapest offers (cached)."""
    global detail_used
    used = 0
    cand = sorted([o for o in OFFERS if o["src"].startswith("st_")], key=lambda o: o["price"])
    for o in cand:
        c = CACHE.get(o["id"])
        if used < limit and detail_used < DETAIL_BUDGET and detail_due(o["id"], o["price"]) and o["price"] <= 35000:
            t = get(o["url"])
            detail_used += 1
            used += 1
            if t:
                vin = (re.search(r"VIN:\s*</p>\s*<p[^>]*>\s*([A-HJ-NPR-Z0-9]{17})", t) or [None, None])[1]
                yr = (re.search(r"Rok výroby:?\s*</p>\s*<p[^>]*>\s*(\d{4})", t) or [None, None])[1]
                legal = text(" ".join(re.findall(r"(?:RPMN|Celková výška|úrokov)[^<]{0,900}", H.unescape(t.encode().decode("unicode_escape", "ignore") if "\\u00" in t else t))))[:1500]
                c = {"price": o["price"], "fetched": TODAY, "vin": vin, "year": yr, "fin": fin_from_text(legal), "cond": conditions(text(t)[:20000])}
                CACHE[o["id"]] = c
        if c:
            o["vin"] = c.get("vin")
            o["year"] = c.get("year")
            if c.get("fin"):
                o["fin"] = c["fin"]
            o["flags"] = sorted(set(o.get("flags", []) + [x for x in c.get("cond", []) if x in ("fin", "tradein")]))


# ---------------------------------------------------------------- Mitsubishi (official)
def mitsubishi():
    key = "mitsubishi"
    n = 0
    for sec, cond in (("skladove-vozidla", "new"), ("predvadzacie-auta", "demo")):
        t = get(f"https://www.mitsubishi-motors.sk/nakup-vozidla/{sec}/")
        if t is None:
            STATUS.setdefault(key, ("blocked", 0))
            continue
        for c in t.split('<div class="car-home">')[1:]:
            m = re.search(r'href="(https://www\.mitsubishi-motors\.sk/nakup-vozidla/[^"]+/(\d+)-[^"]+/)"', c)
            if not m:
                continue
            title = text((re.search(r'car-title-home1[^>]*>(.*?)</div>', c, re.S) or [None, ""])[1])
            pr = num((re.search(r"Zvýhodnená cena:.*?<strong>([^<]+)", c, re.S) or [None, None])[1])
            lst = num((re.search(r"Cenníková cena:.*?<td>([^<]+)", c, re.S) or [None, None])[1])
            model = re.sub(r"^Mitsubishi\s+(Nové\s+|Nový\s+)?", "", title).split(" ")[0]
            add({"id": "mit:" + m.group(2), "src": key, "off": True, "url": m.group(1), "brand": "Mitsubishi", "model": model, "title": title,
                 "body": classify(BODY, title, "suv"), "fuel": classify(FUEL, title, "petrol"), "mhev": mild(title), "gear": "auto" if re.search(r"cvt|automat|phev|at\b", norm(title)) else "man",
                 "cond": cond, "price": pr, "list": lst, "dealer": None, "city": None, "auth": True})
            n += 1
    STATUS[key] = ("ok", n)
    log("Mitsubishi:", n)


# ---------------------------------------------------------------- Dacia + Mazda (official, detail pages from sitemaps, cached)
def sitemap_details(key, sitemap, pat, parse, limit=220, max_age=2):
    sm = get(sitemap)
    if sm is None:
        STATUS[key] = ("blocked", 0)
        return
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if re.search(pat, u)]
    fetched = n = 0
    # never fetched first, then the oldest
    urls.sort(key=lambda u: (CACHE.get(key + ":" + u, {}).get("fetched", "0000")))
    for u in urls:
        ck = key + ":" + u
        c = CACHE.get(ck)
        age = (NOW.date() - dt.date.fromisoformat(c["fetched"])).days if c else 99
        if (not c or age >= max_age) and fetched < limit:
            t = get(u)
            fetched += 1
            if t:
                c = parse(u, t)
                if c:
                    c["fetched"] = TODAY
                    CACHE[ck] = c
        if c and c.get("price") and (NOW.date() - dt.date.fromisoformat(c["fetched"])).days <= 4:
            o = dict(c["o"])
            o["price"] = c["price"]
            o["id"] = key + ":" + re.sub(r"\W+", "", u.split("/")[-2] if u.endswith("/") else u.split("/")[-1])
            add(o)
            n += 1
    STATUS[key] = ("ok", n)
    log(key, n, "offers,", fetched, "pages fetched")


def dacia_parse(u, t):
    h1 = text((re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S) or ["", ""])[-1])
    model = text((re.search(r"<h1[^>]*>\s*<strong>(.*?)</strong>", t, re.S) or [None, h1.split(" ")[0]])[1])
    lst = num((re.search(r'pricelist_price">[^<]*</p>\s*<strong class="price">([^<]+)', t) or [None, None])[1])
    pr = num((re.search(r'final-price">([^<]+)', t) or [None, None])[1])
    dealer = (re.search(r"'dealerName'\s*:\s*'([^']+)'", t) or [None, None])[1]
    vin = (re.search(r"\b(UU1[A-HJ-NPR-Z0-9]{14}|VF1[A-HJ-NPR-Z0-9]{14})\b", t) or [None, None])[1]
    perks = [text(x) for x in re.findall(r'<div class="perk-item[^"]*" title="([^"]+)"', t)]
    flags = ["fin_bonus"] if any(re.search(r"financ", norm(x)) for x in perks) else []
    title = "Dacia " + h1
    if not pr:
        return None
    return {"price": pr, "o": {"src": "dacia", "off": True, "url": u, "brand": "Dacia", "model": model.title(), "title": title, "body": body_of("Dacia", model, title),
            "fuel": "lpg" if re.search(r"eco-?g|lpg", norm(h1)) else classify(FUEL, h1, "petrol"), "mhev": mild(h1),
            "gear": "auto" if re.search(r"\bcvt|edc|automat|hybrid 1[45]5", norm(h1)) else "man", "cond": "new", "list": lst, "dealer": dealer, "auth": True, "vin": vin,
            "perks": perks[:4], "flags": flags}}


def mazda_parse(u, t):
    og = H.unescape((re.search(r'<meta property="og:title" content="([^"]+)"', t) or [None, ""])[1])
    pr = num((re.search(r'class="model-price"[^>]*>([^<]+)', t) or [None, None])[1])
    ld = num((re.search(r'"price":\s*"(\d+)"', t) or [None, None])[1])
    seller = (re.search(r'"seller":\s*\{\s*"@type":\s*"Organization",\s*"name":\s*"([^"]+)"', t) or [None, None])[1]
    vin = (re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", t) or [None, None])[1]
    m = re.search(r"/Mazda/([^/]+)/", u)
    model = m.group(1).replace("-", " ").upper().replace("MAZDA ", "") if m else ""
    model = {"2": "2", "3": "3"}.get(model, model)
    if not pr:
        return None
    flags = ["price_mismatch"] if ld and abs(ld - pr) > 50 else []
    return {"price": pr, "o": {"src": "mazda", "off": True, "url": u, "brand": "Mazda", "model": model.title() if not re.match(r"^(CX|MX)", model) else model, "title": og or ("Mazda " + model),
            "body": body_of("Mazda", model, og), "fuel": classify(FUEL, og, "petrol"), "mhev": mild(og) or "m hybrid" in norm(og),
            "gear": "auto" if re.search(r"\b\d?at\b|automat|aut\.", norm(og)) else "man", "cond": "new", "dealer": seller, "auth": True, "vin": vin, "flags": flags}}


def dacia():
    sitemap_details("dacia", "https://skladove-vozidla.dacia.sk/sitemap.xml", r"-v\d+/$", dacia_parse)


def mazda():
    sitemap_details("mazda", "https://www.mazdaihned.sk/sitemap.xml", r"/Mazda/[^/]+/[a-z0-9]+/$", mazda_parse)


# ---------------------------------------------------------------- autobazar.eu (all brands, authorised-dealer check)
AB_BODY = {"kombi": "estate", "suv": "suv", "hatchback": "hatch", "liftback": "hatch", "sedan": "sedan", "mpv": "mpv", "van": "mpv", "minivan": "mpv", "kupe": "coupe", "kabriolet": "coupe", "pick-up": "other", "terenne": "suv", "crossover": "suv"}


def autobazar():
    key = "autobazar"
    recs = {}
    bands = [(0, 12000), (12000, 15000), (15000, 17000), (17000, 19000), (19000, 20500), (20500, 22000), (22000, 23500), (23500, 25000), (25000, 26500), (26500, 28000),
             (28000, 30000), (30000, 32000), (32000, 34000), (34000, 36500), (36500, 39000), (39000, 42000), (42000, 46000), (46000, PRICE_CAP)]
    for lo, hi in bands:
        for page in range(1, 51):
            t = get(f"https://www.autobazar.eu/vysledky-nove-auta/?category=30900&priceFrom={lo}&priceTo={hi}" + (f"&page={page}" if page > 1 else ""))
            if t is None:
                break
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
            if not m:
                break
            pp = json.loads(m.group(1)).get("props", {}).get("pageProps", {})
            data = pp.get("initialRecords", {}).get("data", [])
            total = pp.get("initialRecords", {}).get("total", 0)
            for r in data:
                recs[r["id"]] = r
            if page == 1:
                log(f"  autobazar {lo}-{hi}: {total}")
                if total > 1000:
                    log("  ! band over 1000 results, some offers not reachable:", lo, hi)
            if not data or page * 20 >= min(total, 1000):
                break
    log("autobazar records:", len(recs))
    if not recs:
        STATUS[key] = ("blocked", 0)
        return []
    # learn which authorised-brand id means which brand, dealer by dealer:
    # for brand X, the id that most of X's authorised dealers carry and few others do
    dealers = {}
    for r in recs.values():
        u = r.get("user") or {}
        ad = u.get("authorizedDealer") or {}
        if not ad.get("isAuthorized") or not u.get("id"):
            continue
        d = dealers.setdefault(u["id"], {"ids": set(ad.get("brands") or []), "brands": set()})
        d["brands"].add(r.get("brandValue"))
    nb, nx, nxb = {}, {}, {}
    for d in dealers.values():
        for b in d["ids"]:
            nb[b] = nb.get(b, 0) + 1
        for x in d["brands"]:
            nx[x] = nx.get(x, 0) + 1
            for b in d["ids"]:
                nxb[(x, b)] = nxb.get((x, b), 0) + 1
    scored = sorted(((c / nx[x]) * (c / nb[b]), x, b, c) for (x, b), c in nxb.items() if c >= 2)
    bmap, used = {}, set()
    for sc, x, b, c in reversed(scored):
        if x in bmap or b in used or c / nx[x] < 0.3:
            continue
        bmap[x] = {b}
        used.add(b)
    log("authorised-brand map:", {k: (sorted(v), nx.get(k)) for k, v in sorted(bmap.items())})
    log("brands without a learned id:", sorted(x for x in nx if x not in bmap))
    out = []
    for r in recs.values():
        u = r.get("user") or {}
        ad = u.get("authorizedDealer") or {}
        brand = r.get("brandValue")
        ids = set(ad.get("brands") or [])
        name_has_brand = bool(re.search(r"\b" + re.escape(norm(brand or "~").split()[0]) + r"\b", norm(u.get("displayName", ""))))
        if ad.get("isAuthorized") and bmap.get(brand):
            auth = bool(ids & bmap[brand]) or name_has_brand
        elif ad.get("isAuthorized") and name_has_brand:
            auth = True
        else:
            auth = False
        cond = {30923: "new", 30924: "demo", 30925: "demo"}.get(r.get("condition"), "new")
        title = r.get("title") or ""
        known = body_of(brand or "", r.get("carModelValue") or "", title, None)
        body = known or AB_BODY.get(norm(r.get("bodyworkValue") or ""), None) or "other"
        fuel_s = r.get("fuelValue") or ""
        fuel = "phev" if "plug" in norm(fuel_s + title) else "hybrid" if "hybrid" in norm(fuel_s) else classify(FUEL, fuel_s, "petrol")
        o = {"id": "ab:" + r["id"], "src": key, "off": False, "url": f"https://www.autobazar.eu/detail-nove-auto/{r.get('sefName')}/{r['id']}/",
             "brand": brand, "model": r.get("carModelValue"), "title": title, "body": body, "fuel": fuel, "mhev": mild(title + fuel_s),
             "gear": "auto" if "autom" in norm(r.get("gearboxValue") or "") else "man", "kw": r.get("enginePower"), "km": r.get("mileage"),
             "year": r.get("yearValue"), "cond": cond, "price": r.get("finalPrice") or r.get("priceCurrent") or r.get("price"),
             "list": r.get("listPrice") or (r.get("price") if r.get("price") and r.get("finalPrice") and r["price"] > r["finalPrice"] else None),
             "dealer": u.get("displayName"), "city": u.get("city") or (r.get("location") or {}).get("name"), "auth": auth, "vin": (r.get("vin") or "").upper() or None,
             "leasing": bool(r.get("leasingPossible")), "img": ((r.get("image") or {}).get("previewUrls") or {}).get("record_preview")}
        add(o)
        out.append(o)
    STATUS[key] = ("ok", len(out))
    return out


def autobazar_details():
    """Price conditions written in the dealer's description, for the cheapest authorised offers (cached)."""
    global detail_used
    cand = sorted([o for o in OFFERS if o["src"] == "autobazar" and o["auth"]], key=lambda o: o["price"])
    for o in cand:
        c = CACHE.get(o["id"])
        if detail_used < DETAIL_BUDGET and detail_due(o["id"], o["price"]) and o["price"] <= 32000:
            t = get(o["url"])
            detail_used += 1
            if t:
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
                adv = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("advertisement", {}) if m else {}
                desc = (adv.get("description") or "") + " " + (adv.get("noteForBuyer") or "")
                c = {"price": o["price"], "fetched": TODAY, "cond": conditions(desc), "cons": adv.get("consumptionCombined"), "text": desc[:500],
                     "fin": fin_from_text(desc)}
                CACHE[o["id"]] = c
        if c:
            o["flags"] = sorted(set(o.get("flags", []) + c.get("cond", [])))
            if c.get("cons"):
                o["cons"] = c["cons"]
            if c.get("fin"):
                o["fin"] = c["fin"]


# ---------------------------------------------------------------- official leasing / financing promotions (quoted, with link)
PROMO_PAGES = [
    ("Škoda", "https://www.skoda-auto.sk/ponuka/financovanie"), ("Škoda", "https://www.skoda-auto.sk/ponuka/akcie"), ("Škoda", "https://www.skoda-auto.sk/ponuka/skoda-bonus"),
    ("Hyundai", "https://www.hyundai.com/sk/sk/aktualna-ponuka/akciove-ponuky.html"), ("Hyundai", "https://www.hyundai.com/sk/sk/predaj/financovanie/prehlad-financovania.html"),
    ("Toyota", "https://www.toyota.sk/nakup-a-ponuky/akciove-ponuky"),
    ("Dacia", "https://www.dacia.sk/financovanie/akciove-ponuky.html"), ("Dacia", "https://www.dacia.sk/akciove-ponuky.html"),
    ("Renault", "https://www.renault.sk/financovanie/akciove-ponuky.html"),
    ("Peugeot", "https://www.peugeot.sk/nasa-ponuka/akciove-ponuky-nove-vozidla/peugeot-pausal.html"), ("Peugeot", "https://www.peugeot.sk/nasa-ponuka/akciove-ponuky-nove-vozidla.html"),
    ("Opel", "https://www.opel.sk/offers/offers-overview.html"),
    ("Fiat", "https://www.fiat.sk/akciove-ponuky/fiat-operativny-leasing"), ("Fiat", "https://www.fiat.sk/akciove-ponuky"),
    ("Jeep", "https://www.jeep.sk/akciove-ponuky/operativny-leasing"),
    ("Mitsubishi", "https://www.mitsubishi-motors.sk/akciova-ponuka/"),
    ("Seat", "https://www.seat.sk/vyber-vozidla-a-konfiguracia/akcie-a-ponuky/akcie-a-ponuky"), ("Cupra", "https://www.cupraofficial.sk/nove-vozidla/akcie-a-ponuky"),
    ("BYD", "https://www.byd.com/sk/akcna-ponuka"), ("Nissan", "https://www.nissan.sk/ponuka/hybridne-vozidla-nove.html"),
]
PROMO_PAT = re.compile(r"(?:(?:od|len|už od|za)\s*\d[\d  ]*(?:,\d+)?\s*€\s*(?:/|za|mesa[čc]ne|mes)\s*(?:mes\w*)?|0\s*%\s*(?:úrok|navýšen|akontác)\w*|operatívn\w* (?:leasing|lízing)|paušál\w*|bonus\w*\s*(?:až\s*)?\d[\d  ]*\s*€|zvýhodnen\w*\s*(?:až\s*)?\d[\d  ]*\s*€|RPMN\s*\d)", re.I)


def promos():
    out = []
    for brand, url in PROMO_PAGES:
        t = get(url, tries=1)
        if not t:
            continue
        title = text((re.search(r"<title>(.*?)</title>", t, re.S) or [None, ""])[1])[:90]
        tx = text(re.sub(r"<(nav|header|footer)\b.*?</\1>", " ", t, flags=re.S))
        snips = []
        for m in PROMO_PAT.finditer(tx):
            a0 = max(0, tx.rfind(". ", 0, m.start()) + 2, m.start() - 160)
            b0 = tx.find(". ", m.end())
            b0 = min(b0 + 1 if b0 >= 0 else len(tx), m.end() + 160)
            sn = tx[a0:b0].strip(" .,-")
            if len(sn) < 25 or any(sn[:60] in x or x[:60] in sn for x in snips) or re.search(r"cookie|súhlas|newsletter", sn, re.I):
                continue
            snips.append(sn)
            if len(snips) >= 4:
                break
        if snips:
            out.append({"brand": brand, "url": url, "title": title, "snips": snips, "checked": NOW.isoformat(timespec="minutes")})
    with open(os.path.join(OUT, "promos.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log("promos:", len(out), "pages with leasing/financing offers")


# ---------------------------------------------------------------- boot space (Cebia guides: litres per version)
def slug(s):
    s = norm(s).replace("&", " ").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def space():
    """Boot volume per model from cebia.cz guides ('Objem kufru'), newest generation table, cached 30 days."""
    sp = load("space.json", {})
    models = {}
    for o in OFFERS:
        if o.get("model"):
            models[norm(o["brand"]) + "|" + norm(o["model"])] = (o["brand"], o["model"])
    fetched = 0
    for key, (brand, model) in sorted(models.items()):
        e = sp.get(key)
        if e and (NOW.date() - dt.date.fromisoformat(e.get("fetched", "2000-01-01"))).days < 30:
            continue
        if fetched >= 120:
            break
        b = slug(brand).replace("mercedes-benz", "mercedes")
        m = slug(re.sub(r"^(nov[ýéá]|new)\s+", "", model, flags=re.I))
        found = None
        for cand in dict.fromkeys([m, m.replace("-", ""), m.split("-")[0]]):
            url = f"https://www.cebia.cz/pruvodce/objem-kufru-{b}-{cand}"
            t = get(url, tries=1)
            fetched += 1
            if t and "<table" in t:
                found = (url, t)
                break
        if not found:
            sp[key] = {"fetched": TODAY, "rows": []}
            continue
        url, t = found
        tab = re.search(r"<table.*?</table>", t, re.S).group(0)
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", tab, re.S):
            cells = [text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if len(cells) >= 2 and re.fullmatch(r"\d{2,4}", cells[1].replace(" ", "")):
                rows.append([cells[0], int(cells[1].replace(" ", "")), int(cells[2].replace(" ", "")) if len(cells) > 2 and re.fullmatch(r"\d{3,4}", cells[2].replace(" ", "")) else None])
        sp[key] = {"fetched": TODAY, "src": url, "rows": rows[:30]}
    with open(os.path.join(OUT, "space.json"), "w", encoding="utf-8") as f:
        json.dump(sp, f, ensure_ascii=False, separators=(",", ":"))
    log("space: models", len(models), "pages fetched", fetched, "with data", sum(1 for k in models if sp.get(k, {}).get("rows")))


# ---------------------------------------------------------------- double check + output
def cross_check():
    by_vin = {}
    for o in OFFERS:
        if o.get("vin"):
            by_vin.setdefault(o["vin"], []).append(o)
    pairs = 0
    for vin, lst in by_vin.items():
        offs = [o for o in lst if o["off"]]
        ab = [o for o in lst if not o["off"]]
        if offs and ab:
            pairs += 1
            a, b = offs[0], ab[0]
            agree = abs(a["price"] - b["price"]) <= max(150, 0.015 * a["price"])
            a["twin"] = {"url": b["url"], "src": b["src"], "price": b["price"], "agree": agree}
            b["twin"] = {"url": a["url"], "src": a["src"], "price": a["price"], "agree": agree}
            for o in lst:
                if o is not a and o is not b:
                    o["dup"] = True
            # keep one card: the official one (it carries the dealer's authorisation by definition); show the lower price with both links
            b["dup"] = True
            a["dealer"] = a.get("dealer") or b.get("dealer")
            a["city"] = a.get("city") or b.get("city")
            a["img"] = a.get("img") or b.get("img")
            a["year"] = a.get("year") or b.get("year")
            a["km"] = a.get("km") if a.get("km") is not None else b.get("km")
            a["kw"] = a.get("kw") or b.get("kw")
    log("VIN double-checked pairs:", pairs)


def sanity(o):
    """drop prices that can't be right: >45 % below list price, or list price far below price"""
    if o.get("list") and o["price"] < 0.55 * o["list"]:
        return False
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in (kia, hyundai, stellantis, mitsubishi, dacia, mazda, autobazar):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log("!! source failed:", fn.__name__, type(e).__name__, e)
            STATUS[fn.__name__] = ("error", 0)
    for fn in (kia_details, hyundai_details, stellantis_details, autobazar_details):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log("!! details failed:", fn.__name__, type(e).__name__, e)
    log("detail pages used:", detail_used)
    try:
        promos()
    except Exception as e:  # noqa: BLE001
        log("!! promos failed:", type(e).__name__, e)
    try:
        space()
    except Exception as e:  # noqa: BLE001
        log("!! space failed:", type(e).__name__, e)
    cross_check()
    keep = [o for o in OFFERS if not o.get("dup") and sanity(o)]
    dropped = len(OFFERS) - len(keep)
    # history: first seen + price drops
    for o in keep:
        h = HIST.setdefault(o["id"], {"first": TODAY, "p": []})
        if not h["p"] or h["p"][-1][1] != o["price"]:
            h["p"].append([TODAY, o["price"]])
            h["p"] = h["p"][-12:]
        o["first"] = h["first"]
        prev = [p for d, p in h["p"][:-1]]
        if prev and max(prev) > o["price"]:
            o["drop"] = max(prev) - o["price"]
    live = {o["id"] for o in keep}
    for k in list(HIST):
        if k not in live and (NOW.date() - dt.date.fromisoformat(HIST[k]["first"])).days > 120:
            del HIST[k]
    for k in list(CACHE):
        if k in live:
            continue
        if re.match(r"(dacia|mazda):http", k) and (NOW.date() - dt.date.fromisoformat(CACHE[k].get("fetched", "2000-01-01"))).days <= 7:
            continue  # sitemap-detail cache, keyed by page URL
        del CACHE[k]
    # safety net: a source that failed today keeps yesterday's offers (marked stale) for up to 2 days
    prev_by_src = {}
    for o in PREV.get("offers", []):
        prev_by_src.setdefault(o["src"], []).append(o)
    for src, (st, n) in list(STATUS.items()):
        pass
    have = {o["src"] for o in keep}
    for src, lst in prev_by_src.items():
        if src not in have and lst:
            age = (NOW - dt.datetime.fromisoformat(lst[0]["checked"])).days if lst[0].get("checked") else 9
            if age <= 2:
                for o in lst:
                    o["stale"] = True
                keep += lst
                log("  kept stale offers from", src, len(lst))
    keep.sort(key=lambda o: o["price"])
    # financing total must be what you pay in total — a figure below the price is the loan amount, not the total
    for o in keep:
        f = o.get("fin")
        if f and f.get("total") and f["total"] < 0.85 * o["price"]:
            f.pop("total", None)
    # identical cars at the same dealer (same version, price, condition) → one line with a count
    grouped, seen = [], {}
    for o in keep:
        k = (o["brand"], norm(o.get("model") or ""), norm(o.get("title") or ""), round(o["price"]), norm(o.get("dealer") or ""), o["cond"], o["src"])
        if k in seen and not o.get("twin"):
            seen[k]["n"] = seen[k].get("n", 1) + 1
            continue
        seen[k] = o
        grouped.append(o)
    log("grouped identical offers:", len(keep), "→", len(grouped))
    keep = grouped
    for o in keep:  # keep the file small for phones: drop fields the app doesn't use
        o.pop("img", None)
        if o.get("checked") and not o.get("stale"):
            o.pop("checked", None)
        for k in [k for k, v in o.items() if v in (None, [], False, "")]:
            del o[k]
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import caraudit
        aud = caraudit.audit(keep, n=40, get=lambda u: get(u, tries=1), log=log)
    except Exception as e:  # noqa: BLE001
        log("!! audit failed:", type(e).__name__, e)
        aud = None
    data = {"generated": NOW.isoformat(timespec="minutes"), "count": len(keep), "dropped_implausible": dropped, "audit": aud,
            "sources": {k: {"status": v[0], "offers": v[1]} for k, v in STATUS.items()}, "offers": keep}
    with open(os.path.join(OUT, "offers.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "history.json"), "w", encoding="utf-8") as f:
        json.dump(HIST, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "details.json"), "w", encoding="utf-8") as f:
        json.dump(CACHE, f, ensure_ascii=False, separators=(",", ":"))
    log("STATUS", STATUS)
    log("offers kept:", len(keep), "under 20k:", sum(1 for o in keep if o["price"] <= 20000), "authorised:", sum(1 for o in keep if o.get("auth")))
    for o in keep[:25]:
        log(f"  {o['price']:>8.0f} {o['brand']:<10} {o.get('model') or '':<12} {o['cond']:<4} {o.get('body') or '-':<6} auth={o.get('auth')} {o['src']:<10} {o.get('dealer') or ''} | {o['title'][:50]}")


if __name__ == "__main__":
    main()
