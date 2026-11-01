"""Discovery run: checks which public price pages the robot may read and how they are structured.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt.
Raw pages go into a short-lived workflow artifact (not committed to the repository).
"""
import json
import os
import re
import time
import urllib.parse
import urllib.robotparser

import requests
from bs4 import BeautifulSoup

UA = "saving-pricebot/0.1 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 3
OUT = "out"
os.makedirs(OUT, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})

q = urllib.parse.quote

TARGETS = {
    # Kupi.cz (all CZ chains + drugstores in one place)
    "kupi_cz_home": "https://www.kupi.cz/",
    "kupi_cz_search_maslo": f"https://www.kupi.cz/hledej?f={q('máslo')}&vse=0",
    "kupi_cz_search_mozzarella": "https://www.kupi.cz/hledej?f=mozzarella&vse=0",
    "kupi_cz_search_kureci_prsa": f"https://www.kupi.cz/hledej?f={q('kuřecí prsní řízky')}&vse=0",
    "kupi_cz_search_vejce": "https://www.kupi.cz/hledej?f=vejce&vse=0",
    "kupi_cz_search_toaletni_papir": f"https://www.kupi.cz/hledej?f={q('toaletní papír')}&vse=0",
    "kupi_cz_shop_lidl": "https://www.kupi.cz/slevy/lidl",
    # Kupi.sk (Kezmarok)
    "kupi_sk_home": "https://www.kupi.sk/",
    "kupi_sk_search_maslo": f"https://www.kupi.sk/hladaj?f={q('maslo')}&vse=0",
    # Chains' own sites
    "lidl_cz_home": "https://www.lidl.cz/",
    "kaufland_cz_home": "https://www.kaufland.cz/",
    "kaufland_cz_offers": "https://www.kaufland.cz/akcni-nabidka/aktualni-tyden.html",
    "tesco_cz_search_maslo": f"https://nakup.itesco.cz/groceries/cs-CZ/search?query={q('máslo')}",
    "billa_cz_home": "https://www.billa.cz/",
    "albert_cz_home": "https://www.albert.cz/",
    "dm_cz_home": "https://www.dm.cz/",
    "teta_cz_home": "https://www.tetadrogerie.cz/",
}

robots_cache = {}


def robots_for(url):
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        info = {"status": None, "text": ""}
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            info["status"] = r.status_code
            info["text"] = r.text[:20000]
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])
        except Exception as e:  # noqa: BLE001
            info["status"] = f"error: {e}"
            rp.parse([])
        robots_cache[base] = (rp, info)
        with open(os.path.join(OUT, re.sub(r"\W+", "_", parts.netloc) + "_robots.txt"), "w") as f:
            f.write(str(info["status"]) + "\n\n" + info["text"])
        time.sleep(DELAY_S)
    return robots_cache[base]


def find_terms_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        text = (a.get_text(" ", strip=True) or "").lower()
        if any(k in text for k in ("podmín", "podmien", "pravidl", "terms")):
            links.append(urllib.parse.urljoin(base_url, a["href"]))
    return list(dict.fromkeys(links))[:3]


summary = {}
extra = {}
for name, url in TARGETS.items():
    rp, rinfo = robots_for(url)
    allowed = rp.can_fetch(UA, url) and rp.can_fetch("*", url)
    entry = {"url": url, "robots_status": rinfo["status"], "allowed_by_robots": allowed}
    if not allowed:
        entry["skipped"] = "disallowed by robots.txt"
        summary[name] = entry
        print(f"[SKIP robots] {name}")
        continue
    try:
        t0 = time.time()
        r = session.get(url, timeout=30)
        entry.update({
            "status": r.status_code,
            "final_url": r.url,
            "content_type": r.headers.get("content-type"),
            "bytes": len(r.content),
            "seconds": round(time.time() - t0, 2),
        })
        with open(os.path.join(OUT, name + ".html"), "wb") as f:
            f.write(r.content)
        html = r.text
        if "kupi" in url:
            soup = BeautifulSoup(html, "html.parser")
            entry["group_discounts"] = len(soup.find_all("div", class_="group_discounts"))
            entry["discount_rows"] = len(soup.find_all("div", class_="discount_row"))
        if name.endswith("_home"):
            for i, tl in enumerate(find_terms_links(html, r.url)):
                extra[f"{name}_terms_{i}"] = tl
        print(f"[{r.status_code}] {name} {entry.get('bytes')} B")
    except Exception as e:  # noqa: BLE001
        entry["error"] = str(e)
        print(f"[ERR] {name}: {e}")
    summary[name] = entry
    time.sleep(DELAY_S)

for name, url in extra.items():
    rp, rinfo = robots_for(url)
    if not (rp.can_fetch(UA, url) and rp.can_fetch("*", url)):
        summary[name] = {"url": url, "skipped": "disallowed by robots.txt"}
        continue
    try:
        r = session.get(url, timeout=30)
        with open(os.path.join(OUT, name + ".html"), "wb") as f:
            f.write(r.content)
        summary[name] = {"url": url, "status": r.status_code, "final_url": r.url, "bytes": len(r.content)}
        print(f"[{r.status_code}] {name}")
    except Exception as e:  # noqa: BLE001
        summary[name] = {"url": url, "error": str(e)}
    time.sleep(DELAY_S)

with open(os.path.join(OUT, "summary.json"), "w") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
