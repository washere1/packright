from __future__ import annotations

from math import isfinite
from uuid import UUID

from .schemas import PackingPlan, PlanMetrics, ValidationResult, ValidationViolation
from .selection import UTILITY, expand_snapshot, oriented_dimensions

TOL = 1e-5


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _union_area(rectangles: list[tuple[float, float, float, float]]) -> float:
    if not rectangles: return 0.0
    xs = sorted({coordinate for rect in rectangles for coordinate in rect[:2]})
    total = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted((rect[2], rect[3]) for rect in rectangles if rect[0] < right - TOL and rect[1] > left + TOL)
        merged: list[list[float]] = []
        for low, high in intervals:
            if merged and low <= merged[-1][1] + TOL: merged[-1][1] = max(merged[-1][1], high)
            else: merged.append([low, high])
        total += (right - left) * sum(high - low for low, high in merged)
    return total


def validate_plan(plan: PackingPlan, snapshot) -> ValidationResult:
    violations: list[ValidationViolation] = []
    expected = {item.instance_id: item for item in expand_snapshot(snapshot)}
    placements = list(plan.placements); by_instance = {placement.instance_id: placement for placement in placements}
    if len(by_instance) != len(placements):
        duplicate_ids = sorted({placement.instance_id for placement in placements if sum(item.instance_id == placement.instance_id for item in placements) > 1}, key=str)
        violations.append(ValidationViolation(code="duplicate_instance", message="A packed instance is referenced more than once.", instance_ids=tuple(duplicate_ids)))
    orders = [placement.packing_order for placement in placements]
    if len(set(orders)) != len(orders):
        violations.append(ValidationViolation(code="duplicate_packing_order", message="Packed instances must have a unique packing sequence.", instance_ids=tuple(placement.instance_id for placement in placements)))
    usable = tuple(value - snapshot.trip.suitcase.clearance_mm for value in (
        snapshot.trip.suitcase.internal_dimensions_mm.width,
        snapshot.trip.suitcase.internal_dimensions_mm.height,
        snapshot.trip.suitcase.internal_dimensions_mm.depth,
    ))
    for placement in placements:
        item = expected.get(placement.instance_id)
        if item is None or placement.item_id != item.item_id:
            violations.append(ValidationViolation(code="unknown_instance", message="Placement does not match the trip snapshot.", instance_ids=(placement.instance_id,))); continue
        if placement.orientation_id not in item.handling.legal_orientations:
            violations.append(ValidationViolation(code="illegal_orientation", message="Placement uses an orientation not approved for this item.", instance_ids=(placement.instance_id,)))
        expected_dims = oriented_dimensions(item.canonical_padded_mm, placement.orientation_id)
        actual_dims = (placement.dimensions_mm.width, placement.dimensions_mm.height, placement.dimensions_mm.depth)
        if any(abs(actual - wanted) > TOL for actual, wanted in zip(actual_dims, expected_dims, strict=True)):
            violations.append(ValidationViolation(code="wrong_dimensions", message="Placement dimensions do not match canonical padded geometry.", instance_ids=(placement.instance_id,)))
        position = placement.position_mm
        if not all(isfinite(value) for value in (*position, *actual_dims)):
            violations.append(ValidationViolation(code="nonfinite_coordinate", message="Placement contains a nonfinite coordinate.", instance_ids=(placement.instance_id,)))
        elif any(position[i] < -TOL or position[i] + actual_dims[i] > usable[i] + TOL for i in range(3)):
            violations.append(ValidationViolation(code="out_of_bounds", message="Placement exceeds the usable suitcase bounds.", instance_ids=(placement.instance_id,)))
    for index, first in enumerate(placements):
        a_pos = first.position_mm; a_dim = (first.dimensions_mm.width, first.dimensions_mm.height, first.dimensions_mm.depth)
        for second in placements[index + 1:]:
            b_pos = second.position_mm; b_dim = (second.dimensions_mm.width, second.dimensions_mm.height, second.dimensions_mm.depth)
            if all(_overlap(a_pos[i], a_pos[i] + a_dim[i], b_pos[i], b_pos[i] + b_dim[i]) > TOL for i in range(3)):
                violations.append(ValidationViolation(code="collision", message="Two placements overlap.", instance_ids=(first.instance_id, second.instance_id)))
    for placement in placements:
        if placement.position_mm[1] <= TOL:
            if abs(placement.support_ratio - 1.0) > TOL:
                violations.append(ValidationViolation(code="wrong_support_ratio", message="Floor support ratio must be one.", instance_ids=(placement.instance_id,), measured_value=1.0))
            continue
        item = expected.get(placement.instance_id)
        if item is None: continue
        dims = (placement.dimensions_mm.width, placement.dimensions_mm.height, placement.dimensions_mm.depth)
        rectangles = []; dependencies: list[UUID] = []; bad_support = False
        for support in placements:
            if support.instance_id == placement.instance_id: continue
            support_dims = (support.dimensions_mm.width, support.dimensions_mm.height, support.dimensions_mm.depth)
            if abs(support.position_mm[1] + support_dims[1] - placement.position_mm[1]) > TOL: continue
            x0 = max(placement.position_mm[0], support.position_mm[0]); x1 = min(placement.position_mm[0] + dims[0], support.position_mm[0] + support_dims[0])
            z0 = max(placement.position_mm[2], support.position_mm[2]); z1 = min(placement.position_mm[2] + dims[2], support.position_mm[2] + support_dims[2])
            if x1 - x0 <= TOL or z1 - z0 <= TOL: continue
            provider = expected.get(support.instance_id)
            if provider is None or not provider.handling.can_support_weight or provider.handling.stack_class.value == "top_only": bad_support = True
            else: rectangles.append((x0, x1, z0, z1)); dependencies.append(support.instance_id)
        ratio = _union_area(rectangles) / (dims[0] * dims[2])
        threshold = .95 if item.handling.stack_class.value == "base" else .80
        if bad_support:
            violations.append(ValidationViolation(code="ineligible_support", message="Placement loads an item that cannot support weight.", instance_ids=(placement.instance_id,)))
        if ratio + TOL < threshold:
            violations.append(ValidationViolation(code="insufficient_support", message="Elevated placement lacks the required support area.", instance_ids=(placement.instance_id,), measured_value=ratio))
        if abs(placement.support_ratio - ratio) > TOL:
            violations.append(ValidationViolation(code="wrong_support_ratio", message="Support ratio does not match independently recomputed support area.", instance_ids=(placement.instance_id,), measured_value=ratio))
        if any(by_instance[provider].packing_order >= placement.packing_order for provider in dependencies):
            violations.append(ValidationViolation(code="packing_order", message="Packing order places an item before its support.", instance_ids=(placement.instance_id,)))
    missing_mandatory = [instance.instance_id for instance in expected.values() if instance.must_pack and instance.instance_id not in by_instance]
    if missing_mandatory:
        violations.append(ValidationViolation(code="missing_mandatory", message="A mandatory trip instance is absent.", instance_ids=tuple(missing_mandatory)))
    packed_weight = sum(expected[p.instance_id].weight_g for p in placements if p.instance_id in expected)
    remaining = snapshot.trip.suitcase.baggage_limit_g - snapshot.trip.suitcase.empty_weight_g - packed_weight
    if remaining < -TOL:
        violations.append(ValidationViolation(code="overweight", message="Packed items exceed the baggage weight allowance.", measured_value=-remaining))
    if violations:
        return ValidationResult(validator_version="packright-validator-v1", valid=False, violations=tuple(violations))
    packed_volume = sum(p.dimensions_mm.width * p.dimensions_mm.height * p.dimensions_mm.depth for p in placements)
    total_mass = max(packed_weight, 1.0)
    center = tuple(sum(expected[p.instance_id].weight_g * (p.position_mm[axis] + (p.dimensions_mm.width, p.dimensions_mm.height, p.dimensions_mm.depth)[axis] / 2) for p in placements) / total_mass for axis in range(3)) if placements else None
    metrics = PlanMetrics(
        packed_weight_g=packed_weight, remaining_allowance_g=remaining,
        utilization=min(1.0, packed_volume / (usable[0] * usable[1] * usable[2])),
        retained_utility=sum(UTILITY[expected[p.instance_id].priority_stars] for p in placements), center_of_mass_mm=center,
    )
    return ValidationResult(validator_version="packright-validator-v1", valid=True, metrics=metrics)
