"""Discovery run 25: why does Lidl give so few offers? tiles per page, sample names, match + validity reasons."""
import html as htmlmod
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import fetch_prices as F  # noqa: E402

for base in ("https://www.lidl.cz", "https://www.lidl.sk"):
    home = F.get(base + "/")
    pages = list(dict.fromkeys(re.findall(r'href="(/c/[a-z0-9-]+/a\d+)"', home.text))) if home else []
    other = sorted(set(re.findall(r'href="(/[a-z]/[a-z0-9-]+/[a-z]\d+)"', home.text)))[:30] if home else []
    print("==", base, "offer pages", len(pages), pages[:20])
    print("   other link shapes:", other)
    tot, why = 0, Counter()
    for path in pages[:20]:
        r = F.get(base + path)
        if r is None:
            print("  ", path, "fetch failed"); continue
        tiles = re.findall(r'data-grid-data="([^"]+)"', r.text)
        names = []
        for raw in tiles:
            try:
                d = json.loads(htmlmod.unescape(raw))
            except Exception:
                why["json"] += 1; continue
            d = d[0] if isinstance(d, list) and d else d
            name = (d.get("fullTitle") or d.get("title") or "") if isinstance(d, dict) else ""
            names.append(name)
            ids = F.match_items(name)
            why["match" if ids else "nomatch"] += 1
        tot += len(tiles)
        print(f"   {path}: {len(tiles)} tiles, html {len(r.text)//1000} kB, sample: {names[:6]}")
    print("   total tiles", tot, dict(why))
