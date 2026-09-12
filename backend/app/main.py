from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import perf_counter
from urllib.parse import unquote
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import PROJECT_ROOT, Limits, get_settings
from .ingestion import IngestionError, ingest_request
from .geometry import GeometryError, extract_geometry
from .enrichment import enrich_item
from .previews import PreviewError, ensure_thumbnail, receive_preview
from .repository import Repository
from .library import clone_template, list_library
from .stock import stock_templates
from .trips import TripError, preflight_trip, set_trip_item, snapshot_trip, summarize_trip
from .suitcases import SuitcaseBoundaryRequest, normalize_suitcase
from .solver import solve_snapshot
from .validation import validate_plan
from .explanation import explain_exclusions
from .schemas import (
    AssetBounds, AssetRecord, ConfidenceScores, EnrichmentResult, Geometry, Handling,
    Item, ItemConfirmation, ItemConfirmationRequest, ItemDraft, ItemReview, ItemStage,
    LibraryItem, PreviewRecord, PreviewView, ProgressStage, StockTemplate, Suitcase,
    PackingPlan, PlanExplanation, PlanJob, PlanJobState, ProcessingJob, ProgressStage, PlanState, Suitcase, Trip, TripItemRequest, TripSnapshot, TripSummary, TripPreflight, ValidationResult,
)

settings = get_settings()
repository = Repository(settings.runtime_dir / "packright.sqlite3")
logger = logging.getLogger("packright.api")
plan_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="packright-plan")


@asynccontextmanager
async def lifespan(_: FastAPI):
    for name in ("assets", "previews", "tmp"):
        (settings.runtime_dir / name).mkdir(parents=True, exist_ok=True)
    repository.initialize()
    recovered = repository.recover_processing_jobs()
    if recovered:
        logger.warning("recovered_interrupted_jobs count=%s", recovered)
    recovered_plans = repository.recover_plan_jobs()
    if recovered_plans:
        logger.warning("recovered_interrupted_plan_jobs count=%s", recovered_plans)
    repository.save_stock_templates(stock_templates())
    yield


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    service: str
    api_version: str


class CapabilityFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_supported: bool
    live_enrichment_configured: bool
    neutral_enrichment_fallback: bool


class PublicConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capabilities: CapabilityFlags
    limits: Limits
    units: dict[str, str]
    coordinates: dict[str, str]


class AssetUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: UUID
    asset_id: UUID
    stage: ItemStage
    progress_stage: ProgressStage
    received_bytes: int
    sha256: str
    bounds: AssetBounds
    vertex_count: int
    face_count: int
    mesh_instance_count: int
    warnings: tuple[str, ...] = ()


class GeometryProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    scale_correction: float = Field(default=1, gt=0, le=1000)


class ItemFieldsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    weight_g: float | None = Field(default=None, gt=0, le=100_000)
    priority_stars: int | None = Field(default=None, ge=1, le=5)


class CreateTripRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    suitcase: Suitcase
    selected_item_ids: tuple[UUID, ...] = ()


class TripItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=0, le=32)
    priority_stars: int = Field(ge=1, le=5)
    must_pack: bool = False
    access_preference: str | None = None


class CreatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: UUID | None = None
    predecessor_plan_id: UUID | None = None
    seed: int = 7


class CreateRootPlanRequest(CreatePlanRequest):
    trip_id: UUID


class ReplanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    suitcase: Suitcase | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    seed: int = 7


class PlanJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    seed: int = 7


class DemoPrepareResponse(BaseModel):
    trip_id: UUID
    suitcase_id: UUID
    snapshot_id: UUID
    plan_id: UUID
    item_ids: tuple[UUID, ...]


class DemoSeedResponse(BaseModel):
    trip_id: UUID
    item_ids: tuple[UUID, ...]


class DemoResetResponse(BaseModel):
    removed_records: int


app = FastAPI(title="PackRight API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dev_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID", "X-Upload-Filename", "X-Idempotency-Key"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "").strip()
    if not request_id or len(request_id) > 80 or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in request_id):
        request_id = str(uuid4())
    started = perf_counter()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            too_large = int(content_length) > settings.limits.max_upload_bytes
        except ValueError:
            too_large = False
        if too_large:
            response = JSONResponse(status_code=413, content={"detail": {"code": "too_large", "message": "Request body exceeds the configured limit."}})
            response.headers["X-Request-ID"] = request_id
            return response
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    elapsed_ms = (perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info("request request_id=%s method=%s path=%s status=%s duration_ms=%.1f", request_id, request.method, request.url.path, response.status_code, elapsed_ms)
    return response


def _idempotency_header(request: Request, operation: str) -> tuple[str, str] | None:
    raw = request.headers.get("x-idempotency-key", "").strip()
    if not raw:
        return None
    if len(raw) > 160 or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for character in raw):
        raise HTTPException(status_code=422, detail={"code": "invalid_idempotency_key", "message": "X-Idempotency-Key contains unsupported characters."})
    return f"{operation}:{raw}", operation


