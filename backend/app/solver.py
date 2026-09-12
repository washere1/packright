from __future__ import annotations

from time import monotonic
from uuid import UUID

from .placement import PlacementDiagnostics, place_subset, to_placements
from .explanation import attach_explanation
from .repository import Repository
from .schemas import BaselineDiagnostic, ExclusionEvidence, PackingPlan, PlanState, SolverDiagnostics, TripSnapshot
from .selection import SelectionError, select_candidates
from .validation import validate_plan

SOLVER_VERSION = "packright-solver-v1"


def solve_snapshot(snapshot: TripSnapshot, repository: Repository, budget_seconds: float, predecessor_plan_id: UUID | None = None, seed: int = 7) -> PackingPlan:
    started = monotonic(); deadline = started + budget_seconds
    placement_diagnostics = PlacementDiagnostics(); validator_rejections = 0
    try:
        selection = select_candidates(snapshot, deadline)
    except SelectionError as error:
        plan = PackingPlan(
            trip_id=snapshot.trip_id, state=PlanState.INFEASIBLE, solver_version=SOLVER_VERSION,
            seed=seed, runtime_ms=(monotonic() - started) * 1000, input_snapshot_version=snapshot.version,
            snapshot_id=snapshot.id, predecessor_plan_id=predecessor_plan_id,
            diagnostics=SolverDiagnostics(selection_mode="exact", heuristic=False, candidate_subsets=0,
                placement_attempts=0, complete_layouts=0, validator_rejections=0, budget_seconds=budget_seconds),
            exclusion_evidence=tuple(ExclusionEvidence(instance_id=instance.id, code=error.code,
                detail=error.message) for entry in snapshot.trip.items for instance in entry.instances if instance.must_pack),
        )
        repository.save_plan(plan); return plan
    usable = tuple(value - snapshot.trip.suitcase.clearance_mm for value in (
        snapshot.trip.suitcase.internal_dimensions_mm.width,
        snapshot.trip.suitcase.internal_dimensions_mm.height,
        snapshot.trip.suitcase.internal_dimensions_mm.depth,
    ))
    failed_members = set(); chosen = None; chosen_placements = (); chosen_validation = None
    for subset in selection.candidates:
        if monotonic() >= deadline: break
        layout = place_subset(subset, usable, deadline, placement_diagnostics)
        if layout is None:
            failed_members.update(item.instance_id for item in subset); continue
        placements = to_placements(layout)
        provisional = PackingPlan(
            trip_id=snapshot.trip_id, state=PlanState.VALIDATING, placements=placements,
            excluded_instance_ids=tuple(item.instance_id for item in selection.all_instances if item.instance_id not in {p.instance_id for p in placements}),
            solver_version=SOLVER_VERSION, seed=seed, runtime_ms=0, input_snapshot_version=snapshot.version,
            snapshot_id=snapshot.id, predecessor_plan_id=predecessor_plan_id,
        )
        validation = validate_plan(provisional, snapshot)
        if validation.valid:
            chosen, chosen_placements, chosen_validation = subset, placements, validation; break
        validator_rejections += 1; failed_members.update(item.instance_id for item in subset)
    baseline_results = []
    chosen_ids_for_baseline = {item.instance_id for item in chosen} if chosen else set()
    for name, baseline in selection.baselines:
        if monotonic() >= deadline:
            baseline_results.append(BaselineDiagnostic(name=name, state="budget_exhausted")); continue
        if {item.instance_id for item in baseline} == chosen_ids_for_baseline and chosen_validation and chosen_validation.valid:
            baseline_results.append(BaselineDiagnostic(name=name, state="feasible", retained_utility=sum(item.utility for item in baseline))); continue
        layout = place_subset(baseline, usable, deadline, placement_diagnostics)
        if layout is None:
            baseline_results.append(BaselineDiagnostic(name=name, state="spatial_failure")); continue
        baseline_placements = to_placements(layout)
        provisional = PackingPlan(
            trip_id=snapshot.trip_id, state=PlanState.VALIDATING, placements=baseline_placements,
            excluded_instance_ids=tuple(item.instance_id for item in selection.all_instances if item.instance_id not in {p.instance_id for p in baseline_placements}),
            solver_version=SOLVER_VERSION, seed=seed, runtime_ms=0, input_snapshot_version=snapshot.version,
            snapshot_id=snapshot.id, predecessor_plan_id=predecessor_plan_id,
        )
        baseline_validation = validate_plan(provisional, snapshot)
        if baseline_validation.valid:
            baseline_results.append(BaselineDiagnostic(name=name, state="feasible", retained_utility=sum(item.utility for item in baseline)))
        else:
            validator_rejections += 1; baseline_results.append(BaselineDiagnostic(name=name, state="spatial_failure"))
    runtime_ms = (monotonic() - started) * 1000
    diagnostics = SolverDiagnostics(
        selection_mode=selection.mode, heuristic=selection.heuristic,
        candidate_subsets=len(selection.candidates), placement_attempts=placement_diagnostics.attempts,
        complete_layouts=placement_diagnostics.complete_layouts, validator_rejections=validator_rejections,
        budget_seconds=budget_seconds, baselines=tuple(baseline_results),
    )
    if chosen is None or chosen_validation is None:
        plan = PackingPlan(
            trip_id=snapshot.trip_id, state=PlanState.SEARCH_EXHAUSTED,
            excluded_instance_ids=tuple(item.instance_id for item in selection.all_instances),
            solver_version=SOLVER_VERSION, seed=seed, runtime_ms=runtime_ms,
            input_snapshot_version=snapshot.version, snapshot_id=snapshot.id,
            predecessor_plan_id=predecessor_plan_id, diagnostics=diagnostics,
            exclusion_evidence=tuple(ExclusionEvidence(instance_id=item.instance_id,
                code=selection.preexcluded.get(item.instance_id, "spatial_search_failure"),
                detail="The item is individually oversized." if item.instance_id in selection.preexcluded else "The bounded spatial search did not find a valid arrangement.")
                for item in selection.all_instances),
        )
    else:
        chosen_ids = {item.instance_id for item in chosen}
        excluded = [item for item in selection.all_instances if item.instance_id not in chosen_ids]
        evidence = []
        for item in excluded:
            code = selection.preexcluded.get(item.instance_id)
            if code is None: code = "spatial_search_failure" if item.instance_id in failed_members else "selection_tradeoff"
            detail = {"individual_oversize": "The item cannot fit in any legal orientation.",
                      "spatial_search_failure": "A higher-ranked subset containing this item could not be placed.",
                      "selection_tradeoff": "The item was excluded by weight or padded-volume selection."}[code]
            evidence.append(ExclusionEvidence(instance_id=item.instance_id, code=code, detail=detail))
        plan = PackingPlan(
            trip_id=snapshot.trip_id, state=PlanState.FEASIBLE, placements=chosen_placements,
            excluded_instance_ids=tuple(item.instance_id for item in excluded), validation=chosen_validation,
            solver_version=SOLVER_VERSION, seed=seed, runtime_ms=runtime_ms,
            input_snapshot_version=snapshot.version, snapshot_id=snapshot.id,
            predecessor_plan_id=predecessor_plan_id, exclusion_evidence=tuple(evidence), diagnostics=diagnostics,
        )
    plan = attach_explanation(plan.model_copy(update={"snapshot": snapshot}), snapshot)
    repository.save_plan(plan); return plan
