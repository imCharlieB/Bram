"""Fail if versions disagree, or shipped code changed without a version bump."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SHIPPED = ["custom_components", "server/bram", "server/Dockerfile", "server/pyproject.toml"]


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)  # noqa: S603, S607


manifest = json.loads((ROOT / "custom_components/bram/manifest.json").read_text("utf-8"))
version = manifest["version"]
server = re.search(r'^version = "(.+)"', (ROOT / "server/pyproject.toml").read_text("utf-8"), re.M)
problems = []
if server is None or server[1] != version:
    problems.append("manifest.json and pyproject.toml have different versions")
if f"\n## {version}\n" not in (ROOT / "CHANGELOG.md").read_text("utf-8"):
    problems.append(f"CHANGELOG.md has no section for {version}")
tag = f"v{version}"
if git("rev-parse", "-q", "--verify", f"refs/tags/{tag}").returncode == 0 and git(
        "diff", "--quiet", tag, "--", *SHIPPED).returncode != 0:
    problems.append(f"Code changed since {tag}: bump the version")
print("\n".join(problems) or f"Version {version} is consistent")
sys.exit(bool(problems))
