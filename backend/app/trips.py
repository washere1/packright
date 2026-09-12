from __future__ import annotations

from uuid import UUID, uuid4

from .library import resolve_library_item
from .repository import Repository
from .schemas import DimensionsMm, ItemInstance, SnapshotBox, Trip, TripItem, TripItemRequest, TripPreflight, TripSnapshot, TripSummary
from .selection import oriented_dimensions

UTILITY = {1: 1, 2: 3, 3: 7, 4: 15, 5: 31}


class TripError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message); self.code = code; self.message = message


def set_trip_item(trip: Trip, request: TripItemRequest, repository: Repository, limit: int) -> Trip:
    record = resolve_library_item(request.item_id, repository)
    if record is None:
        raise TripError("item_not_ready", "Only ready custom items and stock templates can enter a trip.")
    existing = next((entry for entry in trip.items if entry.item_id == request.item_id), None)
    other_count = sum(len(entry.instances) for entry in trip.items if entry.item_id != request.item_id)
    if other_count + request.quantity > limit:
        raise TripError("instance_limit", f"This trip supports at most {limit} item instances.")
    kept = list(existing.instances[:request.quantity]) if existing else []
    instances = [instance.model_copy(update={"copy_number": index + 1, "priority_stars": request.priority_stars, "must_pack": request.must_pack, "access_preference": request.access_preference})
                 for index, instance in enumerate(kept)]
    for index in range(len(instances), request.quantity):
        instances.append(ItemInstance(id=uuid4(), item_id=request.item_id, copy_number=index + 1,
                                      priority_stars=request.priority_stars, must_pack=request.must_pack,
                                      access_preference=request.access_preference))
    items = [entry for entry in trip.items if entry.item_id != request.item_id]
    if instances:
        items.append(TripItem(item_id=request.item_id, instances=tuple(instances)))
    return trip.model_copy(update={"items": tuple(items)})


def summarize_trip(trip: Trip, repository: Repository) -> TripSummary:
    weight = 0.0; utility = 0; warnings: list[str] = []
    usable = (
        trip.suitcase.internal_dimensions_mm.width - trip.suitcase.clearance_mm,
        trip.suitcase.internal_dimensions_mm.height - trip.suitcase.clearance_mm,
        trip.suitcase.internal_dimensions_mm.depth - trip.suitcase.clearance_mm,
    )
    for entry in trip.items:
        record = resolve_library_item(entry.item_id, repository)
        if record is None or record.dimensions_mm is None:
            warnings.append(f"missing_data:{entry.item_id}"); continue
        weight += record.weight_g * len(entry.instances)
        utility += sum(UTILITY[instance.priority_stars] for instance in entry.instances)
        raw_dims = (record.dimensions_mm.width, record.dimensions_mm.height, record.dimensions_mm.depth)
        dims = tuple(value + max(4.0, value * .02) for value in raw_dims)
        if record.handling is None or not any(
            all(value <= bound for value, bound in zip(oriented_dimensions(dims, orientation), usable, strict=True))
            for orientation in record.handling.legal_orientations
        ):
            warnings.append(f"oversize:{entry.item_id}")
    available = trip.suitcase.baggage_limit_g - trip.suitcase.empty_weight_g
    if weight > available:
        warnings.append("requested_items_overweight")
    return TripSummary(trip=trip, requested_item_weight_g=weight, available_item_weight_g=available,
                       total_utility=utility, warnings=tuple(warnings))


def snapshot_trip(trip: Trip, repository: Repository) -> TripSnapshot:
    records = []
    for entry in trip.items:
        record = resolve_library_item(entry.item_id, repository)
        if record is None:
            raise TripError("item_not_ready", "A selected item is no longer ready for packing.")
        records.append(record)
    record_by_id = {record.id: record for record in records}
    expanded_boxes: list[SnapshotBox] = []
    for entry in trip.items:
        record = record_by_id[entry.item_id]
        if record.dimensions_mm is None or record.handling is None:
            raise TripError("missing_packing_data", "Every selected item needs confirmed geometry and handling data.")
        raw = (record.dimensions_mm.width, record.dimensions_mm.height, record.dimensions_mm.depth)
        padded = DimensionsMm(width=raw[0] + max(4.0, raw[0] * .02), height=raw[1] + max(4.0, raw[1] * .02), depth=raw[2] + max(4.0, raw[2] * .02))
        for instance in entry.instances:
            expanded_boxes.append(SnapshotBox(
                instance_id=instance.id, item_id=entry.item_id, copy_number=instance.copy_number,
                priority_stars=instance.priority_stars, must_pack=instance.must_pack,
                effective_padded_dimensions_mm=padded, weight_g=record.weight_g,
                geometry_version=record.geometry.version if getattr(record, "geometry", None) else 1,
                handling_version=record.handling.version if hasattr(record.handling, "version") else 1,
                legal_orientations=record.handling.legal_orientations,
            ))
    snapshot = TripSnapshot(trip_id=trip.id, version=repository.next_trip_snapshot_version(trip.id),
                            trip=trip, item_snapshots=tuple(records), expanded_boxes=tuple(expanded_boxes))
    repository.save_trip_snapshot(snapshot)
    return snapshot


def preflight_trip(trip: Trip, repository: Repository) -> TripPreflight:
    requested_weight = 0.0
    padded_volume = 0.0
    missing: list[UUID] = []
    oversize: list[UUID] = []
    contradictions: list[str] = []
    usable = tuple(value - trip.suitcase.clearance_mm for value in (
        trip.suitcase.internal_dimensions_mm.width,
        trip.suitcase.internal_dimensions_mm.height,
        trip.suitcase.internal_dimensions_mm.depth,
    ))
    for entry in trip.items:
        record = resolve_library_item(entry.item_id, repository)
        if record is None or record.dimensions_mm is None or record.handling is None:
            missing.append(entry.item_id)
            continue
        raw = (record.dimensions_mm.width, record.dimensions_mm.height, record.dimensions_mm.depth)
        padded = tuple(value + max(4.0, value * .02) for value in raw)
        for instance in entry.instances:
            requested_weight += record.weight_g
            padded_volume += padded[0] * padded[1] * padded[2]
            if not any(all(value <= bound for value, bound in zip(oriented_dimensions(padded, orientation), usable, strict=True)) for orientation in record.handling.legal_orientations):
                oversize.append(instance.id)
                if instance.must_pack:
                    contradictions.append(f"mandatory_oversize:{instance.id}")
    remaining = trip.suitcase.baggage_limit_g - trip.suitcase.empty_weight_g - requested_weight
    if remaining < 0:
        contradictions.append("mandatory_weight_over_limit" if any(i.must_pack for e in trip.items for i in e.instances) else "requested_weight_over_limit")
    if padded_volume > usable[0] * usable[1] * usable[2]:
        contradictions.append("requested_padded_volume_over_limit")
    messages = ["Choose a larger suitcase or remove oversized items." for _ in oversize]
    if remaining < 0:
        messages.append("Requested item weight exceeds the remaining baggage allowance.")
    if missing:
        messages.append("Complete item review before creating a packing plan.")
    return TripPreflight(
        requested_instances=sum(len(entry.instances) for entry in trip.items), requested_weight_g=requested_weight,
        padded_volume_mm3=padded_volume, baggage_remaining_g=remaining, missing_metadata=tuple(missing),
        oversize_instances=tuple(oversize), mandatory_contradictions=tuple(dict.fromkeys(contradictions)),
        actionable_messages=tuple(dict.fromkeys(messages)),
    )