def _request_hash(payload: object | None) -> str | None:
    if payload is None:
        return None
    data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="packright-api", api_version="0.1.0")


@app.get("/api/config", response_model=PublicConfigResponse)
def public_config() -> PublicConfigResponse:
    return PublicConfigResponse(
        capabilities=CapabilityFlags(
            preview_supported=True,
            live_enrichment_configured=settings.gemini_configured,
            neutral_enrichment_fallback=True,
        ),
        limits=settings.limits,
        units={"length": "mm", "weight": "g", "glb_source": "m"},
        coordinates={"x": "width", "y": "vertical height", "z": "wheel side toward opening"},
    )


@app.get("/api/processing/status", response_model=list[ProcessingJob])
def processing_status() -> list[ProcessingJob]:
    return repository.list_processing_jobs(active_only=True)


@app.post("/api/processing/{job_id}/retry", response_model=ProcessingJob)
def retry_processing(job_id: UUID) -> ProcessingJob:
    job = repository.get_processing_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "processing_job_not_found", "message": "Processing job not found."})
    if job.status not in ("retryable", "failed"):
        raise HTTPException(status_code=409, detail={"code": "processing_job_not_retryable", "message": "This processing job is not ready for retry."})
    updated = job.model_copy(update={"status": "retryable", "error_code": None, "retry_count": job.retry_count + 1})
    repository.save_processing_job(updated)
    return updated


@app.post("/api/operations/demo/seed", response_model=DemoSeedResponse)
@app.post("/api/demo/seed", response_model=DemoSeedResponse)
def seed_demo() -> DemoSeedResponse:
    case = Suitcase(name="Demo carry-on", internal_dimensions_mm={"width": 550, "height": 350, "depth": 230}, empty_weight_g=2500, baggage_limit_g=10000, clearance_mm=8, display_length_unit="mm", display_weight_unit="g")
    trip = Trip(name="PackRight demo", suitcase=case, items=())
    repository.save_trip(trip); repository.mark_demo_record("trips", trip.id)
    chosen = [template for template in repository.list_stock_templates() if template.name in {"Book", "Camera"}]
    for template in chosen:
        # Stock templates are immutable; trip instances reference them without cloning personal records.
        trip = set_trip_item(trip, TripItemRequest(item_id=template.id, quantity=1, priority_stars=template.priority_stars, must_pack=template.name == "Book"), repository, settings.limits.max_trip_instances)
    repository.save_trip(trip)
    return DemoSeedResponse(trip_id=trip.id, item_ids=tuple(template.id for template in chosen))


@app.post("/api/operations/demo/prepare", response_model=DemoPrepareResponse)
@app.post("/api/demo/prepare", response_model=DemoPrepareResponse)
def prepare_demo() -> DemoPrepareResponse:
    # Preparation is deliberately deterministic and idempotent: the namespace is
    # reset first, then recreated from stock fixtures with a recorded seed.
    repository.reset_demo_records()
    suitcase = Suitcase(id=uuid5(NAMESPACE_URL, "packright-demo-suitcase-v1"), name="Demo carry-on", internal_dimensions_mm={"width": 550, "height": 350, "depth": 230}, empty_weight_g=2500, baggage_limit_g=10000, clearance_mm=8, display_length_unit="mm", display_weight_unit="g")
    trip = Trip(id=uuid5(NAMESPACE_URL, "packright-demo-trip-v1"), name="PackRight demo", suitcase=suitcase, items=())
    repository.save_suitcase(suitcase); repository.mark_demo_record("suitcases", suitcase.id)
    chosen = [template for template in repository.list_stock_templates() if template.name in {"Book", "Camera", "Shirt"}]
    for template in chosen:
        trip = set_trip_item(trip, TripItemRequest(item_id=template.id, quantity=1, priority_stars=template.priority_stars, must_pack=template.name == "Book"), repository, settings.limits.max_trip_instances)
        entry = next(value for value in trip.items if value.item_id == template.id)
        stable_instance = entry.instances[0].model_copy(update={"id": uuid5(NAMESPACE_URL, f"packright-demo-instance:{template.name.lower()}:v1")})
        trip = trip.model_copy(update={"items": tuple(value.model_copy(update={"instances": (stable_instance,)}) if value.item_id == template.id else value for value in trip.items)})
    repository.save_trip(trip); repository.mark_demo_record("trips", trip.id)
    snapshot = snapshot_trip(trip, repository); repository.mark_demo_record("trip_snapshots", snapshot.id)
    plan = solve_snapshot(snapshot, repository, settings.limits.solver_budget_seconds, seed=42); repository.mark_demo_record("plans", plan.id)
    return DemoPrepareResponse(trip_id=trip.id, suitcase_id=suitcase.id, snapshot_id=snapshot.id, plan_id=plan.id, item_ids=tuple(template.id for template in chosen))


