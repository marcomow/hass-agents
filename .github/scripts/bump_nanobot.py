"""Bump nanobot-ai to the latest PyPI release and bump the add-on patch version.

Writes GitHub Actions outputs:
  updated      "true" when a newer nanobot-ai release was applied
  old_nanobot  / new_nanobot    nanobot-ai versions
  old_addon    / new_addon      add-on versions
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "agent" / "Dockerfile"
CONFIG = ROOT / "agent" / "config.yaml"

PIN_RE = re.compile(r"nanobot-ai==([0-9][^\s]*)")
LABEL_RE = re.compile(r'io\.hass\.version="[^"]*"')
ADDON_RE = re.compile(r'^version:\s*"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v))


def output(**kwargs: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{k}={v}" for k, v in kwargs.items()]
    if path:
        with open(path, "a") as f:
            f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


with urllib.request.urlopen("https://pypi.org/pypi/nanobot-ai/json", timeout=30) as r:
    latest = json.load(r)["info"]["version"]

dockerfile = DOCKERFILE.read_text()
m = PIN_RE.search(dockerfile)
if not m:
    sys.exit("could not find nanobot-ai pin in agent/Dockerfile")
current = m.group(1)

if version_key(latest) <= version_key(current):
    print(f"nanobot-ai {current} is up to date (PyPI latest: {latest})")
    output(updated="false")
    sys.exit(0)

dockerfile = PIN_RE.sub(f"nanobot-ai=={latest}", dockerfile, count=1)
dockerfile = LABEL_RE.sub(f'io.hass.version="{latest}"', dockerfile, count=1)
DOCKERFILE.write_text(dockerfile)

config = CONFIG.read_text()
a = ADDON_RE.search(config)
if not a:
    sys.exit("could not find add-on version in agent/config.yaml")
major, minor, patch = (int(x) for x in a.groups())
old_addon = f"{major}.{minor}.{patch}"
new_addon = f"{major}.{minor}.{patch + 1}"
CONFIG.write_text(ADDON_RE.sub(f'version: "{new_addon}"', config, count=1))

output(
    updated="true",
    old_nanobot=current,
    new_nanobot=latest,
    old_addon=old_addon,
    new_addon=new_addon,
)
