from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/pincodes", tags=["pincodes"])


@router.get("")
async def list_pincodes(db: AsyncSession = Depends(get_db)):
    """Return all pincodes as GeoJSON FeatureCollection (lightweight: centroid + bbox, no full geometry)."""
    r = await db.execute(text("""
        SELECT code, name,
               ST_AsGeoJSON(ST_Centroid(geometry))::json AS centroid,
               ST_AsGeoJSON(ST_Envelope(geometry))::json AS bbox_geom,
               round(ST_Area(geometry::geography)::numeric / 1000000, 2) AS area_km2
        FROM pincodes
        ORDER BY code
    """))
    rows = r.fetchall()
    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "pincode": row.code,
                "name": row.name,
                "area_km2": float(row.area_km2),
            },
            "geometry": row.centroid,
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/boundaries")
async def pincode_boundaries(db: AsyncSession = Depends(get_db)):
    """Return all pincode boundary polygons as GeoJSON FeatureCollection."""
    r = await db.execute(text("""
        SELECT code, name,
               ST_AsGeoJSON(geometry, 6)::json AS geometry,
               round(ST_Area(geometry::geography)::numeric / 1000000, 2) AS area_km2
        FROM pincodes
        ORDER BY code
    """))
    rows = r.fetchall()
    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "pincode": row.code,
                "name": row.name,
                "area_km2": float(row.area_km2),
            },
            "geometry": row.geometry,
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/{pincode}")
async def get_pincode(pincode: str, db: AsyncSession = Depends(get_db)):
    """Return a single pincode with full geometry and POI/road summary."""
    r = await db.execute(text("""
        SELECT code, name,
               ST_AsGeoJSON(geometry, 6)::json AS geometry,
               round(ST_Area(geometry::geography)::numeric / 1000000, 2) AS area_km2,
               ST_AsGeoJSON(ST_Centroid(geometry))::json AS centroid
        FROM pincodes WHERE code = :code
    """), {"code": pincode})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Pincode {pincode} not found")

    poi_r = await db.execute(text("""
        SELECT category, COUNT(*) as count
        FROM osm_pois
        WHERE ST_Within(location, (SELECT geometry FROM pincodes WHERE code = :code))
        GROUP BY category ORDER BY count DESC
    """), {"code": pincode})
    poi_summary = {r.category: r.count for r in poi_r.fetchall()}

    road_r = await db.execute(text("""
        SELECT road_type, COUNT(*) as count
        FROM osm_roads
        WHERE ST_Intersects(geometry, (SELECT geometry FROM pincodes WHERE code = :code))
        GROUP BY road_type ORDER BY count DESC
    """), {"code": pincode})
    road_summary = {r.road_type: r.count for r in road_r.fetchall()}

    store_r = await db.execute(text("""
        SELECT store_id, name, address,
               ST_AsGeoJSON(location)::json AS location
        FROM savomart_stores
        WHERE ST_Within(location, (SELECT geometry FROM pincodes WHERE code = :code))
    """), {"code": pincode})
    stores = [{"store_id": r.store_id, "name": r.name, "address": r.address, "location": r.location}
              for r in store_r.fetchall()]

    return {
        "pincode": row.code,
        "name": row.name,
        "area_km2": float(row.area_km2),
        "centroid": row.centroid,
        "geometry": row.geometry,
        "poi_summary": poi_summary,
        "road_summary": road_summary,
        "savomart_stores": stores,
        "total_pois": sum(poi_summary.values()),
        "total_roads": sum(road_summary.values()),
    }
