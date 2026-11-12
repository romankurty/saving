"""Discovery run 44: Kia listing pagination + autobazar first-page URL."""
import re
import time

import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "sk-SK,sk;q=0.9"})


def vins(url):
    time.sleep(1.2)
    try:
        r = S.get(url, timeout=25)
    except Exception as e:  # noqa: BLE001
        print("ERR", url, e)
        return [], ""
    v = list(dict.fromkeys(re.findall(r"/vozidla/([A-HJ-NPR-Z0-9]{17})/", r.text)))
    print(r.status_code, len(v), v[:2], url)
    return v, r.text


base, t = vins("https://www.kiaihned.sk/vozidla?model=K4")
for q in ["&page=2", "&strana=2", "&p=2", "&per_page=100", "&perPage=100", "&limit=100", "&take=100", "&offset=30"]:
    vins("https://www.kiaihned.sk/vozidla?model=K4" + q)
vins("https://www.kiaihned.sk/vozidla")
vins("https://www.kiaihned.sk/vozidla?page=2")
print("count text:", re.findall(r"(\d+)\s*(?:áut|vozid\w*|výsledk\w*)", re.sub(r"<[^>]+>", " ", t))[:10])
for pat in [r"wire:click=\"[^\"]*\"", r"x-on:click=\"[^\"]*\"", r"@click=\"[^\"]*\"", r"wire:[a-z.]+=\"[^\"]{0,80}\"", r"data-[a-z-]*page[a-z-]*=\"[^\"]*\"", r"[Nn]a[čc][ií]ta[ťt] ďal[šs]ie|Zobraziť viac|Ďalšie", r"\?page=\d+"]:
    print(pat, sorted(set(re.findall(pat, t)))[:8])
i = t.find("wire:snapshot")
print("snapshot head:", t[i:i + 600] if i >= 0 else None)
j = t.find("livewire")
print("livewire refs:", sorted(set(re.findall(r'https?://[^"\']*livewire[^"\']*', t)))[:5])
time.sleep(1.2)
r = S.get("https://www.autobazar.eu/vysledky-nove-auta/?category=30900&priceFrom=0&priceTo=12000", timeout=25)
print("ab no-page", r.status_code)
time.sleep(1.2)
r = S.get("https://www.autobazar.eu/vysledky-nove-auta/?category=30900&priceTo=12000", timeout=25)
print("ab priceTo only", r.status_code)
time.sleep(1.2)
r = S.get("https://www.autobazar.eu/vysledky-nove-auta/?category=30900&priceFrom=12000&priceTo=15000&page=2", timeout=25)
print("ab page2", r.status_code)
sm = S.get("https://kiaihned.sk/sitemap.xml", timeout=25).text
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
k4 = [l for l in locs if re.search(r"/vozidla/[A-Z0-9]{17}/k4-", l)]
print("sitemap vehicle urls:", sum(1 for l in locs if "/vozidla/" in l and re.search(r"[A-Z0-9]{17}", l)), "k4:", len(k4), "lastmod sample:", re.findall(r"<lastmod>([^<]+)</lastmod>", sm)[:3])
print("DONE")
