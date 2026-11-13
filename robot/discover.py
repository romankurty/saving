"""Discovery run 57: Dacia robots.txt status."""
import requests

UA = "saving-carbot/1.0 (personal new-car offer check; non-commercial; github.com/romankurty/saving)"
for u in ["https://skladove-vozidla.dacia.sk/robots.txt", "https://skladove-vozidla.dacia.sk/sitemap.xml"]:
    try:
        r = requests.get(u, headers={"User-Agent": UA}, timeout=25)
        print(u, r.status_code, len(r.text), repr(r.text[:600]))
    except Exception as e:  # noqa: BLE001
        print(u, "ERR", e)
print("DONE")
