from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from math import isclose
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .config import get_settings

LIMITS = get_settings().limits
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


class WeightUnit(StrEnum):
    G = "g"
    KG = "kg"
    OZ = "oz"
    LB = "lb"


class LengthUnit(StrEnum):
    MM = "mm"
    CM = "cm"
    IN = "in"


class ItemStage(StrEnum):
    DRAFT = "draft"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    READY = "ready"
    FAILED = "failed"


class ProgressStage(StrEnum):
    NONE = "none"
    UPLOAD = "upload"
    GEOMETRY = "geometry"
    PREVIEWS = "previews"
    ENRICHMENT = "enrichment"
    COMPLETE = "complete"


class PlanState(StrEnum):
    QUEUED = "queued"
    SOLVING = "solving"
    VALIDATING = "validating"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    SEARCH_EXHAUSTED = "search_exhausted"
    FAILED = "failed"


class PlanJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYABLE = "retryable"


class AssetStage(StrEnum):
    RECEIVING = "receiving"
    PROCESSING = "processing"
    INGESTED = "ingested"
    FAILED = "failed"


class Fragility(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Compressibility(StrEnum):
    NONE = "none"
    LIGHT = "light"
    HIGH = "high"


class StackClass(StrEnum):
    BASE = "base"
    NEUTRAL = "neutral"
    TOP_ONLY = "top_only"


class AccessClass(StrEnum):
    BURIED_OK = "buried_ok"
    NORMAL = "normal"
    QUICK = "quick"


class OrientationId(StrEnum):
    XYZ = "xyz"
    XZY = "xzy"
    YXZ = "yxz"
    YZX = "yzx"
    ZXY = "zxy"
    ZYX = "zyx"


ORIENTATION_MATRICES: dict[OrientationId, tuple[tuple[float, float, float], ...]] = {
    OrientationId.XYZ: ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    OrientationId.XZY: ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    OrientationId.YXZ: ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    OrientationId.YZX: ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    OrientationId.ZXY: ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    OrientationId.ZYX: ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
}


class DimensionsMm(ContractModel):
    width: float = Field(gt=0, le=LIMITS.max_dimension_mm)
    height: float = Field(gt=0, le=LIMITS.max_dimension_mm)
    depth: float = Field(gt=0, le=LIMITS.max_dimension_mm)


class Matrix3(ContractModel):
    values: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]

    @model_validator(mode="after")
    def proper_rotation(self) -> "Matrix3":
        m = self.values
        determinant = (
            m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
        )
        if not isclose(determinant, 1.0, abs_tol=1e-6):
            raise ValueError("orientation matrix must be a proper rotation with determinant +1")
        for i in range(3):
            for j in range(3):
                dot = sum(m[i][k] * m[j][k] for k in range(3))
                if not isclose(dot, 1.0 if i == j else 0.0, abs_tol=1e-6):
                    raise ValueError("orientation matrix must be orthonormal")
        return self


class Orientation(ContractModel):
    id: OrientationId
    matrix: Matrix3

    @model_validator(mode="after")
    def matches_identifier(self) -> "Orientation":
        expected = ORIENTATION_MATRICES[self.id]
        if any(not isclose(self.matrix.values[i][j], expected[i][j], abs_tol=1e-6) for i in range(3) for j in range(3)):
            raise ValueError("orientation matrix does not match its orientation ID")
        return self


class BoundsMm(ContractModel):
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]

    @model_validator(mode="after")
    def ordered(self) -> "BoundsMm":
        if any(high < low for low, high in zip(self.minimum, self.maximum, strict=True)):
            raise ValueError("bounds must be ordered")
        return self


