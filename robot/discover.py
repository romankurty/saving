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


print("=== News roundups (arecenze.cz) ===")
r = get("https://www.arecenze.cz/clanky/nejlepsi-slevy/")
if r is not None:
    links = list(dict.fromkeys(re.findall(r'href="(https://www\.arecenze\.cz/clanky/[a-z0-9-]+/)"', r.text)))
    print("  links:", links[:25])
    pick = [l for l in links if "kaufland" in l][:1] + [l for l in links if "tesco" in l][:1] + [l for l in links if "nejlepsi-slevy-z-letaku" in l][:1]
    for art in pick:
        a = get(art)
        if a is None:
            continue
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', a.text)
        print("  ---", art, "| published:", m.group(1) if m else None)
        body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", a.text, flags=re.S)
        body = re.sub(r"<[^>]+>", "\n", body)
        lines = [re.sub(r"\s+", " ", l).strip() for l in body.split("\n")]
        lines = [l for l in lines if re.search(r"\d+[,.]\d{2}\s*Kč|\d+\s*Kč", l) and 8 < len(l) < 260]
        print("   price lines:", len(lines))
        for l in lines[:25]:
            print("    •", l)
