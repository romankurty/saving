"""Discovery run 27: Lidl leaflets on the Schwarz leaflet platform (same as Kaufland) - CZ and SK."""
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import fetch_prices as F  # noqa: E402

for loc in ("lidl%2Fcs-CZ", "lidl%2Fsk-SK"):
    for extra in ("", "&store_id=1"):
        r = F.get(f"https://endpoints.leaflets.schwarz/v4/overview?client_locale={loc}{extra}", as_json=True)
        print("==", loc, extra or "(no store)", "status", r.status_code if r is not None else None)
        if r is None:
            continue
        j = r.json()
        print("   keys:", list(j.keys())[:10])
        for cat in j.get("categories", [])[:8]:
            for sub in cat.get("subcategories", [])[:10]:
                fl = sub.get("flyers", [])
                print("   cat", cat.get("name"), "| sub", sub.get("name"), "| flyers", [(f.get("title"), f.get("offerStartDate"), f.get("offerEndDate"), f.get("id")) for f in fl[:4]])
        # first flyer pages + keywords sample
        for cat in j.get("categories", [])[:1]:
            for sub in cat.get("subcategories", [])[:1]:
                for f in sub.get("flyers", [])[:1]:
                    fr = F.get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={urllib.parse.quote(f['id'])}", as_json=True)
                    if fr is not None:
                        pages = fr.json().get("flyer", {}).get("pages") or []
                        print("   first flyer pages", len(pages), "kw sample:", [(p.get("number"), (p.get("keyWords") or "")[:80]) for p in pages[:5]])
        break
