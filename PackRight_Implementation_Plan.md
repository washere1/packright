# PackRight implementation plan

Status: planning only. No application implementation is authorized by this plan itself.

Source: `C:\Users\ishan\Downloads\PackRight_Software_Only_Build_Guide.md`.

The current deliverable is a concrete plan for building the software-only product. The guide defines the product requirements; its suggested team assignments, hour estimates, and optional features are planning inputs rather than instructions to execute immediately. The earlier hardware and software-first guides do not define this implementation.

## Product outcome and scope

A traveler uploads a GLB, enters weight and priority, reviews generated geometry and handling metadata, and saves the item. They combine custom items with clearly labeled stock templates, configure a suitcase, and receive a validated packing arrangement with exclusions and numbered instructions. Changes to suitcase dimensions, priorities, or baggage allowance produce a new plan.

The required release includes all 16 components in the guide. Gemini enrichment is supported with schema validation, caching, and an explicit neutral fallback. A missing API key must not prevent the core journey. Detailed meshes are preferred in the viewer, with labeled cuboids as a supported fallback. Accounts, scanning, hardware, airline certification, irregular contact physics, and cloud deployment are outside this release.

## Decisions to settle in the foundation

| Area | Planned decision |
|---|---|
| Frontend | React, TypeScript, Vite, Three.js; one typed API client and shared trip state. |
| Backend | Python, FastAPI, Pydantic, SQLite, Trimesh; custom deterministic selection and placement. |
| Execution | Local-only application; bind API to loopback, serve a production frontend from the same origin, and allow the exact development frontend origin. |
| Persistence | SQLite for records and versioned snapshots; local directories for original assets and derived previews. |
| Units | Millimeters and grams internally. GLB source coordinates are meters. Preserve display-unit preference separately. |
| Coordinates | X = width, Y = vertical height, Z = depth from wheel side toward opening. The interface labels these axes consistently. |
| Orientation | Six dimension permutations, each mapped to a proper rotation matrix with determinant +1. Store both the orientation identifier and its matrix. |
| Item clearance | Add `max(4 mm, 0.02 × dimension)` to each canonical box dimension, then rotate the padded box. Center the visible mesh inside that box. |
| Suitcase clearance | Follow the guide's subtraction convention: usable dimension = internal dimension minus the configured clearance. Inset the usable box by half that clearance on each side. UI describes clearance as the total reduction per axis. |
| Stack support | At least 80% bottom-face support for ordinary elevated items, 95% for base-class items. Floor contact gives full support. Never use top-only or non-load-bearing items as support. |
| Compression | Store the metadata, but do not shrink measured geometry automatically. Compression requires a future explicit geometry override. |
| Priorities | Utilities 1, 3, 7, 15, 31 for stars 1–5. Must-pack is a separate trip-level hard constraint. |
| Solver outcomes | Distinguish validated feasible plans, proven impossibility from simple bounds/weight checks, and search exhaustion. A heuristic failure is not proof that no arrangement exists. |
| Reproducibility | Persist input snapshots, geometry and handling versions, solver version, seed, runtime, and validator result. |

Canonical orientation may differ from the source model's visual upright direction. Previews and orientation controls must use the canonical box axes; the reviewer confirms any upright-only restriction against those labeled views. Do not derive orientation restrictions from dimension ordering alone.

## Step 0 — Foundation, schemas, and fixtures

**Purpose:** establish contracts before connecting components.

- Create `frontend/`, `backend/`, `config/`, `assets/stock/`, `assets/demo/`, `tests/`, and a runtime data directory excluded from source control.
- Define ItemDraft, Geometry, Handling, Item, Suitcase, Trip, TripItem, ItemInstance, Placement, ValidationResult, and PackingPlan schemas.
- Give every requested copy a stable instance ID so two shirts cannot be confused with one library record.
- Define item stages: draft, uploaded, processing, awaiting_review, ready, and failed. Store a recoverable error code and progress stage.
- Define plan states: queued, solving, validating, feasible, infeasible, and search_exhausted. Only independent validation can authorize feasible status.
- Set configurable limits: 50 MB upload, positive finite weights up to 100 kg, bounded dimensions, a 24-instance initial trip limit, processing timeout, model timeout, and a solver budget below three seconds including validation.
- Generate known-dimension GLBs, nested-transform fixtures, malformed assets, and a six-item deterministic demo trip. Keep generated demo geometry clearly distinguished from real scans.
- Add local launch scripts, environment example, dependency lockfiles, and API health/config endpoints that expose capability flags without secrets.