class Geometry(ContractModel):
    version: int = Field(ge=1)
    asset_id: UUID
    units: str = Field(default="mm", pattern="^mm$")
    aabb_mm: BoundsMm
    canonical_dimensions_mm: DimensionsMm
    geometric_center_mm: tuple[float, float, float]
    source_to_canonical: tuple[float, ...] = Field(min_length=16, max_length=16)
    canonical_to_source: tuple[float, ...] = Field(min_length=16, max_length=16)
    box_volume_mm3: float = Field(gt=0)
    mesh_volume_mm3: float | None = Field(default=None, gt=0)
    fill_ratio: float | None = Field(default=None, ge=0, le=1)
    clearance_mm: DimensionsMm
    preview_camera_distance_mm: float = Field(gt=0)
    scale_correction: float = Field(default=1, gt=0, le=1000)
    requires_scale_confirmation: bool = False
    mesh_watertight: bool
    orientations: tuple[Orientation, ...] = Field(min_length=6, max_length=6)
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_orientations(self) -> "Geometry":
        identifiers = [orientation.id for orientation in self.orientations]
        if len(set(identifiers)) != 6:
            raise ValueError("geometry must contain each of the six orientation IDs exactly once")
        return self


class ConfidenceScores(ContractModel):
    name: float = Field(ge=0, le=1)
    category: float = Field(ge=0, le=1)
    fragility: float = Field(ge=0, le=1)
    compressibility: float = Field(ge=0, le=1)
    stack_class: float = Field(ge=0, le=1)
    orientations: float = Field(ge=0, le=1)
    access: float = Field(ge=0, le=1)


class Handling(ContractModel):
    version: int = Field(ge=1)
    category: ShortText
    fragility: Fragility = Fragility.MEDIUM
    compressibility: Compressibility = Compressibility.NONE
    stack_class: StackClass = StackClass.NEUTRAL
    can_support_weight: bool = False
    liquid_risk: bool = False
    legal_orientations: tuple[OrientationId, ...] = Field(min_length=1)
    access: AccessClass = AccessClass.NORMAL
    confidence: ConfidenceScores
    provenance: ShortText
    short_reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    needs_confirmation: tuple[ShortText, ...] = ()

    @model_validator(mode="after")
    def consistent_handling(self) -> "Handling":
        if len(set(self.legal_orientations)) != len(self.legal_orientations):
            raise ValueError("legal orientations must not contain duplicates")
        if self.stack_class == StackClass.TOP_ONLY and self.can_support_weight:
            raise ValueError("top-only items cannot be load-bearing")
        return self


class EnrichmentSuggestion(ContractModel):
    name: ShortText
    category: ShortText
    fragility: Fragility
    compressibility: Compressibility
    stack_class: StackClass
    can_support_weight: bool
    liquid_risk: bool
    allowed_orientations: tuple[OrientationId, ...] = Field(min_length=1)
    access: AccessClass
    short_reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    needs_confirmation: tuple[ShortText, ...] = ()
    confidence: ConfidenceScores

    @model_validator(mode="after")
    def consistent(self) -> "EnrichmentSuggestion":
        if len(set(self.allowed_orientations)) != len(self.allowed_orientations):
            raise ValueError("allowed orientations must not contain duplicates")
        if self.stack_class == StackClass.TOP_ONLY and self.can_support_weight:
            raise ValueError("top-only items cannot support weight")
        return self


class EnrichmentResult(ContractModel):
    suggestion: EnrichmentSuggestion
    provider: ShortText
    model_id: ShortText
    prompt_version: ShortText
    fallback_reason: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    cached: bool = False


class HandlingEdit(ContractModel):
    category: ShortText
    fragility: Fragility
    compressibility: Compressibility
    stack_class: StackClass
    can_support_weight: bool
    liquid_risk: bool
    legal_orientations: tuple[OrientationId, ...] = Field(min_length=1)
    access: AccessClass

    @model_validator(mode="after")
    def consistent(self) -> "HandlingEdit":
        if len(set(self.legal_orientations)) != len(self.legal_orientations):
            raise ValueError("legal orientations must not contain duplicates")
        if self.stack_class == StackClass.TOP_ONLY and self.can_support_weight:
            raise ValueError("top-only items cannot support weight")
        return self


class ItemConfirmationRequest(ContractModel):
    name: ShortText
    weight_g: float = Field(gt=0, le=LIMITS.max_item_weight_g)
    priority_stars: int = Field(ge=1, le=5)
    handling: HandlingEdit
    acknowledge_scale: bool = False


