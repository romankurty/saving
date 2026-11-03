"""Discovery run 24: did Billa / Lidl change their robots rules? (status + rules for the paths we use)."""
import os
import sys
import urllib.robotparser

sys.path.insert(0, os.path.dirname(__file__))
import fetch_prices as F  # noqa: E402

for base, paths in (("https://www.billa.cz", ["/api/product-discovery/products?page=0&pageSize=1&term=vejce"]),
                    ("https://www.billa.sk", ["/api/product-discovery/products?page=0&pageSize=1&term=vajcia"]),
                    ("https://www.lidl.cz", ["/c/akcni-nabidka/s10008", "/"]), ("https://www.lidl.sk", ["/"])):
    try:
        r = F.session.get(base + "/robots.txt", timeout=20)
        print("==", base, "robots.txt status", r.status_code, "len", len(r.text))
        lines = [ln for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]
        print("\n".join(lines[:40]))
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        for pth in paths:
            print("  can_fetch", pth, rp.can_fetch(F.UA, base + pth))
    except Exception as e:  # noqa: BLE001
        print("ERR", base, e)