**Depends on:** nothing.

**Done when:** backend and frontend start locally, a typed health request succeeds, and schemas reject nonfinite values, invalid units, invalid stars, and duplicate instance IDs.

## Step 1 — Item creation form

**Build:** `NewItemPage`, `ModelUploader`, and `RequiredItemInputs`.

- Present only GLB file, weight with g/kg/oz/lb, and a one-to-five-star control as required inputs.
- Implement drag/drop and a file-picker fallback with accessible labels and keyboard interaction.
- Convert weight to grams at the client boundary and validate again on the server.
- Show upload progress separately from geometry and enrichment stages; progress must reflect actual events rather than a fabricated percentage.
- Save a draft before processing. Preserve weight, unit choice, and priority after a bad upload or network failure.
- Show duplicate warnings from the server without preventing intentional reuse.

**Depends on:** steps 0, 2, and 16 contracts; can initially use an API fixture.

**Done when:** a valid submission requires one file selection, one weight entry, and one priority selection; malformed input shows an actionable inline error with entered values retained.

## Step 2 — Asset ingestion

**Build:** `services/ingestion.py`, upload endpoints, and asset records.

- Stream uploads into a temporary file while enforcing the byte limit. Ignore user filenames for storage paths; use generated IDs and a fixed `model.glb` filename.
- Verify GLB magic, version, declared lengths, JSON structure, and binary chunks. Reject references to external files or URLs before parsing.
- Hash the original bytes for duplicate detection and downstream cache keys.
- Parse in an isolated worker with a hard timeout and resource limits. Reject empty scenes, nonfinite transforms, invalid indices, and unreasonable decoded geometry sizes.
- Apply all node transforms, including repeated mesh instances, before world-space bounds extraction. Avoid double-applying transforms.
- Save the original asset atomically, record the hash and processing stage, and remove incomplete temporary artifacts on failure.
- Return structured errors such as invalid_glb, too_large, empty_geometry, and processing_timeout without exposing exception internals.

**Depends on:** step 0 and persistence primitives from step 15.

**Done when:** five nested-transform fixtures yield correct world-space geometry or a clear bounded failure; external references and oversized files are rejected without creating ready items.

## Step 3 — Geometry extraction

**Build:** `services/geometry.py` and geometry-versioned records.

- Combine transformed scene geometry and convert meters to millimeters exactly once.
- Compute AABB, conservative OBB, canonical extents, geometric center, transform to canonical coordinates, and inverse transform.
- Calculate box volume, reliable watertight mesh volume when available, fill ratio, preview framing distance, and six proper orthogonal rotations.
- Preserve original detailed assets. Do not simplify geometry before computing bounds.
- Warn for disconnected components, non-watertight meshes, high polygon count, and suspicious scale. Use bounding volume when mesh volume is unreliable.
- Require explicit scale confirmation for implausible dimensions. Offer a uniform scale correction in review and regenerate affected geometry/previews when it changes.
- Handle degenerate or planar geometry with a clear review/error state rather than inventing nonzero thickness.
- Persist canonical transforms so rendering uses the exact same coordinate frame as packing.

**Depends on:** step 2.

**Done when:** a rotated 300 × 200 × 100 mm cuboid recovers those dimensions within tolerance, nested instances are included, and transformed mesh vertices remain inside the returned OBB.

## Step 4 — Multi-view rendering

**Build:** `three/ItemScene.tsx`, preview capture, and preview-storage endpoint.

- Load the GLB with GLTFLoader and apply the canonical transform from geometry extraction.
- Frame front, side, top, and three-quarter views with a neutral background, fixed lighting, and consistent margins.
- Generate PNG/WebP images and a thumbnail in the browser; upload them with the asset/geometry version they represent.
- Use a fallback material where needed, while preserving valid supplied textures.
- Dispose of GPU resources after capture and provide a bounded failure path when WebGL or the asset is unsupported.
- Cache previews by asset hash, geometry version, scale correction, and renderer version. Do not label cuboid fallback renders as actual scans.

**Depends on:** step 3 and preview persistence.

**Done when:** every demo item has four centered, nonblank views; a rendering failure leaves a usable review screen and switches enrichment to explicit fallback metadata.

## Step 5 — Model metadata enrichment

