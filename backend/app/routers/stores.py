from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("")
async def list_stores(db: AsyncSession = Depends(get_db)):
    """Return all Savomart stores as GeoJSON FeatureCollection."""
    r = await db.execute(text("""
        SELECT store_id, name, address,
               ST_AsGeoJSON(location)::json AS geometry
        FROM savomart_stores
        WHERE operational = true
        ORDER BY name
    """))
    features = []
    for row in r.fetchall():
        features.append({
            "type": "Feature",
            "properties": {"store_id": row.store_id, "name": row.name, "address": row.address},
            "geometry": row.geometry,
        })
    return {"type": "FeatureCollection", "features": features}
