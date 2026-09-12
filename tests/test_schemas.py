from math import inf, nan
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    DimensionsMm, Geometry, ItemDraft, ItemInstance, Matrix3, Orientation,
    OrientationId, PackingPlan, PlanState, Suitcase, Trip, TripItem,
)


def suitcase() -> Suitcase:
    return Suitcase(
        name="Carry-on",
        internal_dimensions_mm={"width": 350, "height": 230, "depth": 510},
        empty_weight_g=3000,
        baggage_limit_g=10000,
        clearance_mm=8,
        display_length_unit="mm",
        display_weight_unit="g",
    )


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_nonfinite_values_are_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        ItemDraft(weight_g=value, priority_stars=3, display_weight_unit="g")


def test_invalid_unit_and_stars_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ItemDraft(weight_g=100, priority_stars=0, display_weight_unit="stone")
    with pytest.raises(ValidationError):
        ItemDraft(weight_g=100, priority_stars=6, display_weight_unit="g")


def test_weight_and_dimension_bounds_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ItemDraft(weight_g=100001, priority_stars=3, display_weight_unit="g")
    with pytest.raises(ValidationError):
        DimensionsMm(width=3001, height=100, depth=100)


def test_orientation_id_cannot_be_paired_with_wrong_matrix() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        Orientation(id=OrientationId.XZY, matrix=Matrix3(values=((1, 0, 0), (0, 1, 0), (0, 0, 1))))


def test_duplicate_instance_ids_are_rejected() -> None:
    shared_id, first_item, second_item = uuid4(), uuid4(), uuid4()
    first = ItemInstance(id=shared_id, item_id=first_item, copy_number=1, priority_stars=3)
    second = ItemInstance(id=shared_id, item_id=second_item, copy_number=1, priority_stars=3)
    with pytest.raises(ValidationError, match="duplicate instance IDs"):
        Trip(name="Duplicate test", suitcase=suitcase(), items=(
            TripItem(item_id=first_item, instances=(first,)),
            TripItem(item_id=second_item, instances=(second,)),
        ))


def test_feasible_plan_requires_independent_valid_result() -> None:
    with pytest.raises(ValidationError, match="independent valid"):
        PackingPlan(
            trip_id=uuid4(), state=PlanState.FEASIBLE, solver_version="fixture-1",
            seed=7, runtime_ms=10, input_snapshot_version=1,
        )


def test_suitcase_must_have_positive_item_allowance() -> None:
    with pytest.raises(ValidationError, match="must exceed"):
        Suitcase(
            name="Bad suitcase",
            internal_dimensions_mm={"width": 350, "height": 230, "depth": 510},
            empty_weight_g=10000,
            baggage_limit_g=10000,
            display_length_unit="mm",
            display_weight_unit="g",
        )
