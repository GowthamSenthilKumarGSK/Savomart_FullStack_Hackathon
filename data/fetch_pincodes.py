"""Fetch Chennai pincode boundaries from tanaygshah/India-Pincode-Boundary-Data.

Downloads the Tamil Nadu state GeoJSON via Git LFS batch API, then filters
to Chennai-area pincodes (600xxx, 601xxx, 602xxx, 603xxx).

Source: https://github.com/tanaygshah/India-Pincode-Boundary-Data
License: see source repo.

Produces data/chennai_pincodes.geojson.
Run once: python data/fetch_pincodes.py
"""
import json
import re
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw"
RAW_DIR.mkdir(exist_ok=True)

RAW_TN_FILE = RAW_DIR / "tamil-nadu-pincodes.geojson"
OUTPUT_FILE = DATA_DIR / "chennai_pincodes.geojson"

REPO = "tanaygshah/India-Pincode-Boundary-Data"
LFS_OID = "d0ee9fd63ec906be2b64681a84ccb655640c7108344a642a68640be913330b58"
LFS_SIZE = 10977280

CHENNAI_PINCODE_PREFIXES = ("600", "601", "602", "603")


def download_tn_geojson():
    """Download Tamil Nadu pincode GeoJSON via GitHub LFS batch API."""
    if RAW_TN_FILE.exists() and RAW_TN_FILE.stat().st_size == LFS_SIZE:
        print(f"[fetch_pincodes] Using cached {RAW_TN_FILE}")
        return

    print(f"[fetch_pincodes] Downloading Tamil Nadu GeoJSON via LFS (~{LFS_SIZE // 1024 // 1024}MB)...")
    batch_url = f"https://github.com/{REPO}.git/info/lfs/objects/batch"
    payload = {
        "operation": "download",
        "transfers": ["basic"],
        "objects": [{"oid": LFS_OID, "size": LFS_SIZE}],
    }
    headers = {
        "Accept": "application/vnd.git-lfs+json",
        "Content-Type": "application/vnd.git-lfs+json",
    }
    resp = requests.post(batch_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    obj = resp.json()["objects"][0]

    if "error" in obj:
        raise RuntimeError(f"LFS error: {obj['error']}")

    dl_url = obj["actions"]["download"]["href"]
    dl_headers = obj["actions"]["download"].get("header", {})
    dl = requests.get(dl_url, headers=dl_headers, timeout=120)
    dl.raise_for_status()

    RAW_TN_FILE.write_bytes(dl.content)
    print(f"[fetch_pincodes] Downloaded {len(dl.content)} bytes to {RAW_TN_FILE}")


def extract_chennai_features(content: str) -> list:
    """Extract complete Chennai pincode features from potentially truncated GeoJSON.

    The Tamil Nadu file from the source repo is truncated at the LFS-recorded
    size. We parse individual features by locating their boundaries via regex,
    which works because all Chennai pincodes (600-603) sort before the
    truncation point (~641xxx).
    """
    starts = [m.start() for m in re.finditer(r'\{\s*"type":\s*"Feature"', content)]
    if not starts:
        raise ValueError("No Feature objects found in GeoJSON")

    features = []
    errors = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(content)
        feat_text = content[start:end].rstrip().rstrip(",").rstrip()

        m = re.search(r'"pincode":\s*"(\d+)"', feat_text[:300])
        if not m:
            continue
        pc = m.group(1)
        if not pc.startswith(CHENNAI_PINCODE_PREFIXES):
            continue

        try:
            feat = json.loads(feat_text)
            features.append(feat)
        except json.JSONDecodeError as e:
            errors.append((pc, str(e)))

    return features, errors


def validate_features(features: list):
    """Validate geometry, CRS, duplicates."""
    issues = []
    pincodes_seen = set()

    for f in features:
        pc = f["properties"]["pincode"]
        if pc in pincodes_seen:
            issues.append(f"Duplicate pincode: {pc}")
        pincodes_seen.add(pc)

        geom = f.get("geometry", {})
        if geom.get("type") != "MultiPolygon":
            issues.append(f"{pc}: unexpected geometry type {geom.get('type')}")
            continue

        coords = geom.get("coordinates", [])
        if not coords:
            issues.append(f"{pc}: empty geometry")
            continue

        for pi, poly in enumerate(coords):
            for ri, ring in enumerate(poly):
                if len(ring) < 4:
                    issues.append(f"{pc}: ring too short (poly={pi}, ring={ri}, len={len(ring)})")
                if ring[0] != ring[-1]:
                    issues.append(f"{pc}: ring not closed (poly={pi}, ring={ri})")

    return issues


def main():
    download_tn_geojson()

    print("[fetch_pincodes] Extracting Chennai pincode features...")
    content = RAW_TN_FILE.read_text(encoding="utf-8")
    features, parse_errors = extract_chennai_features(content)

    if parse_errors:
        print(f"[fetch_pincodes] WARNING: {len(parse_errors)} features failed to parse:")
        for pc, err in parse_errors:
            print(f"  {pc}: {err}")

    if not features:
        print("[fetch_pincodes] ERROR: No Chennai pincodes found.")
        return

    print(f"[fetch_pincodes] Found {len(features)} Chennai pincode features.")

    issues = validate_features(features)
    if issues:
        print(f"[fetch_pincodes] Validation issues ({len(issues)}):")
        for issue in issues:
            print(f"  {issue}")
        return

    print("[fetch_pincodes] Validation passed (geometry, CRS, duplicates, ring closure).")

    geojson = {"type": "FeatureCollection", "features": features}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(geojson, f)
    print(f"[fetch_pincodes] Wrote {len(features)} pincodes to {OUTPUT_FILE}")

    prefix_counts = {}
    for feat in features:
        prefix = feat["properties"]["pincode"][:3]
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    for prefix, count in sorted(prefix_counts.items()):
        print(f"  {prefix}xxx: {count} pincodes")


if __name__ == "__main__":
    main()