**Build:** `providers/gemini.py`, `services/enrichment.py`, prompt/schema config, and model-run records.

- Send the four views, canonical dimensions/axis labels, fill ratio, and optional filename to Gemini. Keep weight and priority as immutable context.
- Request schema-constrained name, category, fragility, compressibility, stack class, load-bearing flag, liquid risk, legal orientations, access, confidence, and one-sentence reasoning.
- Treat filenames and embedded asset text as data. The prompt forbids changing weight/priority and producing packing coordinates.
- Validate output enums and lengths, deduplicate orientations, intersect with geometry candidates, require a nonempty orientation set, and clamp finite confidence values to 0–1.
- Retry an invalid response once within the overall model time budget. Use the guide's neutral metadata for missing credentials, timeout, invalid output, or absent valid previews.
- Clearly record provider, model ID, prompt version, response, fallback reason, and per-field provenance.
- Cache on asset hash, geometry version, preview version, prompt version, and model ID. Include any context that materially influences inference; otherwise omit mutable weight/priority from the inference prompt to make reuse sound.
- Keep the API key on the server and explain that live enrichment sends previews to the configured provider.

**Depends on:** steps 3, 4, and 15.

**Done when:** ten varied or mocked responses either pass validation or produce the explicit fallback, with original weight and priority unchanged. Test live Gemini separately when credentials are available; do not claim mocked tests prove live integration.

## Step 6 — Item review and confirmation

**Build:** `MetadataReview`, interactive model preview, and confirm/update endpoints.

- Show name, dimensions, weight, stars, handling summary, and provenance on one card.
- Highlight only necessary questions: suspicious scale, liquid/container ambiguity, and uncertain handling.
- Put name/category, fragility, compression, stack class, load-bearing, legal orientations, access, and liquid risk in an edit drawer.
- Allow weight/priority edits, replacement upload, and draft deletion. Replacing geometry invalidates old previews and enrichment.
- Require acknowledged scale issues before saving. Validate consistent handling, such as top-only implying not load-bearing.
- Store the generated suggestion and user-confirmed version separately so corrections remain inspectable.

**Depends on:** steps 1–5.

**Done when:** an ordinary item can be saved without opening the drawer; an ambiguous item presents its confirmation; ready items contain all packing prerequisites.

## Step 7 — Reusable item library

**Build:** `LibraryPage`, item cards, filtering, selection, and custom item CRUD.

- Provide Custom and Stock tabs, name search, category filter, cards/list view, and multi-select.
- Display thumbnail, dimensions, weight, stars, handling, and readiness status.
- Seed 12 templates: laptop, laptop charger, phone charger, toiletry bag, shirt, shoes, jacket, medication pouch, book, headphones, water bottle, and camera.
- Label template dimensions and weights as examples. Let users accept defaults for the trip or clone a template into a custom editable record.
- Prevent incomplete drafts from entering the trip; provide a direct route back to review.
- Preserve existing saved plan snapshots when a library item is edited or deleted.

**Depends on:** steps 6 and 15.

**Done when:** six mixed items can be selected, searched, and carried into trip configuration; custom edits persist after refresh; stock cloning leaves the template intact.

## Step 8 — Trip builder

**Build:** `TripBuilderPage`, trip state, and trip-item endpoints.

- Show selected items, quantity, trip-specific priority, and must-pack toggles.
- Expand quantities to stable instance IDs on the server. Enforce the supported instance limit with a clear message.
- Show requested item weight and total utility, then suitcase configuration and available weight.
- Keep overrides separate from permanent item defaults. Preserve a draft trip across refreshes.
- Show missing-data warnings and individual oversize/overweight checks before solving.
- Snapshot item geometry/handling and suitcase settings when Pack is pressed; avoid a plan changing underneath an in-flight request.

**Depends on:** steps 7, 9, and 15.

**Done when:** quantities are honored, a priority change affects the constrained test case, and must-pack survives every selection and placement attempt.

## Step 9 — Suitcase editor

**Build:** `SuitcaseForm`, presets, and suitcase CRUD.

- Collect internal width/height/depth with cm/mm/in units, empty weight, and total baggage limit.
- Include an axis-labeled cuboid diagram, wheel-side label, and adjustable 0–15 mm clearance under advanced settings.
- Convert units at the boundary. Reject nonpositive or nonfinite dimensions and a total limit at or below empty weight.
- Display usable dimensions and available item weight using the agreed clearance convention.
- Save named presets and allow per-trip changes without modifying the preset implicitly.
- Warn when no allowed orientation of an item fits in the usable volume.

