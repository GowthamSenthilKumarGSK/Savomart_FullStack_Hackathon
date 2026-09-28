"""Seed OSM POIs and roads from Geofabrik Southern Zone PBF extract.

Downloads the extract once, then reads it with pyosmium to populate
osm_pois and osm_roads tables.

Normal seed: skips PBF parsing if both tables already have data.
Force rebuild: pass force=True to seed_osm() or run with --force flag.
"""
import json
from collections import Counter
from pathlib import Path

import osmium
import requests
from tqdm import tqdm
from sqlalchemy import text
from app.database import async_session

DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw"
RAW_DIR.mkdir(exist_ok=True)

GEOFABRIK_URL = "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
PBF_FILE = RAW_DIR / "southern-zone-latest.osm.pbf"

CHENNAI_BBOX = (79.95, 12.75, 80.35, 13.30)  # (min_lon, min_lat, max_lon, max_lat)

POI_TAGS = {"shop", "amenity", "office"}
BUILDING_SUBTYPES = {"residential", "apartments", "commercial", "retail", "industrial"}

ROAD_TYPES = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "living_street", "service",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
    "pedestrian", "footway", "cycleway", "track", "path",
}


def in_bbox(lon, lat):
    return (CHENNAI_BBOX[0] <= lon <= CHENNAI_BBOX[2] and
            CHENNAI_BBOX[1] <= lat <= CHENNAI_BBOX[3])


def download_pbf():
    if PBF_FILE.exists():
        size_mb = PBF_FILE.stat().st_size // (1024 * 1024)
        print(f"[OSM] Using cached PBF: {PBF_FILE} ({size_mb}MB)")
        return
    print("[OSM] Downloading Geofabrik Southern Zone extract...")
    print(f"  URL: {GEOFABRIK_URL}")
    print("  This is ~500-800MB and may take several minutes.")
    resp = requests.get(GEOFABRIK_URL, stream=True, timeout=600)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    tmp = PBF_FILE.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        with tqdm(total=total, unit="B", unit_scale=True, desc="Downloading") as pbar:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
                pbar.update(len(chunk))
    tmp.rename(PBF_FILE)
    print(f"[OSM] Saved to {PBF_FILE}")


class ChennaiHandler(osmium.SimpleHandler):
    """Single-pass handler that collects both POIs and roads within Chennai bbox."""

    def __init__(self):
        super().__init__()
        self.pois = []
        self.roads = []

    def node(self, n):
        if not in_bbox(n.location.lon, n.location.lat):
            return
        tag_dict = {t.k: t.v for t in n.tags}
        poi = self._try_extract_poi(tag_dict, n.location.lon, n.location.lat)
        if poi:
            poi["osm_id"] = n.id
            poi["osm_type"] = "node"
            self.pois.append(poi)

    def way(self, w):
        coords = []
        for n in w.nodes:
            try:
                if n.location.valid():
                    coords.append((n.location.lon, n.location.lat))
            except osmium.InvalidLocationError:
                continue
        if len(coords) < 2:
            return
        if not any(in_bbox(lon, lat) for lon, lat in coords):
            return

        tag_dict = {t.k: t.v for t in w.tags}

        highway = tag_dict.get("highway")
        if highway in ROAD_TYPES:
            self.roads.append({
                "osm_id": w.id,
                "name": tag_dict.get("name", tag_dict.get("name:en")),
                "road_type": highway,
                "coords": coords,
                "tags": {k: v for k, v in tag_dict.items()
                         if k in ("surface", "lanes", "maxspeed", "oneway", "lit", "sidewalk", "width")},
            })

        avg_lon = sum(c[0] for c in coords) / len(coords)
        avg_lat = sum(c[1] for c in coords) / len(coords)
        if in_bbox(avg_lon, avg_lat):
            poi = self._try_extract_poi(tag_dict, avg_lon, avg_lat)
            if poi:
                poi["osm_id"] = w.id
                poi["osm_type"] = "way"
                self.pois.append(poi)

    def _try_extract_poi(self, tag_dict, lon, lat):
        category = None
        subcategory = None
        for tag_key in POI_TAGS:
            if tag_key in tag_dict:
                category = tag_key
                subcategory = tag_dict[tag_key]
                break
        if category is None:
            building = tag_dict.get("building", "")
            if building in BUILDING_SUBTYPES:
                category = "building"
                subcategory = building
            else:
                return None
        return {
            "category": category,
            "subcategory": subcategory,
            "name": tag_dict.get("name", tag_dict.get("name:en")),
            "lon": lon,
            "lat": lat,
            "tags": tag_dict,
        }


