"""Report which hard rules have a test. With --release, fail if any do not (F9)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
rules = re.findall(r"^\| ([A-G]\d+) \|", (ROOT / "HARD_RULES.md").read_text(encoding="utf-8"),
                   re.M)
tests = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "server/tests").glob("test_*.py"))
proven = set(re.findall(r"mark\.rule\(\"([A-G]\d+)\"\)", tests))
missing = [r for r in rules if r not in proven]
print(f"{len(rules) - len(missing)} of {len(rules)} hard rules have a test")
print("Missing:", " ".join(missing) or "none")
if "--release" in sys.argv and (missing or not rules):
    sys.exit(1)
