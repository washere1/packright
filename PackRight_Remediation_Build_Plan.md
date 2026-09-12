# PackRight Remediation Build Plan

## Purpose and delivery bar

This plan turns the current local-first prototype into a judge-ready packing-planning demo. The primary outcome is an end-to-end trip flow that accepts selected items and suitcase constraints, creates an immutable validated packing plan, and renders that plan as a truthful interactive 3D scene. The application must never visually imply a physical guarantee that the solver does not prove.

Treat the existing implementation and the supplied build guides as reference material. This plan is authoritative for the remediation work.

### Release promise

> Upload or choose items, configure a real trip, create a conservative validated box-based packing plan, and inspect the resulting arrangement and packing sequence in 3D. The result is a planning aid, not certification of physical fit or an insertion-path proof.

### Out of scope

- Accounts, cloud synchronization, airline certification, hardware scanning, irregular-contact physics, arbitrary mesh collision packing, and a native mobile application.
- Replacing the deterministic solver with an opaque AI planner.
- Claiming that visual meshes are collision-certified; validation remains box-based.

## Non-negotiable product rules

1. A displayed plan must always be rendered against *its own immutable snapshot*, never the mutable current trip.
2. A plan is shown as `feasible` only when independent validation passes.
3. A failed or still-running replan never replaces, relabels, or geometrically distorts the prior plan.
4. Every mutation that might be retried has an idempotency key; the server rejects reuse of a key with a different request body.
5. Browser rendering failure falls back to labeled cuboids and continues the core journey.
6. A restart leaves every incomplete operation in a recoverable state with a real resume/retry action.
7. User-entered weight and priority are preserved as user data and never changed by enrichment.

## Workstream 0 — Baseline, data hygiene, and contracts

### Build

- Add a committed `docs/acceptance/` directory containing:
  - `acceptance-matrix.md`
  - `demo-script.md`
  - `rehearsals.csv`
  - `performance-report.md`
  - `known-limitations.md`
- Add a `POST /api/operations/demo/prepare` operation that creates a fixed, marked demo trip, a fixed suitcase, and a precomputed validated plan using stock fixtures and a recorded seed. It must be safe to run repeatedly.
- Keep `POST /api/operations/demo/reset`, but make it remove every record linked to the demo namespace through foreign keys or an explicit `demo_run_id`; never infer demo records from names.
- Add a visible local-only “Reset demo data” action behind an explicit confirmation, plus a documented command for cleaning local runtime data during development.
- Ensure startup never ships test drafts in the demo database. The default demo experience must contain either the curated demo state or an empty personal library.
- Add database migration files, a `schema_migrations` table, and forward-only migration execution. Do not rely only on `PRAGMA user_version`.
- Put all public API types in one generated or shared contract source. Frontend types must be generated from OpenAPI or checked against it in CI.

### Acceptance

- A fresh clone plus setup produces a clean library and the demo seed is deterministic.
- Reset removes only demo data, verified with a personal item, suitcase, trip, snapshot, and plan present.
- Migration tests cover an old database fixture and a fresh database.

## Workstream 1 — Make trip selection a durable, guided input flow

### User flow

1. In Library, users select one or more ready custom or stock items.
2. Selection persists in a server-side `TripDraft`; browser storage only remembers the draft ID.
3. “Configure trip” opens the trip builder with selected items already present.
4. Users set quantity, trip-only priority, must-pack, and optional access preference for every item.
5. Users select or create a suitcase, edit dimensions/clearance/weight limit, and see inline feasibility preflight.
6. “Create packing plan” saves a snapshot and starts a plan job.
7. On completion, the app opens a dedicated plan route with the immutable snapshot and plan.

### Frontend implementation

- Replace loose component-local selection with a `TripDraftProvider` backed by the API.
- Add explicit routes:
  - `/items/new`
  - `/library`
  - `/trips/new`
  - `/trips/:tripId/edit`
  - `/plans/:planId`
- On startup, restore the last active draft or plan by ID; fetch canonical server state rather than trusting cached values.
- Add a selection tray visible in Library with item count, total requested weight, and “Configure trip.”
- Preserve selection across Custom/Stock tabs, filters, layout changes, navigation, and refresh.
- When cloning stock, await success, update the Custom list, announce the result, and provide “Review cloned item.”
- Add ready-item actions: review/edit handling, remove from library, and archive/delete with confirmation. Do not expose deletion for stock records.
- Make all form validation inline and field-specific. Do not use `Number("")` as a valid zero value. Keep the previous valid draft while a field is temporarily empty.
- Keep all controls keyboard-operable with visible focus, labels, error associations, and announced async status.

### Backend/API implementation

