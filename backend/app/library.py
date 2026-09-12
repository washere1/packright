from __future__ import annotations

from uuid import UUID, uuid4

from .repository import Repository
from .schemas import (
    ConfidenceScores, DimensionsMm, Geometry, Handling, HandlingEdit, Item, ItemStage,
    LibraryItem, LibraryKind, Matrix3, Orientation, ORIENTATION_MATRICES, ProgressStage, StockTemplate,
)


def edit_from_handling(handling: Handling) -> HandlingEdit:
    return HandlingEdit(**handling.model_dump(include={
        "category", "fragility", "compressibility", "stack_class", "can_support_weight",
        "liquid_risk", "legal_orientations", "access",
    }))


def stock_library_item(template: StockTemplate) -> LibraryItem:
    return LibraryItem(
        id=template.id, kind=LibraryKind.STOCK, name=template.name, category=template.category,
        dimensions_mm=template.dimensions_mm, weight_g=template.weight_g,
        priority_stars=template.priority_stars, handling=template.handling,
        ready=True, example_values=True,
    )


def custom_library_item(item: Item, repository: Repository) -> LibraryItem:
    current_version = item.geometry.version if item.geometry else None
    preview = next((record for record in repository.list_previews(item.id, current_version) if record.view.value == "thumbnail"), None)
    return LibraryItem(
        id=item.id, kind=LibraryKind.CUSTOM, name=item.name or "Untitled draft",
        category=item.handling.category if item.handling else "other",
        dimensions_mm=item.geometry.canonical_dimensions_mm if item.geometry else None,
        weight_g=item.weight_g, priority_stars=item.priority_stars,
        handling=edit_from_handling(item.handling) if item.handling else None,
        ready=item.stage == ItemStage.READY and item.geometry is not None and item.handling is not None and not repository.is_item_deleted(item.id),
        thumbnail_id=preview.id if preview else None,
        review_route=f"/review/{item.id}" if item.stage != ItemStage.READY else None,
        asset_id=item.asset_id,
        geometry=item.geometry,
        lifecycle="archived" if repository.is_item_deleted(item.id) else ("ready" if item.stage == ItemStage.READY and item.geometry is not None and item.handling is not None else "draft"),
        archived=repository.is_item_deleted(item.id),
    )


def list_library(repository: Repository, kind: str | None, search: str, category: str | None, lifecycle: str | None = None) -> list[LibraryItem]:
    records: list[LibraryItem] = []
    if kind in (None, "custom"):
        records.extend(custom_library_item(item, repository) for item in repository.list_items(include_deleted=lifecycle == "archived"))
    if kind in (None, "stock"):
        records.extend(stock_library_item(template) for template in repository.list_stock_templates())
    needle = search.strip().casefold()
    return [record for record in records if
            (not needle or needle in record.name.casefold()) and
            (not category or record.category.casefold() == category.casefold()) and
            (not lifecycle or record.lifecycle == lifecycle)]


def clone_template(template: StockTemplate, repository: Repository) -> Item:
    dims = template.dimensions_mm
    transform = (1000.0, 0, 0, 0, 0, 1000.0, 0, 0, 0, 0, 1000.0, 0, 0, 0, 0, 1)
    geometry = Geometry(
        version=1, asset_id=uuid4(), aabb_mm={"minimum": (0, 0, 0), "maximum": (dims.width, dims.height, dims.depth)},
        canonical_dimensions_mm=dims, geometric_center_mm=(dims.width / 2, dims.height / 2, dims.depth / 2),
        source_to_canonical=transform, canonical_to_source=tuple(value / 1000 if index in (0, 5, 10) else value for index, value in enumerate(transform)),
        box_volume_mm3=dims.width * dims.height * dims.depth, mesh_volume_mm3=None, fill_ratio=None,
        clearance_mm=DimensionsMm(width=max(4, dims.width * .02), height=max(4, dims.height * .02), depth=max(4, dims.depth * .02)),
        preview_camera_distance_mm=max(dims.width, dims.height, dims.depth) * 2,
        mesh_watertight=False,
        orientations=tuple(Orientation(id=identifier, matrix=Matrix3(values=matrix)) for identifier, matrix in ORIENTATION_MATRICES.items()),
        warnings=("example_template_geometry",),
    )
    confidence = ConfidenceScores(name=1, category=1, fragility=1, compressibility=1, stack_class=1, orientations=1, access=1)
    handling = Handling(
        version=1, **template.handling.model_dump(), confidence=confidence, provenance="stock_example",
        short_reason="Cloned from clearly labeled example template values.",
    )
    item = Item(
        name=f"{template.name} copy", weight_g=template.weight_g, priority_stars=template.priority_stars,
        display_weight_unit="g", stage=ItemStage.READY, geometry=geometry, handling=handling,
        progress_stage=ProgressStage.COMPLETE,
    )
    repository.save_item(item)
    return item


def resolve_library_item(item_id: UUID, repository: Repository, require_ready: bool = True) -> LibraryItem | None:
    item = repository.get_item(item_id)
    if item and not repository.is_item_deleted(item_id):
        record = custom_library_item(item, repository)
        return record if not require_ready or record.ready else None
    stock = repository.get_stock_template(item_id)
    return stock_library_item(stock) if stock else None