@app.post("/api/operations/demo/reset", response_model=DemoResetResponse)
@app.post("/api/demo/reset", response_model=DemoResetResponse)
def reset_demo() -> DemoResetResponse:
    return DemoResetResponse(removed_records=repository.reset_demo_records())


@app.post("/api/items", response_model=Item, status_code=201)
def create_item_draft(payload: ItemDraft) -> Item:
    item = Item(**payload.model_dump(), stage=ItemStage.DRAFT, progress_stage=ProgressStage.NONE)
    repository.save_item(item)
    return item


@app.get("/api/items", response_model=list[Item])
def list_items(include_deleted: bool = False) -> list[Item]:
    return repository.list_items(include_deleted=include_deleted)


@app.get("/api/items/{item_id}", response_model=Item)
@app.get("/api/items/{item_id}/status", response_model=Item)
def get_item(item_id: UUID) -> Item:
    item = repository.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Item not found."})
    return item


@app.get("/api/items/{item_id}/asset", response_model=AssetRecord)
def get_item_asset(item_id: UUID) -> AssetRecord:
    asset = repository.get_latest_asset(item_id)
    if asset is None:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return asset


@app.post("/api/items/{item_id}/asset", response_model=AssetUploadResponse)
async def upload_item_asset(item_id: UUID, request: Request) -> AssetUploadResponse:
    item = repository.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Item not found."})
    filename = unquote(request.headers.get("x-upload-filename", ""))
    receiving = item.model_copy(update={"stage": ItemStage.UPLOADED, "progress_stage": ProgressStage.UPLOAD, "error_code": None})
    repository.save_item(receiving)
    try:
        result = await ingest_request(request, item_id, filename, repository, settings)
    except IngestionError as error:
        upload_codes = {"invalid_file_type", "invalid_content_length", "too_large", "invalid_glb", "external_reference"}
        failed = receiving.model_copy(
            update={
                "stage": ItemStage.FAILED,
                "progress_stage": ProgressStage.UPLOAD if error.code in upload_codes else ProgressStage.GEOMETRY,
                "error_code": error.code,
            }
        )
        repository.save_item(failed)
        raise HTTPException(
            status_code=error.status_code, detail={"code": error.code, "message": error.message}
        ) from None

    processing = receiving.model_copy(
        update={
            "asset_id": result.asset.id, "geometry": None, "handling": None,
            "stage": ItemStage.PROCESSING, "progress_stage": ProgressStage.GEOMETRY,
        }
    )
    repository.save_item(processing)
    warnings = ("This model matches an earlier upload. You can continue if reuse is intentional.",) if result.duplicate_of else ()
    return AssetUploadResponse(
        item_id=item_id, asset_id=result.asset.id, stage=processing.stage,
        progress_stage=processing.progress_stage, received_bytes=result.asset.byte_size,
        sha256=result.asset.sha256, bounds=result.asset.bounds,
        vertex_count=result.asset.vertex_count, face_count=result.asset.face_count,
        mesh_instance_count=result.asset.mesh_instance_count, warnings=warnings,
    )


@app.post("/api/items/{item_id}/process", response_model=Geometry)
async def process_item_geometry(item_id: UUID, request: Request, payload: GeometryProcessRequest = GeometryProcessRequest()) -> Geometry:
    item = repository.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Item not found."})
    job = ProcessingJob(item_id=item_id, stage=ProgressStage.GEOMETRY, status="running", request_key=request.headers.get("x-idempotency-key"), operation_type="geometry", requested_scale_correction=payload.scale_correction, stable_input_reference=f"item:{item_id}")
    repository.save_processing_job(job)
    try:
        geometry = await asyncio.to_thread(extract_geometry, item_id, repository, settings, payload.scale_correction)
    except GeometryError as error:
        repository.save_processing_job(job.model_copy(update={"status": "failed", "error_code": error.code}))
        failed = item.model_copy(
            update={"stage": ItemStage.FAILED, "progress_stage": ProgressStage.GEOMETRY, "error_code": error.code}
        )
        repository.save_item(failed)
        raise HTTPException(status_code=422, detail={"code": error.code, "message": error.message}) from None
    updated = item.model_copy(update={
        "geometry": geometry, "stage": ItemStage.PROCESSING,
        "progress_stage": ProgressStage.PREVIEWS, "error_code": None,
    })
    repository.save_item(updated)
    repository.save_processing_job(job.model_copy(update={"status": "completed", "error_code": None}))
    return geometry