- Add `GET /api/suitcases/{suitcase_id}`.
- Add `GET /api/trips`, `GET /api/trips/{id}`, and `GET /api/trips/{id}/plans`; return `404` for unknown trip IDs, not an empty history.
- Model trip editing as explicit draft updates:
  - `POST /api/trips` creates an empty or selected-item draft.
  - `PATCH /api/trips/{id}` updates name and suitcase.
  - `PUT /api/trips/{id}/items/{item_id}` sets quantity/priority/must-pack atomically.
  - `DELETE /api/trips/{id}/items/{item_id}` removes it.
- Return a `TripPreflight` with requested instances, requested weight, padded volume, baggage remaining, missing metadata, oversize instances, mandatory contradictions, and actionable messages. Preflight is advisory; plan validation remains authoritative.
- Give every selected copy a stable instance UUID generated on the server. Quantity changes must preserve existing instance IDs where possible and add/remove deterministically.

### Acceptance

- Select six mixed Custom/Stock items, configure quantities and must-pack settings, refresh at each page, and verify the exact draft persists.
- An invalid suitcase field identifies the field and blocks plan submission without erasing valid edits.
- A stock clone never mutates its source and appears in Custom immediately after creation.

## Workstream 2 — Correct plan lifecycle, snapshots, and replanning

### Data model

Introduce or formalize these relationships:

```
Trip (mutable draft)
  ├─ TripSnapshot (immutable input: suitcase, expanded instances, geometry/handling versions)
  │    └─ PackingPlan (immutable output, validation, instructions, diagnostics)
  └─ PackingPlanJob (operation state; may create a snapshot and plan)

PackingPlan.predecessor_plan_id -> PackingPlan.id (nullable)
```

The snapshot must include the entire suitcase, all expanded instances, effective padded dimensions, geometry version, handling-confirmation version, solver version, seed, and timestamps needed to reproduce validation.

### Plan creation

- Change plan creation to an asynchronous persisted job:
  - `POST /api/trips/{id}/plan-jobs` returns `202`, `{ job_id, snapshot_id }`.
  - `GET /api/plan-jobs/{id}` returns `queued | running | completed | failed | retryable`, progress stage, plan ID if complete, and typed failure information.
  - Solver work runs off the request loop.
- Make plan submission idempotent. Store operation name, idempotency key, canonical request-body hash, status, and result ID in one transaction. Reusing a key with a different payload returns `409 idempotency_conflict`.
- Use the same plan job path for normal packing and replan.

### Replan semantics

- `POST /api/plans/{plan_id}/replan-jobs` accepts an optional replacement suitcase/name and always creates a *new trip snapshot* and a new plan linked by `predecessor_plan_id`.
- Do not mutate the prior plan or its snapshot. Updating the mutable trip is allowed only after the new snapshot is stored, and must not affect the old-plan route.
- In the UI, keep the old plan mounted with an “Outdated — replanning with new constraints” banner while the job runs.
- On successful replan, navigate to the new plan or provide a clear Baseline/Latest switcher.
- On infeasible/search-exhausted/error, keep the prior plan selected and show the new attempt as a separate failed result with typed evidence. Do not present it as current validated packing.
- Ignore stale responses using job ID plus request generation; cancel display only, never delete a server job solely because the user navigates away.

### Acceptance

- Create a feasible plan, reduce suitcase width until failure, then confirm the original plan remains rendered using its original dimensions and is clearly historical.
- Trigger two replans rapidly; only the latest job can change the current UI selection.
- Reload any saved plan URL and obtain the identical snapshot, placements, diagnostics, instructions, and validation result without re-running enrichment.

## Workstream 3 — Build a truthful interactive 3D packing viewer

### Required architecture

- Replace the CSS-based viewer with a Three.js scene, isolated as `frontend/src/viewer/`.
- Use `@react-three/fiber` and `@react-three/drei`, or a plain Three.js scene wrapper if the project deliberately avoids React bindings. Do not simulate camera controls through CSS transforms.
- Use a single coordinate mapping throughout:
  - backend X = viewer X (width)
  - backend Y = viewer Y (vertical)
  - backend Z = viewer Z (wheel side toward opening)
- Render the suitcase from the plan snapshot’s usable dimensions. Display clearance inset and a labeled wheel/opening orientation.
- Render a supplied item GLB when it is available, loaded, and within a configurable device-performance budget.
- Render a colored, labeled padded cuboid when a GLB is unavailable, fails to load, is too large, or the user switches to fast mode.
- GLB display transforms must map canonical item axes to the selected legal orientation and placement position. Visual mesh extent may differ from padded collision box; show that padded clearance is what the validator uses.

