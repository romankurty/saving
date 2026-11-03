"""Discovery run 26: where are Lidl's FOOD offer pages linked? (leaflet page, sitemap)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import fetch_prices as F  # noqa: E402

FOOD = re.compile(r"nabidk|ponuk|potravin|maso|maso|ovoce|zelenin|ovocie|mlec|mliec|pecivo|napoj|napoje|ryb|syr|lahud|trvanl|mrazen|pondel|ctvrt|stvrt|vikend|tyzd|tyden|cerstv|cerstve|xxl|super|akcn|akcia|farm|bio|vegan|zdrav|cukrov|sladk|kava|caj|grill|svaci|snidan|ranajk|piekar|cesk|slovensk")
for base in ("https://www.lidl.cz", "https://www.lidl.sk"):
    home = F.get(base + "/")
    s_links = sorted(set(re.findall(r'href="(/c/[a-z0-9-]+/s\d+)"', home.text))) if home else []
    print("==", base, "s-links with letak/leaflet/nabidk:", [x for x in s_links if re.search(r"letak|nabidk|ponuk|akc", x)])
    for sl in [x for x in s_links if re.search(r"letak|nabidk|ponuk|akc", x)][:3]:
        r = F.get(base + sl)
        if r is None:
            continue
        a = list(dict.fromkeys(re.findall(r'href="(/c/[a-z0-9-]+/a\d+)"', r.text)))
        print("  ", sl, "-> a-links:", a[:40])
    sm = F.get(base + "/static/sitemap.xml")
    if sm is not None:
        locs = re.findall(r"<loc>([^<]+)</loc>", sm.text)
        print("   sitemap entries:", len(locs), locs[:8])
        sub = [u for u in locs if "sitemap" in u][:10]
        for u in sub[:6]:
            r = F.get(u)
            if r is None:
                continue
            ll = re.findall(r"<loc>([^<]+)</loc>", r.text)
            cpages = [x for x in ll if re.search(r"/c/[a-z0-9-]+/a\d+", x)]
            food = [x for x in cpages if FOOD.search(x)]
            print("   ", u, "entries", len(ll), "c/a pages", len(cpages), "food-like:", food[:30])