@app.get("/api/items/{item_id}/geometry", response_model=Geometry)
def get_item_geometry(item_id: UUID) -> Geometry:
    geometry = repository.get_latest_geometry(item_id)
    if geometry is None:
        raise HTTPException(status_code=404, detail={"code": "geometry_not_found", "message": "Geometry not found."})
    return geometry


@app.get("/api/assets/{asset_id}/model.glb", response_class=FileResponse)
def read_asset(asset_id: UUID) -> FileResponse:
    with repository.connect() as connection:
        row = connection.execute("SELECT storage_path FROM assets WHERE id=? AND stage='ingested'", (str(asset_id),)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    target = (settings.runtime_dir / row["storage_path"]).resolve()
    asset_root = (settings.runtime_dir / "assets").resolve()
    if asset_root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail={"code": "asset_missing", "message": "Stored asset is missing."})
    return FileResponse(target, media_type="model/gltf-binary", filename="model.glb")


@app.post("/api/items/{item_id}/previews", response_model=PreviewRecord)
async def upload_preview(
    item_id: UUID, request: Request, view: PreviewView, geometry_version: int = 1,
    renderer_version: str = "three-r180-v1",
) -> PreviewRecord:
    if not renderer_version or len(renderer_version) > 80 or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in renderer_version):
        raise HTTPException(status_code=422, detail={"code": "invalid_renderer_version", "message": "Renderer version is invalid."})
    try:
        preview = await receive_preview(
            request, item_id, view, geometry_version, renderer_version, repository, settings,
        )
        if view == PreviewView.FRONT:
            ensure_thumbnail(preview, repository, settings)
    except PreviewError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message}) from None
    item = repository.get_item(item_id)
    geometry = repository.get_latest_geometry(item_id)
    if item and geometry:
        available = {record.view for record in repository.list_previews(item_id, geometry.version)}
        required = {PreviewView.FRONT, PreviewView.SIDE, PreviewView.TOP, PreviewView.THREE_QUARTER}
        if required.issubset(available):
            repository.save_item(item.model_copy(update={"progress_stage": ProgressStage.ENRICHMENT}))
    return preview


@app.get("/api/items/{item_id}/previews", response_model=list[PreviewRecord])
def list_item_previews(item_id: UUID, geometry_version: int | None = None) -> list[PreviewRecord]:
    return repository.list_previews(item_id, geometry_version)


@app.get("/api/previews/{preview_id}", response_class=FileResponse)
def read_preview(preview_id: UUID) -> FileResponse:
    preview = repository.get_preview(preview_id)
    if preview is None:
        raise HTTPException(status_code=404, detail={"code": "preview_not_found", "message": "Preview not found."})
    target = (settings.runtime_dir / preview.storage_path).resolve()
    preview_root = (settings.runtime_dir / "previews").resolve()
    if preview_root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail={"code": "preview_missing", "message": "Preview file is missing."})
    return FileResponse(target, media_type=preview.mime_type)


@app.post("/api/items/{item_id}/enrich", response_model=EnrichmentResult)
async def enrich_item_metadata(item_id: UUID) -> EnrichmentResult:
    try:
        return await asyncio.to_thread(enrich_item, item_id, repository, settings)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail={"code": "enrichment_prerequisites_missing", "message": "Item geometry is required before enrichment."},
        ) from None


def _review_questions(item: Item) -> tuple[str, ...]:
    questions: list[str] = []
    if item.geometry and item.geometry.requires_scale_confirmation:
        questions.append("suspicious_scale")
    if item.handling:
        confirmation_text = " ".join(item.handling.needs_confirmation).casefold()
        if "liquid" in confirmation_text or "container" in confirmation_text:
            questions.append("liquid_container")
        if item.handling.provenance == "neutral_fallback" or min(item.handling.confidence.model_dump().values()) < .55:
            questions.append("uncertain_handling")
    return tuple(dict.fromkeys(questions))


@app.get("/api/items/{item_id}/review", response_model=ItemReview)
def get_item_review(item_id: UUID) -> ItemReview:
    item = repository.get_item(item_id)
    if item is None or repository.is_item_deleted(item_id):
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Item not found."})
    return ItemReview(item=item, latest_confirmation=repository.latest_confirmation(item_id), questions=_review_questions(item))


@app.patch("/api/items/{item_id}", response_model=Item)
def update_item_fields(item_id: UUID, payload: ItemFieldsUpdate) -> Item:
    item = repository.get_item(item_id)
    if item is None or repository.is_item_deleted(item_id):
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Item not found."})
    changes = payload.model_dump(exclude_none=True)
    updated = item.model_copy(update=changes)
    repository.save_item(updated)
    return updated