class ItemConfirmation(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    item_id: UUID
    version: int = Field(ge=1)
    generated_handling: Handling
    confirmed_handling: Handling
    confirmed_name: ShortText
    confirmed_weight_g: float = Field(gt=0, le=LIMITS.max_item_weight_g)
    confirmed_priority_stars: int = Field(ge=1, le=5)
    scale_acknowledged: bool
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ItemReview(ContractModel):
    item: "Item"
    latest_confirmation: ItemConfirmation | None = None
    questions: tuple[str, ...] = ()


class ItemDraft(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: ShortText | None = None
    weight_g: float = Field(gt=0, le=LIMITS.max_item_weight_g)
    priority_stars: int = Field(ge=1, le=5)
    display_weight_unit: WeightUnit


class Item(ItemDraft):
    stage: ItemStage = ItemStage.DRAFT
    asset_id: UUID | None = None
    geometry: Geometry | None = None
    handling: Handling | None = None
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    progress_stage: ProgressStage = ProgressStage.NONE

    @model_validator(mode="after")
    def stage_requirements(self) -> "Item":
        if self.stage == ItemStage.READY and (self.geometry is None or self.handling is None):
            raise ValueError("ready items require geometry and handling")
        if self.stage == ItemStage.FAILED and not self.error_code:
            raise ValueError("failed items require a recoverable error code")
        return self


class AssetBounds(ContractModel):
    minimum_m: tuple[float, float, float]
    maximum_m: tuple[float, float, float]

    @model_validator(mode="after")
    def ordered(self) -> "AssetBounds":
        if any(high < low for low, high in zip(self.minimum_m, self.maximum_m, strict=True)):
            raise ValueError("asset bounds must be ordered")
        return self


class AssetRecord(ContractModel):
    id: UUID
    item_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(gt=0)
    storage_path: str
    original_filename: ShortText
    stage: AssetStage
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    bounds: AssetBounds | None = None
    vertex_count: int | None = Field(default=None, ge=0)
    face_count: int | None = Field(default=None, ge=0)
    mesh_instance_count: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PreviewView(StrEnum):
    FRONT = "front"
    SIDE = "side"
    TOP = "top"
    THREE_QUARTER = "three_quarter"
    THUMBNAIL = "thumbnail"


class PreviewRecord(ContractModel):
    id: UUID
    item_id: UUID
    asset_id: UUID
    geometry_version: int = Field(ge=1)
    view: PreviewView
    renderer_version: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9._-]{1,80}$")]
    mime_type: str = Field(pattern=r"^image/(png|webp)$")
    byte_size: int = Field(gt=0)
    width: int = Field(gt=0, le=4096)
    height: int = Field(gt=0, le=4096)
    storage_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Suitcase(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: ShortText
    internal_dimensions_mm: DimensionsMm
    empty_weight_g: float = Field(ge=0, le=LIMITS.max_item_weight_g)
    baggage_limit_g: float = Field(gt=0, le=LIMITS.max_item_weight_g)
    clearance_mm: float = Field(default=0, ge=0, le=LIMITS.max_suitcase_clearance_mm)
    display_length_unit: LengthUnit
    display_weight_unit: WeightUnit

    @model_validator(mode="after")
    def has_capacity(self) -> "Suitcase":
        if self.baggage_limit_g <= self.empty_weight_g:
            raise ValueError("baggage limit must exceed empty suitcase weight")
        usable = self.internal_dimensions_mm.model_dump()
        if any(value - self.clearance_mm <= 0 for value in usable.values()):
            raise ValueError("clearance must leave positive usable dimensions")
        return self


class ItemInstance(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    item_id: UUID
    copy_number: int = Field(ge=1)
    priority_stars: int = Field(ge=1, le=5)
    must_pack: bool = False
    access_preference: AccessClass | None = None


class TripItem(ContractModel):
    item_id: UUID
    instances: tuple[ItemInstance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def references_match(self) -> "TripItem":
        if any(instance.item_id != self.item_id for instance in self.instances):
            raise ValueError("all instances must reference the trip item's library item")
        copy_numbers = [instance.copy_number for instance in self.instances]
        if len(set(copy_numbers)) != len(copy_numbers):
            raise ValueError("copy numbers must be unique within a trip item")
        return self


class Trip(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: ShortText
    suitcase: Suitcase
    items: tuple[TripItem, ...]

    @model_validator(mode="after")
    def unique_instances(self) -> "Trip":
        instance_ids = [instance.id for item in self.items for instance in item.instances]
        if len(instance_ids) > LIMITS.max_trip_instances:
            raise ValueError(f"trip supports at most {LIMITS.max_trip_instances} instances")
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("duplicate instance IDs are not allowed")
        return self


class StockTemplate(ContractModel):
    id: UUID
    name: ShortText
    category: ShortText
    dimensions_mm: DimensionsMm
    weight_g: float = Field(gt=0, le=LIMITS.max_item_weight_g)
    priority_stars: int = Field(default=3, ge=1, le=5)
    handling: HandlingEdit
    example_values: bool = True


class LibraryKind(StrEnum):
    CUSTOM = "custom"
    STOCK = "stock"


class LibraryItem(ContractModel):
    id: UUID
    kind: LibraryKind
    name: ShortText
    category: ShortText
    dimensions_mm: DimensionsMm | None = None
    weight_g: float = Field(gt=0, le=LIMITS.max_item_weight_g)
    priority_stars: int = Field(ge=1, le=5)
    handling: HandlingEdit | None = None
    ready: bool
    example_values: bool = False
    thumbnail_id: UUID | None = None
    review_route: str | None = None
    asset_id: UUID | None = None
    geometry: Geometry | None = None
    lifecycle: str = Field(default="ready", pattern=r"^(draft|ready|archived)$")
    archived: bool = False


class TripItemRequest(ContractModel):
    item_id: UUID
    quantity: int = Field(ge=0, le=LIMITS.max_trip_instances)
    priority_stars: int = Field(ge=1, le=5)
    must_pack: bool = False
    access_preference: AccessClass | None = None


class TripSummary(ContractModel):
    trip: Trip
    requested_item_weight_g: float = Field(ge=0)
    available_item_weight_g: float
    total_utility: int = Field(ge=0)
    warnings: tuple[str, ...] = ()


class TripPreflight(ContractModel):
    requested_instances: int = Field(ge=0)
    requested_weight_g: float = Field(ge=0)
    padded_volume_mm3: float = Field(ge=0)
    baggage_remaining_g: float
    missing_metadata: tuple[UUID, ...] = ()
    oversize_instances: tuple[UUID, ...] = ()
    mandatory_contradictions: tuple[str, ...] = ()
    actionable_messages: tuple[str, ...] = ()


class SnapshotBox(ContractModel):
    instance_id: UUID
    item_id: UUID
    copy_number: int = Field(ge=1)
    priority_stars: int = Field(ge=1, le=5)
    must_pack: bool
    effective_padded_dimensions_mm: DimensionsMm
    weight_g: float = Field(gt=0)
    geometry_version: int = Field(ge=1)
    handling_version: int = Field(ge=1)
    legal_orientations: tuple[OrientationId, ...] = Field(min_length=1)


class TripSnapshot(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    trip_id: UUID
    version: int = Field(ge=1)
    trip: Trip
    item_snapshots: tuple[LibraryItem, ...]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expanded_boxes: tuple[SnapshotBox, ...] = ()
    geometry_version: str = "geometry-v1"
    handling_confirmation_version: str = "handling-v1"
    solver_version: str = "packright-solver-v1"
    seed: int = 7


class Placement(ContractModel):
    instance_id: UUID
    item_id: UUID
    position_mm: tuple[float, float, float]
    dimensions_mm: DimensionsMm
    orientation_id: OrientationId
    orientation_matrix: Matrix3
    packing_order: int = Field(ge=1)
    support_ratio: float = Field(ge=0, le=1)


class ValidationViolation(ContractModel):
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
    message: ShortText
    instance_ids: tuple[UUID, ...] = ()
    measured_value: float | None = None


class PlanMetrics(ContractModel):
    packed_weight_g: float = Field(ge=0)
    remaining_allowance_g: float
    utilization: float = Field(ge=0, le=1)
    retained_utility: int = Field(ge=0)
    center_of_mass_mm: tuple[float, float, float] | None = None


class ValidationResult(ContractModel):
    validator_version: ShortText
    valid: bool
    violations: tuple[ValidationViolation, ...] = ()
    metrics: PlanMetrics | None = None
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def result_consistency(self) -> "ValidationResult":
        if self.valid and self.violations:
            raise ValueError("a valid result cannot contain violations")
        if not self.valid and not self.violations:
            raise ValueError("an invalid result must contain at least one violation")
        return self


class ExclusionEvidence(ContractModel):
    instance_id: UUID
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
    detail: ShortText


class PackingInstruction(ContractModel):
    number: int = Field(ge=1)
    instance_id: UUID
    item_name: ShortText
    copy_number: int = Field(ge=1)
    destination: ShortText
    orientation_label: ShortText
    handling_note: ShortText | None = None


class PlanExplanation(ContractModel):
    instructions: tuple[PackingInstruction, ...] = ()
    exclusions: tuple[str, ...] = ()
    balance_note: ShortText = "Center of mass is an approximate mass-at-box-center model, not a physical measurement."


class ProcessingJob(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    item_id: UUID
    stage: ProgressStage
    status: str = Field(pattern=r"^(running|completed|failed|retryable)$")
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    request_key: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operation_type: str = "geometry"
    requested_scale_correction: float | None = None
    renderer_version: str | None = None
    required_previews: tuple[PreviewView, ...] = ()
    retry_count: int = Field(default=0, ge=0)
    stable_input_reference: str | None = None


class PlanJob(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    trip_id: UUID
    snapshot_id: UUID
    kind: str = Field(pattern=r"^(plan|replan)$")
    status: PlanJobState = PlanJobState.QUEUED
    progress_stage: str = "queued"
    plan_id: UUID | None = None
    predecessor_plan_id: UUID | None = None
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    error_message: str | None = None
    idempotency_key: str | None = None
    request_hash: str | None = None
    seed: int = 7
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BaselineDiagnostic(ContractModel):
    name: str = Field(pattern=r"^(lowest_star_first|heaviest_first)$")
    state: str = Field(pattern=r"^(feasible|spatial_failure|budget_exhausted)$")
    retained_utility: int | None = Field(default=None, ge=0)


class SolverDiagnostics(ContractModel):
    selection_mode: str = Field(pattern=r"^(exact|bounded_beam)$")
    heuristic: bool
    candidate_subsets: int = Field(ge=0)
    placement_attempts: int = Field(ge=0)
    complete_layouts: int = Field(ge=0)
    validator_rejections: int = Field(ge=0)
    budget_seconds: float = Field(gt=0)
    baselines: tuple[BaselineDiagnostic, ...] = ()


class PackingPlan(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    trip_id: UUID
    state: PlanState = PlanState.QUEUED
    placements: tuple[Placement, ...] = ()
    excluded_instance_ids: tuple[UUID, ...] = ()
    validation: ValidationResult | None = None
    solver_version: ShortText
    seed: int
    runtime_ms: float = Field(ge=0)
    input_snapshot_version: int = Field(ge=1)
    snapshot_id: UUID | None = None
    snapshot: TripSnapshot | None = None
    predecessor_plan_id: UUID | None = None
    exclusion_evidence: tuple[ExclusionEvidence, ...] = ()
    instructions: tuple[PackingInstruction, ...] = ()
    diagnostics: SolverDiagnostics | None = None

    @model_validator(mode="after")
    def feasible_requires_validation(self) -> "PackingPlan":
        if self.state == PlanState.FEASIBLE and (self.validation is None or not self.validation.valid):
            raise ValueError("only an independent valid ValidationResult can authorize feasible status")
        placement_ids = [placement.instance_id for placement in self.placements]
        if len(set(placement_ids)) != len(placement_ids):
            raise ValueError("duplicate placement instance IDs are not allowed")
        if set(placement_ids) & set(self.excluded_instance_ids):
            raise ValueError("an instance cannot be both placed and excluded")
        return self