### Viewer interactions and content

- OrbitControls: orbit, zoom, pan disabled unless specifically needed, reset camera, and keyboard-accessible equivalents.
- Ordered stepper with numeric steps, Back, Next, Show all, and visible current-step highlight.
- One controlled insertion animation when advancing one step; `prefers-reduced-motion` disables it.
- Toggle: `Detailed meshes` / `Validated cuboids`; switch automatically to cuboids after performance threshold failure and explain why.
- Toggle layers: packed items, transparent suitcase shell, clearance envelope, X-ray, center of mass, and wheel/opening labels.
- Item click/focus panel: name, copy number, priority, weight, destination, orientation, handling notes, support relationship, and whether it is mandatory.
- Category legend must derive each item’s color from one shared `instanceId -> color` mapping.
- Compute progressive center of mass from only placements visible at the current step. Show final COM separately when all items are visible.
- Render a target/acceptable COM region and explain that it is a heuristic target, not a stability guarantee.
- Include a compact validation checklist with bounds, collision, orientation, support, sequence, mandatory inclusion, and weight. Link to typed violations when invalid.
- Engineering drawer must show the snapshot ID, geometry versions, effective padded boxes, solver version/seed/runtime, model provenance, and plan state.

### Performance and resilience

- Lazy-load viewer and GLB decoding so the trip form is not bundled with preview/3D code.
- Split the current preview-rendering chunk; set and test a performance budget.
- Dispose textures, geometries, object URLs, and GLTF resources on unmount/change.
- Use error boundaries around model loading. A single bad mesh cannot blank the full plan.
- Add a scene-level fallback that is itself useful: dimensioned cuboids, labels, and instructions remain usable without WebGL.

### Acceptance

- In a plan with at least three placed items, a new user can identify each first-three item, its destination, and its order without a verbal explanation.
- Inspect a non-zero-Z placement from orbiting camera angles and verify depth is visually distinguishable.
- Toggle detailed meshes, force a load failure, and verify labeled cuboids remain accurate and usable.
- Step through a plan and confirm COM moves as placements become visible.
- Screenshot-test the feasible plan, a failed plan, and fallback mode.

## Workstream 4 — Processing, enrichment, and offline recovery

### Persisted operations

- Replace the current state-only retry record with a `ProcessingJob` that stores item ID, operation type, requested scale correction, renderer version, required previews, retry count, stage, typed failure, and stable input references.
- Split processing into resumable operations: ingest, geometry, preview capture/upload, enrichment, and confirmation readiness.
- The backend owns geometry and enrichment; browser preview capture remains browser-owned but has a clear `needs_browser_preview` state instead of pretending it can retry server-side.
- After restart, mark interrupted server-owned jobs `retryable`; resume only when the caller explicitly retries.
- Provide an item-level recovery UI listing interrupted jobs and exact next actions: “Retry geometry,” “Open browser to recreate previews,” or “Use cuboid fallback and review metadata.”

### Enrichment

- Keep neutral fallback and cache results by asset digest, geometry version, prompt version, provider/model, and preview-content hash.
- Record provider status and parse failures without raw credentials, prompts, uploads, or exception text in user-visible responses.
- Keep user weight and priority outside model-controlled fields. Explain this in review UI.
- Do not claim live enrichment is active unless `/api/config` confirms it.

### Acceptance

- Kill the API during geometry and during solver work, restart it, and verify each operation is visible and recoverable.
- Disable WebGL and complete item confirmation using cuboid fallback.
- Disable provider/network access and complete trip planning with cached or neutral handling.

## Workstream 5 — Library and review quality

### Build

- Add lifecycle states and filters: Drafts needing attention, Ready custom items, Archived/deleted items, and Stock examples.
- Do not show raw unnamed test drafts in the normal ready-item grid. Require a name before ready confirmation or label drafts as recoverable work in a separate area.
- Add rename/edit/archive actions to custom cards. Handle delete errors visibly.
- Preserve filters and selection in URL query parameters where useful.
- In review, display canonical previews with axis labels and current geometry version. If preview regeneration fails, show a persistent explicit dimension-fallback notice.
- Make normal review one confirmation action; show focused questions only for low-confidence/suspicious cases.

### Acceptance

- Ready custom records can be edited, archived, and restored without affecting historical plan snapshots.
- An intentionally failed preview render creates a clear fallback notice, not a silent image loss.

## Workstream 6 — Solver and validation hardening

### Build

- Preserve the existing deterministic selection/placement/independent-validator design.
- Ensure every output state distinguishes:
  - `feasible`: validator passed.
  - `infeasible`: a hard contradiction was proven.
  - `search_exhausted`: bounded search did not find a valid arrangement; not proof of impossibility.
  - `failed`: operation/system failure.