**Depends on:** step 0 schemas and step 15.

**Done when:** equivalent imperial/metric inputs yield equivalent canonical values; reducing a dimension changes feasibility or placement in the fixed scenario.

## Step 10 — Priority-aware selection

**Build:** `services/selection.py` and selection-specific tests.

- Expand validated trip instances; compute nonlinear utility and padded volumes.
- Reject a mandatory instance that is oversized in every legal orientation or prove impossible total mandatory weight immediately.
- Generate ranked candidate subsets using branch-and-bound for small sets and a bounded deterministic candidate beam near the instance limit.
- Respect weight, mandatory inclusion, individual geometric fit, and aggregate padded-volume necessary checks.
- Rank primarily by retained utility, then item count and deterministic tie-breaking. Feed multiple candidates to spatial placement rather than treating volume as proof of fit.
- Track exclusion evidence separately: individual oversize, weight tradeoff, and spatial search failure must not be conflated.
- Implement heaviest-first removal and lowest-star-first removal baselines. Subject comparison results to the same placement constraints and validator before comparing feasible outcomes.

**Depends on:** steps 8 and 9.

**Done when:** small cases match brute-force utility optima for the selection constraints, mandatory items are never dropped, and raising a priority changes the intended exclusion decision. Larger bounded searches report their heuristic nature.

## Step 11 — 3D placement engine

**Build:** `services/placement.py` with deterministic search diagnostics.

- Try several item orders based on mandatory status, support capacity, footprint, volume, mass, and priority.
- Seed usable-box origin as an extreme point; try permitted rotations at generated face/intersection points.
- Reject local candidates violating bounds, collisions, support thresholds, or load-bearing restrictions.
- Keep a bounded beam of promising partial layouts. Score low center of mass, wheel-side weight, access near the opening, limited fragmentation, and retained utility.
- Compute support from the union of coplanar contact rectangles, avoiding double-counting overlapping support areas.
- Do not place an item so it loads a top-only or non-load-bearing item. Prefer quick-access items late in packing and near the opening; expose access/balance as soft objectives.
- Retry alternate candidate subsets/orderings within one shared runtime budget. Return the best independently valid complete candidate, preserving mandatory items.
- If the budget expires without a valid mandatory arrangement, return search_exhausted unless a hard lower-bound check proves infeasibility.
- Build a support dependency graph and derive a bottom-up packing order; reject dependency cycles.

**Depends on:** steps 10 and 12 contracts.

**Done when:** 20 fixed scenarios finish within three seconds on the target laptop and yield either a validator-approved plan or a truthful failure status. Record measured runtime rather than assuming the target is met.

## Step 12 — Independent plan validator

**Build:** `services/validation.py`; independent of optimizer candidate-validity code.

- Reconstruct expected instances from the immutable trip snapshot, including quantities and mandatory flags.
- Check finite coordinates, unique IDs, correct item references, legal orientation, and placement dimensions recomputed from canonical geometry and clearance.
- Independently verify usable bounds and every pairwise intersection with a documented numeric tolerance.
- Recompute total item weight plus empty suitcase weight and mandatory inclusion.
- Recompute union-area support, support-provider eligibility, and stack restrictions for every elevated item.
- Verify the packing sequence respects support dependencies and references every packed instance exactly once.
- Recompute utilization, retained utility, center of mass, remaining allowance, and support ratios from accepted placements.
- Return typed violations with instance IDs and measured values; never trust optimizer-supplied metrics or success flags.

**Depends on:** step 0 schemas and geometry primitives. Implement early using hand-authored placements before the optimizer exists.

**Done when:** deliberate collision, overflow, illegal rotation, missing mandatory copy, duplicate ID, wrong dimensions, unsupported item, top-only loading, nonfinite coordinate, and overweight corruption each fail for the expected reason.

## Step 13 — Packing instructions and exclusions

**Build:** `services/explanation.py` and deterministic instruction templates.

- Generate one numbered instruction for each validated placement, ordered by support dependency then stable spatial ordering.
- Include the item name/copy, destination, canonical orientation label, and applicable handling note.
- Explain excluded items using recorded evidence. Say that the search could not find space when no proof of geometric impossibility exists.
- Show missing mandatory items prominently on unsuccessful results and suggest which constraint can be edited.
- Display balance as an approximate mass-at-box-center model, not a physical measurement.
- Keep instruction generation deterministic; model-written prose is optional and deferred.

