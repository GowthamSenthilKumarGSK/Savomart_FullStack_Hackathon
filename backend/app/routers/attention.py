from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/attention", tags=["attention"])

VALID_ROLES = {"bd_manager", "bd_executive", "survey_manager", "survey_executive"}


@router.get("")
async def get_attention_items(
    user_id: str = Query(...),
    role: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    items = []

    if role == "bd_manager":
        # Tasks awaiting assignment (created but not yet assigned)
        r = await db.execute(text("""
            SELECT st.id, st.pincode_code, st.hotspot_rank, st.status, st.created_at
            FROM scouting_tasks st
            WHERE st.status = 'assigned' AND st.property_id IS NULL
            ORDER BY st.created_at DESC LIMIT 10
        """))
        for row in r:
            items.append({
                "type": "scouting_task",
                "priority": "medium",
                "title": f"Hotspot #{row.hotspot_rank} in {row.pincode_code} — awaiting property submission",
                "task_id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        # Properties awaiting evaluation
        r = await db.execute(text("""
            SELECT p.id, p.address, p.pincode, p.stage, p.created_at
            FROM properties p
            LEFT JOIN property_evaluations pe ON pe.property_id = p.id
            WHERE pe.id IS NULL
            ORDER BY p.created_at DESC LIMIT 10
        """))
        for row in r:
            items.append({
                "type": "property_eval",
                "priority": "high",
                "title": f"Property at {row.address or row.pincode} needs evaluation",
                "property_id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        # Properties scouted but no catchment study requested
        r = await db.execute(text("""
            SELECT p.id, p.address, p.pincode, p.created_at
            FROM properties p
            LEFT JOIN catchment_studies cs ON cs.property_id = p.id
            WHERE p.stage = 'scouted' AND cs.id IS NULL
            ORDER BY p.created_at DESC LIMIT 10
        """))
        for row in r:
            items.append({
                "type": "catchment_needed",
                "priority": "medium",
                "title": f"Property at {row.address or row.pincode} — no catchment study requested",
                "property_id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        # Catchment studies in requested/planning status
        r = await db.execute(text("""
            SELECT cs.id, cs.status, p.address, p.pincode, cs.created_at
            FROM catchment_studies cs
            JOIN properties p ON p.id = cs.property_id
            WHERE cs.status IN ('requested', 'planning')
            ORDER BY cs.created_at ASC LIMIT 10
        """))
        for row in r:
            items.append({
                "type": "catchment_study",
                "priority": "high" if row.status == "requested" else "medium",
                "title": f"Catchment study for {row.address or row.pincode} — {row.status.replace('_', ' ')}",
                "study_id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

    elif role == "bd_executive":
        # Assigned/in-progress tasks for this user
        r = await db.execute(text("""
            SELECT st.id, st.pincode_code, st.hotspot_rank, st.status, st.property_id, st.created_at
            FROM scouting_tasks st
            WHERE st.assigned_to = :uid AND st.status IN ('assigned', 'in_progress')
            ORDER BY st.created_at ASC LIMIT 10
        """), {"uid": user_id})
        for row in r:
            has_prop = row.property_id is not None
            if has_prop:
                title = f"Hotspot #{row.hotspot_rank} in {row.pincode_code} — property submitted, {row.status.replace('_', ' ')}"
                prio = "low"
            else:
                title = f"Hotspot #{row.hotspot_rank} in {row.pincode_code} — needs property submission"
                prio = "high"
            items.append({
                "type": "scouting_task",
                "priority": prio,
                "title": title,
                "task_id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

    elif role == "survey_manager":
        # Requested catchment studies
        r = await db.execute(text("""
            SELECT cs.id, cs.status, p.address, p.pincode, cs.created_at
            FROM catchment_studies cs
            JOIN properties p ON p.id = cs.property_id
            WHERE cs.status IN ('requested', 'planning', 'in_progress')
            ORDER BY
                CASE cs.status WHEN 'requested' THEN 0 WHEN 'planning' THEN 1 ELSE 2 END,
                cs.created_at ASC
            LIMIT 15
        """))
        for row in r:
            prio = {"requested": "high", "planning": "medium"}.get(row.status, "low")
            items.append({
                "type": "catchment_study",
                "priority": prio,
                "title": f"Study for {row.address or row.pincode} — {row.status.replace('_', ' ')}",
                "study_id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        # Assignments that are in_progress
        r = await db.execute(text("""
            SELECT sa.id, sa.status, sa.study_id, u.name AS assignee,
                   cs.status AS study_status, p.address
            FROM survey_assignments sa
            JOIN catchment_studies cs ON cs.id = sa.study_id
            JOIN properties p ON p.id = cs.property_id
            LEFT JOIN users u ON u.id = sa.assigned_to
            WHERE sa.status = 'in_progress'
            ORDER BY sa.created_at ASC LIMIT 10
        """))
        for row in r:
            items.append({
                "type": "assignment",
                "priority": "medium",
                "title": f"Zone assignment for {row.address} ({row.assignee or 'unassigned'}) — in progress",
                "study_id": str(row.study_id),
                "created_at": None,
            })

    elif role == "survey_executive":
        r = await db.execute(text("""
            SELECT sa.id, sa.status, sa.study_id, p.address,
                   (SELECT count(*) FROM lane_surveys ls WHERE ls.assignment_id = sa.id) AS surveyed
            FROM survey_assignments sa
            JOIN catchment_studies cs ON cs.id = sa.study_id
            JOIN properties p ON p.id = cs.property_id
            WHERE sa.assigned_to = :uid AND sa.status IN ('assigned', 'in_progress')
            ORDER BY sa.created_at ASC LIMIT 10
        """), {"uid": user_id})
        for row in r:
            surveyed = row.surveyed or 0
            title = f"Zone for {row.address} — {surveyed} road(s) surveyed, {row.status.replace('_', ' ')}"
            items.append({
                "type": "assignment",
                "priority": "high" if row.status == 'assigned' else "medium",
                "title": title,
                "study_id": str(row.study_id),
                "created_at": None,
            })

    return {"items": items, "count": len(items)}
