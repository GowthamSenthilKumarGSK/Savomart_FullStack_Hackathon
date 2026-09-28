"""Seed Chennai pincode boundaries.

Uses a pre-built GeoJSON of Chennai-area pincodes stored in data/chennai_pincodes.geojson.
If not present, downloads India pincode boundaries from data.gov.in and filters to Chennai.
"""
import json
from pathlib import Path

from sqlalchemy import text
from app.database import async_session

DATA_DIR = Path(__file__).parent
CHENNAI_PINCODES_FILE = DATA_DIR / "chennai_pincodes.geojson"

CHENNAI_PINCODE_RANGES = [
    range(600001, 600130),
    range(601001, 601300),
    range(602001, 602120),
    range(603001, 603130),
]

CHENNAI_BBOX = {
    "min_lon": 79.95,
    "max_lon": 80.35,
    "min_lat": 12.75,
    "max_lat": 13.30,
}


def is_chennai_pincode(code: str) -> bool:
    try:
        n = int(code)
    except ValueError:
        return False
    return any(n in r for r in CHENNAI_PINCODE_RANGES)


def point_in_chennai(lon: float, lat: float) -> bool:
    return (
        CHENNAI_BBOX["min_lon"] <= lon <= CHENNAI_BBOX["max_lon"]
        and CHENNAI_BBOX["min_lat"] <= lat <= CHENNAI_BBOX["max_lat"]
    )


async def seed_pincodes():
    print("[Pincodes] Loading Chennai pincode boundaries...")

    if not CHENNAI_PINCODES_FILE.exists():
        print(f"[Pincodes] ERROR: {CHENNAI_PINCODES_FILE} not found.")
        print("[Pincodes] Please run: python data/fetch_pincodes.py first,")
        print("[Pincodes] or place a GeoJSON of Chennai pincodes at the path above.")
        return

    with open(CHENNAI_PINCODES_FILE, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    print(f"[Pincodes] Found {len(features)} features in GeoJSON.")

    async with async_session() as session:
        r = await session.execute(text("SELECT COUNT(*) FROM pincodes"))
        existing = r.scalar()

        inserted = 0
        skipped = 0
        errors = 0

        for feat in features:
            props = feat.get("properties", {})
            code = str(props.get("pincode", props.get("Pincode", props.get("PIN", ""))))
            if not code or not code.isdigit():
                errors += 1
                continue

            geom = feat.get("geometry")
            if not geom:
                errors += 1
                continue

            geom_type = geom.get("type", "")
            if geom_type == "Polygon":
                geom["type"] = "MultiPolygon"
                geom["coordinates"] = [geom["coordinates"]]
            elif geom_type != "MultiPolygon":
                errors += 1
                continue

            r = await session.execute(
                text("SELECT 1 FROM pincodes WHERE code = :code"), {"code": code}
            )
            if r.scalar() is not None:
                skipped += 1
                continue

            name = props.get("officename", props.get("Name", props.get("name", "")))
            geom_json = json.dumps(geom)

            try:
                await session.execute(
                    text(
                        "INSERT INTO pincodes (id, code, name, geometry) "
                        "VALUES (gen_random_uuid(), :code, :name, "
                        "ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))"
                    ),
                    {"code": code, "name": name, "geom": geom_json},
                )
                inserted += 1
            except Exception as e:
                print(f"[Pincodes] Error inserting {code}: {e}")
                await session.rollback()
                errors += 1

        await session.commit()
    print(f"[Pincodes] Inserted {inserted}, skipped {skipped} existing, {errors} errors. Total now {existing + inserted}.")