def coords_to_linestring_wkt(coords):
    points = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"SRID=4326;LINESTRING({points})"


async def _check_existing():
    """Return (poi_count, road_count) currently in the database."""
    async with async_session() as session:
        r = await session.execute(text("SELECT COUNT(*) FROM osm_pois"))
        poi_count = r.scalar()
        r = await session.execute(text("SELECT COUNT(*) FROM osm_roads"))
        road_count = r.scalar()
    return poi_count, road_count


async def insert_pois(pois):
    async with async_session() as session:
        await session.execute(text("TRUNCATE osm_pois"))
        await session.commit()

        batch_size = 500
        inserted = 0
        for i in range(0, len(pois), batch_size):
            batch = pois[i:i + batch_size]
            for p in batch:
                await session.execute(
                    text(
                        "INSERT INTO osm_pois (id, osm_id, osm_type, category, subcategory, name, location, tags) "
                        "VALUES (gen_random_uuid(), :osm_id, :osm_type, :category, :subcategory, :name, "
                        "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), CAST(:tags AS jsonb))"
                    ),
                    {
                        "osm_id": p["osm_id"],
                        "osm_type": p["osm_type"],
                        "category": p["category"],
                        "subcategory": p["subcategory"],
                        "name": p["name"],
                        "lon": p["lon"],
                        "lat": p["lat"],
                        "tags": json.dumps(p["tags"]),
                    },
                )
            await session.commit()
            inserted += len(batch)
            if inserted % 5000 == 0 or inserted == len(pois):
                print(f"[OSM]   POIs: {inserted}/{len(pois)}")
        return inserted


async def insert_roads(roads):
    async with async_session() as session:
        await session.execute(text("TRUNCATE osm_roads CASCADE"))
        await session.commit()

        batch_size = 500
        inserted = 0
        for i in range(0, len(roads), batch_size):
            batch = roads[i:i + batch_size]
            for rd in batch:
                wkt = coords_to_linestring_wkt(rd["coords"])
                await session.execute(
                    text(
                        "INSERT INTO osm_roads (id, osm_id, name, road_type, geometry, tags) "
                        "VALUES (gen_random_uuid(), :osm_id, :name, :road_type, "
                        "ST_GeomFromEWKT(:geom), CAST(:tags AS jsonb))"
                    ),
                    {
                        "osm_id": rd["osm_id"],
                        "name": rd["name"],
                        "road_type": rd["road_type"],
                        "geom": wkt,
                        "tags": json.dumps(rd["tags"]),
                    },
                )
            await session.commit()
            inserted += len(batch)
            if inserted % 10000 == 0 or inserted == len(roads):
                print(f"[OSM]   Roads: {inserted}/{len(roads)}")
        return inserted


async def seed_osm(force=False):
    print("[OSM] Starting OSM data seed...")

    poi_count, road_count = await _check_existing()
    if poi_count > 0 and road_count > 0 and not force:
        print(f"[OSM] Already seeded: {poi_count} POIs, {road_count} roads. Skipping PBF parse.")
        print("[OSM] To rebuild, pass force=True or run with --force.")
        return

    if force and (poi_count > 0 or road_count > 0):
        print(f"[OSM] Force rebuild requested. Existing data ({poi_count} POIs, {road_count} roads) will be replaced.")

    download_pbf()

    print("[OSM] Reading POIs and roads from PBF (single pass)...")
    handler = ChennaiHandler()
    handler.apply_file(str(PBF_FILE), locations=True)
    print(f"[OSM] Found {len(handler.pois)} POIs and {len(handler.roads)} road segments in Chennai bbox.")

    if handler.pois:
        print("[OSM] Inserting POIs...")
        poi_count = await insert_pois(handler.pois)
    else:
        poi_count = 0
        print("[OSM] WARNING: No POIs found. Check bbox and PBF file.")

    if handler.roads:
        print("[OSM] Inserting roads...")
        road_count = await insert_roads(handler.roads)
    else:
        road_count = 0
        print("[OSM] WARNING: No roads found. Check bbox and PBF file.")

    print(f"[OSM] Summary: {poi_count} POIs, {road_count} road segments inserted.")

    if handler.pois:
        cats = Counter(p["category"] + "/" + p["subcategory"] for p in handler.pois)
        print("[OSM] Top 15 POI categories:")
        for cat, count in cats.most_common(15):
            print(f"  {cat}: {count}")

    if handler.roads:
        types = Counter(r["road_type"] for r in handler.roads)
        print("[OSM] Road type breakdown:")
        for rt, count in types.most_common():
            print(f"  {rt}: {count}")
