# PackRight architecture and limitations

PackRight is a local-first React/FastAPI application. The browser owns selection,
keyboard interaction, preview capture, and the Three.js presentation. The API owns
canonical GLB ingestion, geometry, enrichment, trip drafts, immutable snapshots,
persisted plan jobs, deterministic selection/placement, and independent validation.
SQLite stores the mutable library/trip state and immutable snapshot/plan history;
local files store original assets and previews under a checked runtime root.

The solver is deterministic and bounded. It packs padded axis-aligned boxes in a
single X/Y/Z convention, records support dependencies and typed exclusion evidence,
then must pass a separate validator before reporting `feasible`. `search_exhausted`
means the bounded search did not find a layout, not that physical packing is
impossible.

Detailed GLBs are visual context and are normalized to the saved placement for
inspection. The validator never trusts a mesh collision result and uses the
immutable snapshot’s effective padded boxes. If WebGL or mesh loading fails, the
scene remains usable with dimensioned labeled cuboids. The center-of-mass marker is
a mass-at-box-center heuristic and not a stability guarantee. The product does not
certify airline compliance, insertion paths, arbitrary mesh contact, or physical fit.
