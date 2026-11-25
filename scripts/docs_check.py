"""Fail on broken local links, orphaned docs, or undocumented command options."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
pages = [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md")]
problems = []

for page in pages:
    for link in re.findall(r"\]\(([^)]+)\)", page.read_text(encoding="utf-8")):
        target = link.split("#")[0]
        if target and "://" not in target and not (page.parent / target).exists():
            problems.append(f"{page.relative_to(ROOT)}: broken link {link}")

index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
docs = "".join(p.read_text(encoding="utf-8") for p in ROOT.glob("docs/**/*.md"))
for page in ROOT.glob("docs/**/*.md"):
    if page.name != "README.md" and f"({page.name})" not in index:
        problems.append(f"{page.relative_to(ROOT)}: not linked from docs/README.md")

for source in ROOT.glob("server/bram/**/*.py"):
    text = source.read_text(encoding="utf-8")
    for option in re.findall(r"add_argument\(\s*\"(--[a-z-]+)\"", text):
        if f"`{option}`" not in docs:
            problems.append(f"{source.relative_to(ROOT)}: {option} is not in docs/")
    for setting in set(re.findall(r"\"(BRAM_[A-Z_]+)\"", text)):
        if f"`{setting}`" not in docs:
            problems.append(f"{source.relative_to(ROOT)}: {setting} is not in docs/")

print("\n".join(problems) or "Docs check passed")
sys.exit(bool(problems))
