"""Discovery run 2: terms of use, page structure of Kupi.cz results, Kupino.sk search format.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt.
"""
import re
import time
import urllib.parse
import urllib.robotparser
from collections import Counter

import requests
from bs4 import BeautifulSoup, Tag

UA = "saving-pricebot/0.1 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 3
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
q = urllib.parse.quote
_robots = {}


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url) and _robots[base].can_fetch("*", url)


def get(url):
    if not allowed(url):
        print(f"[SKIP robots] {url}")
        return None
    time.sleep(DELAY_S)
    r = session.get(url, timeout=30)
    print(f"[{r.status_code}] {url} -> {r.url} ({len(r.content)} B)")
    return r


KEYWORDS = ("automat", "robot", "stahov", "sťahov", "kopír", "kopirov", "vytěž", "vyťaž",
            "databáz", "scrap", "crawl", "hromadn", "strojov", "softwar")


def terms_check(url):
    r = get(url)
    if not r or r.status_code != 200:
        return
    text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    hits = [s for s in sentences if any(k in s.lower() for k in KEYWORDS)]
    print(f"  terms sentences matching keywords: {len(hits)}")
    for s in hits[:12]:
        print("   >", s[:400])


def dump(el, depth=0, lines=None, limit=90):
    if lines is None:
        lines = []
    if len(lines) >= limit:
        return lines
    if isinstance(el, Tag):
        cls = ".".join(el.get("class", []))
        own = "".join(t for t in el.find_all(string=True, recursive=False)).strip()
        own = " ".join(own.split())[:70]
        attrs = {k: v for k, v in el.attrs.items() if k.startswith("data-") or k in ("title", "alt")}
        attr_txt = (" " + str(attrs)[:120]) if attrs else ""
        lines.append(f"{'  ' * depth}<{el.name}{'.' + cls if cls else ''}>{attr_txt} {own}")
        for c in el.children:
            if isinstance(c, Tag):
                dump(c, depth + 1, lines, limit)
    return lines


print("=== 1. Kupi.cz terms ===")
home = get("https://www.kupi.cz/")
if home is not None:
    soup = BeautifulSoup(home.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        h = a["href"].lower()
        if any(k in h for k in ("podmin", "pravidl", "obchodni", "terms", "gdpr", "ochrana")):
            links.append(urllib.parse.urljoin(home.url, a["href"]))
    links = list(dict.fromkeys(links))
    print("  candidate terms links:", links[:8])
    for link in links[:3]:
        terms_check(link)

print("=== 2. Kupino.sk terms ===")
terms_check("https://www.kupino.sk/vseobecne-podmienky")

print("=== 3. Kupi.cz result structure (butter search) ===")
r = get(f"https://www.kupi.cz/hledej?f={q('máslo')}&vse=0")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    groups = soup.find_all("div", class_="group_discounts")
    for i, g in enumerate(groups[:2]):
        print(f"--- product block {i} ---")
        print("\n".join(dump(g)))
    shops = Counter(s.get_text(strip=True) for s in soup.find_all("span", class_="discounts_shop_name"))
    print("  shops in butter results:", dict(shops))
    print("  pagination links:", [a["href"] for a in soup.find_all("a", href=True) if "page=" in a["href"]][:5])

print("=== 4. Shop coverage (toilet paper + kefir) ===")
for term in ("toaletní papír", "kefír"):
    r = get(f"https://www.kupi.cz/hledej?f={q(term)}&vse=0")
    if r is not None:
        soup = BeautifulSoup(r.text, "html.parser")
        shops = Counter(s.get_text(strip=True) for s in soup.find_all("span", class_="discounts_shop_name"))
        print(f"  shops for {term}:", dict(shops))

print("=== 5. Kupino.sk search format ===")
r = get("https://www.kupino.sk/")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    for f in soup.find_all("form"):
        print("  form:", f.get("action"), f.get("method"), [i.get("name") for i in f.find_all("input")])
    hrefs = [a["href"] for a in soup.find_all("a", href=True)]
    interesting = [h for h in hrefs if any(k in h.lower() for k in ("hlad", "zlav", "akci", "lidl", "billa", "kaufland", "tesco", "sintra", "letak", "obchod"))]
    print("  links:", list(dict.fromkeys(interesting))[:40])
    classes = Counter(c for el in soup.find_all(class_=True) for c in el.get("class", []))
    print("  common classes:", [c for c, _ in classes.most_common(40)])
