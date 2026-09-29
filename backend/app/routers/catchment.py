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

    await db.commit()

    return {
        "assignment_id": str(a.id),
        "status": body.new_status,
        "study_id": str(a.study_id),
    }
