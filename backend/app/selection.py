from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from time import monotonic
from uuid import UUID

from .schemas import HandlingEdit, LibraryItem, OrientationId, TripSnapshot

UTILITY = {1: 1, 2: 3, 3: 7, 4: 15, 5: 31}


@dataclass(frozen=True)
class CandidateInstance:
    instance_id: UUID
    item_id: UUID
    copy_number: int
    weight_g: float
    priority_stars: int
    utility: int
    must_pack: bool
    canonical_padded_mm: tuple[float, float, float]
    handling: HandlingEdit

    @property
    def volume(self) -> float:
        x, y, z = self.canonical_padded_mm
        return x * y * z


@dataclass(frozen=True)
class SelectionResult:
    candidates: tuple[tuple[CandidateInstance, ...], ...]
    all_instances: tuple[CandidateInstance, ...]
    mode: str
    heuristic: bool
    preexcluded: dict[UUID, str]
    baselines: tuple[tuple[str, tuple[CandidateInstance, ...]], ...]


class SelectionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message); self.code = code; self.message = message


def oriented_dimensions(dimensions: tuple[float, float, float], orientation: OrientationId | str) -> tuple[float, float, float]:
    x, y, z = dimensions
    return {
        "xyz": (x, y, z), "xzy": (x, z, y), "yxz": (y, x, z),
        "yzx": (y, z, x), "zxy": (z, x, y), "zyx": (z, y, x),
    }[str(orientation)]


def expand_snapshot(snapshot: TripSnapshot) -> tuple[CandidateInstance, ...]:
    records = {record.id: record for record in snapshot.item_snapshots}
    frozen_boxes = {box.instance_id: box for box in snapshot.expanded_boxes}
    expanded = []
    for entry in snapshot.trip.items:
        record = records.get(entry.item_id)
        if record is None or not record.ready or record.dimensions_mm is None or record.handling is None:
            raise SelectionError("missing_packing_data", "A selected item lacks confirmed packing data.")
        base = record.dimensions_mm
        padded = tuple(value + max(4.0, value * .02) for value in (base.width, base.height, base.depth))
        for instance in entry.instances:
            frozen = frozen_boxes.get(instance.id)
            if frozen is not None:
                padded = (frozen.effective_padded_dimensions_mm.width, frozen.effective_padded_dimensions_mm.height, frozen.effective_padded_dimensions_mm.depth)
            handling = record.handling.model_copy(update={"access": instance.access_preference}) if instance.access_preference is not None else record.handling
            expanded.append(CandidateInstance(
                instance_id=instance.id, item_id=entry.item_id, copy_number=instance.copy_number,
                weight_g=record.weight_g, priority_stars=instance.priority_stars,
                utility=UTILITY[instance.priority_stars], must_pack=instance.must_pack,
                canonical_padded_mm=padded, handling=handling,
            ))
    return tuple(expanded)


def _fits(instance: CandidateInstance, usable: tuple[float, float, float]) -> bool:
    return any(all(value <= bound + 1e-7 for value, bound in zip(oriented_dimensions(instance.canonical_padded_mm, orientation), usable, strict=True))
               for orientation in instance.handling.legal_orientations)


