"""
GET /api/pincodes/{pincode}/hotspots

Deterministic scouting hotspot identification using PostGIS hex grid.
Uses ST_HexagonGrid at ~0.003 degree step (~300-330m at Chennai latitude).
No H3 library, no LLM.
"""

import json
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/pincodes", tags=["hotspots"])

HEX_STEP = 0.003
TOP_N = 5

HOTSPOT_WEIGHTS = {
    "commercial_activity": 0.30,
    "competitive_gap": 0.30,
    "savomart_gap": 0.20,
    "accessibility": 0.20,
}

WINSORIZE_LOW = 5
WINSORIZE_HIGH = 95

CELLS_SQL = text("""
WITH pincode AS (
    SELECT geometry FROM pincodes WHERE code = :code
),
raw_cells AS (
    SELECT row_number() OVER () as cell_id,
           (h).geom as geom
    FROM pincode p, ST_HexagonGrid(:step, p.geometry) h
    WHERE ST_Intersects((h).geom, p.geometry)
),
cells AS (
    SELECT c.cell_id, c.geom,
        ST_Area(ST_Intersection(c.geom, p.geometry)::geography)::numeric /
        NULLIF(ST_Area(c.geom::geography)::numeric, 0) as overlap_ratio,
        round(ST_Area(ST_Intersection(c.geom, p.geometry)::geography)::numeric / 1000000, 6) as cell_area_km2
    FROM raw_cells c, pincode p
),
qualified AS (
    SELECT * FROM cells WHERE overlap_ratio > 0.5
),
cell_pois AS (
    SELECT q.cell_id,
        count(*) as poi_count,
        count(*) FILTER (WHERE o.category = 'shop') as shop_count,
        count(*) FILTER (WHERE o.subcategory IN ('restaurant','cafe','fast_food')) as food_count,
        count(*) FILTER (WHERE o.subcategory IN ('supermarket','convenience','grocery','greengrocer','general','department_store')) as grocery_count,
        count(*) FILTER (WHERE o.category = 'building' AND o.subcategory IN ('residential','apartments')) as residential_count
    FROM qualified q
    LEFT JOIN osm_pois o ON ST_Within(o.location, q.geom)
    GROUP BY q.cell_id
),
cell_roads AS (
    SELECT q.cell_id,
        round(coalesce(sum(ST_Length(ST_Intersection(r.geometry, q.geom)::geography))::numeric / 1000, 0), 3) as road_km,
        bool_or(r.road_type IN ('primary','secondary','trunk','motorway')) as has_major_road
    FROM qualified q
    LEFT JOIN osm_roads r ON ST_Intersects(r.geometry, q.geom)
    GROUP BY q.cell_id
),
store_in_cell AS (
    SELECT q.cell_id, count(*) as store_count
    FROM qualified q
    JOIN savomart_stores s ON ST_Within(s.location, q.geom)
    GROUP BY q.cell_id
),
nearest_store AS (
    SELECT q.cell_id,
        round(min(ST_Distance(ST_Centroid(q.geom)::geography, s.location::geography))::numeric) as nearest_savomart_m
    FROM qualified q
    CROSS JOIN savomart_stores s
    GROUP BY q.cell_id
),
grocery_pois AS (
    SELECT location FROM osm_pois
    WHERE subcategory IN ('supermarket','convenience','grocery','greengrocer','general','department_store')
),
nearest_grocery AS (
    SELECT q.cell_id,
        round(min(ST_Distance(ST_Centroid(q.geom)::geography, gp.location::geography))::numeric) as nearest_grocery_m
    FROM qualified q
    CROSS JOIN grocery_pois gp
    GROUP BY q.cell_id
)
SELECT
    q.cell_id,
    q.overlap_ratio,
    q.cell_area_km2,
    ST_Y(ST_Centroid(q.geom)) as lat,
    ST_X(ST_Centroid(q.geom)) as lng,
    ST_AsGeoJSON(q.geom, 6)::json as geometry,
    coalesce(cp.poi_count, 0) as poi_count,
    coalesce(cp.shop_count, 0) as shop_count,
    coalesce(cp.food_count, 0) as food_count,
    coalesce(cp.grocery_count, 0) as grocery_count,
    coalesce(cp.residential_count, 0) as residential_count,
    coalesce(cr.road_km, 0) as road_km,
    coalesce(cr.has_major_road, false) as has_major_road,
    coalesce(sc.store_count, 0) as has_savomart,
    coalesce(ns.nearest_savomart_m, 0) as nearest_savomart_m,
    coalesce(ng.nearest_grocery_m, 0) as nearest_grocery_m
FROM qualified q
LEFT JOIN cell_pois cp ON q.cell_id = cp.cell_id
LEFT JOIN cell_roads cr ON q.cell_id = cr.cell_id
LEFT JOIN store_in_cell sc ON q.cell_id = sc.cell_id
LEFT JOIN nearest_store ns ON q.cell_id = ns.cell_id
LEFT JOIN nearest_grocery ng ON q.cell_id = ng.cell_id
ORDER BY q.cell_id
""")


