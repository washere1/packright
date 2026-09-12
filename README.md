# PackRight

PackRight is a local-first packing planner. Steps 0–5 establish typed contracts,
durable GLB ingestion, canonical geometry extraction, browser-rendered previews,
and schema-validated metadata enrichment with a conservative offline fallback.

## Requirements

- Python 3.12
- Node.js 20 or newer (tested with Node 24)
- PowerShell 7 on Windows

## Setup and run

```powershell
.\scripts\setup.ps1
```

For development, run these in separate terminals:

```powershell
.\scripts\start-backend.ps1
.\scripts\start-frontend.ps1
```

Open `http://127.0.0.1:5173`. The development server proxies `/api` to the
loopback-only backend. For a same-origin production-style run:

```powershell
.\scripts\start.ps1
```

Then open `http://127.0.0.1:8000`. OpenAPI documentation is available at
`http://127.0.0.1:8000/docs`.

## Step 1 item flow

The Add item page requires exactly one GLB, a positive weight in g/kg/oz/lb, and
a one-to-five-star priority. It saves the draft before sending the model, reports
actual browser upload events separately from later geometry and enrichment work,
and retains the selected file and entered values after errors. Content-identical
uploads receive a non-blocking reuse warning. Selecting a rating fills every star
through that value.

## Step 2 ingestion

Drafts and asset records persist in `runtime-data/packright.sqlite3`. Uploads stream
to generated temporary paths with a 50 MB hard limit, receive a SHA-256 digest, and
pass GLB header/chunk/accessor/reference checks before entering an isolated Trimesh
worker. The worker has a hard timeout, a 2048 MB process-memory limit, and decoded
geometry limits. It applies every scene-node transform and reports world-space
bounds, including repeated mesh instances.

Accepted originals are atomically moved to
`runtime-data/assets/<generated asset UUID>/model.glb`; user filenames never become
storage paths. Failed temporary files are removed, while the item and asset records
retain stable recoverable error codes. `/api/items/{id}/status` and
`/api/items/{id}/asset` expose processing state and safe asset metadata.

## Steps 3–5 processing

`POST /api/items/{id}/process` combines world-space mesh instances, calculates a
versioned conservative OBB and canonical transforms, and converts meters to
millimeters once. Scale corrections create a new geometry version. Six proper
rotations, reliable volume/fill values, preview framing, and review warnings are
stored with the geometry.

The browser loads the original GLB, applies that persisted transform, and captures
front, side, top, and three-quarter views. The API verifies that uploaded PNG/WebP
previews are bounded and nonblank, creates a thumbnail, and caches all views against
the geometry and renderer versions. A WebGL failure leaves a clearly labeled
dimension-box fallback and continues with neutral metadata.

When `GEMINI_API_KEY` is configured, the server sends the four generated previews,
canonical dimensions, fill ratio, and optional filename to Gemini. Weight and star
priority are neither sent nor changed. Responses are schema-validated, normalized,
retried once when invalid, recorded, and cached. Missing credentials, previews,
timeouts, provider errors, or invalid output use explicit conservative metadata.

## Steps 6–8 review, library, and trips

The review screen keeps the generated suggestion and each user-confirmed handling
version separately. Normal items can be saved directly; only suspicious scale,
liquid/container ambiguity, or low-confidence handling creates a focused question.
The advanced drawer exposes every handling field. Replacement uploads invalidate
the current derived state, and uniform scale corrections regenerate geometry and
previews before confirmation.

The reusable library separates Custom items from 12 clearly labeled Stock examples.
It supports search, category filtering, card/list layouts, multi-select, review links
for incomplete drafts, and cloning without modifying the stock source.

Trip drafts persist in SQLite and are resumed from the browser's saved active-trip
ID. Quantities expand to stable server-generated instance IDs. Priority and must-pack
are trip-only overrides. The builder reports requested weight, nonlinear utility,
available baggage weight, missing data, oversize items, and overweight requests.
Pressing **Pack these items** records an immutable input snapshot and queues a persisted plan job. The browser polls the job by ID, so refresh or navigation does not erase the operation; a completed plan URL reloads from its own snapshot.

## Steps 9–11 suitcase and packing

The suitcase editor supports mm/cm/in dimensions, g/kg/oz/lb weights, named local
presets, an axis- and wheel-labeled diagram, and 0–15 mm total-per-axis clearance.
All values are normalized to millimeters and grams at the API boundary. Per-trip
changes use a copy and never silently modify the selected preset.

Packing expands stable trip instances and applies `max(4 mm, 2% of dimension)` item
padding before rotation. For up to 16 eligible instances, selection is exact under
the weight and padded-volume necessary constraints; larger trips use a deterministic
bounded beam and are labeled heuristic. Utility is 1/3/7/15/31 for priorities 1–5.
Mandatory oversize, mandatory overweight, and impossible mandatory aggregate volume
are proven early. Baseline selectors pass through the same placement and validation
pipeline before their diagnostic results are recorded.

The deterministic 3D placement beam tests legal rotations at generated extreme and
face-intersection points. It enforces bounds, collisions, 80% ordinary or 95% base
support, and support-provider eligibility. Its soft score favors a low approximate
center of mass, wheel-side mass, quick access near the opening, and less fragmentation.
Every successful plan passes an independent validation boundary before receiving
`feasible`; otherwise the API reports a proven `infeasible` or honest
`search_exhausted` state. Solver version, seed, measured runtime, diagnostics,
snapshot, placements, exclusions, and validator result are persisted.