@app.post("/api/items/{item_id}/confirm", response_model=ItemConfirmation)
def confirm_item(item_id: UUID, request: Request, payload: ItemConfirmationRequest) -> ItemConfirmation:
    cached, identity = _cached_idempotent(request, f"confirm:{item_id}", ItemConfirmation, payload)
    if cached is not None:
        return cached
    item = repository.get_item(item_id)
    if item is None or repository.is_item_deleted(item_id):
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Item not found."})
    if item.geometry is None or item.handling is None:
        raise HTTPException(status_code=409, detail={"code": "review_incomplete", "message": "Geometry and handling are required before confirmation."})
    if item.geometry.requires_scale_confirmation and not payload.acknowledge_scale:
        raise HTTPException(status_code=422, detail={"code": "scale_acknowledgement_required", "message": "Confirm or correct the model scale before saving."})
    version = repository.next_confirmation_version(item_id)
    confirmed_handling = Handling(
        version=version, **payload.handling.model_dump(), confidence=item.handling.confidence,
        provenance="user_confirmed", short_reason=item.handling.short_reason, needs_confirmation=(),
    )
    confirmation = ItemConfirmation(
        item_id=item_id, version=version, generated_handling=item.handling,
        confirmed_handling=confirmed_handling, confirmed_name=payload.name,
        confirmed_weight_g=payload.weight_g, confirmed_priority_stars=payload.priority_stars,
        scale_acknowledged=payload.acknowledge_scale,
    )
    ready = item.model_copy(update={
        "name": payload.name, "weight_g": payload.weight_g, "priority_stars": payload.priority_stars,
        "handling": confirmed_handling, "stage": ItemStage.READY, "progress_stage": ProgressStage.COMPLETE,
        "error_code": None,
    })
    repository.confirm_item(ready, confirmation)
    if identity: repository.save_idempotent_response(identity[0], identity[1], confirmation, 200, _request_hash(payload))
    return confirmation


@app.delete("/api/items/{item_id}")
def delete_item(item_id: UUID) -> dict[str, bool]:
    if not repository.soft_delete_item(item_id):
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Item not found."})
    return {"deleted": True}


@app.post("/api/items/{item_id}/restore", response_model=Item)
def restore_item(item_id: UUID) -> Item:
    item = repository.get_item(item_id)
    if item is None or not repository.is_item_deleted(item_id):
        raise HTTPException(status_code=404, detail={"code": "item_not_found", "message": "Archived item not found."})
    with repository.connect() as connection:
        connection.execute("DELETE FROM deleted_items WHERE item_id=?", (str(item_id),))
    return item


@app.get("/api/library", response_model=list[LibraryItem])
def get_library(kind: str | None = None, search: str = "", category: str | None = None, lifecycle: str | None = None) -> list[LibraryItem]:
    if kind not in (None, "custom", "stock"):
        raise HTTPException(status_code=422, detail={"code": "invalid_library_kind", "message": "Library kind must be custom or stock."})
    if lifecycle not in (None, "draft", "ready", "archived"):
        raise HTTPException(status_code=422, detail={"code": "invalid_lifecycle", "message": "Lifecycle must be draft, ready, or archived."})
    return list_library(repository, kind, search, category, lifecycle)


@app.get("/api/stock", response_model=list[StockTemplate])
def get_stock_templates() -> list[StockTemplate]:
    return repository.list_stock_templates()


@app.post("/api/stock/{template_id}/clone", response_model=Item, status_code=201)
def clone_stock_template(template_id: UUID) -> Item:
    template = repository.get_stock_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Stock template not found."})
    return clone_template(template, repository)


@app.post("/api/trips", response_model=TripSummary, status_code=201)
def create_trip(payload: CreateTripRequest) -> TripSummary:
    trip = Trip(name=payload.name, suitcase=payload.suitcase, items=())
    for item_id in payload.selected_item_ids:
        record = repository.get_item(item_id)
        priority = record.priority_stars if record else 3
        try:
            trip = set_trip_item(trip, TripItemRequest(item_id=item_id, quantity=1, priority_stars=priority), repository, settings.limits.max_trip_instances)
        except TripError as error:
            raise HTTPException(status_code=409, detail={"code": error.code, "message": error.message}) from None
    repository.save_trip(trip)
    return summarize_trip(trip, repository)


@app.get("/api/trips", response_model=list[TripSummary])
def list_trips() -> list[TripSummary]:
    return [summarize_trip(trip, repository) for trip in repository.list_trips()]


@app.get("/api/trips/{trip_id}", response_model=TripSummary)
def get_trip(trip_id: UUID) -> TripSummary:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    return summarize_trip(trip, repository)


