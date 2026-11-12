"""Discovery run 46: run the independent offer audit on the current data (no write-back)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import caraudit  # noqa: E402

import json  # noqa: E402

data = json.load(open(os.path.join(caraudit.ROOT, "auta", "data", "offers.json"), encoding="utf-8"))
print(caraudit.audit(data["offers"], n=45, seed=1))
print("DONE")
