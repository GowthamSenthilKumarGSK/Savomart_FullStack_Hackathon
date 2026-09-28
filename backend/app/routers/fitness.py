"""
GET /api/pincodes/{pincode}/fitness

Computes deterministic area fitness score using only PostGIS/OSM data.
Persists the result in area_reports for revisitability.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.scoring import compute_fitness
from app.llm import generate_explanation

router = APIRouter(prefix="/api/pincodes", tags=["fitness"])

DATA_SOURCES = ["osm_pois", "osm_roads", "savomart_stores", "pincodes"]

ALL_METRICS_SQL = text("""
WITH pincode_base AS (
    SELECT code, name, geometry,
           round(ST_Area(geometry::geography)::numeric / 1000000, 4) AS area_km2
    FROM pincodes
),
poi_counts AS (
    SELECT p.code,
        count(*) FILTER (WHERE o.category = 'shop') AS shop_count,
        count(DISTINCT o.subcategory) FILTER (WHERE o.category = 'shop') AS shop_diversity,
        count(*) FILTER (WHERE o.subcategory IN ('restaurant','cafe','fast_food')) AS food_count,
        count(*) FILTER (WHERE o.subcategory IN ('supermarket','convenience','grocery','greengrocer','general','department_store')) AS grocery_competitor_count,
        count(*) FILTER (WHERE o.category = 'building' AND o.subcategory IN ('commercial','retail','industrial')) AS commercial_building_count,
        count(*) FILTER (WHERE o.category = 'building' AND o.subcategory = 'residential') AS residential_building_count,
        count(*) FILTER (WHERE o.category = 'building' AND o.subcategory = 'apartments') AS apartment_count,
        count(*) FILTER (WHERE o.subcategory IN ('school','college','university')) AS school_college_count,
        count(*) FILTER (WHERE o.subcategory IN ('bank','atm')) AS bank_atm_count,
        count(*) FILTER (WHERE o.subcategory IN ('hospital','clinic','pharmacy')) AS healthcare_count,
        count(*) FILTER (WHERE o.subcategory = 'fuel') AS fuel_count,
        count(DISTINCT o.subcategory) FILTER (WHERE o.category = 'amenity') AS amenity_diversity,
        count(*) AS total_pois
    FROM pincode_base p
    LEFT JOIN osm_pois o ON ST_Within(o.location, p.geometry)
    GROUP BY p.code
),
road_agg AS (
    SELECT p.code,
        round(coalesce(sum(ST_Length(ST_Intersection(r.geometry, p.geometry)::geography))::numeric / 1000, 0), 2) AS road_network_km,
        count(*) FILTER (WHERE r.road_type IN ('primary','secondary','trunk','motorway')) AS major_road_count
    FROM pincode_base p
    LEFT JOIN osm_roads r ON ST_Intersects(r.geometry, p.geometry)
    GROUP BY p.code
),
store_in AS (
    SELECT p.code, count(*) AS savomart_in_pincode
    FROM pincode_base p
    LEFT JOIN savomart_stores s ON ST_Within(s.location, p.geometry)
    GROUP BY p.code
),
nearest_store AS (
    SELECT p.code,
        min(ST_Distance(s.location::geography, ST_Centroid(p.geometry)::geography)::numeric) AS nearest_savomart_m
    FROM pincode_base p
    CROSS JOIN savomart_stores s
    GROUP BY p.code
)
SELECT
    pb.code, pb.name, pb.area_km2,
    coalesce(pc.shop_count, 0) AS shop_count,
    coalesce(pc.shop_diversity, 0) AS shop_diversity,
    coalesce(pc.food_count, 0) AS food_count,
    coalesce(pc.grocery_competitor_count, 0) AS grocery_competitor_count,
    coalesce(pc.commercial_building_count, 0) AS commercial_building_count,
    coalesce(pc.residential_building_count, 0) AS residential_building_count,
    coalesce(pc.apartment_count, 0) AS apartment_count,
    coalesce(pc.school_college_count, 0) AS school_college_count,
    coalesce(pc.bank_atm_count, 0) AS bank_atm_count,
    coalesce(pc.healthcare_count, 0) AS healthcare_count,
    coalesce(pc.fuel_count, 0) AS fuel_count,
    coalesce(pc.amenity_diversity, 0) AS amenity_diversity,
    coalesce(pc.total_pois, 0) AS total_pois,
    coalesce(ra.road_network_km, 0) AS road_network_km,
    coalesce(ra.major_road_count, 0) AS major_road_count,
    coalesce(si.savomart_in_pincode, 0) AS savomart_in_pincode,
    coalesce(ns.nearest_savomart_m, 0) AS nearest_savomart_m