@app.patch("/api/trips/{trip_id}", response_model=TripSummary)
def update_trip(trip_id: UUID, payload: CreateTripRequest) -> TripSummary:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    updated = trip.model_copy(update={"name": payload.name, "suitcase": payload.suitcase})
    repository.save_trip(updated)
    return summarize_trip(updated, repository)


@app.post("/api/trips/{trip_id}/items", response_model=TripSummary)
def update_trip_item(trip_id: UUID, payload: TripItemRequest) -> TripSummary:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    try:
        updated = set_trip_item(trip, payload, repository, settings.limits.max_trip_instances)
    except TripError as error:
        raise HTTPException(status_code=409, detail={"code": error.code, "message": error.message}) from None
    repository.save_trip(updated)
    return summarize_trip(updated, repository)


@app.put("/api/trips/{trip_id}/items/{item_id}", response_model=TripSummary)
def put_trip_item(trip_id: UUID, item_id: UUID, payload: TripItemUpdateRequest) -> TripSummary:
    return update_trip_item(trip_id, TripItemRequest(item_id=item_id, **payload.model_dump()))


@app.delete("/api/trips/{trip_id}/items/{item_id}", response_model=TripSummary)
def delete_trip_item(trip_id: UUID, item_id: UUID) -> TripSummary:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    updated = trip.model_copy(update={"items": tuple(entry for entry in trip.items if entry.item_id != item_id)})
    repository.save_trip(updated)
    return summarize_trip(updated, repository)


@app.get("/api/trips/{trip_id}/preflight", response_model=TripPreflight)
def get_trip_preflight(trip_id: UUID) -> TripPreflight:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    return preflight_trip(trip, repository)


@app.post("/api/trips/{trip_id}/snapshot", response_model=TripSnapshot, status_code=201)
def create_trip_snapshot(trip_id: UUID) -> TripSnapshot:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    try:
        return snapshot_trip(trip, repository)
    except TripError as error:
        raise HTTPException(status_code=409, detail={"code": error.code, "message": error.message}) from None


@app.get("/api/trips/{trip_id}/snapshots", response_model=list[TripSnapshot])
def get_trip_snapshots(trip_id: UUID) -> list[TripSnapshot]:
    if repository.get_trip(trip_id) is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    return repository.list_trip_snapshots(trip_id)


@app.post("/api/suitcases", response_model=Suitcase, status_code=201)
def create_suitcase(payload: SuitcaseBoundaryRequest) -> Suitcase:
    suitcase = normalize_suitcase(payload)
    repository.save_suitcase(suitcase)
    return suitcase


@app.get("/api/suitcases", response_model=list[Suitcase])
def list_suitcases() -> list[Suitcase]:
    return repository.list_suitcases()


@app.get("/api/suitcases/{suitcase_id}", response_model=Suitcase)
def get_suitcase(suitcase_id: UUID) -> Suitcase:
    suitcase = repository.get_suitcase(suitcase_id)
    if suitcase is None:
        raise HTTPException(status_code=404, detail={"code": "suitcase_not_found", "message": "Suitcase preset not found."})
    return suitcase


@app.patch("/api/suitcases/{suitcase_id}", response_model=Suitcase)
def update_suitcase(suitcase_id: UUID, payload: SuitcaseBoundaryRequest) -> Suitcase:
    if repository.get_suitcase(suitcase_id) is None:
        raise HTTPException(status_code=404, detail={"code": "suitcase_not_found", "message": "Suitcase preset not found."})
    suitcase = normalize_suitcase(payload, suitcase_id)
    repository.save_suitcase(suitcase)
    return suitcase


@app.delete("/api/suitcases/{suitcase_id}")
def delete_suitcase(suitcase_id: UUID) -> dict[str, bool]:
    if not repository.delete_suitcase(suitcase_id):
        raise HTTPException(status_code=404, detail={"code": "suitcase_not_found", "message": "Suitcase preset not found."})
    return {"deleted": True}


def _solve_trip_plan(trip_id: UUID, payload: CreatePlanRequest, predecessor_plan_id: UUID | None = None) -> PackingPlan:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    if payload.snapshot_id:
        snapshot = repository.get_trip_snapshot(payload.snapshot_id)
        if snapshot is None or snapshot.trip_id != trip_id:
            raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Trip snapshot not found."})
    else:
        try: snapshot = snapshot_trip(trip, repository)
        except TripError as error:
            raise HTTPException(status_code=409, detail={"code": error.code, "message": error.message}) from None
    return solve_snapshot(snapshot, repository, settings.limits.solver_budget_seconds, predecessor_plan_id if predecessor_plan_id is not None else payload.predecessor_plan_id, payload.seed)