**Depends on:** steps 11 and 12.

**Done when:** every instruction maps to one placement and no explanation asserts a cause absent from the solver/validator evidence.

## Step 14 — Interactive packing viewer and replan

**Build:** `PlanPage`, `PackingViewer`, `PackingStepper`, and `PlanMetrics`.

- Render a dominant translucent suitcase, packed items, selected-item label, and category legend.
- Render supplied meshes through canonical transform and placement rotation; use cuboids when loading/performance fails or the user disables meshes.
- Provide orbit, zoom, reset camera, step forward/back, show-all, x-ray/layer visibility, and current-item emphasis.
- Animate a single item when the step changes, with reduced-motion support. Treat insertion animation as illustrative, not a certified collision-free insertion trajectory.
- Show progressive approximate center of mass and the target marker using only currently visible packed steps.
- Present weight, utilization, priority retained, exclusions, and the real validator checklist.
- Add suitcase-dimension and baggage-limit quick edits with explicit Replan. Keep the previous result visible but marked outdated until the new validated result arrives.
- Ignore stale responses from earlier requests; retain user edits after errors.
- Put raw geometry, effective boxes, model provenance, solver attempts, validation details, and versioned demo reset in a separate engineering view.

**Depends on:** steps 4 and 11–13.

**Done when:** a new viewer can identify the first three items and destinations; changing one constraint visibly updates arrangement/exclusions; a failed replan never leaves the previous result labeled current.

## Step 15 — Persistence and offline recovery

**Build:** SQLite schema/migrations and repository layer.

- Store items, assets, geometry versions, handling versions, stock templates, suitcases, trips, trip instances, plans, placements, and model runs.
- Use transactions for ready-item confirmation and plan finalization. Do not hold database transactions open during rendering or model calls.
- Persist input snapshots and independent validation results so old plans remain reproducible after library changes.
- Store generated suggestions and user corrections separately with timestamps and provenance.
- Cache previews and enrichment with versioned keys; support the neutral fallback with no internet.
- On restart, detect interrupted processing jobs and expose retry rather than leaving perpetual loading states.
- Provide a demo seed/reset action scoped to explicitly marked demo records; preserve user-created items and trips.
- Document backup/restore of both SQLite and asset directories, plus migration behavior.

**Depends on:** step 0; build the minimal repository before steps 2 and 6, then extend as components land.

**Done when:** restarting reproduces a saved plan and its assets without a model call; editing the source item cannot alter the old snapshot; demo reset leaves personal data untouched.

## Step 16 — API integration and operational behavior

**Build:** FastAPI routers and generated/shared frontend types.

| Resource | Endpoints |
|---|---|
| Items | POST/GET `/api/items`; GET/PATCH/DELETE `/api/items/{id}`; POST asset, process, enrich, confirm actions under that item. |
| Preview assets | POST `/api/items/{id}/previews`; validated local asset reads with generated paths. |
| Suitcases | POST/GET `/api/suitcases`; GET/PATCH/DELETE `/api/suitcases/{id}`. |
| Trips | POST/GET `/api/trips`; GET/PATCH `/api/trips/{id}`; POST `/api/trips/{id}/items`. |
| Plans | POST `/api/plans`; GET `/api/plans/{id}`; POST validate and replan actions under that plan. |
| Operations | GET health/config; GET processing status; scoped demo seed/reset. |

- Validate every request/response, return stable error codes, and enforce body-size/resource limits server-side.
- Run expensive processing outside request-loop work; return stage/status for polling when work is asynchronous.
- Make confirmation and plan submission safe to retry with idempotency keys. Replan creates a new immutable plan linked to its predecessor.
- Handle missing/stale item versions and deleted assets explicitly.
- Publish OpenAPI docs and expose safe capability status: preview support, live enrichment configured, and solver limits.
- Add structured local logs with request IDs, timings, stage, and errors; omit API keys and raw uploaded contents.

**Depends on:** step 0 initially; integrates each service as it is completed.

**Done when:** an API integration test performs create → upload → process → previews → enrich/fallback → confirm → trip → plan → validate → replan → reload, including expected failure paths.

## Delivery order and gates

The component numbers above match the guide. Implementation follows dependency order rather than finishing each number in isolation.

