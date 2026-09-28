"""Fetch missing Chennai pincode boundaries from Esri India Living Atlas.

Source: https://livingatlas.esri.in/server1/rest/services/India/Pincode_Boundary_2025/MapServer/0
Attribution: Esri India / Department of Posts (Living Atlas)

Run once: python data/fetch_missing_pincodes.py
"""
import json
from pathlib import Path
import requests

DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw"
RAW_DIR.mkdir(exist_ok=True)

CHENNAI_GEOJSON = DATA_DIR / "chennai_pincodes.geojson"
RAW_ESRI_FILE = RAW_DIR / "esri_missing_pincodes.geojson"

ESRI_QUERY_URL = (
    "https://livingatlas.esri.in/server1/rest/services/India/"
    "Pincode_Boundary_2025/MapServer/0/query"
)

CHENNAI_LON_RANGE = (79.5, 80.8)
CHENNAI_LAT_RANGE = (12.5, 13.6)


def load_existing():
    with open(CHENNAI_GEOJSON) as f:
        return json.load(f)


def get_missing_pincodes(existing_gj):
    current = {f["properties"]["pincode"] for f in existing_gj["features"]}
    expected = {str(i) for i in range(600001, 600120)}
    return sorted(expected - current), current


def fetch_from_esri(missing):
    in_clause = ",".join("'" + p + "'" for p in missing)
    params = {
        "where": "pin_code IN (" + in_clause + ")",
        "outFields": "pin_code,fname,type",
        "outSR": "4326",
        "f": "geojson",
    }
    print("[esri] Querying " + str(len(missing)) + " pincodes from Esri Living Atlas...")
    resp = requests.get(ESRI_QUERY_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    RAW_ESRI_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    size_kb = RAW_ESRI_FILE.stat().st_size // 1024
    print("[esri] Raw response saved to " + str(RAW_ESRI_FILE) + " (" + str(size_kb) + " KB)")
    return data


def validate_feature(feat):
    geom = feat.get("geometry")
    props = feat.get("properties", {})
    pin = props.get("pin_code", "???")

    if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
        gtype = geom.get("type") if geom else "null"
        return False, pin + ": invalid geometry type " + str(gtype)

    coords = geom["coordinates"]
    if geom["type"] == "Polygon":
        rings = coords
    else:
        rings = [r for poly in coords for r in poly]

    if not rings or not rings[0]:
        return False, pin + ": empty coordinates"

    for ring in rings:
        for pt in ring:
            lon, lat = pt[0], pt[1]
            if not (CHENNAI_LON_RANGE[0] <= lon <= CHENNAI_LON_RANGE[1]):
                return False, pin + ": longitude " + str(lon) + " outside Chennai range"
            if not (CHENNAI_LAT_RANGE[0] <= lat <= CHENNAI_LAT_RANGE[1]):
                return False, pin + ": latitude " + str(lat) + " outside Chennai range"

    first_ring = rings[0]
    if first_ring[0] != first_ring[-1]:
        return False, pin + ": ring not closed"
    if len(first_ring) < 4:
        return False, pin + ": ring has fewer than 4 points"

    return True, None


def to_multipolygon(geom):
    if geom["type"] == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
    return geom


def to_our_schema(feat):
    props = feat["properties"]
    return {
        "type": "Feature",
        "properties": {
            "pincode": props["pin_code"],
            "state": "Tamil Nadu",
            "district": "Chennai",
            "officename": props.get("fname", ""),
            "officetype": props.get("type", ""),
            "orig_ogc_fid": None,
            "source": "esri_livingatlas",
        },
        "geometry": to_multipolygon(feat["geometry"]),
    }


def main():
    existing_gj = load_existing()
    old_count = len(existing_gj["features"])
    print("[merge] Existing pincodes: " + str(old_count))

    missing, current_pins = get_missing_pincodes(existing_gj)
    print("[merge] Missing pincodes to fetch: " + str(len(missing)))

    esri_data = fetch_from_esri(missing)
    fetched_features = esri_data.get("features", [])
    fetched_pins = {f["properties"]["pin_code"] for f in fetched_features}
    print("[esri] Fetched: " + str(len(fetched_features)) + " features")

    not_found = sorted(set(missing) - fetched_pins)
    print("[esri] Not available (" + str(len(not_found)) + "): " + ", ".join(not_found))

    valid = []
    rejected = []
    duplicates = []

    for feat in fetched_features:
        pin = feat["properties"]["pin_code"]
        if pin in current_pins:
            duplicates.append(pin)
            continue
        ok, reason = validate_feature(feat)
        if not ok:
            rejected.append(reason)
            print("[validate] REJECTED: " + reason)
            continue
        valid.append(to_our_schema(feat))

    print("")
    print("--- Summary ---")
    print("Old count:        " + str(old_count))
    print("Fetched:          " + str(len(fetched_features)))
    print("Duplicates:       " + str(len(duplicates)))
    print("Invalid/rejected: " + str(len(rejected)))
    print("Valid new:        " + str(len(valid)))
    print("Not in Esri:      " + str(len(not_found)))

    if rejected:
        for r in rejected:
            print("  REJECTED: " + r)

    existing_gj["features"].extend(valid)
    final_count = len(existing_gj["features"])
    print("Final count:      " + str(final_count))

    with open(CHENNAI_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(existing_gj, f)
    print("[merge] Written to " + str(CHENNAI_GEOJSON))

    if not_found:
        print("")
        print("Unavailable pincodes (" + str(len(not_found)) + "):")
        for p in not_found:
            print("  " + p)


if __name__ == "__main__":
    main()