def _execute_plan_job(job: PlanJob) -> None:
    running = job.model_copy(update={"status": PlanJobState.RUNNING, "progress_stage": "solving", "updated_at": datetime.now(timezone.utc)})
    repository.save_plan_job(running)
    try:
        snapshot = repository.get_trip_snapshot(job.snapshot_id)
        if snapshot is None:
            raise ValueError("snapshot_not_found")
        plan = solve_snapshot(snapshot, repository, settings.limits.solver_budget_seconds, job.predecessor_plan_id, job.seed)
    except Exception:
        logger.exception("plan_job_failed job_id=%s", job.id)
        repository.save_plan_job(running.model_copy(update={"status": PlanJobState.FAILED, "progress_stage": "failed", "error_code": "plan_job_failed", "error_message": "The plan operation failed. Retry the operation or inspect the prior plan.", "updated_at": datetime.now(timezone.utc)}))
        return
    repository.save_plan_job(running.model_copy(update={"status": PlanJobState.COMPLETED, "progress_stage": "completed", "plan_id": plan.id, "updated_at": datetime.now(timezone.utc)}))


def _submit_plan_job(job: PlanJob) -> PlanJob:
    repository.save_plan_job(job)
    plan_executor.submit(_execute_plan_job, job)
    return job


@app.post("/api/trips/{trip_id}/plan-jobs", response_model=PlanJob, status_code=202)
def create_plan_job(trip_id: UUID, request: Request, payload: PlanJobRequest = PlanJobRequest()) -> PlanJob:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    cached, identity = _cached_idempotent(request, f"plan-job:{trip_id}", PlanJob, payload)
    if cached is not None:
        return cached
    try:
        snapshot = snapshot_trip(trip, repository)
    except TripError as error:
        raise HTTPException(status_code=409, detail={"code": error.code, "message": error.message}) from None
    job = PlanJob(trip_id=trip_id, snapshot_id=snapshot.id, kind="plan", seed=payload.seed,
                  idempotency_key=identity[0] if identity else None, request_hash=_request_hash(payload))
    job = _submit_plan_job(job)
    if identity:
        repository.save_idempotent_response(identity[0], identity[1], job, 202, _request_hash(payload))
    return job


@app.get("/api/plan-jobs/{job_id}", response_model=PlanJob)
def get_plan_job(job_id: UUID) -> PlanJob:
    job = repository.get_plan_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "plan_job_not_found", "message": "Plan job not found."})
    return job


@app.get("/api/plan-jobs", response_model=list[PlanJob])
def list_plan_jobs(trip_id: UUID | None = None) -> list[PlanJob]:
    return repository.list_plan_jobs(trip_id)


@app.post("/api/plan-jobs/{job_id}/retry", response_model=PlanJob, status_code=202)
def retry_plan_job(job_id: UUID) -> PlanJob:
    job = repository.get_plan_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "plan_job_not_found", "message": "Plan job not found."})
    if job.status not in (PlanJobState.RETRYABLE, PlanJobState.FAILED):
        raise HTTPException(status_code=409, detail={"code": "plan_job_not_retryable", "message": "This plan job is not ready for retry."})
    return _submit_plan_job(job.model_copy(update={"status": PlanJobState.QUEUED, "progress_stage": "queued", "error_code": None, "error_message": None, "updated_at": datetime.now(timezone.utc)}))


def _cached_idempotent(request: Request, operation: str, model_type, payload: object | None = None):
    identity = _idempotency_header(request, operation)
    if identity is None:
        return None, None
    cached = repository.get_idempotent_response(identity[0], identity[1])
    if cached and cached[2] and _request_hash(payload) and cached[2] != _request_hash(payload):
        raise HTTPException(status_code=409, detail={"code": "idempotency_conflict", "message": "This idempotency key was already used with a different request body."})
    return (model_type.model_validate_json(cached[0]), identity) if cached else (None, identity)


@app.post("/api/trips/{trip_id}/plans", response_model=PackingPlan, status_code=201)
async def create_plan(trip_id: UUID, request: Request, payload: CreatePlanRequest = CreatePlanRequest()) -> PackingPlan:
    cached, identity = _cached_idempotent(request, f"plan:{trip_id}", PackingPlan, payload)
    if cached is not None:
        return cached
    plan = await asyncio.to_thread(_solve_trip_plan, trip_id, payload)
    if identity: repository.save_idempotent_response(identity[0], identity[1], plan, 201, _request_hash(payload))
    return plan


