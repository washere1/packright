from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from uuid import UUID

from .schemas import DimensionsMm, Matrix3, OrientationId, ORIENTATION_MATRICES, Placement
from .selection import CandidateInstance, oriented_dimensions

TOL = 1e-6


@dataclass(frozen=True)
class Box:
    item: CandidateInstance
    position: tuple[float, float, float]
    dimensions: tuple[float, float, float]
    orientation: OrientationId
    providers: tuple[UUID, ...]
    support_ratio: float


@dataclass(frozen=True)
class Layout:
    boxes: tuple[Box, ...]
    score: float


@dataclass
class PlacementDiagnostics:
    attempts: int = 0
    complete_layouts: int = 0


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _collides(position: tuple[float, float, float], dims: tuple[float, float, float], other: Box) -> bool:
    return all(_overlap(position[i], position[i] + dims[i], other.position[i], other.position[i] + other.dimensions[i]) > TOL for i in range(3))


def _union_area(rectangles: list[tuple[float, float, float, float]]) -> float:
    if not rectangles: return 0.0
    xs = sorted({value for rect in rectangles for value in (rect[0], rect[1])})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted((z0, z1) for x0, x1, z0, z1 in rectangles if x0 < right - TOL and x1 > left + TOL)
        covered = 0.0; start = end = None
        for low, high in intervals:
            if start is None: start, end = low, high
            elif low <= end + TOL: end = max(end, high)
            else: covered += end - start; start, end = low, high
        if start is not None: covered += end - start
        area += (right - left) * covered
    return area


def _support(position: tuple[float, float, float], dims: tuple[float, float, float], boxes: tuple[Box, ...], item: CandidateInstance) -> tuple[float, tuple[UUID, ...]] | None:
    if position[1] <= TOL: return 1.0, ()
    eligible = []; providers = []; ineligible_contact = False
    for box in boxes:
        if abs(box.position[1] + box.dimensions[1] - position[1]) > TOL: continue
        x0, x1 = max(position[0], box.position[0]), min(position[0] + dims[0], box.position[0] + box.dimensions[0])
        z0, z1 = max(position[2], box.position[2]), min(position[2] + dims[2], box.position[2] + box.dimensions[2])
        if x1 - x0 <= TOL or z1 - z0 <= TOL: continue
        if not box.item.handling.can_support_weight or box.item.handling.stack_class.value == "top_only": ineligible_contact = True
        else: eligible.append((x0, x1, z0, z1)); providers.append(box.item.instance_id)
    if ineligible_contact: return None
    ratio = _union_area(eligible) / (dims[0] * dims[2])
    threshold = .95 if item.handling.stack_class.value == "base" else .80
    return (ratio, tuple(sorted(set(providers), key=str))) if ratio + TOL >= threshold else None


def _points(boxes: tuple[Box, ...], usable: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    xs = {0.0}; ys = {0.0}; zs = {0.0}
    for box in boxes:
        xs.add(box.position[0] + box.dimensions[0]); ys.add(box.position[1] + box.dimensions[1]); zs.add(box.position[2] + box.dimensions[2])
    points = [(x, y, z) for y in ys for z in zs for x in xs if x <= usable[0] and y <= usable[1] and z <= usable[2]]
    return sorted(points, key=lambda point: (point[1], point[2], point[0]))[:512]


def _layout_score(boxes: tuple[Box, ...], usable: tuple[float, float, float]) -> float:
    total_mass = max(1.0, sum(box.item.weight_g for box in boxes))
    vertical = sum(box.item.weight_g * (box.position[1] + box.dimensions[1] / 2) for box in boxes) / total_mass
    wheel = sum(box.item.weight_g * (box.position[2] + box.dimensions[2] / 2) for box in boxes) / total_mass
    access = sum(max(0.0, usable[2] - (box.position[2] + box.dimensions[2])) for box in boxes if box.item.handling.access.value == "quick")
    fragmentation = len(_points(boxes, usable))
    return vertical * 3 + wheel * .15 + access * .4 + fragmentation * .01


def _orders(items: tuple[CandidateInstance, ...]) -> list[tuple[CandidateInstance, ...]]:
    keys = (
        lambda i: (not i.must_pack, not i.handling.can_support_weight, -i.volume, -i.weight_g, str(i.instance_id)),
        lambda i: (not i.must_pack, -i.weight_g, -i.utility, str(i.instance_id)),
        lambda i: (not i.must_pack, -max(i.canonical_padded_mm[0], i.canonical_padded_mm[2]), -i.volume, str(i.instance_id)),
        lambda i: (not i.must_pack, -i.utility, -i.volume, str(i.instance_id)),
    )
    unique = []
    for key in keys:
        order = tuple(sorted(items, key=key))
        if order not in unique: unique.append(order)
    return unique


def place_subset(items: tuple[CandidateInstance, ...], usable: tuple[float, float, float], deadline: float, diagnostics: PlacementDiagnostics, beam_width: int = 48) -> Layout | None:
    best = None
    for order in _orders(items):
        states = [Layout((), 0.0)]
        for item in order:
            expanded = []
            for state in states:
                for orientation in item.handling.legal_orientations:
                    dims = oriented_dimensions(item.canonical_padded_mm, orientation)
                    for point in _points(state.boxes, usable):
                        if monotonic() >= deadline: return best
                        diagnostics.attempts += 1
                        if any(point[index] + dims[index] > usable[index] + TOL for index in range(3)): continue
                        if any(_collides(point, dims, other) for other in state.boxes): continue
                        support = _support(point, dims, state.boxes, item)
                        if support is None: continue
                        ratio, providers = support
                        boxes = state.boxes + (Box(item, point, dims, OrientationId(orientation), providers, ratio),)
                        expanded.append(Layout(boxes, _layout_score(boxes, usable)))
            if not expanded: states = []; break
            signatures = {}
            for state in expanded:
                signature = tuple((str(box.item.instance_id), box.position, box.orientation.value) for box in state.boxes)
                signatures[signature] = state
            states = sorted(signatures.values(), key=lambda state: (state.score, tuple(str(box.item.instance_id) for box in state.boxes)))[:beam_width]
        if states:
            diagnostics.complete_layouts += len(states)
            candidate = min(states, key=lambda state: state.score)
            if best is None or candidate.score < best.score: best = candidate
    return best


def to_placements(layout: Layout) -> tuple[Placement, ...]:
    remaining = {box.item.instance_id: box for box in layout.boxes}; ordered: list[Box] = []
    while remaining:
        ready = [box for box in remaining.values() if all(provider not in remaining for provider in box.providers)]
        if not ready: raise ValueError("support dependency cycle")
        ready.sort(key=lambda box: (box.position[1], box.position[2], box.position[0], str(box.item.instance_id)))
        for box in ready: ordered.append(box); remaining.pop(box.item.instance_id)
    return tuple(Placement(
        instance_id=box.item.instance_id, item_id=box.item.item_id, position_mm=box.position,
        dimensions_mm=DimensionsMm(width=box.dimensions[0], height=box.dimensions[1], depth=box.dimensions[2]),
        orientation_id=box.orientation, orientation_matrix=Matrix3(values=ORIENTATION_MATRICES[box.orientation]),
        packing_order=index + 1, support_ratio=box.support_ratio,
    ) for index, box in enumerate(ordered))
