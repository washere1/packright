# PackRight acceptance matrix

This matrix records the remediation acceptance targets. A check is only marked complete when the corresponding automated test or rehearsal evidence exists.

| Area | Acceptance evidence |
| --- | --- |
| Data hygiene | Migration, deterministic demo prepare, and namespace-only reset tests |
| Trip flow | Draft persistence, PUT/DELETE item updates, preflight, refresh/reload checks |
| Plans | Immutable snapshot, persisted async job, replay/conflict idempotency, replan predecessor |
| Viewer | Three.js scene or labeled cuboid fallback, stepper, COM, typed checklist |
| Recovery | Restarted processing and plan jobs expose retryable actions |
| Validation | Corruption suite returns typed independent validator violations |
| API/security | OpenAPI job routes, request IDs, body/path limits, stable errors |
| Demo readiness | Ten clean-runtime rehearsal rows with actual timings and outcomes |
