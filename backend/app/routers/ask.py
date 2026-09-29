import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str
    role: str = "bd_manager"


QUERY_PATTERNS = [
    ("compare_areas", re.compile(
        r"compare.*?(\d{6}).*?(\d{6})", re.I)),
    ("find_areas", re.compile(
        r"(?:find|which|what|list).*?(?:area|pincode|zone)s?.*?(?:score|fitness|above|below|over|under|best|worst|top|high|low)", re.I)),
    ("explain_evaluation", re.compile(
        r"(?:explain|why|what|how|tell).*?(?:evaluat|score|grade|rating).*?(?:property|address|site)", re.I)),
    ("explain_evaluation_addr", re.compile(
        r"(?:explain|why|what|how|tell).*?(?:property|address|site).*?(?:evaluat|score|grade|rating)", re.I)),
    ("explain_catchment", re.compile(
        r"(?:explain|what|how|tell|status).*?(?:catchment|survey|insight|zone)", re.I)),
]


def classify_question(q: str) -> tuple[str, dict]:
    for qtype, pattern in QUERY_PATTERNS:
        m = pattern.search(q)
        if m:
            if qtype == "compare_areas":
                return "compare_areas", {"pincode1": m.group(1), "pincode2": m.group(2)}
            if qtype in ("explain_evaluation", "explain_evaluation_addr"):
                return "explain_evaluation", {}
            return qtype, {}
    return "unsupported", {}