@app.post("/api/plans", response_model=PackingPlan, status_code=201)
async def create_plan_root(request: Request, payload: CreateRootPlanRequest) -> PackingPlan:
    cached, identity = _cached_idempotent(request, f"plan:{payload.trip_id}", PackingPlan, payload)
    if cached is not None:
        return cached
    plan = await asyncio.to_thread(_solve_trip_plan, payload.trip_id, payload)
    if identity: repository.save_idempotent_response(identity[0], identity[1], plan, 201, _request_hash(payload))
    return plan


@app.get("/api/plans/{plan_id}", response_model=PackingPlan)
def get_plan(plan_id: UUID) -> PackingPlan:
    plan = repository.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail={"code": "plan_not_found", "message": "Plan not found."})
    return plan


@app.post("/api/plans/{plan_id}/validate", response_model=ValidationResult)
def validate_saved_plan(plan_id: UUID) -> ValidationResult:
    plan = repository.get_plan(plan_id)
    if plan is None or plan.snapshot_id is None:
        raise HTTPException(status_code=404, detail={"code": "plan_not_found", "message": "Plan or immutable snapshot not found."})
    snapshot = repository.get_trip_snapshot(plan.snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Plan snapshot not found."})
    return validate_plan(plan, snapshot)


@app.post("/api/plans/{plan_id}/replan", response_model=PackingPlan, status_code=201)
async def replan_saved_plan(plan_id: UUID, request: Request, payload: ReplanRequest = ReplanRequest()) -> PackingPlan:
    predecessor = repository.get_plan(plan_id)
    if predecessor is None:
        raise HTTPException(status_code=404, detail={"code": "plan_not_found", "message": "Plan not found."})
    cached, identity = _cached_idempotent(request, f"replan:{plan_id}", PackingPlan, payload)
    if cached is not None:
        return cached
    trip = repository.get_trip(predecessor.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    if payload.suitcase is not None or payload.name is not None:
        trip = trip.model_copy(update={"suitcase": payload.suitcase or trip.suitcase, "name": payload.name or trip.name})
        repository.save_trip(trip)
    plan = await asyncio.to_thread(_solve_trip_plan, trip.id, CreatePlanRequest(seed=payload.seed), predecessor.id)
    if identity: repository.save_idempotent_response(identity[0], identity[1], plan, 201, _request_hash(payload))
    return plan


@app.post("/api/plans/{plan_id}/replan-jobs", response_model=PlanJob, status_code=202)
def create_replan_job(plan_id: UUID, request: Request, payload: ReplanRequest = ReplanRequest()) -> PlanJob:
    predecessor = repository.get_plan(plan_id)
    if predecessor is None:
        raise HTTPException(status_code=404, detail={"code": "plan_not_found", "message": "Plan not found."})
    cached, identity = _cached_idempotent(request, f"replan-job:{plan_id}", PlanJob, payload)
    if cached is not None:
        return cached
    trip = repository.get_trip(predecessor.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    candidate = trip.model_copy(update={
        "suitcase": payload.suitcase or trip.suitcase,
        "name": payload.name or trip.name,
    })
    try:
        # Store the new immutable snapshot before updating the mutable trip.
        snapshot = snapshot_trip(candidate, repository)
    except TripError as error:
        raise HTTPException(status_code=409, detail={"code": error.code, "message": error.message}) from None
    if payload.suitcase is not None or payload.name is not None:
        repository.save_trip(candidate)
    job = PlanJob(trip_id=candidate.id, snapshot_id=snapshot.id, kind="replan", predecessor_plan_id=predecessor.id,
                  seed=payload.seed, idempotency_key=identity[0] if identity else None, request_hash=_request_hash(payload))
    job = _submit_plan_job(job)
    if identity:
        repository.save_idempotent_response(identity[0], identity[1], job, 202, _request_hash(payload))
    return job


@app.get("/api/plans/{plan_id}/instructions", response_model=PlanExplanation)
def get_plan_instructions(plan_id: UUID) -> PlanExplanation:
    plan = repository.get_plan(plan_id)
    if plan is None or plan.snapshot_id is None:
        raise HTTPException(status_code=404, detail={"code": "plan_not_found", "message": "Plan or immutable snapshot not found."})
    snapshot = repository.get_trip_snapshot(plan.snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Plan snapshot not found."})
    from .explanation import generate_instructions
    return PlanExplanation(instructions=generate_instructions(plan, snapshot), exclusions=explain_exclusions(plan, snapshot))


@app.get("/api/trips/{trip_id}/plans", response_model=list[PackingPlan])
def list_trip_plans(trip_id: UUID) -> list[PackingPlan]:
    if repository.get_trip(trip_id) is None:
        raise HTTPException(status_code=404, detail={"code": "trip_not_found", "message": "Trip not found."})
    return repository.list_plans(trip_id)


frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        candidate = (frontend_dist / path).resolve()
        if candidate.is_file() and frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")
