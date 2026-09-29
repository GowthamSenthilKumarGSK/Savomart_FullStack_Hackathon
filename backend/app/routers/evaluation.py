import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.property_scoring import compute_property_evaluation, GROCERY_SUBCATEGORIES, FOOD_SUBCATEGORIES, MAJOR_ROAD_TYPES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/properties", tags=["evaluation"])


async def _collect_spatial_metrics(db: AsyncSession, lat: float, lng: float) -> dict:
    """Run PostGIS queries around property location. All distances in metres via ::geography casts."""
    point_expr = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)"
    params = {"lat": lat, "lng": lng}

    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) FILTER (WHERE category = 'building' AND subcategory = 'residential') AS residential_buildings_500m,
                COUNT(*) FILTER (WHERE category = 'building' AND subcategory = 'apartments') AS apartments_500m,
                COUNT(*) FILTER (WHERE category = 'amenity' AND subcategory IN ('school', 'college', 'university')) AS schools_colleges_500m
            FROM osm_pois
            WHERE ST_DWithin(location::geography, {point_expr}::geography, 500)
        """),
        params,
    )
    row = result.fetchone()
    metrics = {
        "residential_buildings_500m": row.residential_buildings_500m,
        "apartments_500m": row.apartments_500m,
        "schools_colleges_500m": row.schools_colleges_500m,
    }

    grocery_subs = ", ".join(f"'{s}'" for s in GROCERY_SUBCATEGORIES)
    food_subs = ", ".join(f"'{s}'" for s in FOOD_SUBCATEGORIES)
    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) FILTER (WHERE category = 'shop' AND ST_DWithin(location::geography, {point_expr}::geography, 300)) AS shops_300m,
                COUNT(*) FILTER (WHERE category = 'shop' AND subcategory IN ({grocery_subs}) AND ST_DWithin(location::geography, {point_expr}::geography, 500)) AS grocery_competition_500m,
                COUNT(*) FILTER (WHERE (category = 'shop' OR category = 'amenity') AND subcategory IN ({food_subs}) AND ST_DWithin(location::geography, {point_expr}::geography, 300)) AS food_outlets_300m,
                COUNT(DISTINCT subcategory) FILTER (WHERE category = 'shop' AND ST_DWithin(location::geography, {point_expr}::geography, 300)) AS shop_diversity_300m
            FROM osm_pois
            WHERE ST_DWithin(location::geography, {point_expr}::geography, 500)
        """),
        params,
    )
    row = result.fetchone()
    metrics["shops_300m"] = row.shops_300m
    metrics["grocery_competition_500m"] = row.grocery_competition_500m
    metrics["food_outlets_300m"] = row.food_outlets_300m
    metrics["shop_diversity_300m"] = row.shop_diversity_300m

    road_types = ", ".join(f"'{t}'" for t in MAJOR_ROAD_TYPES)
    result = await db.execute(
        text(f"""
            SELECT
                MIN(ST_Distance(geometry::geography, {point_expr}::geography))
                    FILTER (WHERE road_type IN ({road_types})) AS nearest_major_road_m,
                COUNT(DISTINCT id) FILTER (WHERE road_type IN ({road_types})
                    AND ST_DWithin(geometry::geography, {point_expr}::geography, 500)) AS major_roads_500m
            FROM osm_roads
            WHERE ST_DWithin(geometry::geography, {point_expr}::geography, 500)
        """),
        params,
    )
    row = result.fetchone()
    metrics["nearest_major_road_m"] = float(row.nearest_major_road_m) if row.nearest_major_road_m is not None else None
    metrics["major_roads_500m"] = row.major_roads_500m

    result = await db.execute(
        text(f"""
            SELECT COALESCE(SUM(
                ST_Length(
                    ST_Intersection(
                        geometry,
                        ST_Buffer({point_expr}::geography, 300)::geometry
                    )::geography
                )
            ), 0) AS road_length_300m
            FROM osm_roads
            WHERE ST_DWithin(geometry::geography, {point_expr}::geography, 300)
        """),
        params,
    )
    row = result.fetchone()
    metrics["road_length_300m"] = float(row.road_length_300m)

    result = await db.execute(
        text(f"""
            SELECT
                MIN(ST_Distance(location::geography, {point_expr}::geography)) AS nearest_savomart_m,
                COUNT(*) FILTER (WHERE ST_DWithin(location::geography, {point_expr}::geography, 2000)) AS savomart_count_2km
            FROM savomart_stores
            WHERE operational = true
        """),
        params,
    )
    row = result.fetchone()
    metrics["nearest_savomart_m"] = float(row.nearest_savomart_m) if row.nearest_savomart_m is not None else None
    metrics["savomart_count_2km"] = row.savomart_count_2km

    return metrics