| Phase | Work | Exit gate |
|---|---|---|
| A — contracts and runnable shell | Step 0; minimal steps 15/16; one browser and server GLB fixture. | Same asset loads on both sides and normalized bounds are visible. |
| B — trusted packing core | Step 12 first, then steps 10/11 using hard-coded inputs. | A six-item fixture generates a validated textual plan; corruption tests fail correctly. |
| C — upload to reusable item | Steps 1–4, 6/7 with neutral metadata; complete item persistence. | Upload, derive, preview, review, save, restart, and select work without live AI. |
| D — real trip planning | Steps 8/9 and full plans API/persistence. | Mixed custom/stock trip with quantities and mandatory items produces a stored validated plan. |
| E — enrichment and visual explanation | Steps 5, 13/14. | Generated or fallback review metadata plus interactive sequence and constraint replan work end to end. |
| F — verification and delivery | Failure recovery, baseline evaluation, usability, launcher, docs. | Acceptance matrix below passes; remaining limitations are recorded accurately. |

A 24-hour event schedule is a constraint to assess after the early gates, not a guarantee. Protect the validator, honest failure states, weight/priority inputs, and replan before spending time on optional visual effects.

## Verification plan

| Area | Evidence required |
|---|---|
| Ingestion/geometry | Five transformed GLBs, known rotated cuboid, repeated mesh instances, empty/corrupt/oversized assets, nonfinite transforms, external-reference rejection, suspicious-scale review. |
| Preview | Four saved nonblank images per demo asset; canonical-frame consistency; graceful WebGL/loader failure. |
| Enrichment | Ten valid/invalid/timeout cases; neutral fallback; immutable user inputs; schema enforcement; cache reuse and invalidation. Live provider smoke test only with configured credentials. |
| Selection | Small exhaustive oracle comparisons, priority reversal, multiple quantities, oversize detection, mandatory overweight, deterministic tie-breaking. |
| Placement | Twenty fixed scenarios covering floor-only layouts, stacks, fragile items, restricted rotations, tight clearance, tiny capacity, and time-budget exhaustion. |
| Validator | Independent corruption suite for every hard constraint and malicious/mismatched dimensions/IDs. |
| API/persistence | Complete journey, idempotent retries, stale version handling, restart during processing, snapshot reload, safe demo reset. |
| Frontend | Keyboard operation, form validation, preserved drafts, loading/error/retry states, mesh fallback, stepper, and stale replan-response handling. |
| Demo | Ten timed upload-to-replan rehearsals, at least nine successful; log each outcome and failure cause. |
| Performance | End-to-end solver plus validation under three seconds on the actual laptop for the fixed set; record maximum and median with hardware/runtime versions. |

Do not display invented acceptance rates, baseline improvements, or onboarding timings. Report measured comparisons, including ties or losses. The release can be functional without claiming global optimality or physical fit guarantees.

## Acceptance checklist mapped to the guide

- [ ] GLB upload with weight and stars — steps 1/2.
- [ ] Normalized dimensions and preview — steps 3/4.
- [ ] Valid semantic metadata or clear fallback — step 5.
- [ ] Review and persistent custom item — steps 6/15.
- [ ] Custom and stock browsing; six selected items — steps 7/8.
- [ ] Suitcase dimensions and baggage limit — step 9.
- [ ] Mandatory preservation and priority-aware candidate selection — step 10.
- [ ] 3D plan produced within measured runtime budget — step 11.
- [ ] Independent bounds/collision/orientation/support/weight validation — step 12.
- [ ] Evidence-based exclusions and numbered sequence — steps 13/14.
- [ ] Visible replan after a changed constraint — steps 14/16.
- [ ] Saved plan recovery without a fresh model call — step 15.
- [ ] At least nine successful rehearsals out of ten — verification phase.

## Expected handoff artifacts

- Working source tree with local setup/start scripts and locked dependencies.
- `.env.example` describing optional Gemini configuration and runtime limits.
- Seeded stock catalog, generated geometry fixtures, and a reproducible demo trip.
- API documentation and a README covering setup, offline behavior, coordinate conventions, limits, and troubleshooting.
- Automated test suite and measured acceptance/performance report.
- A short demo script covering upload, review, six-item selection, changed constraint, packing sequence, and validator inspection.

Current environment note: initial setup created a `.venv` before the request changed to planning only. Dependency installation did not complete because network access was restricted. No application code has been created. Resolve dependency installation when implementation is requested; it does not block this plan.