def _winsorized_pctl(values: np.ndarray, target: float) -> float:
    if len(values) == 0:
        return 50.0
    low = np.percentile(values, WINSORIZE_LOW)
    high = np.percentile(values, WINSORIZE_HIGH)
    if high <= low:
        return 50.0
    clipped = np.clip(values, low, high)
    target_clipped = np.clip(target, low, high)
    rank = np.sum(clipped < target_clipped) + 0.5 * np.sum(clipped == target_clipped)
    return float(rank / len(clipped) * 100)


def _score_cells(cells: list[dict]) -> list[dict]:
    if not cells:
        return []

    def pctl(metric):
        vals = np.array([c[metric] for c in cells], dtype=float)
        return lambda target: _winsorized_pctl(vals, target)

    poi_pctl = pctl("poi_count")
    shop_pctl = pctl("shop_count")
    food_pctl = pctl("food_count")
    road_pctl = pctl("road_km")
    grocery_dist_pctl = pctl("nearest_grocery_m")
    savo_dist_pctl = pctl("nearest_savomart_m")

    for c in cells:
        commercial = (poi_pctl(c["poi_count"]) + shop_pctl(c["shop_count"]) + food_pctl(c["food_count"])) / 3
        competitive_gap = grocery_dist_pctl(c["nearest_grocery_m"])
        savomart_gap = savo_dist_pctl(c["nearest_savomart_m"])
        road_score = road_pctl(c["road_km"])
        if c["has_major_road"]:
            road_score = min(100, road_score + 15)
        accessibility = road_score

        hotspot_score = round(
            commercial * HOTSPOT_WEIGHTS["commercial_activity"]
            + competitive_gap * HOTSPOT_WEIGHTS["competitive_gap"]
            + savomart_gap * HOTSPOT_WEIGHTS["savomart_gap"]
            + accessibility * HOTSPOT_WEIGHTS["accessibility"]
        )
        hotspot_score = min(100, max(0, hotspot_score))

        c["hotspot_score"] = hotspot_score
        c["sub_scores"] = {
            "commercial_activity": round(commercial),
            "competitive_gap": round(competitive_gap),
            "savomart_gap": round(savomart_gap),
            "accessibility": round(accessibility),
        }

    cells.sort(key=lambda c: (-c["hotspot_score"], -c["sub_scores"]["commercial_activity"]))
    return cells


@router.get("/{pincode}/hotspots")
async def get_hotspots(pincode: str, db: AsyncSession = Depends(get_db)):
    check = await db.execute(
        text("SELECT code, name FROM pincodes WHERE code = :code"),
        {"code": pincode},
    )
    pin_row = check.fetchone()
    if not pin_row:
        raise HTTPException(status_code=404, detail=f"Pincode {pincode} not found")

    result = await db.execute(CELLS_SQL, {"code": pincode, "step": HEX_STEP})
    rows = result.fetchall()

    total_cells = len(rows)
    excluded_insufficient = 0
    excluded_savomart = 0
    qualified = []

    for r in rows:
        if r.poi_count < 3:
            excluded_insufficient += 1
            continue
        if r.has_savomart > 0:
            excluded_savomart += 1
            continue
        qualified.append({
            "cell_id": int(r.cell_id),
            "lat": float(r.lat),
            "lng": float(r.lng),
            "geometry": r.geometry,
            "poi_count": int(r.poi_count),
            "shop_count": int(r.shop_count),
            "food_count": int(r.food_count),
            "grocery_count": int(r.grocery_count),
            "residential_count": int(r.residential_count),
            "road_km": float(r.road_km),
            "has_major_road": bool(r.has_major_road),
            "nearest_savomart_m": float(r.nearest_savomart_m),
            "nearest_grocery_m": float(r.nearest_grocery_m),
        })

    scored = _score_cells(qualified)
    top = scored[:TOP_N]

    hotspots = []
    for i, c in enumerate(top):
        hotspots.append({
            "rank": i + 1,
            "cell_id": c["cell_id"],
            "hotspot_score": c["hotspot_score"],
            "centroid": {"lat": c["lat"], "lng": c["lng"]},
            "geometry": c["geometry"],
            "signals": {
                "poi_count": c["poi_count"],
                "shop_count": c["shop_count"],
                "food_count": c["food_count"],
                "grocery_competitor_count": c["grocery_count"],
                "road_km": c["road_km"],
                "has_major_road": c["has_major_road"],
                "residential_count": c["residential_count"],
                "nearest_savomart_m": round(c["nearest_savomart_m"]),
                "nearest_grocery_competitor_m": round(c["nearest_grocery_m"]),
            },
            "sub_scores": c["sub_scores"],
        })

    return {
        "pincode": pincode,
        "name": pin_row.name,
        "cell_resolution_degrees": HEX_STEP,
        "cell_resolution_note": "~300-330m hex diameter at Chennai latitude (13°N)",
        "total_cells": total_cells,
        "qualified_cells": len(qualified),
        "excluded": {
            "insufficient_data": excluded_insufficient,
            "existing_savomart": excluded_savomart,
        },
        "weights": HOTSPOT_WEIGHTS,
        "hotspots": hotspots,
    }
