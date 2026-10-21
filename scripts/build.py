#!/usr/bin/env python3
"""Build a PS5 Library compatible Pegasus catalog from explicitly configured sources."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "atlas-sources.json"
OUTPUT = ROOT / "catalog.json"
REPORT = ROOT / "build-report.json"

def fetch(url):
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS source URLs are supported")
    req = urllib.request.Request(url, headers={"User-Agent": "PS5-Atlas/0.1 (+GitHub Actions)"})
    with urllib.request.urlopen(req, timeout=35) as response:
        data = response.read(35_000_001)
    if len(data) > 35_000_000:
        raise ValueError("Source exceeds 35 MB")
    return json.loads(data.decode("utf-8"))

def package_identity(p):
    # Preserve distinct versions, regions and mirrors; only remove exact duplicate packages.
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    packages, seen, stats = [], set(), []
    success = 0
    for item in config["sources"]:
        if not item.get("enabled", True):
            continue
        try:
            payload = fetch(item["url"])
            if not isinstance(payload, dict) or not isinstance(payload.get("packages"), list):
                raise ValueError("Expected Pegasus catalog with a packages array")
            count = 0
            for p in payload["packages"]:
                if not isinstance(p, dict):
                    continue
                key = package_identity(p)
                if key in seen:
                    continue
                seen.add(key)
                packages.append(p)
                count += 1
            success += 1
            stats.append({"name":item["name"],"status":"ok","source_records":len(payload["packages"]),"new_records":count})
        except Exception as e:
            stats.append({"name":item.get("name", "?"),"status":"error","detail":str(e)[:250]})
    if success == 0 or not packages:
        raise SystemExit("No valid catalogs fetched; keeping prior catalog.json unchanged")
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    catalog = {"name":"PS5 Atlas","version":generated,"packages":packages}
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({"generated_at":generated,"records":len(packages),"sources":stats}, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(packages)} catalog entries")
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
