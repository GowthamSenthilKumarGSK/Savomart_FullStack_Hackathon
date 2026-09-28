"""
LLM service for grounded area fitness explanations.

Uses the OpenAI-compatible SDK with configurable provider/base_url.
Falls back gracefully when no API key is configured.
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

log = logging.getLogger(__name__)

PROVIDER_DEFAULTS = {
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/",
        "model": "claude-sonnet-4-20250514",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}

SYSTEM_PROMPT = """\
You are an area intelligence analyst for Savomart, a grocery retail chain expanding in Chennai, India.
You will receive a structured Area Fitness Report containing deterministic scores and raw metrics computed from OpenStreetMap and Savomart store data.

Your job is to explain the report in plain language for a BD Manager deciding where to scout for new store locations.

STRICT RULES:
- Every number you cite MUST come directly from the supplied report data. Do not round, estimate, or invent numbers.
- Do not mention population, income, rent, footfall, revenue, or any metric not in the data.
- Clearly note when a metric is a "proxy" or "derived" signal (the report labels these).
- Keep the tone professional and concise.
- Focus on actionable insights for grocery retail expansion.

Respond with valid JSON matching this exact structure:
{
  "area_summary": "2-3 sentence overview of this area's fitness for Savomart expansion",
  "positive_signals": ["signal 1", "signal 2", "signal 3"],
  "risks": ["risk 1", "risk 2"],
  "scouting_focus": "1-2 sentence recommendation on what to investigate during field visits"
}

Return ONLY the JSON object, no markdown fences or extra text."""


def _is_configured() -> bool:
    return bool(settings.llm_api_key)


def _get_client() -> AsyncOpenAI:
    provider = settings.llm_provider.lower()
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    base_url = settings.llm_base_url or defaults.get("base_url", "")
    return AsyncOpenAI(api_key=settings.llm_api_key, base_url=base_url or None)


def _get_model() -> str:
    if settings.llm_model:
        return settings.llm_model
    provider = settings.llm_provider.lower()
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    return defaults.get("model", "gpt-4o-mini")


def _build_user_prompt(report: dict[str, Any]) -> str:
    return f"""\
Area Fitness Report for {report.get('name', 'Unknown')} (Pincode: {report.get('pincode', '?')})

Overall Score: {report.get('overall_score')}/100 — Grade {report.get('grade')}

Dimension Scores (weight → score):
{_format_dimensions(report.get('sub_scores', {}))}

Raw Metrics:
{json.dumps(report.get('raw_data', {}), indent=2)}

Data Sources: {', '.join(report.get('data_sources', []))}
"""


def _format_dimensions(sub_scores: dict) -> str:
    lines = []
    for name, data in sub_scores.items():
        label = name.replace('_', ' ').title()
        lines.append(f"  {label}: {data.get('weight', 0)*100:.0f}% → {data.get('score', 0)}/100")
        if 'metrics' in data:
            for mkey, mval in data['metrics'].items():
                mlabel = mkey.replace('_', ' ')
                mtype = mval.get('type', 'direct')
                lines.append(f"    - {mlabel}: {mval.get('value')} [{mtype}]")
    return '\n'.join(lines)


def _validate_response(data: Any) -> dict | None:
    if not isinstance(data, dict):
        return None
    required = {'area_summary', 'positive_signals', 'risks', 'scouting_focus'}
    if not required.issubset(data.keys()):
        return None
    if not isinstance(data['area_summary'], str) or not data['area_summary']:
        return None
    if not isinstance(data['positive_signals'], list) or len(data['positive_signals']) == 0:
        return None
    if not isinstance(data['risks'], list):
        return None
    if not isinstance(data['scouting_focus'], str):
        return None
    return {
        'area_summary': data['area_summary'],
        'positive_signals': [str(s) for s in data['positive_signals'][:5]],
        'risks': [str(r) for r in data['risks'][:5]],
        'scouting_focus': data['scouting_focus'],
    }


async def generate_explanation(report: dict[str, Any]) -> dict | None:
    if not _is_configured():
        log.info("LLM not configured (no API key), skipping explanation")
        return None

    client = _get_client()
    model = _get_model()
    user_prompt = _build_user_prompt(report)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(content)
        validated = _validate_response(parsed)
        if not validated:
            log.warning("LLM response failed validation: %s", content[:200])
            return None
        return validated
    except json.JSONDecodeError as e:
        log.warning("LLM returned invalid JSON: %s", e)
        return None
    except Exception as e:
        log.warning("LLM call failed: %s", e)
        return None
