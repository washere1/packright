from __future__ import annotations

import io
import os
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from fastapi import Request

from .config import Settings
from .repository import Repository
from .schemas import PreviewRecord, PreviewView


class PreviewError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def inspect_image(payload: bytes, settings: Settings) -> tuple[str, int, int]:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            if image.format not in {"PNG", "WEBP"}:
                raise PreviewError("invalid_preview", "Preview must be PNG or WebP.")
            width, height = image.size
            if width < 128 or height < 128 or width > settings.limits.max_preview_dimension_px or height > settings.limits.max_preview_dimension_px:
                raise PreviewError("invalid_preview_dimensions", "Preview dimensions are outside the supported range.")
            sample = image.convert("RGBA").resize((32, 32))
            extrema = sample.getextrema()
            visible = extrema[3][1] > 0
            color_range = sum(high - low for low, high in extrema[:3])
            if not visible or color_range < 6:
                raise PreviewError("blank_preview", "Preview appears blank or contains no visible model.")
            return ("image/png" if image.format == "PNG" else "image/webp", width, height)
    except UnidentifiedImageError:
        raise PreviewError("invalid_preview", "Preview bytes are not a supported image.") from None


async def receive_preview(
    request: Request, item_id: UUID, view: PreviewView, geometry_version: int,
    renderer_version: str, repository: Repository, settings: Settings,
) -> PreviewRecord:
    item = repository.get_item(item_id)
    geometry = repository.get_latest_geometry(item_id)
    if item is None or geometry is None or item.asset_id is None or geometry.version != geometry_version:
        raise PreviewError("stale_geometry", "Preview geometry version is missing or stale.", 409)
    existing = repository.find_preview(item.asset_id, geometry_version, view.value, renderer_version)
    if existing:
        return existing

    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > settings.limits.max_preview_bytes:
            raise PreviewError("preview_too_large", "Preview exceeds the 5 MB limit.", 413)
    mime_type, width, height = inspect_image(bytes(payload), settings)
    extension = "png" if mime_type == "image/png" else "webp"
    preview_id = uuid4()
    relative = Path("previews") / str(item.asset_id) / f"geometry-{geometry_version}" / renderer_version / f"{view.value}.{extension}"
    target = settings.runtime_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = settings.runtime_dir / "tmp" / f"{preview_id}.preview.part"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    preview = PreviewRecord(
        id=preview_id, item_id=item_id, asset_id=item.asset_id, geometry_version=geometry_version,
        view=view, renderer_version=renderer_version, mime_type=mime_type, byte_size=len(payload),
        width=width, height=height, storage_path=relative.as_posix(),
    )
    repository.save_preview(preview)
    return preview


def ensure_thumbnail(front: PreviewRecord, repository: Repository, settings: Settings) -> PreviewRecord:
    existing = repository.find_preview(front.asset_id, front.geometry_version, PreviewView.THUMBNAIL.value, front.renderer_version)
    if existing:
        return existing
    source = settings.runtime_dir / front.storage_path
    with Image.open(source) as image:
        image.thumbnail((256, 256), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.convert("RGB").save(output, format="WEBP", quality=82, method=6)
        payload = output.getvalue()
        width, height = image.size
    preview_id = uuid4()
    relative = Path("previews") / str(front.asset_id) / f"geometry-{front.geometry_version}" / front.renderer_version / "thumbnail.webp"
    target = settings.runtime_dir / relative
    temporary = settings.runtime_dir / "tmp" / f"{preview_id}.thumbnail.part"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    thumbnail = PreviewRecord(
        id=preview_id, item_id=front.item_id, asset_id=front.asset_id, geometry_version=front.geometry_version,
        view=PreviewView.THUMBNAIL, renderer_version=front.renderer_version, mime_type="image/webp",
        byte_size=len(payload), width=width, height=height, storage_path=relative.as_posix(),
    )
    repository.save_preview(thumbnail)
    return thumbnail
