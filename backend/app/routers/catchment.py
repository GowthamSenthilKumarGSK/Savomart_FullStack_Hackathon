import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/catchment-studies", tags=["catchment"])


class RequestStudy(BaseModel):
    property_id: str
    requested_by: str
    radius_m: float = 500.0
    notes: str | None = None


class CreateAssignment(BaseModel):
    assigned_to: str
    assigned_by: str
    zone_geojson: dict


class UpdateAssignmentStatus(BaseModel):
    user_id: str
    new_status: str


class SubmitLaneSurvey(BaseModel):
    road_id: str
    user_id: str
    household_type: str | None = None
    household_count_range: str | None = None
    shop_count: int | None = None
    shop_types: list[str] | None = None
    road_condition: str | None = None
    foot_traffic: str | None = None
    notes: str | None = None


@router.post("")
async def request_catchment_study(body: RequestStudy, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(body.property_id)
        uuid.UUID(body.requested_by)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    user = await db.execute(
        text("SELECT id, role FROM users WHERE id = cast(:uid as uuid)"),
        {"uid": body.requested_by},
    )
    u = user.fetchone()
    if not u or u.role != "bd_manager":
        raise HTTPException(status_code=403, detail="Only a BD Manager can request a catchment study")

    prop = await db.execute(
        text("""
            SELECT id, stage, area_report_id,
                   ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng
            FROM properties WHERE id = cast(:pid as uuid)
        """),
        {"pid": body.property_id},
    )
    p = prop.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    if p.stage != "scouted":
        raise HTTPException(status_code=422, detail=f"Property must be in 'scouted' stage (current: {p.stage})")

    existing = await db.execute(
        text("SELECT id FROM catchment_studies WHERE property_id = cast(:pid as uuid) AND status != 'completed'"),
        {"pid": body.property_id},
    )
    if existing.fetchone():
        raise HTTPException(status_code=409, detail="An active catchment study already exists for this property")

    study_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    await db.execute(
        text("""
            INSERT INTO catchment_studies (id, property_id, area_report_id, boundary, radius_m, status, created_by, created_at)
            VALUES (
                :id, cast(:pid as uuid), :arid,
                ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)::geometry,
                :radius, 'requested', cast(:uid as uuid), :now
            )
        """),
        {
            "id": study_id,
            "pid": body.property_id,
            "arid": p.area_report_id,
            "lng": p.lng, "lat": p.lat,
            "radius": body.radius_m,
            "uid": body.requested_by,
            "now": now,
        },
    )

    await db.execute(
        text("UPDATE properties SET stage = 'catchment_requested', updated_at = :now WHERE id = cast(:pid as uuid)"),
        {"pid": body.property_id, "now": now},
    )

    history_id = uuid.uuid4()
    await db.execute(
        text("""
            INSERT INTO property_history (id, property_id, from_stage, to_stage, changed_by, notes, created_at)
            VALUES (:id, cast(:pid as uuid), 'scouted', 'catchment_requested', cast(:uid as uuid), :notes, :now)
        """),
        {"id": history_id, "pid": body.property_id, "uid": body.requested_by, "notes": body.notes, "now": now},
    )

    await db.commit()

    return {
        "study_id": str(study_id),
        "property_id": body.property_id,
        "status": "requested",
        "radius_m": body.radius_m,
        "created_at": now.isoformat(),
    }


@router.get("")
async def list_catchment_studies(
    status: str | None = None,
    property_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    clauses = []
    params: dict = {}
    if status:
        clauses.append("cs.status = :status")
        params["status"] = status
    if property_id:
        clauses.append("cs.property_id = cast(:pid as uuid)")
        params["pid"] = property_id

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    result = await db.execute(
        text(f"""
            SELECT cs.id, cs.property_id, cs.radius_m, cs.status, cs.created_at,
                   p.address AS property_address, p.pincode AS property_pincode, p.stage AS property_stage,
                   ST_Y(p.location::geometry) AS prop_lat, ST_X(p.location::geometry) AS prop_lng,
                   u.name AS requested_by_name,
                   (SELECT count(*) FROM survey_assignments sa WHERE sa.study_id = cs.id) AS assignment_count,
                   (SELECT count(*) FROM survey_assignments sa WHERE sa.study_id = cs.id AND sa.status = 'completed') AS completed_assignments
            FROM catchment_studies cs
            JOIN properties p ON cs.property_id = p.id
            JOIN users u ON cs.created_by = u.id
            {where}
            ORDER BY cs.created_at DESC
        """),
        params,
    )
    rows = result.fetchall()

    return {
        "studies": [
            {
                "study_id": str(r.id),
                "property_id": str(r.property_id),
                "property_address": r.property_address,
                "property_pincode": r.property_pincode,
                "property_stage": r.property_stage,
                "property_location": {"lat": r.prop_lat, "lng": r.prop_lng},
                "radius_m": r.radius_m,
                "status": r.status,
                "requested_by": r.requested_by_name,
                "assignment_count": r.assignment_count,
                "completed_assignments": r.completed_assignments,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/{study_id}")
async def get_catchment_study(study_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(study_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid study ID")

    result = await db.execute(
        text("""
            SELECT cs.id, cs.property_id, cs.area_report_id, cs.radius_m, cs.status, cs.created_at,
                   cs.created_by,
                   ST_AsGeoJSON(cs.boundary)::json AS boundary_geojson,
                   p.address AS property_address, p.pincode AS property_pincode,
                   p.stage AS property_stage, p.rent_monthly, p.carpet_area_sqft,
                   p.frontage_ft, p.floor, p.building_type,
                   ST_Y(p.location::geometry) AS prop_lat, ST_X(p.location::geometry) AS prop_lng,
                   u.name AS requested_by_name
            FROM catchment_studies cs
            JOIN properties p ON cs.property_id = p.id
            JOIN users u ON cs.created_by = u.id
            WHERE cs.id = cast(:sid as uuid)
        """),
        {"sid": study_id},
    )
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Catchment study not found")

    assignments_result = await db.execute(
        text("""
            SELECT sa.id, sa.assigned_to, sa.status, sa.created_at,
                   u.name AS executive_name,
                   ST_AsGeoJSON(sa.zone_boundary)::json AS zone_geojson,
                   (SELECT count(*) FROM lane_surveys ls WHERE ls.assignment_id = sa.id) AS survey_count
            FROM survey_assignments sa
            JOIN users u ON sa.assigned_to = u.id
            WHERE sa.study_id = cast(:sid as uuid)
            ORDER BY sa.created_at
        """),
        {"sid": study_id},
    )

    road_count = await db.execute(
        text("""
            SELECT count(*) FROM osm_roads
            WHERE ST_Intersects(geometry, (SELECT boundary FROM catchment_studies WHERE id = cast(:sid as uuid)))
        """),
        {"sid": study_id},
    )
    total_roads = road_count.scalar() or 0

    return {
        "study_id": str(r.id),
        "property_id": str(r.property_id),
        "area_report_id": str(r.area_report_id) if r.area_report_id else None,
        "radius_m": r.radius_m,
        "status": r.status,
        "boundary": r.boundary_geojson,
        "requested_by": r.requested_by_name,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "property": {
            "address": r.property_address,
            "pincode": r.property_pincode,
            "stage": r.property_stage,
            "location": {"lat": r.prop_lat, "lng": r.prop_lng},
            "rent_monthly": r.rent_monthly,
            "carpet_area_sqft": r.carpet_area_sqft,
            "frontage_ft": r.frontage_ft,
            "floor": r.floor,
            "building_type": r.building_type,
        },
        "total_roads_in_area": total_roads,
        "assignments": [
            {
                "assignment_id": str(a.id),
                "assigned_to": str(a.assigned_to),
                "executive_name": a.executive_name,
                "status": a.status,
                "zone_boundary": a.zone_geojson,
                "survey_count": a.survey_count,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assignments_result.fetchall()
        ],
    }


@router.post("/{study_id}/assignments")
async def create_assignment(study_id: str, body: CreateAssignment, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(study_id)
        uuid.UUID(body.assigned_to)
        uuid.UUID(body.assigned_by)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    user = await db.execute(
        text("SELECT id, role FROM users WHERE id = cast(:uid as uuid)"),
        {"uid": body.assigned_by},
    )
    u = user.fetchone()
    if not u or u.role != "survey_manager":
        raise HTTPException(status_code=403, detail="Only a Survey Manager can assign zones")

    exec_check = await db.execute(
        text("SELECT id, role FROM users WHERE id = cast(:uid as uuid)"),
        {"uid": body.assigned_to},
    )
    ex = exec_check.fetchone()
    if not ex or ex.role != "survey_executive":
        raise HTTPException(status_code=422, detail="Assignee must be a Survey Executive")

    study = await db.execute(
        text("SELECT id, status, ST_AsGeoJSON(boundary)::json AS boundary_geojson FROM catchment_studies WHERE id = cast(:sid as uuid)"),
        {"sid": study_id},
    )
    s = study.fetchone()
    if not s:
        raise HTTPException(status_code=404, detail="Catchment study not found")
    if s.status not in ("requested", "planning", "in_progress"):
        raise HTTPException(status_code=422, detail=f"Cannot assign zones to a study with status '{s.status}'")

    zone_geojson = body.zone_geojson
    if zone_geojson.get("type") != "Polygon" or not zone_geojson.get("coordinates"):
        raise HTTPException(status_code=422, detail="zone_geojson must be a GeoJSON Polygon")

    import json
    zone_str = json.dumps(zone_geojson)

    overlap = await db.execute(
        text("""
            SELECT ST_Intersects(
                ST_SetSRID(ST_GeomFromGeoJSON(:zone), 4326),
                (SELECT boundary FROM catchment_studies WHERE id = cast(:sid as uuid))
            ) AS overlaps
        """),
        {"zone": zone_str, "sid": study_id},
    )
    if not overlap.scalar():
        raise HTTPException(status_code=422, detail="Zone must overlap with the study boundary")

    assignment_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    await db.execute(
        text("""
            INSERT INTO survey_assignments (id, study_id, assigned_to, zone_boundary, status, created_at)
            VALUES (:id, cast(:sid as uuid), cast(:uid as uuid),
                    ST_SetSRID(ST_GeomFromGeoJSON(:zone), 4326), 'pending', :now)
        """),
        {"id": assignment_id, "sid": study_id, "uid": body.assigned_to, "zone": zone_str, "now": now},
    )

    if s.status == "requested":
        await db.execute(
            text("UPDATE catchment_studies SET status = 'planning' WHERE id = cast(:sid as uuid)"),
            {"sid": study_id},
        )

    await db.commit()

    return {
        "assignment_id": str(assignment_id),
        "study_id": study_id,
        "assigned_to": body.assigned_to,
        "status": "pending",
        "created_at": now.isoformat(),
    }


@router.patch("/assignments/{assignment_id}/status")
async def update_assignment_status(assignment_id: str, body: UpdateAssignmentStatus, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(assignment_id)
        uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    VALID_TRANSITIONS = {
        "pending": ["in_progress"],
        "in_progress": ["completed"],
    }

    assignment = await db.execute(
        text("""
            SELECT sa.id, sa.assigned_to, sa.status, sa.study_id
            FROM survey_assignments sa
            WHERE sa.id = cast(:aid as uuid)
        """),
        {"aid": assignment_id},
    )
    a = assignment.fetchone()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")

    user = await db.execute(
        text("SELECT id, role FROM users WHERE id = cast(:uid as uuid)"),
        {"uid": body.user_id},
    )
    u = user.fetchone()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    if u.role == "survey_executive" and str(a.assigned_to) != body.user_id:
        raise HTTPException(status_code=403, detail="Survey Executive can only update their own assignments")
    if u.role not in ("survey_manager", "survey_executive"):
        raise HTTPException(status_code=403, detail="Only Survey Manager or assigned Survey Executive can update status")

    allowed = VALID_TRANSITIONS.get(a.status, [])
    if body.new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"Cannot transition from '{a.status}' to '{body.new_status}'")

    if body.new_status == "completed":
        road_counts = await db.execute(
            text("""
                SELECT
                    (SELECT count(*) FROM osm_roads r
                     WHERE ST_Intersects(r.geometry, sa.zone_boundary)) AS total_roads,
                    (SELECT count(*) FROM lane_surveys ls
                     WHERE ls.assignment_id = sa.id) AS surveyed_roads
                FROM survey_assignments sa
                WHERE sa.id = cast(:aid as uuid)
            """),
            {"aid": assignment_id},
        )
        rc = road_counts.fetchone()
        if rc.surveyed_roads < rc.total_roads:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot complete assignment: {rc.surveyed_roads}/{rc.total_roads} roads surveyed. All roads must be surveyed before marking complete.",
            )

    await db.execute(
        text("UPDATE survey_assignments SET status = :status WHERE id = cast(:aid as uuid)"),
        {"status": body.new_status, "aid": assignment_id},
    )

    if body.new_status == "in_progress":
        await db.execute(
            text("UPDATE catchment_studies SET status = 'in_progress' WHERE id = cast(:sid as uuid) AND status != 'in_progress'"),
            {"sid": str(a.study_id)},
        )

    if body.new_status == "completed":
        incomplete = await db.execute(
            text("SELECT count(*) FROM survey_assignments WHERE study_id = cast(:sid as uuid) AND status != 'completed'"),
            {"sid": str(a.study_id)},
        )
        if incomplete.scalar() == 0:
            await db.execute(
                text("UPDATE catchment_studies SET status = 'completed' WHERE id = cast(:sid as uuid)"),
                {"sid": str(a.study_id)},
            )
            await _generate_insight(str(a.study_id), db)

    await db.commit()

    return {
        "assignment_id": str(a.id),
        "status": body.new_status,
        "study_id": str(a.study_id),
    }


@router.get("/assignments/{assignment_id}/roads")
async def get_assignment_roads(assignment_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(assignment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    assignment = await db.execute(
        text("SELECT id, study_id FROM survey_assignments WHERE id = cast(:aid as uuid)"),
        {"aid": assignment_id},
    )
    a = assignment.fetchone()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")

    roads = await db.execute(
        text("""
            SELECT r.id, r.name, r.road_type,
                   ST_AsGeoJSON(r.geometry)::json AS geometry,
                   ls.id AS survey_id
            FROM osm_roads r
            LEFT JOIN lane_surveys ls ON ls.road_id = r.id AND ls.assignment_id = cast(:aid as uuid)
            WHERE ST_Intersects(r.geometry,
                (SELECT zone_boundary FROM survey_assignments WHERE id = cast(:aid as uuid)))
            ORDER BY r.name NULLS LAST
        """),
        {"aid": assignment_id},
    )
    rows = roads.fetchall()

    return {
        "assignment_id": assignment_id,
        "total_roads": len(rows),
        "surveyed_count": sum(1 for r in rows if r.survey_id),
        "roads": [
            {
                "road_id": str(r.id),
                "name": r.name or "Unnamed road",
                "road_type": r.road_type,
                "geometry": r.geometry,
                "surveyed": r.survey_id is not None,
                "survey_id": str(r.survey_id) if r.survey_id else None,
            }
            for r in rows
        ],
    }


@router.get("/assignments/{assignment_id}/surveys")
async def get_assignment_surveys(assignment_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(assignment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    surveys = await db.execute(
        text("""
            SELECT ls.id, ls.road_id, ls.household_type, ls.household_count_range,
                   ls.shop_count, ls.shop_types, ls.road_condition, ls.foot_traffic,
                   ls.notes, ls.submitted_at,
                   r.name AS road_name, r.road_type
            FROM lane_surveys ls
            LEFT JOIN osm_roads r ON ls.road_id = r.id
            WHERE ls.assignment_id = cast(:aid as uuid)
            ORDER BY ls.submitted_at DESC
        """),
        {"aid": assignment_id},
    )
    rows = surveys.fetchall()

    return {
        "assignment_id": assignment_id,
        "surveys": [
            {
                "survey_id": str(r.id),
                "road_id": str(r.road_id) if r.road_id else None,
                "road_name": r.road_name or "Unnamed road",
                "road_type": r.road_type,
                "household_type": r.household_type,
                "household_count_range": r.household_count_range,
                "shop_count": r.shop_count,
                "shop_types": r.shop_types,
                "road_condition": r.road_condition,
                "foot_traffic": r.foot_traffic,
                "notes": r.notes,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in rows
        ],
    }


@router.post("/assignments/{assignment_id}/surveys")
async def submit_lane_survey(assignment_id: str, body: SubmitLaneSurvey, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(assignment_id)
        uuid.UUID(body.road_id)
        uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    assignment = await db.execute(
        text("SELECT id, assigned_to, status FROM survey_assignments WHERE id = cast(:aid as uuid)"),
        {"aid": assignment_id},
    )
    a = assignment.fetchone()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if a.status != "in_progress":
        raise HTTPException(status_code=422, detail="Assignment must be in_progress to submit surveys")

    user = await db.execute(
        text("SELECT id, role FROM users WHERE id = cast(:uid as uuid)"),
        {"uid": body.user_id},
    )
    u = user.fetchone()
    if not u or u.role != "survey_executive":
        raise HTTPException(status_code=403, detail="Only a Survey Executive can submit lane surveys")
    if str(a.assigned_to) != body.user_id:
        raise HTTPException(status_code=403, detail="Only the assigned executive can submit surveys for this assignment")

    existing = await db.execute(
        text("SELECT id FROM lane_surveys WHERE assignment_id = cast(:aid as uuid) AND road_id = cast(:rid as uuid)"),
        {"aid": assignment_id, "rid": body.road_id},
    )
    import json
    now = datetime.now(timezone.utc)
    shop_types_json = json.dumps(body.shop_types) if body.shop_types else None

    ex = existing.fetchone()
    if ex:
        await db.execute(
            text("""
                UPDATE lane_surveys SET
                    household_type = :ht, household_count_range = :hcr,
                    shop_count = :sc, shop_types = cast(:st as jsonb),
                    road_condition = :rc, foot_traffic = :ft,
                    notes = :notes, submitted_at = :now
                WHERE id = cast(:sid as uuid)
            """),
            {
                "sid": str(ex.id), "ht": body.household_type, "hcr": body.household_count_range,
                "sc": body.shop_count, "st": shop_types_json,
                "rc": body.road_condition, "ft": body.foot_traffic,
                "notes": body.notes, "now": now,
            },
        )
        survey_id = str(ex.id)
    else:
        survey_id = str(uuid.uuid4())
        await db.execute(
            text("""
                INSERT INTO lane_surveys (id, assignment_id, road_id, household_type, household_count_range,
                    shop_count, shop_types, road_condition, foot_traffic, notes, submitted_at)
                VALUES (cast(:id as uuid), cast(:aid as uuid), cast(:rid as uuid),
                    :ht, :hcr, :sc, cast(:st as jsonb), :rc, :ft, :notes, :now)
            """),
            {
                "id": survey_id, "aid": assignment_id, "rid": body.road_id,
                "ht": body.household_type, "hcr": body.household_count_range,
                "sc": body.shop_count, "st": shop_types_json,
                "rc": body.road_condition, "ft": body.foot_traffic,
                "notes": body.notes, "now": now,
            },
        )

    await db.commit()

    return {
        "survey_id": survey_id,
        "assignment_id": assignment_id,
        "road_id": body.road_id,
        "updated": ex is not None,
        "submitted_at": now.isoformat(),
    }


async def _generate_insight(study_id: str, db: AsyncSession):
    import json as _json

    total_roads_result = await db.execute(
        text("""
            SELECT count(*) FROM osm_roads
            WHERE ST_Intersects(geometry, (SELECT boundary FROM catchment_studies WHERE id = cast(:sid as uuid)))
        """),
        {"sid": study_id},
    )
    total_roads = total_roads_result.scalar() or 0

    surveys = await db.execute(
        text("""
            SELECT ls.household_type, ls.household_count_range, ls.shop_count,
                   ls.shop_types, ls.road_condition, ls.foot_traffic
            FROM lane_surveys ls
            JOIN survey_assignments sa ON ls.assignment_id = sa.id
            WHERE sa.study_id = cast(:sid as uuid)
        """),
        {"sid": study_id},
    )
    rows = surveys.fetchall()
    surveyed = len(rows)

    household_types: dict[str, int] = {}
    household_ranges: dict[str, int] = {}
    road_conditions: dict[str, int] = {}
    foot_traffic: dict[str, int] = {}
    shop_type_counts: dict[str, int] = {}
    total_shops = 0

    for r in rows:
        if r.household_type:
            household_types[r.household_type] = household_types.get(r.household_type, 0) + 1
        if r.household_count_range:
            household_ranges[r.household_count_range] = household_ranges.get(r.household_count_range, 0) + 1
        if r.road_condition:
            road_conditions[r.road_condition] = road_conditions.get(r.road_condition, 0) + 1
        if r.foot_traffic:
            foot_traffic[r.foot_traffic] = foot_traffic.get(r.foot_traffic, 0) + 1
        if r.shop_count:
            total_shops += r.shop_count
        if r.shop_types:
            types = r.shop_types if isinstance(r.shop_types, list) else []
            for t in types:
                shop_type_counts[t] = shop_type_counts.get(t, 0) + 1

    aggregated = {
        "household_types": household_types,
        "household_count_ranges": household_ranges,
        "road_conditions": road_conditions,
        "foot_traffic": foot_traffic,
        "total_shops": total_shops,
        "shop_type_distribution": shop_type_counts,
    }

    completion_pct = round((surveyed / total_roads * 100) if total_roads > 0 else 0, 1)

    existing = await db.execute(
        text("SELECT id FROM catchment_insights WHERE study_id = cast(:sid as uuid)"),
        {"sid": study_id},
    )
    ex = existing.fetchone()

    if ex:
        await db.execute(
            text("""
                UPDATE catchment_insights SET
                    total_roads_surveyed = :surveyed, total_roads_in_area = :total,
                    completion_pct = :pct, aggregated_data = cast(:agg as jsonb),
                    created_at = now()
                WHERE id = cast(:iid as uuid)
            """),
            {"iid": str(ex.id), "surveyed": surveyed, "total": total_roads, "pct": completion_pct, "agg": _json.dumps(aggregated)},
        )
    else:
        insight_id = uuid.uuid4()
        await db.execute(
            text("""
                INSERT INTO catchment_insights (id, study_id, total_roads_surveyed, total_roads_in_area, completion_pct, aggregated_data)
                VALUES (cast(:id as uuid), cast(:sid as uuid), :surveyed, :total, :pct, cast(:agg as jsonb))
            """),
            {"id": str(insight_id), "sid": study_id, "surveyed": surveyed, "total": total_roads, "pct": completion_pct, "agg": _json.dumps(aggregated)},
        )


@router.get("/{study_id}/insight")
async def get_catchment_insight(study_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(study_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid study ID")

    study = await db.execute(
        text("""
            SELECT cs.id, cs.status, cs.property_id,
                   p.address AS property_address, p.pincode AS property_pincode
            FROM catchment_studies cs
            JOIN properties p ON cs.property_id = p.id
            WHERE cs.id = cast(:sid as uuid)
        """),
        {"sid": study_id},
    )
    s = study.fetchone()
    if not s:
        raise HTTPException(status_code=404, detail="Catchment study not found")

    insight = await db.execute(
        text("""
            SELECT id, total_roads_surveyed, total_roads_in_area, completion_pct,
                   aggregated_data, ai_narrative, created_at
            FROM catchment_insights WHERE study_id = cast(:sid as uuid)
            ORDER BY created_at DESC LIMIT 1
        """),
        {"sid": study_id},
    )
    row = insight.fetchone()
    if not row:
        if s.status == "completed":
            await _generate_insight(study_id, db)
            await db.commit()
            re = await db.execute(
                text("SELECT id, total_roads_surveyed, total_roads_in_area, completion_pct, aggregated_data, ai_narrative, created_at FROM catchment_insights WHERE study_id = cast(:sid as uuid) ORDER BY created_at DESC LIMIT 1"),
                {"sid": study_id},
            )
            row = re.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No insight generated yet. Study must be completed first.")

    return {
        "study_id": study_id,
        "study_status": s.status,
        "property_id": str(s.property_id),
        "property_address": s.property_address,
        "property_pincode": s.property_pincode,
        "insight": {
            "id": str(row.id),
            "total_roads_surveyed": row.total_roads_surveyed,
            "total_roads_in_area": row.total_roads_in_area,
            "completion_pct": row.completion_pct,
            "aggregated_data": row.aggregated_data,
            "ai_narrative": row.ai_narrative,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        },
    }
