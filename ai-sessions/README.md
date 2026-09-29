# AI Usage in Savo SiteScout Development

## Tool Used

**Claude Code** (Anthropic's AI coding assistant) was used as a development aid throughout the project.

## How AI Was Used

### Code Generation & Implementation
- AI assisted with writing backend routers, database queries, and frontend components across all three modules (M1, M2, M3) and the bonus features
- PostGIS spatial queries (ST_HexagonGrid, ST_DWithin, ST_Intersects, etc.) were developed iteratively with AI assistance
- The scoring algorithms (area fitness, property evaluation, hotspot ranking) were implemented with AI help, with weights and normalization approaches directed by the developer

### Debugging & Problem Solving
- AI helped diagnose and fix database schema mismatches (e.g., incorrect column references, wrong JOIN directions)
- Regex patterns for the Ask SiteScout question classifier were refined through iterative testing with AI
- Frontend role-based navigation filtering was verified and corrected with AI assistance

### Documentation
- This README and the project README were drafted with AI assistance using the actual codebase as the source of truth

## What AI Did NOT Do

- **Product decisions**: Feature scope, scoring weights, workflow design, and UX choices were made by the developer
- **Data sourcing**: The choice of OpenStreetMap via Geofabrik, the Chennai bounding box, and the pincode boundary source were developer decisions
- **Architecture decisions**: The choice of FastAPI + React + PostGIS, raw SQL over ORM, server-rendered Decision Pack, and regex-based question classification were developer-directed
- **Testing**: All verification was performed manually by the developer through the browser

## AI in the Product

The product itself has optional LLM integration in two places:

1. **Area Fitness Explanation** (M1): An LLM explains pre-computed fitness reports in natural language
2. **Ask SiteScout** (Bonus): A conversational interface that retrieves structured DB data and sends it to an LLM for grounded explanation

In both cases:
- All scores and rankings are computed by deterministic algorithms before the LLM is invoked
- The LLM is strictly grounded — it can only explain data it receives, never calculate or invent
- The system works fully without any LLM configured (explanation fields are null; Ask SiteScout returns raw data)
- LLM provider is configurable (Anthropic Claude or OpenAI) via environment variables

## Session History

Development spanned multiple Claude Code sessions covering:
- M1 Area Intelligence (pincode boundaries, fitness scoring, hotspot identification)
- M2 Property Scouting (task management, property submission, evaluation scoring)
- M3 Catchment Study (study lifecycle, zone assignments, lane surveys, insight generation)
- Bonus features (Decision Pack export, Attention Feed, Ask SiteScout)
- Documentation

### Session Transcripts

This directory contains the raw, unedited AI session history from development:

| File | Format | Size | Coverage |
|------|--------|------|----------|
| `session-earlier.jsonl` | Raw JSONL transcript | ~31 MB | M1 Area Intelligence, M2 Property Scouting, M3 Catchment Study — the core platform build |
| `session-current.zip` | Claude Code export (zip) | ~21 MB | Bonus features (Decision Pack, Attention Feed, Ask SiteScout) and documentation |

**`session-earlier.jsonl`** is the raw Claude Code conversation log from the earlier development session. Each line is a JSON object representing one message or tool call in the conversation. This session built the full M1→M2→M3 pipeline: database schema and migrations, PostGIS spatial queries, area fitness scoring, hotspot detection, scouting task workflow, property evaluation, catchment studies with zone assignments and lane surveys, and the React frontend for all three modules.

**`session-current.zip`** is a Claude Code native export containing the conversation transcript, subagent transcripts, and session metadata. This session implemented the three bonus features (Decision Pack export, Needs Attention feed, Ask SiteScout conversational analyst) and wrote all project documentation.

Both files are unmodified transcripts — no content has been summarized, edited, or fabricated.