def select_candidates(snapshot: TripSnapshot, deadline: float, max_candidates: int = 32) -> SelectionResult:
    instances = expand_snapshot(snapshot)
    suitcase = snapshot.trip.suitcase
    usable = tuple(value - suitcase.clearance_mm for value in (
        suitcase.internal_dimensions_mm.width, suitcase.internal_dimensions_mm.height, suitcase.internal_dimensions_mm.depth,
    ))
    capacity_weight = suitcase.baggage_limit_g - suitcase.empty_weight_g
    capacity_volume = usable[0] * usable[1] * usable[2]
    preexcluded: dict[UUID, str] = {}
    eligible = []
    for instance in instances:
        if not _fits(instance, usable):
            if instance.must_pack:
                raise SelectionError("mandatory_oversize", "A mandatory item cannot fit in any legal orientation.")
            preexcluded[instance.instance_id] = "individual_oversize"
        else:
            eligible.append(instance)
    mandatory = [instance for instance in eligible if instance.must_pack]
    if sum(instance.weight_g for instance in mandatory) > capacity_weight + 1e-7:
        raise SelectionError("mandatory_overweight", "Mandatory items exceed the available baggage weight.")
    if sum(instance.volume for instance in mandatory) > capacity_volume + 1e-7:
        raise SelectionError("mandatory_volume_impossible", "Mandatory padded volume exceeds suitcase volume.")

    rank = lambda subset: (-sum(item.utility for item in subset), -len(subset), tuple(str(item.instance_id) for item in subset))
    candidates: list[tuple[CandidateInstance, ...]] = []
    if len(eligible) <= 16:
        optional = [item for item in eligible if not item.must_pack]
        base_weight = sum(item.weight_g for item in mandatory); base_volume = sum(item.volume for item in mandatory)
        timed_out = False
        def visit(index: int, chosen: list[CandidateInstance], weight: float, volume: float) -> None:
            nonlocal timed_out
            if monotonic() >= deadline:
                timed_out = True
                return
            if weight > capacity_weight + 1e-7 or volume > capacity_volume + 1e-7:
                return
            if index == len(optional):
                candidates.append(tuple(sorted((*mandatory, *chosen), key=lambda item: str(item.instance_id))))
                return
            chosen.append(optional[index]); visit(index + 1, chosen, weight + optional[index].weight_g, volume + optional[index].volume); chosen.pop()
            visit(index + 1, chosen, weight, volume)
        visit(0, [], base_weight, base_volume)
        mode, heuristic = ("bounded_beam", True) if timed_out else ("exact", False)
    else:
        states: list[tuple[tuple[CandidateInstance, ...], float, float]] = [(tuple(mandatory), sum(i.weight_g for i in mandatory), sum(i.volume for i in mandatory))]
        optional = sorted((item for item in eligible if not item.must_pack), key=lambda i: (-i.utility, i.weight_g, str(i.instance_id)))
        for item in optional:
            if monotonic() >= deadline: break
            expanded = states + [(chosen + (item,), weight + item.weight_g, volume + item.volume) for chosen, weight, volume in states
                                 if weight + item.weight_g <= capacity_weight + 1e-7 and volume + item.volume <= capacity_volume + 1e-7]
            unique = {tuple(sorted(str(value.instance_id) for value in chosen)): (chosen, weight, volume) for chosen, weight, volume in expanded}
            states = sorted(unique.values(), key=lambda state: rank(state[0]))[:128]
        candidates = [tuple(sorted(state[0], key=lambda item: str(item.instance_id))) for state in states]
        mode, heuristic = "bounded_beam", True
    # Baselines enter the same downstream spatial search and independent validator;
    # their weight-only heuristics are never reported as feasible on their own.
    baseline_candidates = []
    for baseline_name, baseline_ids in (
        ("lowest_star_first", lowest_star_first_baseline(tuple(eligible), capacity_weight)),
        ("heaviest_first", heaviest_first_baseline(tuple(eligible), capacity_weight)),
    ):
        baseline_set = set(baseline_ids)
        baseline = tuple(sorted((item for item in eligible if item.instance_id in baseline_set), key=lambda item: str(item.instance_id)))
        if sum(item.volume for item in baseline) <= capacity_volume + 1e-7:
            baseline_candidates.append((baseline_name, baseline))
    unique_candidates = {tuple(str(item.instance_id) for item in candidate): candidate for candidate in candidates}
    candidates = sorted(unique_candidates.values(), key=rank)[:max_candidates]
    signatures = {tuple(str(item.instance_id) for item in candidate) for candidate in candidates}
    for _, baseline in baseline_candidates:
        signature = tuple(str(item.instance_id) for item in baseline)
        if signature not in signatures:
            candidates.append(baseline); signatures.add(signature)
    if not candidates:
        raise SelectionError("selection_infeasible", "No subset satisfies mandatory weight and volume constraints.")
    return SelectionResult(tuple(candidates), instances, mode, heuristic, preexcluded, tuple(baseline_candidates))


def lowest_star_first_baseline(instances: tuple[CandidateInstance, ...], weight_limit: float) -> tuple[UUID, ...]:
    kept = list(instances)
    for item in sorted((i for i in kept if not i.must_pack), key=lambda i: (i.priority_stars, i.weight_g, str(i.instance_id))):
        if sum(value.weight_g for value in kept) <= weight_limit: break
        kept.remove(item)
    return tuple(value.instance_id for value in kept)


def heaviest_first_baseline(instances: tuple[CandidateInstance, ...], weight_limit: float) -> tuple[UUID, ...]:
    kept = list(instances)
    for item in sorted((i for i in kept if not i.must_pack), key=lambda i: (-i.weight_g, str(i.instance_id))):
        if sum(value.weight_g for value in kept) <= weight_limit: break
        kept.remove(item)
    return tuple(value.instance_id for value in kept)