FROM pincode_base pb
LEFT JOIN poi_counts pc USING (code)
LEFT JOIN road_agg ra USING (code)
LEFT JOIN store_in si USING (code)
LEFT JOIN nearest_store ns USING (code)
ORDER BY pb.code
""")


def _build_all_raw(rows) -> dict[str, dict[str, float]]:
    result = {}
    for r in rows:
        area = float(r.area_km2) if r.area_km2 and float(r.area_km2) > 0 else 0.01
        raw = {
            "area_km2": area,
            "shop_count": int(r.shop_count),
            "shop_diversity": int(r.shop_diversity),
            "food_count": int(r.food_count),
            "grocery_competitor_count": int(r.grocery_competitor_count),
            "commercial_building_count": int(r.commercial_building_count),
            "residential_building_count": int(r.residential_building_count),
            "apartment_count": int(r.apartment_count),
            "school_college_count": int(r.school_college_count),
            "bank_atm_count": int(r.bank_atm_count),
            "healthcare_count": int(r.healthcare_count),
            "fuel_count": int(r.fuel_count),
            "amenity_diversity": int(r.amenity_diversity),
            "total_pois": int(r.total_pois),
            "road_network_km": float(r.road_network_km),
            "major_road_count": int(r.major_road_count),
            "savomart_in_pincode": int(r.savomart_in_pincode),
            "nearest_savomart_m": float(r.nearest_savomart_m) if r.nearest_savomart_m else 0,
            "poi_density_per_km2": round(int(r.total_pois) / area, 2),
            "grocery_density_per_km2": round(int(r.grocery_competitor_count) / area, 2),
            "road_density_km_per_km2": round(float(r.road_network_km) / area, 2),
            "apartment_density_per_km2": round(int(r.apartment_count) / area, 2),
        }
        result[r.code] = raw
    return result


@router.get("/{pincode}/fitness")
async def get_fitness(pincode: str, db: AsyncSession = Depends(get_db)):
    check = await db.execute(
        text("SELECT code, name FROM pincodes WHERE code = :code"),
        {"code": pincode},
    )
    pin_row = check.fetchone()
    if not pin_row:
        raise HTTPException(status_code=404, detail=f"Pincode {pincode} not found")

    result = await db.execute(ALL_METRICS_SQL)
    rows = result.fetchall()
    all_raw = _build_all_raw(rows)

    if pincode not in all_raw:
        raise HTTPException(status_code=404, detail=f"Pincode {pincode} metrics unavailable")

    report = compute_fitness(pincode, all_raw)
    now = datetime.now(timezone.utc)

    # Find or create area record for this pincode
    area_check = await db.execute(
        text("SELECT id FROM areas WHERE pincode_id = (SELECT id FROM pincodes WHERE code = :code) LIMIT 1"),
        {"code": pincode},
    )
    area_row = area_check.fetchone()

    if area_row:
        area_id = area_row.id
    else:
        area_id = uuid.uuid4()
        await db.execute(
            text("""
                INSERT INTO areas (id, name, pincode_id, geometry, selection_method, created_by, created_at)
                SELECT :area_id, p.name || ' (' || p.code || ')', p.id, ST_GeometryN(p.geometry, 1), 'pincode',
                       '00000000-0000-0000-0000-000000000001'::uuid, now()
                FROM pincodes p WHERE p.code = :code
            """),
            {"area_id": area_id, "code": pincode},
        )

    report_id = uuid.uuid4()
    await db.execute(
        text("""
            INSERT INTO area_reports (id, area_id, overall_score, sub_scores, raw_data, data_sources, status, created_at)
            VALUES (:id, :area_id, :score, cast(:sub_scores as jsonb), cast(:raw_data as jsonb), cast(:data_sources as jsonb), 'completed', :created_at)
        """),
        {
            "id": report_id,
            "area_id": area_id,
            "score": report["overall_score"],
            "sub_scores": json.dumps(report["sub_scores"]),
            "raw_data": json.dumps(report["raw_data"]),
            "data_sources": json.dumps(DATA_SOURCES),
            "created_at": now,
        },
    )
    await db.commit()

    return {
        "report_id": str(report_id),
        "pincode": pincode,
        "name": pin_row.name,
        "generated_at": now.isoformat(),
        "overall_score": report["overall_score"],
        "grade": report["grade"],
        "sub_scores": report["sub_scores"],
        "raw_data": report["raw_data"],
        "weights": report["weights"],
        "data_sources": DATA_SOURCES,
    }


@router.post("/{pincode}/fitness/{report_id}/explain")
async def explain_fitness(pincode: str, report_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.execute(
        text("""
            SELECT ar.overall_score, ar.sub_scores, ar.raw_data, ar.data_sources, ar.ai_narrative,
                   p.code, p.name
            FROM area_reports ar
            JOIN areas a ON ar.area_id = a.id
            JOIN pincodes p ON a.pincode_id = p.id
            WHERE ar.id = cast(:report_id as uuid) AND p.code = :pincode
        """),
        {"report_id": report_id, "pincode": pincode},
    )
    report_row = row.fetchone()
    if not report_row:
        raise HTTPException(status_code=404, detail="Report not found")

    if report_row.ai_narrative:
        try:
            cached = json.loads(report_row.ai_narrative)
            return {"explanation": cached, "cached": True}
        except (json.JSONDecodeError, TypeError):
            pass

    from app.scoring import WEIGHTS, GRADES
    report_data = {
        "pincode": report_row.code,
        "name": report_row.name,
        "overall_score": report_row.overall_score,
        "grade": next((g for threshold, g in GRADES if report_row.overall_score >= threshold), "F"),
        "sub_scores": report_row.sub_scores,
        "raw_data": report_row.raw_data,
        "data_sources": report_row.data_sources or DATA_SOURCES,
    }

    explanation = await generate_explanation(report_data)
    if explanation is None:
        return {"explanation": None, "cached": False, "reason": "LLM unavailable or not configured"}

    await db.execute(
        text("UPDATE area_reports SET ai_narrative = :narrative WHERE id = cast(:report_id as uuid)"),
        {"narrative": json.dumps(explanation), "report_id": report_id},
    )
    await db.commit()

    return {"explanation": explanation, "cached": False}