async def run_evaluation(db: AsyncSession, property_id: str, hotspot_context: dict | None = None) -> dict:
    """Compute and persist a property evaluation. Returns the evaluation dict."""
    prop_result = await db.execute(
        text("""
            SELECT id, rent_monthly, carpet_area_sqft, frontage_ft, floor,
                   ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng
            FROM properties WHERE id = cast(:pid as uuid)
        """),
        {"pid": property_id},
    )
    prop = prop_result.fetchone()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    raw_metrics = await _collect_spatial_metrics(db, prop.lat, prop.lng)

    property_data = {
        "floor": prop.floor,
        "carpet_area_sqft": prop.carpet_area_sqft,
        "frontage_ft": prop.frontage_ft,
        "rent_monthly": prop.rent_monthly,
    }

    evaluation = compute_property_evaluation(raw_metrics, property_data)

    if hotspot_context:
        evaluation["raw_data"]["hotspot_context"] = hotspot_context

    eval_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    await db.execute(
        text("""
            INSERT INTO property_evaluations (id, property_id, overall_score, sub_scores, raw_data, created_at)
            VALUES (:id, cast(:pid as uuid), :score, cast(:sub as jsonb), cast(:raw as jsonb), :now)
        """),
        {
            "id": eval_id,
            "pid": property_id,
            "score": evaluation["overall_score"],
            "sub": json.dumps(evaluation["sub_scores"]),
            "raw": json.dumps(evaluation["raw_data"]),
            "now": now,
        },
    )
    await db.commit()

    return {
        "evaluation_id": str(eval_id),
        "property_id": property_id,
        "overall_score": evaluation["overall_score"],
        "grade": evaluation["grade"],
        "sub_scores": evaluation["sub_scores"],
        "raw_data": evaluation["raw_data"],
        "created_at": now.isoformat(),
    }


@router.post("/{property_id}/evaluate")
async def evaluate_property(property_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(property_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid property ID")

    task_result = await db.execute(
        text("SELECT hotspot_score, hotspot_signals FROM scouting_tasks WHERE property_id = cast(:pid as uuid) LIMIT 1"),
        {"pid": property_id},
    )
    task_row = task_result.fetchone()
    hotspot_context = None
    if task_row:
        hotspot_context = {
            "hotspot_score": task_row.hotspot_score,
            "hotspot_signals": task_row.hotspot_signals,
        }

    return await run_evaluation(db, property_id, hotspot_context)


@router.get("/{property_id}/evaluation")
async def get_evaluation(property_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(property_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid property ID")

    result = await db.execute(
        text("""
            SELECT id, property_id, overall_score, sub_scores, raw_data, ai_narrative, created_at
            FROM property_evaluations
            WHERE property_id = cast(:pid as uuid)
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"pid": property_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No evaluation found for this property")

    raw_data = row.raw_data if isinstance(row.raw_data, dict) else json.loads(row.raw_data) if row.raw_data else {}
    sub_scores = row.sub_scores if isinstance(row.sub_scores, dict) else json.loads(row.sub_scores) if row.sub_scores else {}

    from app.property_scoring import grade_from_score
    score = row.overall_score or 0

    return {
        "evaluation_id": str(row.id),
        "property_id": str(row.property_id),
        "overall_score": score,
        "grade": grade_from_score(score),
        "sub_scores": sub_scores,
        "raw_data": raw_data,
        "ai_narrative": row.ai_narrative,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
