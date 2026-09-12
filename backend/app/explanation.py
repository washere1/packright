"""Deterministic, evidence-backed packing instructions.

This module deliberately contains no language-model calls.  Every sentence is
derived from the immutable snapshot, accepted placements, and recorded solver
evidence so an explanation cannot invent a cause for an exclusion.
"""
from __future__ import annotations

from uuid import UUID

from .schemas import PackingInstruction, PackingPlan, PlanState, TripSnapshot

_ORIENTATION_LABELS = {
    "xyz": "canonical (width × height × depth)",
    "xzy": "opening-side depth upright",
    "yxz": "width upright",
    "yzx": "height along depth",
    "zxy": "depth along width",
    "zyx": "rotated 180° from canonical",
}


def _destination(position: tuple[float, float, float], usable_depth: float) -> str:
    x, y, z = position
    vertical = "floor" if y <= 1e-5 else "upper layer"
    opening = "near the opening" if z >= usable_depth * 0.55 else "toward the wheel side"
    side = "left" if x < 0.33 else "right" if x > 0.66 else "center"
    return f"{vertical}, {side} side, {opening}"


def _handling_note(item) -> str | None:
    handling = item.handling
    if handling is None:
        return None
    notes: list[str] = []
    if handling.fragility.value == "high":
        notes.append("handle as fragile")
    if handling.liquid_risk:
        notes.append("keep upright and contain liquids")
    if handling.stack_class.value == "top_only":
        notes.append("keep on top")
    if handling.access.value == "quick":
        notes.append("leave accessible")
    return "; ".join(notes) if notes else None


def generate_instructions(plan: PackingPlan, snapshot: TripSnapshot) -> tuple[PackingInstruction, ...]:
    """Return one stable instruction per accepted placement.

    Packing order is authoritative for support dependencies; spatial fields are
    only a deterministic tie-breaker for malformed/legacy plans.
    """
    if plan.state != PlanState.FEASIBLE or plan.validation is None or not plan.validation.valid:
        return ()
    records = {item.id: item for item in snapshot.item_snapshots}
    copy_numbers = {
        instance.id: instance.copy_number
        for entry in snapshot.trip.items
        for instance in entry.instances
    }
    usable_depth = snapshot.trip.suitcase.internal_dimensions_mm.depth - snapshot.trip.suitcase.clearance_mm
    ordered = sorted(plan.placements, key=lambda p: (p.packing_order, p.position_mm[1], p.position_mm[2], p.position_mm[0], str(p.instance_id)))
    instructions: list[PackingInstruction] = []
    for number, placement in enumerate(ordered, start=1):
        record = records.get(placement.item_id)
        if record is None:
            continue
        instructions.append(PackingInstruction(
            number=number,
            instance_id=placement.instance_id,
            item_name=record.name or "Unnamed item",
            copy_number=copy_numbers.get(placement.instance_id, 1),
            destination=_destination(placement.position_mm, usable_depth),
            orientation_label=_ORIENTATION_LABELS[str(placement.orientation_id)],
            handling_note=_handling_note(record),
        ))
    return tuple(instructions)


def explain_exclusions(plan: PackingPlan, snapshot: TripSnapshot) -> tuple[str, ...]:
    """Turn recorded evidence into concise UI-ready exclusion messages."""
    records = {item.id: item for item in snapshot.item_snapshots}
    instances = {
        instance.id: instance
        for entry in snapshot.trip.items
        for instance in entry.instances
    }
    messages: list[str] = []
    for evidence in sorted(plan.exclusion_evidence, key=lambda e: str(e.instance_id)):
        record = records.get(instances.get(evidence.instance_id, object()).item_id) if evidence.instance_id in instances else None
        name = record.name if record and record.name else "Item"
        copy = instances[evidence.instance_id].copy_number if evidence.instance_id in instances else 1
        required = " REQUIRED" if evidence.instance_id in instances and instances[evidence.instance_id].must_pack else ""
        messages.append(f"{name} (copy {copy}){required}: {evidence.detail}")
    missing = [
        (record.name or "Item", instance.copy_number)
        for entry in snapshot.trip.items
        for instance in entry.instances
        if instance.must_pack and instance.id in set(plan.excluded_instance_ids)
        for record in snapshot.item_snapshots
        if record.id == instance.item_id
    ]
    if missing:
        names = ", ".join(f"{name} (copy {copy})" for name, copy in missing)
        messages.insert(0, f"Missing mandatory items: {names}. Consider editing suitcase dimensions, clearance, or baggage limit and replan.")
    return tuple(messages)


def attach_explanation(plan: PackingPlan, snapshot: TripSnapshot) -> PackingPlan:
    return plan.model_copy(update={"instructions": generate_instructions(plan, snapshot)})

