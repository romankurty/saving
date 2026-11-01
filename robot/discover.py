"""Discovery run 12: Lidl full leaflet text (PDF), news roundups of Kaufland/Tesco leaflet prices (arecenze.cz).

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import io
import json
import re
import time
import urllib.parse
import urllib.robotparser

import requests

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 3
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
_robots = {}


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        status = None
        text = ""
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            status, text = r.status_code, r.text
            rp.parse(text.splitlines() if status == 200 and "<html" not in text[:200].lower() else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status)
        print(f"  robots {base}: {status} {[l for l in text.splitlines() if l.lower().startswith(('disallow', 'crawl'))][:12]}")
        time.sleep(DELAY_S)
    rp, status = _robots[base]
    if status in (401, 403):
        return False
    return rp.can_fetch(UA, url)


def get(url, as_json=False):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=60, headers={"Accept": "application/json"} if as_json else {})
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:170]} ({len(r.content)} B, {r.headers.get('content-type')})")
    return r if r.status_code == 200 else None


print("=== 1. Lidl leaflet PDF text ===")
home = get("https://www.lidl.cz/c/akcni-letak/s10008644")
slugs = sorted(set(re.findall(r"/l/cs/letak/([a-z0-9-]+)/", home.text))) if home is not None else []
food = [s for s in slugs if s.startswith("akcni-letak")]
print("  food leaflets:", food)
for slug in food[:1]:
    fj = get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={slug}&region_id=0&region_code=0", as_json=True)
    if fj is None:
        continue
    fl = fj.json().get("flyer", {})
    print("  pdf:", fl.get("pdfUrl"), fl.get("fileSize"), "| dates:", fl.get("offerStartDate"), fl.get("offerEndDate"))
    pdf = get(fl.get("pdfUrl")) if fl.get("pdfUrl") else None
    if pdf is not None:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf.content)) as doc:
            print("  pages:", len(doc.pages))
            for pn in (1, 2, 5):
                if pn < len(doc.pages):
                    txt = doc.pages[pn].extract_text() or ""
                    print(f"  --- page {pn + 1}: {len(txt)} chars, prices: {len(re.findall(r'\\d+[,.]\\d{2}', txt))}")
                    print("  ", txt[:1200].replace("\n", " | "))
                    words = doc.pages[pn].extract_words()[:40]
                    print("   words:", [(w['text'], round(w['x0']), round(w['top'])) for w in words])

print("=== 2. News roundups with Kaufland / Tesco leaflet prices ===")
r = get("https://www.arecenze.cz/")
links = []
if r is not None:
    links = list(dict.fromkeys(re.findall(r'href="(https://www\.arecenze\.cz/clanky/[^"]+)"', r.text)))
    pick = [l for l in links if any(k in l for k in ("kaufland", "tesco", "nejlepsi-slevy", "letak"))]
    print("  candidate articles:", pick[:15])
    for art in pick[:2]:
        a = get(art)
        if a is None:
            continue
        txt = re.sub(r"<[^>]+>", " ", a.text)
        txt = re.sub(r"\s+", " ", txt)
        hits = re.findall(r"[^.]{0,80}\d+[,.]\d{2} Kč[^.]{0,60}", txt)
        print(f"  {art}: {len(hits)} price sentences")
        for h in hits[:12]:
            print("    •", h.strip()[:200])
