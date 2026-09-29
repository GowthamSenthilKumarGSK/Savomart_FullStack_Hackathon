import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.property_scoring import compute_property_evaluation, grade_from_score, GROCERY_SUBCATEGORIES, FOOD_SUBCATEGORIES, MAJOR_ROAD_TYPES

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


@router.get("/{property_id}/decision-pack")
async def decision_pack(property_id: str, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import HTMLResponse

    try:
        uuid.UUID(property_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid property ID")

    prop = await db.execute(
        text("""
            SELECT p.id, p.address, p.pincode, p.stage, p.rent_monthly, p.carpet_area_sqft,
                   p.frontage_ft, p.floor, p.building_type,
                   ST_Y(p.location::geometry) AS lat, ST_X(p.location::geometry) AS lng,
                   p.created_at, p.updated_at,
                   st.id AS task_id, st.hotspot_rank, st.hotspot_score, st.notes AS task_notes,
                   u_exec.name AS scout_name, u_mgr.name AS manager_name
            FROM properties p
            LEFT JOIN scouting_tasks st ON st.property_id = p.id
            LEFT JOIN users u_exec ON st.assigned_to = u_exec.id
            LEFT JOIN users u_mgr ON st.assigned_by = u_mgr.id
            WHERE p.id = cast(:pid as uuid)
        """),
        {"pid": property_id},
    )
    p = prop.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")

    eval_row = await db.execute(
        text("""
            SELECT overall_score, sub_scores, raw_data, created_at
            FROM property_evaluations WHERE property_id = cast(:pid as uuid)
            ORDER BY created_at DESC LIMIT 1
        """),
        {"pid": property_id},
    )
    ev = eval_row.fetchone()

    study_row = await db.execute(
        text("""
            SELECT cs.id, cs.status, cs.radius_m, cs.created_at,
                   u.name AS requested_by
            FROM catchment_studies cs
            JOIN users u ON cs.created_by = u.id
            WHERE cs.property_id = cast(:pid as uuid)
            ORDER BY cs.created_at DESC LIMIT 1
        """),
        {"pid": property_id},
    )
    study = study_row.fetchone()

    insight = None
    if study:
        ins_row = await db.execute(
            text("""
                SELECT total_roads_surveyed, total_roads_in_area, completion_pct,
                       aggregated_data, created_at
                FROM catchment_insights WHERE study_id = cast(:sid as uuid)
                ORDER BY created_at DESC LIMIT 1
            """),
            {"sid": str(study.id)},
        )
        insight = ins_row.fetchone()

    def _score_bar(score, label, weight=None):
        color = '#059669' if score >= 70 else '#D97706' if score >= 40 else '#DC2626'
        w = f' <span style="color:#94a3b8">({int(weight*100)}%)</span>' if weight else ''
        return f'''<div style="margin-bottom:6px">
            <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px">
                <span>{label}{w}</span><span style="font-weight:600">{score}/100</span>
            </div>
            <div style="height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden">
                <div style="height:100%;width:{score}%;background:{color};border-radius:3px"></div>
            </div>
        </div>'''

    def _kv(label, value, fallback='—'):
        v = value if value is not None and value != '' else fallback
        return f'<div style="margin-bottom:4px"><span style="color:#94a3b8;font-size:10px;display:block">{label}</span><span style="font-size:13px;font-weight:500">{v}</span></div>'

    eval_section = ''
    if ev:
        score = ev.overall_score or 0
        grade = grade_from_score(score)
        grade_color = {'A': '#059669', 'B': '#2563EB', 'C': '#D97706', 'D': '#EA580C', 'F': '#DC2626'}.get(grade, '#6b7280')
        sub = ev.sub_scores if isinstance(ev.sub_scores, dict) else json.loads(ev.sub_scores) if ev.sub_scores else {}
        raw = ev.raw_data if isinstance(ev.raw_data, dict) else json.loads(ev.raw_data) if ev.raw_data else {}

        bars = ''
        for dim, data in sub.items():
            bars += _score_bar(data.get('score', 0), dim.replace('_', ' ').title(), data.get('weight'))

        signals = ''
        if raw:
            skip_keys = {'notes', 'missing_data', 'field_derived', 'scoring_notes', 'hotspot_signals', 'positive_signals', 'radius_m', 'recommendation', 'hotspot_context'}
            for k, v in raw.items():
                if k in skip_keys:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    display_v = v
                    if isinstance(v, float):
                        display_v = f'{v:.1f}'
                    signals += f'<div style="background:#f9fafb;padding:4px 8px;border-radius:4px;font-size:11px"><span style="color:#6b7280">{k.replace("_"," ")}:</span> <strong>{display_v}</strong></div>'

        eval_section = f'''
        <div style="page-break-inside:avoid">
            <h2 style="font-size:16px;font-weight:700;border-bottom:2px solid #782B90;padding-bottom:4px;margin:24px 0 12px">Property Evaluation</h2>
            <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px">
                <div style="width:64px;height:64px;border-radius:50%;background:{grade_color};color:white;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:800">{grade}</div>
                <div>
                    <div style="font-size:24px;font-weight:700">{score}/100</div>
                    <div style="font-size:11px;color:#94a3b8">Evaluated {ev.created_at.strftime("%b %d, %Y %H:%M") if ev.created_at else "—"}</div>
                </div>
            </div>
            {bars}
            <h3 style="font-size:12px;font-weight:600;margin:16px 0 8px;color:#6b7280">Spatial Signals</h3>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px">{signals}</div>
        </div>'''
    else:
        eval_section = '<div style="padding:12px;background:#fef3c7;border-radius:8px;font-size:12px;color:#92400e;margin:16px 0">No property evaluation available.</div>'

    study_section = ''
    if study:
        status_colors = {'requested': '#2563EB', 'planning': '#D97706', 'in_progress': '#782B90', 'completed': '#059669'}
        sc = status_colors.get(study.status, '#6b7280')
        study_section = f'''
        <div style="page-break-inside:avoid">
            <h2 style="font-size:16px;font-weight:700;border-bottom:2px solid #782B90;padding-bottom:4px;margin:24px 0 12px">Catchment Study</h2>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px">
                {_kv("Status", f'<span style="color:{sc};font-weight:600">{study.status.replace("_"," ").title()}</span>')}
                {_kv("Radius", f"{study.radius_m}m")}
                {_kv("Requested by", study.requested_by)}
            </div>'''

        if insight:
            agg = insight.aggregated_data if isinstance(insight.aggregated_data, dict) else {}
            def _dist_list(d):
                if not d: return '<span style="color:#94a3b8;font-style:italic">No data</span>'
                total = sum(d.values())
                return ', '.join(f'{k}: {v} ({round(v/total*100)}%)' for k, v in d.items())

            study_section += f'''
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px;margin-bottom:12px">
                <div style="font-size:12px;font-weight:600;margin-bottom:8px">Catchment Insight</div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px">
                    <div style="text-align:center"><div style="font-size:20px;font-weight:700;color:#782B90">{insight.total_roads_surveyed}</div><div style="font-size:10px;color:#6b7280">Roads Surveyed</div></div>
                    <div style="text-align:center"><div style="font-size:20px;font-weight:700;color:#782B90">{insight.total_roads_in_area}</div><div style="font-size:10px;color:#6b7280">Total Roads</div></div>
                    <div style="text-align:center"><div style="font-size:20px;font-weight:700;color:#782B90">{insight.completion_pct}%</div><div style="font-size:10px;color:#6b7280">Coverage</div></div>
                </div>
                <div style="font-size:11px;line-height:1.8">
                    <div><strong>Total Shops:</strong> {agg.get("total_shops", 0)}</div>
                    <div><strong>Shop Types:</strong> {_dist_list(agg.get("shop_type_distribution"))}</div>
                    <div><strong>Household Mix:</strong> {_dist_list(agg.get("household_types"))}</div>
                    <div><strong>Road Condition:</strong> {_dist_list(agg.get("road_conditions"))}</div>
                    <div><strong>Foot Traffic:</strong> {_dist_list(agg.get("foot_traffic"))}</div>
                    <div><strong>Household Ranges:</strong> {_dist_list(agg.get("household_count_ranges"))}</div>
                </div>
                <div style="font-size:9px;color:#94a3b8;margin-top:8px">Generated {insight.created_at.strftime("%b %d, %Y %H:%M") if insight.created_at else "—"}</div>
            </div>'''
        elif study.status == 'completed':
            study_section += '<div style="padding:8px;background:#fef3c7;border-radius:6px;font-size:11px;color:#92400e">Study completed but no insight data available.</div>'
        else:
            study_section += f'<div style="padding:8px;background:#eff6ff;border-radius:6px;font-size:11px;color:#1e40af">Study is {study.status.replace("_"," ")} — insight will be generated upon completion.</div>'
        study_section += '</div>'
    else:
        study_section = '<div style="padding:12px;background:#f3f4f6;border-radius:8px;font-size:12px;color:#6b7280;margin:16px 0">No catchment study requested for this property.</div>'

    scouting_section = ''
    if p.task_id:
        scouting_section = f'''
        <div style="page-break-inside:avoid">
            <h2 style="font-size:16px;font-weight:700;border-bottom:2px solid #782B90;padding-bottom:4px;margin:24px 0 12px">Scouting Context</h2>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                {_kv("Hotspot Rank", f"#{p.hotspot_rank}" if p.hotspot_rank else "—")}
                {_kv("Hotspot Score", f"{p.hotspot_score}/100" if p.hotspot_score else "—")}
                {_kv("Scouted by", p.scout_name or "—")}
                {_kv("Assigned by", p.manager_name or "—")}
            </div>
            {f'<div style="margin-top:8px;font-size:11px;color:#6b7280"><strong>Notes:</strong> {p.task_notes}</div>' if p.task_notes else ''}
        </div>'''

    now_str = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decision Pack — {p.address or p.pincode}</title>
<style>
  @page {{ margin: 16mm; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color:#1f2937; max-width:800px; margin:0 auto; padding:24px; line-height:1.5; }}
  @media print {{
    body {{ padding:0; }}
    .no-print {{ display:none !important; }}
  }}
</style>
</head>
<body>
  <div class="no-print" style="margin-bottom:16px;display:flex;gap:8px">
    <button onclick="window.print()" style="padding:8px 20px;background:#782B90;color:white;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer">Print / Save PDF</button>
    <button onclick="window.close()" style="padding:8px 16px;background:#e5e7eb;color:#374151;border:none;border-radius:6px;font-size:13px;cursor:pointer">Close</button>
  </div>

  <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;border-bottom:3px solid #782B90;padding-bottom:12px">
    <div style="width:40px;height:40px;background:#FFF200;border-radius:8px;display:flex;align-items:center;justify-content:center">
      <span style="color:#782B90;font-weight:900;font-size:18px">S</span>
    </div>
    <div>
      <div style="font-size:20px;font-weight:800;color:#782B90">Savo SiteScout</div>
      <div style="font-size:11px;color:#94a3b8">Decision Pack</div>
    </div>
    <div style="margin-left:auto;text-align:right">
      <div style="font-size:10px;color:#94a3b8">Generated</div>
      <div style="font-size:11px;font-weight:500">{now_str}</div>
    </div>
  </div>

  <h2 style="font-size:16px;font-weight:700;border-bottom:2px solid #782B90;padding-bottom:4px;margin-bottom:12px">Property Details</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:8px">
    {_kv("Address", p.address)}
    {_kv("Pincode", p.pincode)}
    {_kv("Stage", p.stage.replace("_"," ").title() if p.stage else "—")}
    {_kv("Building Type", (p.building_type or "—").replace("_"," ").title())}
    {_kv("Rent (Monthly)", f"₹{p.rent_monthly:,.0f}" if p.rent_monthly else "—")}
    {_kv("Carpet Area", f"{p.carpet_area_sqft:,.0f} sqft" if p.carpet_area_sqft else "—")}
    {_kv("Frontage", f"{p.frontage_ft} ft" if p.frontage_ft else "—")}
    {_kv("Floor", str(p.floor) if p.floor is not None else "—")}
    {_kv("Location", f"{p.lat:.6f}, {p.lng:.6f}")}
    {_kv("Scouted", p.created_at.strftime("%b %d, %Y") if p.created_at else "—")}
  </div>

  {scouting_section}
  {eval_section}
  {study_section}

  <div style="margin-top:32px;padding-top:12px;border-top:1px solid #e5e7eb;font-size:9px;color:#94a3b8;text-align:center">
    Savo SiteScout Decision Pack · Data sourced from OpenStreetMap, Savomart Stores API, and field surveys · {now_str}
  </div>
</body>
</html>'''

    return HTMLResponse(content=html)