## Steps 12–14 validation, instructions, and viewer

The independent validator reconstructs padded dimensions and legal rotations from
the immutable snapshot, then checks finite coordinates, bounds, pairwise collision,
support union/provider eligibility, stack order, mandatory inclusion, weight, and
all derived metrics. It returns typed violations and never trusts optimizer metrics.

Validated plans include deterministic numbered instructions with copy labels,
destinations, orientation names, and handling notes. Exclusions use only recorded
solver evidence; unsuccessful plans call out missing mandatory items and suggest
which suitcase constraint to edit. Instructions are also available at
`GET /api/plans/{id}/instructions`.

The plan viewer is a lazy-loaded Three.js scene with OrbitControls and a scene-level
fallback. It provides a translucent suitcase, shared instance colors, labeled
validated cuboids, optional GLB context, step back/forward, show-all, x-ray, reset
camera, depth-aware orbiting, an approximate center-of-mass marker, typed validation
details, and an engineering drawer. Quick edits create a new replan job against a
new snapshot; the prior plan stays mounted and marked outdated while the job runs.

## Steps 15–16 persistence and API operations

SQLite initialization uses a forward-only `schema_migrations` table (currently
version 3; `PRAGMA user_version` is only a compatibility marker) and stores
immutable trip snapshots/plans, versioned geometry/previews, model runs,
idempotency responses with request hashes, processing/plan-job recovery state, and
explicitly marked demo records. Startup converts interrupted server-owned jobs to
`retryable`; status is available at `/api/processing/status` and each plan job has a
real retry endpoint. `POST /api/operations/demo/prepare` is deterministic and
safe to repeat; `POST /api/operations/demo/reset` touches only explicitly marked
demo records, so reset does not touch personal trips or items.

Plan creation is available at `/api/trips/{id}/plan-jobs` and the legacy synchronous
compatibility route. `GET /api/plan-jobs/{id}` exposes queued/running/completed/
failed/retryable state, and `POST /api/plans/{id}/replan-jobs` always creates a new
immutable snapshot linked to its predecessor. `POST /api/plans/{id}/validate`
reruns the independent validator. Confirmation and plan writes accept
`X-Idempotency-Key`; a replay with the same canonical body returns the original
result and a different body returns `409 idempotency_conflict`. Request
IDs are echoed in `X-Request-ID` and structured logs include method, stage,
status, and timing without uploaded contents or credentials. Heavy geometry,
enrichment, and solver work is offloaded from the async request loop.

Back up both the database and local assets together. For example:

```powershell
Copy-Item runtime-data/packright.sqlite3 backups/packright.sqlite3
Copy-Item runtime-data/assets backups/assets -Recurse
Copy-Item runtime-data/previews backups/previews -Recurse
```

Restore by stopping the API, replacing those exact paths, and restarting; schema
initialization applies additive migrations without changing immutable snapshots.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend test
npm --prefix frontend run build
```

The frontend build uses Vite's runner config loader for Windows/OneDrive
compatibility. The build output keeps the viewer and GLTF decoder in lazy chunks;
the trip form does not pay that preview cost until a plan is opened.

## Recovery and local data

The local database and generated files live under `runtime-data/`. An interrupted
geometry or plan operation is shown as retryable after restart. Geometry recovery
can be retried server-side; browser-owned preview capture must be reopened in a
browser, and a plan can always be inspected with validated cuboids. The browser
stores only the active trip ID and canonical state is fetched from the API.

For a clean demo rehearsal, run:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/operations/demo/prepare
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/operations/demo/reset
```

For a complete local reset during development, stop the API and run
`.\scripts\clean-runtime.ps1`. It verifies that only the workspace runtime
directory is removed. This is intentionally a development command, not an
application action.

## Contracts and conventions

- Internal length is millimeters and weight is grams. GLB coordinates are meters.
- X is width, Y is vertical height, and Z runs from the wheel side toward the opening.
- Suitcase clearance is the total reduction per axis; the usable box is inset by
  half the clearance on each side.
- Item clearance will add `max(4 mm, 2% of the dimension)` to each canonical box
  dimension before rotation.
- Trip copies receive distinct stable UUIDs. A library record is never used as a
  placement identity.
- A solver may return `search_exhausted`; heuristic failure is not presented as
  proof of infeasibility.
- A plan can be `feasible` only when it contains an independently valid validation result.
- Compression is metadata only and does not alter measured geometry.

Configured bounds live in [`config/limits.json`](config/limits.json). Public
capabilities and limits are exposed at `/api/config`; credentials are never
returned. Gemini is optional, and a missing key leaves neutral enrichment fallback
available.

## Data and fixtures

`runtime-data/` is created on API startup and intentionally excluded from version
control. It contains local mutable assets, previews, and temporary processing data.

All content under `assets/demo/` is explicitly generated demo data, not a real scan.
Regenerate known-dimension, nested-transform, repeated-instance, and malformed GLBs
with:

```powershell
.\.venv\Scripts\python.exe scripts\generate_fixtures.py
```

`assets/stock/` is reserved for later clearly labeled example templates.

The five user-supplied reference scans and their weights remain in `assets/demo/`.
`scan-weights.json` mirrors `Scan Weights.xlsx` for deterministic automated tests;
it does not seed production records.