async def _fetch_area_report(db: AsyncSession, pincode: str) -> dict | None:
    r = await db.execute(text("""
        SELECT ar.id, p.code AS pincode, ar.overall_score, ar.sub_scores, ar.raw_data, ar.created_at
        FROM area_reports ar
        JOIN areas a ON a.id = ar.area_id
        JOIN pincodes p ON p.id = a.pincode_id
        WHERE p.code = :p
        ORDER BY ar.created_at DESC LIMIT 1
    """), {"p": pincode})
    row = r.fetchone()
    if not row:
        return None
    sub = row.sub_scores if isinstance(row.sub_scores, dict) else json.loads(row.sub_scores) if row.sub_scores else {}
    raw = row.raw_data if isinstance(row.raw_data, dict) else json.loads(row.raw_data) if row.raw_data else {}
    return {
        "report_id": str(row.id),
        "pincode": row.pincode,
        "overall_score": row.overall_score,
        "sub_scores": sub,
        "raw_data": raw,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _handle_compare(db: AsyncSession, question: str, params: dict) -> dict:
    p1, p2 = params["pincode1"], params["pincode2"]
    r1 = await _fetch_area_report(db, p1)
    r2 = await _fetch_area_report(db, p2)
    missing = []
    if not r1:
        missing.append(p1)
    if not r2:
        missing.append(p2)
    if missing:
        return {
            "answer": f"No fitness report found for pincode(s): {', '.join(missing)}. Run Area Intelligence first.",
            "sources": [],
            "query_type": "compare_areas",
        }
    context = _build_comparison_context(r1, r2)
    answer = await _llm_answer(question, context)
    return {
        "answer": answer,
        "sources": [
            {"type": "area_report", "pincode": p1, "score": r1["overall_score"], "report_id": r1["report_id"]},
            {"type": "area_report", "pincode": p2, "score": r2["overall_score"], "report_id": r2["report_id"]},
        ],
        "query_type": "compare_areas",
    }


def _build_comparison_context(r1: dict, r2: dict) -> str:
    def _dim_summary(sub: dict) -> str:
        return ", ".join(f"{k.replace('_',' ').title()}: {v.get('score',0)}/100 ({v.get('weight',0)*100:.0f}%)"
                         for k, v in sub.items())
    return f"""Area Comparison Data (from database — do not invent additional data):

Area {r1['pincode']}:
  Overall Score: {r1['overall_score']}/100
  Dimensions: {_dim_summary(r1['sub_scores'])}
  Report date: {r1['created_at']}

Area {r2['pincode']}:
  Overall Score: {r2['overall_score']}/100
  Dimensions: {_dim_summary(r2['sub_scores'])}
  Report date: {r2['created_at']}
"""


async def _handle_find_areas(db: AsyncSession, question: str) -> dict:
    r = await db.execute(text("""
        SELECT DISTINCT ON (p.code) p.code AS pincode, ar.overall_score, ar.sub_scores, ar.created_at
        FROM area_reports ar
        JOIN areas a ON a.id = ar.area_id
        JOIN pincodes p ON p.id = a.pincode_id
        ORDER BY p.code, ar.created_at DESC
    """))
    rows = r.fetchall()
    if not rows:
        return {"answer": "No area fitness reports found. Run Area Intelligence analysis first.", "sources": [], "query_type": "find_areas"}

    summaries = []
    sources = []
    for row in sorted(rows, key=lambda x: x.overall_score or 0, reverse=True):
        sub = row.sub_scores if isinstance(row.sub_scores, dict) else json.loads(row.sub_scores) if row.sub_scores else {}
        dims = ", ".join(f"{k.replace('_',' ').title()}: {v.get('score',0)}" for k, v in sub.items())
        summaries.append(f"  {row.pincode}: {row.overall_score}/100 — {dims}")
        sources.append({"type": "area_report", "pincode": row.pincode, "score": row.overall_score})

    context = f"All analyzed areas (from database):\n" + "\n".join(summaries)
    answer = await _llm_answer(question, context)
    return {"answer": answer, "sources": sources, "query_type": "find_areas"}


async def _handle_explain_evaluation(db: AsyncSession, question: str) -> dict:
    addr_match = re.search(r'(?:property|site|address)\s+(?:at|on|in)\s+["\']?(.+?)(?:["\']|\?|$)', question, re.I)
    if not addr_match:
        addr_match = re.search(r'(?:at|on)\s+["\']?(\d+.*?(?:Road|Street|Lane|Nagar|Avenue).+?)(?:["\']|\?|$)', question, re.I)

    if addr_match:
        search = addr_match.group(1).strip().rstrip("?").strip()
        r = await db.execute(text("""
            SELECT p.id, p.address, p.pincode, pe.overall_score, pe.sub_scores, pe.raw_data, pe.created_at
            FROM properties p
            JOIN property_evaluations pe ON pe.property_id = p.id
            WHERE p.address ILIKE :q
            ORDER BY pe.created_at DESC LIMIT 1
        """), {"q": f"%{search}%"})
    else:
        r = await db.execute(text("""
            SELECT p.id, p.address, p.pincode, pe.overall_score, pe.sub_scores, pe.raw_data, pe.created_at
            FROM properties p
            JOIN property_evaluations pe ON pe.property_id = p.id
            ORDER BY pe.created_at DESC LIMIT 1
        """))

    row = r.fetchone()
    if not row:
        return {"answer": "No evaluated properties found matching your query. Submit and evaluate a property first.", "sources": [], "query_type": "explain_evaluation"}

    sub = row.sub_scores if isinstance(row.sub_scores, dict) else json.loads(row.sub_scores) if row.sub_scores else {}
    raw = row.raw_data if isinstance(row.raw_data, dict) else json.loads(row.raw_data) if row.raw_data else {}

    dims = "\n".join(f"  {k.replace('_',' ').title()}: {v.get('score',0)}/100 (weight {v.get('weight',0)*100:.0f}%)"
                     for k, v in sub.items())

    scalar_raw = {k: v for k, v in raw.items() if isinstance(v, (str, int, float, bool))}

    context = f"""Property Evaluation Data (from database):
Property: {row.address} ({row.pincode})
Overall Score: {row.overall_score}/100
Evaluated: {row.created_at.isoformat() if row.created_at else 'unknown'}

Dimension Scores:
{dims}

Key Signals:
{json.dumps(scalar_raw, indent=2)}
"""
    answer = await _llm_answer(question, context)
    return {
        "answer": answer,
        "sources": [{"type": "property_evaluation", "property_id": str(row.id), "address": row.address, "score": row.overall_score}],
        "query_type": "explain_evaluation",
    }


async def _handle_explain_catchment(db: AsyncSession, question: str) -> dict:
    r = await db.execute(text("""
        SELECT cs.id AS study_id, cs.status, cs.radius_m, cs.created_at,
               p.address, p.pincode,
               ci.total_roads_surveyed, ci.total_roads_in_area, ci.completion_pct,
               ci.aggregated_data
        FROM catchment_studies cs
        JOIN properties p ON p.id = cs.property_id
        LEFT JOIN catchment_insights ci ON ci.study_id = cs.id
        ORDER BY cs.created_at DESC LIMIT 5
    """))
    rows = r.fetchall()
    if not rows:
        return {"answer": "No catchment studies found. Request one from the Scouting Tasks page.", "sources": [], "query_type": "explain_catchment"}

    parts = []
    sources = []
    for row in rows:
        agg = row.aggregated_data if isinstance(row.aggregated_data, dict) else {}
        insight_text = ""
        if row.total_roads_surveyed is not None:
            insight_text = f"\n  Roads Surveyed: {row.total_roads_surveyed}/{row.total_roads_in_area} ({row.completion_pct}% coverage)"
            if agg:
                insight_text += f"\n  Total Shops: {agg.get('total_shops', 0)}"
                for key in ("household_types", "road_conditions", "foot_traffic"):
                    d = agg.get(key, {})
                    if d:
                        insight_text += f"\n  {key.replace('_',' ').title()}: {', '.join(f'{k}: {v}' for k,v in d.items())}"
        parts.append(f"""Study for {row.address} ({row.pincode}):
  Status: {row.status}, Radius: {row.radius_m}m, Created: {row.created_at.isoformat() if row.created_at else '?'}{insight_text}""")
        sources.append({"type": "catchment_study", "study_id": str(row.study_id), "address": row.address, "status": row.status})

    context = "Catchment Study Data (from database):\n\n" + "\n\n".join(parts)
    answer = await _llm_answer(question, context)
    return {"answer": answer, "sources": sources, "query_type": "explain_catchment"}


ASK_SYSTEM = """\
You are SiteScout Analyst, an internal data assistant for Savomart's expansion team.
You answer questions using ONLY the structured data provided below.

STRICT RULES:
- Every number you cite MUST come from the provided data. Never calculate, estimate, or invent scores.
- If data is missing or unavailable, say so explicitly.
- Keep answers concise (3-5 sentences).
- Use professional tone suitable for a BD Manager.
- Do not mention population, income, footfall, or metrics not in the data.
- Do not use markdown formatting. Plain text only."""


async def _llm_answer(question: str, context: str) -> str:
    if not settings.llm_api_key:
        return _fallback_answer(context)

    from app.llm import _get_client, _get_model
    client = _get_client()
    model = _get_model()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ASK_SYSTEM},
                {"role": "user", "content": f"DATA:\n{context}\n\nQUESTION: {question}"},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.warning("LLM call failed for Ask SiteScout: %s", e)
        return _fallback_answer(context)


def _fallback_answer(context: str) -> str:
    return f"LLM is not configured. Here is the raw data retrieved:\n\n{context}"


@router.post("")
async def ask_sitescout(req: AskRequest, db: AsyncSession = Depends(get_db)):
    if req.role != "bd_manager":
        raise HTTPException(status_code=403, detail="Ask SiteScout is available to BD Manager only")

    q = req.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question is required")
    if len(q) > 500:
        raise HTTPException(status_code=400, detail="Question too long (max 500 characters)")

    qtype, params = classify_question(q)

    if qtype == "compare_areas":
        return await _handle_compare(db, q, params)
    elif qtype == "find_areas":
        return await _handle_find_areas(db, q)
    elif qtype == "explain_evaluation":
        return await _handle_explain_evaluation(db, q)
    elif qtype == "explain_catchment":
        return await _handle_explain_catchment(db, q)
    else:
        return {
            "answer": "I can help with: comparing two areas by fitness score, finding areas matching criteria, explaining a property evaluation, or explaining catchment study status. Please rephrase your question to match one of these.",
            "sources": [],
            "query_type": "unsupported",
        }
