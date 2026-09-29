import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/scouting-tasks", tags=["scouting"])

VALID_TRANSITIONS = {
    "assigned": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
}


class HotspotCentroid(BaseModel):
    lat: float
    lng: float


class CreateScoutingTask(BaseModel):
    pincode: str
    area_report_id: str | None = None
    hotspot_rank: int
    hotspot_geometry: dict
    hotspot_centroid: HotspotCentroid
    hotspot_score: int
    hotspot_signals: dict | None = None
    assigned_to: str
    assigned_by: str
    notes: str | None = None


class UpdateScoutingTask(BaseModel):
    status: str


@router.post("")
async def create_scouting_task(body: CreateScoutingTask, db: AsyncSession = Depends(get_db)):
    manager = await db.execute(
        text("SELECT id, role FROM users WHERE id = cast(:uid as uuid)"),
        {"uid": body.assigned_by},
    )
    mgr = manager.fetchone()
    if not mgr or mgr.role != "bd_manager":
        raise HTTPException(status_code=403, detail="assigned_by must be a BD Manager")

    executive = await db.execute(
        text("SELECT id, role FROM users WHERE id = cast(:uid as uuid)"),
        {"uid": body.assigned_to},
    )
    exec_row = executive.fetchone()
    if not exec_row or exec_row.role != "bd_executive":
        raise HTTPException(status_code=403, detail="assigned_to must be a BD Executive")

    pincode = await db.execute(
        text("SELECT code, geometry FROM pincodes WHERE code = :code"),
        {"code": body.pincode},
    )
    pin_row = pincode.fetchone()
    if not pin_row:
        raise HTTPException(status_code=404, detail=f"Pincode {body.pincode} not found")

    geojson_str = json.dumps(body.hotspot_geometry)
    geom_check = await db.execute(
        text("""
            SELECT ST_Intersects(
                ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326),
                p.geometry
            ) AS inside
            FROM pincodes p WHERE p.code = :code
        """),
        {"geojson": geojson_str, "code": body.pincode},
    )
    check_row = geom_check.fetchone()
    if not check_row or not check_row.inside:
        raise HTTPException(status_code=422, detail="Hotspot geometry is not within the specified pincode boundary")

    area = await db.execute(
        text("SELECT a.id FROM areas a JOIN pincodes p ON a.pincode_id = p.id WHERE p.code = :code LIMIT 1"),
        {"code": body.pincode},
    )
    area_row = area.fetchone()
    if not area_row:
        raise HTTPException(status_code=404, detail=f"No area found for pincode {body.pincode}")

    if body.area_report_id:
        try:
            uuid.UUID(body.area_report_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid area_report_id")
        report_check = await db.execute(
            text("SELECT id FROM area_reports WHERE id = cast(:rid as uuid) AND area_id = :aid"),
            {"rid": body.area_report_id, "aid": area_row.id},
        )
        if not report_check.fetchone():
            raise HTTPException(status_code=404, detail="Area report not found for this pincode")

    task_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    await db.execute(
        text("""
            INSERT INTO scouting_tasks
                (id, area_id, area_report_id, pincode_code, hotspot_rank,
                 hotspot_geometry, hotspot_centroid, hotspot_score, hotspot_signals,
                 assigned_to, assigned_by, status, notes, created_at, updated_at)
            VALUES
                (:id, :area_id, :area_report_id, :pincode, :rank,
                 ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326),
                 ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                 :score, cast(:signals as jsonb),
                 cast(:assigned_to as uuid), cast(:assigned_by as uuid),
                 'assigned', :notes, :now, :now)
        """),
        {
            "id": task_id,
            "area_id": area_row.id,
            "area_report_id": uuid.UUID(body.area_report_id) if body.area_report_id else None,
            "pincode": body.pincode,
            "rank": body.hotspot_rank,
            "geom": geojson_str,
            "lat": body.hotspot_centroid.lat,
            "lng": body.hotspot_centroid.lng,
            "score": body.hotspot_score,
            "signals": json.dumps(body.hotspot_signals) if body.hotspot_signals else None,
            "assigned_to": body.assigned_to,
            "assigned_by": body.assigned_by,
            "notes": body.notes,
            "now": now,
        },
    )
    await db.commit()

    return {
        "task_id": str(task_id),
        "status": "assigned",
        "pincode": body.pincode,
        "hotspot_rank": body.hotspot_rank,
        "assigned_to": body.assigned_to,
        "created_at": now.isoformat(),
    }


@router.get("")
async def list_scouting_tasks(
    assigned_to: str | None = None,
    pincode: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    clauses = []
    params: dict = {}
    if assigned_to:
        clauses.append("st.assigned_to = cast(:assigned_to as uuid)")
        params["assigned_to"] = assigned_to
    if pincode:
        clauses.append("st.pincode_code = :pincode")
        params["pincode"] = pincode
    if status:
        clauses.append("st.status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    result = await db.execute(
        text(f"""
            SELECT st.id, st.pincode_code, st.hotspot_rank, st.hotspot_score,
                   ST_AsGeoJSON(st.hotspot_centroid)::json AS centroid_geojson,
                   st.status, st.notes, st.created_at, st.updated_at,
                   u_to.name AS executive_name, u_by.name AS manager_name,
                   st.area_report_id
            FROM scouting_tasks st
            JOIN users u_to ON st.assigned_to = u_to.id
            JOIN users u_by ON st.assigned_by = u_by.id
            {where}
            ORDER BY st.created_at DESC
        """),
        params,
    )
    rows = result.fetchall()

    tasks = []
    for r in rows:
        centroid = r.centroid_geojson
        tasks.append({
            "task_id": str(r.id),
            "pincode": r.pincode_code,
            "hotspot_rank": r.hotspot_rank,
            "hotspot_score": r.hotspot_score,
            "centroid": {"lat": centroid["coordinates"][1], "lng": centroid["coordinates"][0]} if centroid else None,
            "status": r.status,
            "notes": r.notes,
            "executive_name": r.executive_name,
            "manager_name": r.manager_name,
            "area_report_id": str(r.area_report_id) if r.area_report_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })

    return {"tasks": tasks}


@router.get("/{task_id}")
async def get_scouting_task(task_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    result = await db.execute(
        text("""
            SELECT st.id, st.pincode_code, st.hotspot_rank, st.hotspot_score,
                   ST_AsGeoJSON(st.hotspot_geometry)::json AS geometry_geojson,
                   ST_AsGeoJSON(st.hotspot_centroid)::json AS centroid_geojson,
                   st.hotspot_signals, st.status, st.notes,
                   st.created_at, st.updated_at, st.area_report_id,
                   st.assigned_to, st.assigned_by,
                   u_to.name AS executive_name, u_to.email AS executive_email,
                   u_by.name AS manager_name, u_by.email AS manager_email
            FROM scouting_tasks st
            JOIN users u_to ON st.assigned_to = u_to.id
            JOIN users u_by ON st.assigned_by = u_by.id
            WHERE st.id = cast(:tid as uuid)
        """),
        {"tid": task_id},
    )
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Scouting task not found")

    centroid = r.centroid_geojson
    return {
        "task_id": str(r.id),
        "pincode": r.pincode_code,
        "hotspot_rank": r.hotspot_rank,
        "hotspot_score": r.hotspot_score,
        "hotspot_geometry": r.geometry_geojson,
        "centroid": {"lat": centroid["coordinates"][1], "lng": centroid["coordinates"][0]} if centroid else None,
        "hotspot_signals": r.hotspot_signals,
        "status": r.status,
        "notes": r.notes,
        "area_report_id": str(r.area_report_id) if r.area_report_id else None,
        "assigned_to": {"id": str(r.assigned_to), "name": r.executive_name, "email": r.executive_email},
        "assigned_by": {"id": str(r.assigned_by), "name": r.manager_name, "email": r.manager_email},
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.patch("/{task_id}")
async def update_scouting_task(task_id: str, body: UpdateScoutingTask, db: AsyncSession = Depends(get_db)):
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    result = await db.execute(
        text("SELECT id, status FROM scouting_tasks WHERE id = cast(:tid as uuid)"),
        {"tid": task_id},
    )
    task = result.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Scouting task not found")

    allowed = VALID_TRANSITIONS.get(task.status, [])
    if body.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{task.status}' to '{body.status}'. Allowed: {allowed}",
        )

    now = datetime.now(timezone.utc)
    await db.execute(
        text("UPDATE scouting_tasks SET status = :status, updated_at = :now WHERE id = cast(:tid as uuid)"),
        {"status": body.status, "now": now, "tid": task_id},
    )
    await db.commit()

    return {"task_id": task_id, "status": body.status, "updated_at": now.isoformat()}
