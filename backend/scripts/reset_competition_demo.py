"""Remove only the isolated competition database and its synthetic assets."""

import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TARGETS = [BASE / "data" / "site_secretary_demo.db", BASE / "data" / "uploads" / "demo"]

for target in TARGETS:
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()

print("Competition demo database and synthetic uploads removed.")