- Persist placement diagnostics with exclusion evidence per instance.
- Validate copies/instances, not library item IDs, at every boundary.
- Make support-provider logic and support ratio visible in engineering details.
- Test deterministic solver output for fixed snapshot/seed, allowing documented stable tie-breaking only.

### Corruption suite

Add direct validator tests that mutate a persisted valid plan to independently prove rejection of:

- bounds overflow;
- collision;
- illegal orientation;
- wrong effective dimensions;
- missing mandatory instance;
- duplicate instance;
- duplicate packing order;
- non-finite coordinate;
- overweight total;
- insufficient support;
- ineligible/top-only support;
- support dependency out of packing order.

### Acceptance

- Twenty representative cases run under the documented three-second plan-time budget on the target demo laptop.
- Every corruption returns typed violation codes without trusting solver-provided metrics.

## Workstream 7 — API, observability, and security boundaries

### Build

- Complete OpenAPI contracts for item, suitcase, trip, snapshot, plan, plan job, processing job, demo, and error responses.
- Add request ID middleware and structured logs for request ID, route, operation, status, elapsed time, and typed error code. Never log raw model bytes, preview bytes, API keys, or full provider output.
- Enforce request-size limits for streamed/chunked bodies, not only `Content-Length`.
- Verify file and preview paths remain under their configured runtime roots.
- Return stable public error codes/messages. Replace inaccurate `draft_not_found` errors for ready items with `item_not_found`.
- Add route-level tests for `404`, `409`, idempotency conflict/replay, stale geometry, and body limits.

### Acceptance

- OpenAPI includes `GET /api/suitcases/{id}` and all job endpoints.
- Retrying a request with the same key/body returns the original result; reusing the key for a different body returns `409`.

## Workstream 8 — Verification, accessibility, and demo readiness

### Automated tests

- Backend: unit tests for ingestion, geometry, snapshot creation, jobs/recovery, solver, validator corruption, idempotency, and demo reset.
- API integration: one complete custom-item journey and one mixed stock/custom trip, each ending with reload and replan. Include expected failure paths.
- Frontend component tests: trip selection, field errors, draft persistence, replan stale protection, viewer stepper, fallback, and plan-route reload.
- End-to-end browser tests: keyboard-only journey, upload failure/retry, fallback mode, replan failure, demo reset, and browser refresh at every major state.
- Visual regression: library states, trip editor, feasible plan, failed replan, cuboid fallback, and mobile-width layout if mobile is supported.

### Manual acceptance rehearsals

Run ten timed, clean-runtime rehearsals of:

1. prepare/reset demo;
2. upload one provided GLB and enter weight/priority;
3. process/review it or use controlled fallback;
4. combine it with stock items;
5. configure suitcase and trip overrides;
6. create a plan;
7. inspect the first three 3D steps;
8. change a constraint and replan;
9. reload the plan route.

Log environment, runtime, result, any failure cause, and recovery. Require at least nine successful rehearsals. Do not invent timings, accuracy, or improvement claims.

### Documentation

- Rewrite README around the real end-to-end journey.
- Include setup, local-only data location, demo preparation/reset, coordinate system, units, API docs, backup/restore, recovery behavior, limits, fallback behavior, and known non-guarantees.
- Add a two-minute demo script and a one-page judge-facing architecture/limitations sheet.

## Recommended execution order

1. Workstream 0: data hygiene, migrations, and contracts.
2. Workstream 1: durable trip drafts and input flow.
3. Workstream 2: snapshots, jobs, and correct replan semantics.
4. Workstream 3: true 3D viewer against immutable snapshot data.
5. Workstream 4: processing recovery and fallback UX.
6. Workstreams 5–7: library polish, validation/API hardening.
7. Workstream 8: end-to-end tests, rehearsals, documentation, and demo preparation.

Do not start viewer polish before Workstreams 1 and 2: the scene must have a correct immutable plan/snapshot contract first.

## Definition of done

The remediation is complete only when all of the following are true:

- A fresh user can select items, configure a suitcase, and create a plan without losing input state.
- The plan is independently valid and is shown as an actual orbitable 3D arrangement or a clearly labeled cuboid fallback.
- The 3D scene uses the plan’s immutable snapshot, including during failed and concurrent replans.
- Reloading a plan URL reproduces the saved plan without rerunning model processing or enrichment.
- Interrupted work has a usable, genuine recovery path.
- API contracts, tests, demo reset, rehearsal evidence, and documentation are present.
- The product makes no stronger physical-fit, AI, performance, or acceptance claims than the recorded evidence supports.
