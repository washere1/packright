from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import LengthUnit, Suitcase, WeightUnit

LENGTH_TO_MM = {LengthUnit.MM: 1.0, LengthUnit.CM: 10.0, LengthUnit.IN: 25.4}
WEIGHT_TO_G = {WeightUnit.G: 1.0, WeightUnit.KG: 1000.0, WeightUnit.OZ: 28.349523125, WeightUnit.LB: 453.59237}


class SuitcaseBoundaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    depth: float = Field(gt=0)
    length_unit: LengthUnit
    empty_weight: float = Field(ge=0)
    baggage_limit: float = Field(gt=0)
    weight_unit: WeightUnit
    clearance_mm: float = Field(default=0, ge=0, le=15)

    @model_validator(mode="after")
    def allowance_in_input_units(self) -> "SuitcaseBoundaryRequest":
        if self.baggage_limit <= self.empty_weight:
            raise ValueError("baggage limit must exceed empty suitcase weight")
        return self


def normalize_suitcase(payload: SuitcaseBoundaryRequest, suitcase_id: UUID | None = None) -> Suitcase:
    length = LENGTH_TO_MM[payload.length_unit]
    weight = WEIGHT_TO_G[payload.weight_unit]
    values = {
        "name": payload.name,
        "internal_dimensions_mm": {
            "width": payload.width * length, "height": payload.height * length, "depth": payload.depth * length,
        },
        "empty_weight_g": payload.empty_weight * weight,
        "baggage_limit_g": payload.baggage_limit * weight,
        "clearance_mm": payload.clearance_mm,
        "display_length_unit": payload.length_unit,
        "display_weight_unit": payload.weight_unit,
    }
    return Suitcase(id=suitcase_id, **values) if suitcase_id else Suitcase(**values)
