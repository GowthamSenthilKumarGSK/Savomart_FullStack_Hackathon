# Savo SiteScout

**Expansion Intelligence Platform for Savomart**

Savo SiteScout is a geospatial decision-support tool built for Savomart's Business Development team to identify, evaluate, and validate new grocery store locations across Chennai. It replaces manual, intuition-driven site selection with a structured, data-backed workflow spanning three modules:

**M1 Area Intelligence → M2 Property Scouting & Evaluation → M3 Catchment Study**

Built for the Savomart Full Stack Hackathon 2026.

---

## Table of Contents

- [Product Overview](#product-overview)
- [Personas & Workflows](#personas--workflows)
- [Feature List](#feature-list)
- [Architecture](#architecture)
- [Database & Spatial Design](#database--spatial-design)
- [M1: Area Intelligence](#m1-area-intelligence)
- [M2: Property Scouting & Evaluation](#m2-property-scouting--evaluation)
- [M3: Catchment Study](#m3-catchment-study)
- [Bonus Features](#bonus-features)
- [Data Sources](#data-sources)
- [AI Architecture](#ai-architecture)
- [Setup & Installation](#setup--installation)
- [API Overview](#api-overview)
- [Demo Roles & Usage](#demo-roles--usage)
- [Design Decisions & Product Thinking](#design-decisions--product-thinking)
- [Known Limitations](#known-limitations)
- [Testing & Verification](#testing--verification)
- [AI Usage Disclosure](#ai-usage-disclosure)
- [Demo Video](#demo-video)

---

## Product Overview

Savomart is expanding its grocery retail chain across Chennai. The BD team needs to answer three questions for every potential location:

1. **Which areas are worth scouting?** (M1)
2. **Is this specific property a good fit?** (M2)
3. **What does the surrounding catchment look like on the ground?** (M3)

SiteScout provides deterministic, auditable answers to each question using publicly available geospatial data (OpenStreetMap), Savomart's own store data, and structured field surveys.

## Personas & Workflows

| Persona | Role ID | Primary Workflow |
|---------|---------|-----------------|
| **Priya Sharma** | `bd_manager` | Analyze areas, assign scouting tasks, review properties, request catchment studies |
| **Arjun Patel** | `bd_executive` | Visit assigned hotspots, submit property details, field-validate locations |
| **Meena Krishnan** | `survey_manager` | Plan catchment studies, create zones, assign survey executives |
| **Ravi Kumar** | `survey_executive` | Walk assigned zones, submit lane-by-lane survey data |

### Workflow Sequence

```
BD Manager: Select pincode → View fitness report → Identify hotspots
    ↓
BD Manager: Assign hotspot to BD Executive as scouting task
    ↓
BD Executive: Start task → Visit location → Submit property details
    ↓
System: Auto-evaluate property (deterministic scoring)
    ↓
BD Manager: Review evaluation → Request catchment study
    ↓
Survey Manager: Open study → Create zone(s) → Assign to Survey Executive
    ↓
Survey Executive: Walk zone → Submit lane surveys for each road
    ↓
System: When all assignments complete → Generate catchment insight
    ↓
BD Manager: Review complete decision pack (evaluation + catchment)
```

## Feature List

### M1 — Area Intelligence
- Interactive Leaflet map of 164 Chennai pincodes with boundaries
- Pincode search and click-to-select
- Deterministic area fitness scoring (5 weighted dimensions)
- Winsorized percentile normalization across all pincodes
- Sub-hexagonal hotspot identification using PostGIS `ST_HexagonGrid`
- Top-5 hotspot ranking per pincode with geometry
- Fitness report history and comparison
- Optional LLM-generated explanation (grounded in report data)
- Savomart store overlay on map

### M2 — Property Scouting & Evaluation
- Scouting task assignment from hotspot to BD Executive
- Task lifecycle: `assigned → in_progress → completed`
- Property submission with address, rent, area, frontage, floor, building type
- Duplicate property detection (50m radius using PostGIS `ST_DWithin`)
- Deterministic property evaluation (5 weighted dimensions)
- Grade system (A–F) with positive signals, risks, and recommendation
- Missing-data handling: neutral scores with explicit "missing" flags
- Hotspot context linkback (rank, score, signals)
- Property stage tracking: `scouted → catchment_requested → ...`

### M3 — Catchment Study
- Study request from evaluated property with configurable radius
- Auto-generated study boundary (circular buffer around property)
- Zone creation with H3 hex cells (resolution 9)
- Zone assignment to Survey Executive
- Lane survey capture: household type, count range, shop count/types, road condition, foot traffic
- Road intersection detection using PostGIS `ST_Intersects` with `planet_osm_line`
- Completion guard: assignment cannot complete until all roads surveyed
- Study auto-completion when all assignments complete
- Deterministic catchment insight generation: aggregates all lane surveys into household mix, shop distribution, road conditions, foot traffic
- Insight display with stacked bar charts and summary cards

### Bonus Features
- **Decision Pack Export**: Server-rendered, print-friendly HTML report combining property details, evaluation scores, scouting context, and catchment insight. Browser Print/Save-as-PDF.
- **Needs Attention Feed**: Role-specific action items displayed below the header, showing pending tasks, unevaluated properties, and active studies per persona.
- **Ask SiteScout**: Conversational analyst for BD Manager. Regex-classified queries retrieve structured DB data, sent to LLM for grounded explanation. Supports area comparison, area search, evaluation explanation, and catchment status. Falls back to raw data display when LLM is unconfigured.

## Architecture

```
┌─────────────────────────────┐
│       React Frontend        │
│  Vite + React 19 + Leaflet  │
│  Tailwind CSS + axios       │
│  react-router-dom v7        │
└──────────┬──────────────────┘
           │ HTTP/JSON
┌──────────▼──────────────────┐
│       FastAPI Backend       │
│  async SQLAlchemy + asyncpg │
│  Pydantic v2 models        │
│  Raw SQL via text()         │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│  PostgreSQL 16 + PostGIS    │
│  3.4 (Docker)               │
│  Spatial indexes, geography │
│  casts, hex grids           │
└─────────────────────────────┘
```

### Project Structure

```
├── backend/
│   ├── app/
│   │   ├── config.py              # Environment/settings
│   │   ├── database.py            # Async SQLAlchemy session
│   │   ├── llm.py                 # LLM provider abstraction
│   │   ├── scoring.py             # M1 area fitness scoring
│   │   ├── property_scoring.py    # M2 property evaluation scoring
│   │   ├── models/                # SQLAlchemy ORM models
│   │   │   ├── area.py, geo.py, property.py, scouting.py, survey.py, user.py
│   │   └── routers/
│   │       ├── pincodes.py        # Pincode boundaries
│   │       ├── stores.py          # Savomart store data
│   │       ├── fitness.py         # M1 fitness reports
│   │       ├── hotspots.py        # M1 hotspot identification
│   │       ├── scouting.py        # M2 scouting tasks
│   │       ├── evaluation.py      # M2 property evaluation + Decision Pack
│   │       ├── catchment.py       # M3 studies, assignments, surveys, insights
│   │       ├── attention.py       # Needs Attention feed
│   │       └── ask.py             # Ask SiteScout analyst
│   ├── alembic/                   # 3 migrations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Routes + role-based redirect
│   │   ├── api.js                 # All API client functions
│   │   ├── components/
│   │   │   ├── Layout.jsx         # Header, role switcher, nav filter
│   │   │   ├── NeedsAttention.jsx # Attention feed component
│   │   │   └── AskSiteScout.jsx   # Conversational analyst panel
│   │   └── pages/
│   │       ├── AreaExplorer.jsx   # M1 map + reports
│   │       ├── ScoutingTasks.jsx  # M2 tasks + properties
│   │       └── CatchmentStudies.jsx # M3 studies + surveys
│   └── package.json
├── data/
│   ├── seed_all.py                # Master seed pipeline
│   ├── seed_users.py              # 4 demo users
│   ├── seed_pincodes.py           # Chennai pincode boundaries
│   ├── seed_stores.py             # Savomart stores from API
│   └── seed_osm.py                # OSM POIs + roads from Geofabrik PBF
├── docker-compose.yml             # PostGIS database only
└── .env.example                   # All environment variables
```

## Database & Spatial Design

**Engine**: PostgreSQL 16 with PostGIS 3.4 (Docker)

**Schema** (3 Alembic migrations):

| Table | Purpose | Key Spatial Column |
|-------|---------|-------------------|
| `pincodes` | Chennai pincode boundaries | `geometry` (MULTIPOLYGON, SRID 4326) |
| `osm_pois` | POIs from OpenStreetMap | `location` (POINT, SRID 4326) |
| `osm_roads` | Road network from OSM | `geometry` (LINESTRING, SRID 4326) |
| `savomart_stores` | Savomart store locations | `location` (POINT, SRID 4326) |
| `users` | 4 demo personas | — |
| `areas` | Analyzed pincode areas | links to `pincodes` |
| `area_reports` | M1 fitness reports | — |
| `scouting_tasks` | M2 scouting assignments | `hotspot_geometry`, `hotspot_centroid` |
| `properties` | Submitted properties | `location` (POINT, SRID 4326) |
| `property_evaluations` | M2 evaluation results | — |
| `catchment_studies` | M3 study instances | `boundary` (POLYGON, SRID 4326) |
| `survey_assignments` | M3 zone assignments | `zone_boundary` (POLYGON, SRID 4326) |
| `lane_surveys` | M3 individual road surveys | `location` (POINT, SRID 4326) |
| `catchment_insights` | M3 aggregated insights | — |

**PostGIS usage**: `ST_DWithin` (duplicate detection), `ST_Intersects` (POI containment, road-zone intersection), `ST_Buffer` (catchment boundary), `ST_Distance` (nearest Savomart), `ST_Area` (pincode area), `ST_HexagonGrid` (hotspot cells), `::geography` casts for metre-accurate distances.

**planet_osm_line**: The M3 completion guard uses `planet_osm_line` (imported by osm2pgsql if available) for road intersection counting. On systems without this table, the lane survey form uses `osm_roads` as the road source.

## M1: Area Intelligence

### Scoring Methodology

The area fitness score evaluates each of Chennai's 164 pincodes for grocery retail expansion potential.

**Dimensions and Weights**:

| Dimension | Weight | What It Measures | Key Metrics |
|-----------|--------|------------------|-------------|
| Market Opportunity | 30% | Competitive whitespace | Grocery density, nearest Savomart distance, Savomart presence |
| Commercial Vitality | 25% | Existing commercial ecosystem | POI density, shop count, food outlets, shop diversity, commercial buildings |
| Accessibility | 20% | Road connectivity | Road network km, road density, major road count |
| Residential Signal | 15% | Demand proxy (not real population) | Residential buildings, apartment density, schools/colleges |
| Amenity Infrastructure | 10% | Area maturity signals | Banks/ATMs, healthcare, fuel stations, amenity diversity |

**Important**: Residential Signal uses OSM building tags as a *proxy* for residential density. It is not population data, census data, or actual household counts. Schools/colleges serve as an additional catchment proxy.

**Normalization**: Winsorized percentile ranking (5th–95th percentile) across all 164 pincodes. Each pincode's metrics are ranked against all others, eliminating outlier distortion.

**Market Opportunity scoring**: Not a simple linear percentile. Uses a non-linear whitespace model:
- Very low grocery density (<P10): partial score (area may lack commercial viability)
- Sweet spot (P10–P60): highest scores (underserved but viable)
- Saturated (>P60): declining scores with floor of 20

**Grades**: A (≥80), B (≥60), C (≥40), D (≥20), F (<20)

### Hotspot Identification

Uses PostGIS `ST_HexagonGrid` to subdivide each pincode into ~300m hex cells. Each cell is scored on:

| Factor | Weight |
|--------|--------|
| Commercial activity | 30% |
| Competitive gap | 30% |
| Savomart gap | 20% |
| Accessibility | 20% |

Top 5 cells per pincode are returned as ranked hotspots with their geometry for map display.

### Explainability

Optional LLM explanation (when API key is configured) takes the complete structured report and generates:
- Area summary
- Positive signals
- Risks
- Scouting focus recommendation

The LLM receives only the computed data and is prompted to never invent numbers. When unconfigured, the system operates fully without AI — all scores and hotspots are deterministic.

## M2: Property Scouting & Evaluation

### Scouting Workflow

1. BD Manager assigns a hotspot to a BD Executive (creates scouting task)
2. BD Executive starts the task, visits the location, submits property details
3. System auto-evaluates the property upon submission

### Duplicate Detection

Before accepting a property submission, the system checks for existing properties within 50 metres using `ST_DWithin(location, new_point, 50)` with geography cast. If a duplicate is found, the submission is rejected with the existing property's address.

### Evaluation Methodology

**Dimensions and Weights**:

| Dimension | Weight | Metrics |
|-----------|--------|---------|
| Residential Catchment Proxies | 25% | Residential buildings (500m), apartments (500m), schools/colleges (500m) |
| Commercial Context | 25% | Shops (300m), grocery competition (500m), food outlets (300m), shop diversity (300m) |
| Accessibility | 20% | Nearest major road, road network length (300m), major roads (500m) |
| Savomart Fit | 15% | Nearest Savomart distance, Savomart count (2km) |
| Property Attributes | 15% | Floor, carpet area, frontage |

All spatial metrics use point-radius queries (`ST_DWithin`) with `::geography` casts for metre-accurate distances.

**Property Attributes normalization** uses product heuristics:
- Floor: ground=100, 1st=60, 2nd=35, 3rd+=15
- Carpet area: 300–1500 sqft optimal (90), outside range declines
- Frontage: 10–40 ft optimal (90)

**Missing data handling**: When a property attribute (floor, carpet area, frontage) is not provided, it receives a neutral score of 50 and is flagged as `"missing": true` in the report. The system never fabricates values.

**Output**: Overall score, grade, per-dimension breakdown, positive signals, risks/concerns, and a grade-specific recommendation.

## M3: Catchment Study

### Study Flow

1. BD Manager requests a catchment study for a scouted property (configurable radius, default 100m)
2. System creates a circular boundary around the property location
3. Survey Manager creates zone assignments using H3 hex cells (resolution 9, ~175m radius)
4. Survey Manager assigns zones to Survey Executives
5. Survey Executives walk their zones and submit lane surveys for each road

### Lane Survey Data

Each lane survey captures:
- **Household type**: residential, commercial, mixed, industrial, institutional
- **Household count range**: 0-10, 11-25, 26-50, 51-100, 100+
- **Shop count and types**: grocery, pharmacy, clothing, electronics, food, hardware, etc.
- **Road condition**: excellent, good, fair, poor
- **Foot traffic**: very_high, high, medium, low, very_low
- **Photos** (file path references) and notes

### Completion Rules

- An assignment cannot be marked `completed` until all roads intersecting its zone boundary have been surveyed. The system counts roads via `ST_Intersects` against the zone boundary and compares against submitted lane surveys.
- When all assignments for a study reach `completed`, the study auto-transitions to `completed`.
- Upon study completion, a catchment insight is auto-generated.

### Catchment Insight

Deterministic aggregation of all lane surveys for the study:
- Total roads surveyed vs. total roads in area
- Completion percentage
- Household type distribution
- Household count range distribution
- Shop type distribution and total count
- Road condition distribution
- Foot traffic distribution

No AI is used for insight generation — it is pure aggregation. The `ai_narrative` field exists in the schema but is always null in the current implementation.

## Data Sources

| Source | What | How |
|--------|------|-----|
| **OpenStreetMap via Geofabrik** | POIs (shops, amenities, offices, buildings) and road network | Southern Zone PBF extract, parsed with pyosmium, filtered to Chennai bounding box |
| **Chennai pincode boundaries** | 164 pincode polygons | GeoJSON from data.gov.in / pre-built file |
| **Savomart Stores API** | Operational store locations | Live fetch from `internal-service.savomart.in` with API token (server-side only) |
| **Field surveys** | Lane-level catchment data | Manual entry by Survey Executives via the app |

**No fabricated or synthetic data is used for scoring.** All metrics derive from the OSM dataset and actual Savomart store locations. Residential signals are explicitly labeled as "proxies" — they are building tag counts, not census data.

## AI Architecture

### Where AI Is Used

1. **Area Fitness Explanation** (M1): Optional LLM call to explain a fitness report in natural language. The report data is computed deterministically first; the LLM only explains it.
2. **Ask SiteScout** (Bonus): Conversational analyst that retrieves structured DB data based on question classification, then sends the data + question to the LLM for a grounded answer.

### Where AI Is NOT Used

- Area fitness scoring (deterministic, `scoring.py`)
- Property evaluation scoring (deterministic, `property_scoring.py`)
- Hotspot identification (PostGIS hex grid + weighted ranking)
- Catchment insight generation (deterministic aggregation)
- All data collection, storage, and retrieval

### Provider Abstraction

The LLM integration uses a provider-agnostic abstraction (`app/llm.py`):

```
LLM_PROVIDER=anthropic|openai     # Provider
LLM_API_KEY=                       # API key (empty = LLM disabled)
LLM_MODEL=                         # Model override (uses provider default if empty)
LLM_BASE_URL=                      # Custom endpoint (uses provider default if empty)
```

**Default models**: `claude-sonnet-4-20250514` (Anthropic), `gpt-4o-mini` (OpenAI).

### Grounding Rules

Both LLM integration points enforce strict grounding:
- System prompt forbids inventing numbers or citing metrics not in the data
- Only pre-computed, structured data is sent to the LLM
- Temperature is set low (0.2–0.3) to minimize creative output
- Response validation rejects malformed or ungrounded responses

### Fallback Behavior

When `LLM_API_KEY` is not configured:
- Area fitness reports work fully without explanation (explanation field is null)
- Ask SiteScout returns the raw structured data with a "LLM not configured" prefix
- No features are degraded or unavailable

## Setup & Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ with pip
- Node.js 18+ with npm
- ~600MB disk space for the Geofabrik OSM extract (downloaded automatically)

### 1. Start the Database

```bash
docker compose up -d
```

This starts PostgreSQL 16 with PostGIS 3.4 on port 5432.

### 2. Configure Environment

```bash
cp .env.example backend/.env
```

Edit `backend/.env`:
- `DATABASE_URL` — default works with Docker setup
- `SAVOMART_API_TOKEN` — required for Savomart store data
- `LLM_API_KEY` — optional; leave empty for deterministic-only mode

### 3. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install numpy openai    # scoring and LLM dependencies (not in requirements.txt)
pip install pyosmium tqdm requests  # seed script dependencies

# Run migrations
alembic upgrade head
```

### 4. Seed Data

From the repository root (with the backend venv still active):

```bash
cd ..
python data/seed_all.py
```

This runs four seed steps in order:
1. **Users**: Creates 4 demo personas (fixed UUIDs, no passwords)
2. **Stores**: Fetches Savomart store locations from the API (requires `SAVOMART_API_TOKEN` in `backend/.env`)
3. **Pincodes**: Loads Chennai pincode boundaries from `data/chennai_pincodes.geojson`
4. **OSM**: Downloads the Geofabrik Southern Zone PBF (~558MB, cached in `data/`) and parses POIs and roads within the Chennai bounding box (79.95–80.35°E, 12.75–13.30°N)

Use `python data/seed_all.py --force` to rebuild OSM data from the PBF.

### 5. Start Backend

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6. Start Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The app is available at `http://localhost:5173`. The Vite dev server proxies `/api` requests to the backend at `http://localhost:8000`.

## API Overview

### M1 — Area Intelligence
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/pincodes/boundaries` | All pincode polygons |
| GET | `/api/pincodes/{code}` | Single pincode detail |
| GET | `/api/pincodes/{code}/fitness` | Generate fitness report |
| GET | `/api/pincodes/{code}/fitness/history` | Report history |
| GET | `/api/pincodes/{code}/fitness/{id}` | Saved report |
| POST | `/api/pincodes/{code}/fitness/{id}/explain` | LLM explanation |
| GET | `/api/pincodes/{code}/hotspots` | Top-5 hotspots |
| GET | `/api/stores` | Savomart store locations |

### M2 — Property Scouting
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/scouting-tasks` | Create scouting task |
| GET | `/api/scouting-tasks` | List tasks |
| GET | `/api/scouting-tasks/{id}` | Task detail |
| PATCH | `/api/scouting-tasks/{id}` | Update task status |
| POST | `/api/scouting-tasks/{id}/property` | Submit property |
| GET | `/api/properties/{id}/evaluation` | Get evaluation |
| POST | `/api/properties/{id}/evaluate` | Run evaluation |
| GET | `/api/properties/{id}/decision-pack` | Decision Pack HTML |

### M3 — Catchment Study
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/catchment-studies` | Request study |
| GET | `/api/catchment-studies` | List studies |
| GET | `/api/catchment-studies/{id}` | Study detail |
| POST | `/api/catchment-studies/{id}/assignments` | Create zone assignment |
| PATCH | `/api/catchment-studies/assignments/{id}/status` | Update assignment status |
| GET | `/api/catchment-studies/assignments/{id}/roads` | Roads in zone |
| GET | `/api/catchment-studies/assignments/{id}/surveys` | Surveys for assignment |
| POST | `/api/catchment-studies/assignments/{id}/surveys` | Submit lane survey |
| GET | `/api/catchment-studies/{id}/insight` | Catchment insight |

### Bonus
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/attention` | Role-specific attention items |
| POST | `/api/ask` | Ask SiteScout conversational query |

## Demo Roles & Usage

The app uses a **demo role switcher** in the header — not production authentication. Switching the dropdown changes the active persona and filters navigation, data, and actions accordingly.

| Role | User ID | Nav Links | Key Actions |
|------|---------|-----------|-------------|
| BD Manager | `0001` | Area Intelligence, Scouting Tasks, Catchment Studies | Analyze, assign, review, request studies, Ask SiteScout |
| BD Executive | `0002` | Scouting Tasks, Catchment Studies | Start tasks, submit properties |
| Survey Manager | `0003` | Catchment Studies | Create zones, assign surveyors |
| Survey Executive | `0004` | Catchment Studies | Submit lane surveys |

The role switcher is intentionally kept as a dropdown for demo purposes to make it easy for evaluators to test all 4 personas without login flows.

## Design Decisions & Product Thinking

### 1. One Continuous Workflow, Not Disconnected Modules

M1 → M2 → M3 mirrors how expansion actually works: you pick an area, then scout specific properties, then validate the surrounding catchment before signing a lease. Each module's output feeds the next — a fitness report produces hotspots, hotspots become scouting tasks, scouted properties get evaluated, and evaluated properties trigger catchment studies. This means a BD Manager can trace any property decision back to the area-level data that justified looking there in the first place. Building them as isolated tools would lose that chain of evidence.

### 2. Deterministic Scoring, AI Only for Explanation

Every score in the system — area fitness, property evaluation, hotspot ranking, catchment insight — is computed by deterministic algorithms with documented weights and normalization. The LLM is never in the scoring loop. It only explains results that already exist. This is deliberate: scores that change based on LLM mood are not auditable, not reproducible, and not trustworthy for real estate decisions. A BD Manager needs to compare two reports run a week apart and trust the numbers are consistent. The tradeoff is that the explanations can feel formulaic without an LLM configured, but the numbers are always reliable.

### 3. Pincode Boundaries + Hex-Grid Hotspots

Starting at the pincode level gives the BD team a familiar, administratively meaningful unit — they already think in pincodes. But a pincode is too large to scout on foot. The hex-grid hotspot layer subdivides each pincode into ~300m cells and ranks them by commercial activity, competitive gaps, and accessibility. This turns "600034 looks promising" into "walk to *this specific intersection*." The tradeoff is that hotspot quality depends entirely on OSM data density — sparse OSM coverage in a pincode produces unreliable hotspots. We document this rather than papering over it.

### 4. Progressive Property Validation

Properties go through multiple validation gates before reaching a decision:
- **Location containment**: the property must be within the assigned hotspot area
- **Duplicate detection**: `ST_DWithin` at 50m rejects properties too close to existing submissions, preventing the same location from being scouted twice
- **Missing-data handling**: if the BD Executive doesn't know the rent or carpet area, the system scores those dimensions at a neutral 50 and flags them as missing — it never fabricates values or silently drops dimensions
- **Evaluation after submission**: scoring runs only on submitted data, so the evaluation reflects what was actually observed

This layered approach catches problems early without blocking the workflow. A property with missing frontage data still gets evaluated — it just gets an honest score with explicit gaps noted.

### 5. Zone-Based Lane Surveys for Ground Truth

Catchment studies could have been automated — buffer the property, count OSM POIs, done. Instead, we built a structured field survey system where Survey Executives walk assigned zones and report what they see road by road: household types, shop counts, road conditions, foot traffic. This is slower but produces data that OSM doesn't have (household density estimates, foot traffic levels, road quality). The completion guard ensures every road in a zone is surveyed before the assignment can close, preventing partial data from being treated as complete. The tradeoff is operational overhead — this requires actual people walking actual streets — but that's the point. The catchment study answers "what's really there?" not "what does the map say?"

### 6. Attention Feed From Existing State, Not a Notification System

The Needs Attention banner queries the same tables the rest of the app uses. "3 tasks awaiting property submission" is just a count of `scouting_tasks WHERE status IN ('assigned','in_progress') AND property_id IS NULL`. No event bus, no notification queue, no read/unread tracking. This means it's always consistent with reality — if you complete a task, it disappears from the feed on next load without any event propagation. The tradeoff is no push notifications and no persistence of "when did I last see this?" But for a 4-persona demo with deterministic state, polling the DB is simpler and more reliable than building notification infrastructure.

### 7. Decision Pack as a Single Exportable Artifact

The Decision Pack combines property details, evaluation scores, scouting task context (which hotspot, which area report), and catchment insight into one server-rendered HTML page. The BD Manager can print it or save it as PDF using the browser's built-in functionality. This is the artifact that goes to the decision-maker — it should contain everything needed to say yes or no to a lease without opening the app. We chose server-rendered HTML over a PDF library (WeasyPrint, ReportLab) because it avoids heavy native dependencies, renders identically across platforms, and the browser's Print dialog handles pagination and PDF export for free.

### 8. Ask SiteScout: Constrained by Design

Ask SiteScout supports exactly 4 question types: compare areas, find areas by criteria, explain a property evaluation, and explain catchment status. Questions outside these types get a clear "I can help with these specific things" response, not a hallucinated answer. The classifier is regex-based — no vector DB, no embeddings, no RAG pipeline. Each supported question type maps to a specific SQL query that retrieves structured data, which is then sent to the LLM with strict grounding rules (temperature 0.2, system prompt forbidding invented numbers). When the LLM isn't configured, the raw data is returned directly. The tradeoff is obvious: you can't ask freeform questions. But a generic chatbot that confidently answers "what's the population of 600034?" with a hallucinated number is worse than one that says "I don't have population data."

### 9. Key Engineering Tradeoffs

**Raw SQL over ORM queries**: Spatial queries with PostGIS functions (`ST_HexagonGrid`, `ST_Intersects`, CTEs with window functions) are more readable and performant as raw SQL via `text()` than through SQLAlchemy's query builder. The ORM is used for model definitions and session management, not for query construction.

**Savomart API access is server-side only**: The API token for fetching store locations never reaches the frontend. Store data is seeded into the database and served through our own API. This prevents token exposure in browser dev tools or network inspection.

**Demo role switcher instead of auth**: A dropdown in the header switches between 4 fixed personas. No login flow, no JWT, no session management. Every API endpoint accepts `user_id` as a parameter. This is intentionally insecure — it lets evaluators test all 4 workflows in seconds without managing credentials. Production would need proper RBAC, but for a 48-hour hackathon demo, the friction cost of real auth outweighs the security benefit.

**Photo paths, not uploads**: Lane survey photos are stored as string references, not binary blobs. Wiring up multipart upload, object storage, signed URLs, and image display would consume time better spent on the core workflow. The data model is ready for it — the field exists and accepts values — but the upload pipeline is deferred.

**H3 for zones, PostGIS hex grid for hotspots**: Two different hex systems for two different purposes. Hotspot identification uses PostGIS-native `ST_HexagonGrid` because the scoring happens entirely in SQL. Zone creation uses the H3 library because the frontend needs to render selectable hex cells that the user clicks to assign, and h3-js provides that interactivity.

### 10. What We Deliberately Did Not Build

**Automated test suite**: No unit or integration tests. Every hour spent writing tests for a 48-hour hackathon is an hour not spent on features the evaluator will interact with. All verification was manual and end-to-end.

**Real authentication**: See above. Demo role switching is a conscious tradeoff, not an oversight.

**Multi-city support**: The Chennai bounding box, pincode ranges, and OSM extract are hardcoded. Parameterizing these is straightforward but adds configuration surface without demonstrating new capability.

**Real-time updates (WebSockets)**: Status changes require a page refresh. Push updates matter for a team of 20 using the tool simultaneously; they don't matter for a single evaluator walking through the demo.

**Mobile-optimized survey form**: Survey Executives would use this on phones in the field. We built a desktop-first responsive layout. A proper mobile experience with offline draft capability, GPS auto-fill, and camera integration is a production concern.

**Scoring calibration against real store performance**: The scoring weights (market opportunity 30%, commercial vitality 25%, etc.) are product heuristics, not regression coefficients. Calibrating them would require historical data on which Savomart locations succeeded or failed, which we don't have. We document them as assumptions.

**Catchment AI narrative**: The `ai_narrative` field exists on `catchment_insights` but is always null. The deterministic aggregation (household mix, shop distribution, road conditions) is more useful than an LLM summary of the same numbers. We left the field for future use rather than generating filler text.

## Known Limitations

- **Demo authentication only**: Role switching is client-side; no JWT/session auth. All API endpoints accept `user_id` as a parameter without verification.
- **Single-city scope**: Hardcoded to Chennai bounding box and pincode ranges. Multi-city would require parameterizing the bbox and pincode filters.
- **No real population data**: Residential Signal dimension uses OSM building tags as proxies, not census or population data.
- **ai_narrative always null**: The catchment insight `ai_narrative` field exists but is not populated. LLM is only used for fitness explanations and Ask SiteScout.
- **Photo upload not implemented**: Lane survey photo field accepts paths but file upload/storage is not wired.
- **No WebSocket/real-time updates**: Status changes require page refresh or re-fetch.
- **planet_osm_line dependency**: The M3 completion guard uses the `planet_osm_line` table (from osm2pgsql). If this table is not present, the road count query will fail for assignment completion. The app's own `osm_roads` table is used for the survey form's road list.
- **No pagination**: List endpoints return all matching records. Would need cursor-based pagination for production scale.
- **Scoring weights are product heuristics**: Not statistically calibrated against actual store performance. Documented as assumptions, not benchmarks.

### Production Improvements

- JWT authentication with role-based access control
- Object storage for survey photos with signed upload URLs
- Background job queue (Celery/ARQ) for long-running fitness calculations
- WebSocket notifications for status changes
- Multi-city/region support with configurable boundaries
- Scoring weight calibration against actual store performance data
- Mobile-optimized survey form with offline draft capability
- Rate limiting and input validation hardening

## Testing & Verification

Testing was performed manually throughout development:

- **End-to-end smoke test**: Full 7-step workflow across all 4 personas — area analysis → hotspot assignment → property submission → evaluation → catchment study → zone assignment → lane survey → study completion → insight generation
- **Role-based navigation**: Verified each persona sees only their permitted nav links and actions
- **M3 completion guard**: Verified that assignments cannot be marked complete with unsurveyed roads
- **Catchment insight**: Verified auto-generation on study completion; verified zero/empty metrics when no surveys exist
- **Default route redirect**: Verified each role redirects to their appropriate landing page
- **Decision Pack**: Verified HTML rendering with property, evaluation, scouting, and catchment data
- **Attention Feed**: Verified role-specific items for all 4 personas
- **Ask SiteScout**: Tested all 4 supported query types and 1 unsupported query; verified role guard (403 for non-BD-Manager)
- **Duplicate detection**: Verified property rejection within 50m radius

No automated test suite (unit/integration) was written. All verification was manual and API-level.

## AI Usage Disclosure

This project was developed with the assistance of **Claude Code** (Anthropic's AI coding assistant). See [`ai-sessions/README.md`](ai-sessions/README.md) for detailed AI usage documentation.

**AI in the product itself**:
- LLM integration is optional and clearly separated from deterministic scoring
- All scores, ranks, and aggregations are computed by deterministic algorithms
- When LLM is used, it only explains pre-computed data — it never calculates scores or invents metrics
- The system functions fully without any LLM API key configured

## Demo Video

https://www.loom.com/share/1d4253f5e80d40a88f08dd0746bcd620

---

**Built for Savomart Full Stack Hackathon 2026**
