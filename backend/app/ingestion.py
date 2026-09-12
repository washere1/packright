from __future__ import annotations

import asyncio
import json
import math
import os
import struct
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request

from .config import Limits, Settings
from .repository import Repository
from .schemas import AssetBounds, AssetRecord, AssetStage

JSON_CHUNK = b"JSON"
BIN_CHUNK = b"BIN\x00"
VALID_COMPONENT_TYPES = {5120, 5121, 5122, 5123, 5125, 5126}
VALID_ACCESSOR_TYPES = {"SCALAR", "VEC2", "VEC3", "VEC4", "MAT2", "MAT3", "MAT4"}
COMPONENT_SIZES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
INDEX_FORMATS = {5121: "B", 5123: "H", 5125: "I"}


class IngestionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class IngestionResult:
    asset: AssetRecord
    duplicate_of: UUID | None


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise IngestionError("invalid_glb", f"The GLB contains an invalid {field}.")
    return value


def validate_glb_structure(path: Path, limits: Limits) -> dict[str, Any]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise IngestionError("invalid_glb", "The file is too short to be a GLB container.")
        magic, version, declared_length = struct.unpack("<4sII", header)
        if magic != b"glTF" or version != 2 or declared_length != size:
            raise IngestionError("invalid_glb", "The GLB header is malformed or unsupported.")

        chunks: list[tuple[bytes, bytes]] = []
        consumed = 12
        while consumed < size:
            chunk_header = stream.read(8)
            if len(chunk_header) != 8:
                raise IngestionError("invalid_glb", "The GLB has a truncated chunk header.")
            chunk_length, chunk_type = struct.unpack("<I4s", chunk_header)
            consumed += 8
            if chunk_length % 4 != 0 or consumed + chunk_length > size:
                raise IngestionError("invalid_glb", "The GLB has an invalid chunk length.")
            if chunk_type == JSON_CHUNK and chunk_length > limits.max_glb_json_bytes:
                raise IngestionError("unreasonable_geometry", "The GLB metadata exceeds the configured limit.")
            chunk_data = stream.read(chunk_length)
            if len(chunk_data) != chunk_length:
                raise IngestionError("invalid_glb", "The GLB has a truncated chunk.")
            chunks.append((chunk_type, chunk_data))
            consumed += chunk_length

    if not chunks or chunks[0][0] != JSON_CHUNK or sum(kind == JSON_CHUNK for kind, _ in chunks) != 1:
        raise IngestionError("invalid_glb", "The GLB must contain one leading JSON chunk.")
    if sum(kind == BIN_CHUNK for kind, _ in chunks) > 1 or any(kind not in {JSON_CHUNK, BIN_CHUNK} for kind, _ in chunks):
        raise IngestionError("invalid_glb", "The GLB contains unsupported chunks.")

    try:
        document = json.loads(chunks[0][1].rstrip(b" \x00").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise IngestionError("invalid_glb", "The GLB JSON metadata is malformed.") from None
    if not isinstance(document, dict) or str(document.get("asset", {}).get("version", "")).split(".")[0] != "2":
        raise IngestionError("invalid_glb", "The GLB does not declare glTF 2.x metadata.")

    nodes = document.get("nodes", [])
    if not isinstance(nodes, list) or len(nodes) > limits.max_scene_nodes:
        raise IngestionError("unreasonable_geometry", "The GLB scene has too many nodes.")
    for node in nodes:
        if not isinstance(node, dict):
            raise IngestionError("invalid_glb", "The GLB contains an invalid node.")
        for key, length in (("matrix", 16), ("translation", 3), ("rotation", 4), ("scale", 3)):
            if key in node and (not isinstance(node[key], list) or len(node[key]) != length):
                raise IngestionError("invalid_glb", f"The GLB contains an invalid node {key}.")
            if key in node and any(
                not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
                for value in node[key]
            ):
                raise IngestionError("nonfinite_transform", "The GLB contains a nonfinite node transform.")
        children = node.get("children", [])
        if not isinstance(children, list) or any(
            not isinstance(child, int) or isinstance(child, bool) or child < 0 or child >= len(nodes) for child in children
        ):
            raise IngestionError("invalid_glb", "A node references an invalid child.")

    buffers = document.get("buffers", [])
    if not isinstance(buffers, list) or not buffers:
        raise IngestionError("invalid_glb", "The GLB does not declare an embedded buffer.")
    if any(not isinstance(buffer, dict) or buffer.get("uri") for buffer in buffers):
        raise IngestionError("external_reference", "External buffer references are not allowed.")
    if len(buffers) != 1:
        raise IngestionError("external_reference", "GLB uploads must use one embedded binary buffer.")

    for image in document.get("images", []):
        if not isinstance(image, dict):
            raise IngestionError("invalid_glb", "The GLB contains an invalid image entry.")
        uri = image.get("uri")
        if uri and (not isinstance(uri, str) or not uri.startswith("data:")):
            raise IngestionError("external_reference", "External image references are not allowed.")

    binary_chunks = [data for kind, data in chunks if kind == BIN_CHUNK]
    binary_size = len(binary_chunks[0]) if binary_chunks else 0
    declared_buffer_size = _integer(buffers[0].get("byteLength"), "buffer byte length")
    if declared_buffer_size > binary_size or binary_size - declared_buffer_size > 3:
        raise IngestionError("invalid_glb", "The embedded buffer length does not match the binary chunk.")

    buffer_views = document.get("bufferViews", [])
    if not isinstance(buffer_views, list):
        raise IngestionError("invalid_glb", "The GLB contains invalid buffer views.")
    for view in buffer_views:
        if not isinstance(view, dict) or _integer(view.get("buffer"), "buffer index") != 0:
            raise IngestionError("invalid_glb", "A buffer view references an invalid buffer.")
        offset = _integer(view.get("byteOffset", 0), "buffer offset")
        length = _integer(view.get("byteLength"), "buffer view length")
        if offset + length > declared_buffer_size:
            raise IngestionError("invalid_glb", "A buffer view exceeds the embedded buffer.")

    accessors = document.get("accessors", [])
    if not isinstance(accessors, list):
        raise IngestionError("invalid_glb", "The GLB contains invalid accessors.")
    total_accessor_values = 0
    accessor_layouts: list[tuple[int, int, int, int] | None] = []
    for accessor in accessors:
        if not isinstance(accessor, dict):
            raise IngestionError("invalid_glb", "The GLB contains an invalid accessor.")
        count = _integer(accessor.get("count"), "accessor count", 1)
        total_accessor_values += count
        component_type = accessor.get("componentType")
        accessor_type = accessor.get("type")
        if component_type not in VALID_COMPONENT_TYPES or accessor_type not in VALID_ACCESSOR_TYPES:
            raise IngestionError("invalid_glb", "The GLB contains an unsupported accessor.")
        if "bufferView" in accessor:
            view_index = _integer(accessor["bufferView"], "buffer view index")
            if view_index >= len(buffer_views):
                raise IngestionError("invalid_glb", "An accessor references an invalid buffer view.")
            view = buffer_views[view_index]
            element_size = COMPONENT_SIZES[component_type] * TYPE_COMPONENTS[accessor_type]
            stride = _integer(view.get("byteStride", element_size), "buffer byte stride", 1)
            offset = _integer(accessor.get("byteOffset", 0), "accessor byte offset")
            if stride < element_size or offset + stride * (count - 1) + element_size > view["byteLength"]:
                raise IngestionError("invalid_glb", "An accessor exceeds its buffer view.")
            accessor_layouts.append((view_index, offset, stride, count))
        else:
            accessor_layouts.append(None)
    if total_accessor_values > limits.max_decoded_vertices * 8 + limits.max_decoded_faces * 4:
        raise IngestionError("unreasonable_geometry", "The declared geometry exceeds configured limits.")

    binary = binary_chunks[0] if binary_chunks else b""
    meshes = document.get("meshes", [])
    if not isinstance(meshes, list):
        raise IngestionError("invalid_glb", "The GLB contains invalid meshes.")
    for mesh in meshes:
        if not isinstance(mesh, dict) or not isinstance(mesh.get("primitives"), list):
            raise IngestionError("invalid_glb", "The GLB contains an invalid mesh primitive.")
        for primitive in mesh["primitives"]:
            if not isinstance(primitive, dict) or not isinstance(primitive.get("attributes"), dict):
                raise IngestionError("invalid_glb", "The GLB contains an invalid mesh primitive.")
            position_index = primitive["attributes"].get("POSITION")
            if not isinstance(position_index, int) or position_index < 0 or position_index >= len(accessors):
                raise IngestionError("invalid_glb", "A mesh primitive has no valid position accessor.")
            if "indices" not in primitive:
                continue
            index_accessor_index = _integer(primitive["indices"], "index accessor")
            if index_accessor_index >= len(accessors):
                raise IngestionError("invalid_indices", "A mesh references an invalid index accessor.")
            index_accessor = accessors[index_accessor_index]
            component_type = index_accessor["componentType"]
            layout = accessor_layouts[index_accessor_index]
            if component_type not in INDEX_FORMATS or index_accessor["type"] != "SCALAR" or layout is None:
                raise IngestionError("invalid_indices", "A mesh has an unsupported index accessor.")
            view_index, accessor_offset, stride, count = layout
            view = buffer_views[view_index]
            start = view.get("byteOffset", 0) + accessor_offset
            component_size = COMPONENT_SIZES[component_type]
            if start < 0 or start + stride * (count - 1) + component_size > len(binary):
                raise IngestionError("invalid_indices", "A mesh index accessor exceeds the binary buffer.")
            maximum_index = max(
                struct.unpack_from("<" + INDEX_FORMATS[component_type], binary, start + stride * index)[0]
                for index in range(count)
            )
            if maximum_index >= accessors[position_index]["count"]:
                raise IngestionError("invalid_indices", "A mesh index references a missing vertex.")
    return document


def _run_worker(path: Path, settings: Settings) -> dict[str, Any]:
    output_path = settings.runtime_dir / "tmp" / f"{uuid4()}.json"
    command = [
        sys.executable, str(Path(__file__).with_name("ingestion_worker.py")), str(path), str(output_path),
        str(settings.limits.parser_memory_limit_mb), str(settings.limits.max_decoded_vertices),
        str(settings.limits.max_decoded_faces),
    ]
    try:
        completed = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=settings.limits.processing_timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired:
        raise IngestionError("processing_timeout", "Model processing exceeded the configured time limit.") from None
    try:
        if not output_path.exists():
            raise IngestionError("processing_failed", "The isolated model parser failed safely.")
        result = json.loads(output_path.read_text(encoding="utf-8"))
    finally:
        output_path.unlink(missing_ok=True)
    if completed.returncode != 0 or not result.get("ok"):
        code = result.get("code", "processing_failed")
        messages = {
            "empty_geometry": "The GLB does not contain usable mesh geometry.",
            "nonfinite_transform": "The GLB contains a nonfinite transform or vertex.",
            "invalid_indices": "The GLB contains invalid mesh indices.",
            "unreasonable_geometry": "The decoded geometry exceeds configured limits.",
            "processing_failed": "The isolated model parser could not process this GLB.",
        }
        raise IngestionError(code, messages.get(code, messages["processing_failed"]))
    return result


async def ingest_request(
    request: Request, item_id: UUID, original_filename: str, repository: Repository, settings: Settings,
) -> IngestionResult:
    if not original_filename.lower().endswith(".glb"):
        raise IngestionError("invalid_file_type", "Select a .glb file.")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.limits.max_upload_bytes:
                raise IngestionError("too_large", "GLB exceeds the 50 MB upload limit.", 413)
        except ValueError:
            raise IngestionError("invalid_content_length", "The upload length is invalid.", 400) from None

    temporary_path = settings.runtime_dir / "tmp" / f"{uuid4()}.part"
    digest = sha256()
    received = 0
    asset: AssetRecord | None = None
    try:
        with temporary_path.open("xb") as destination:
            async for chunk in request.stream():
                received += len(chunk)
                if received > settings.limits.max_upload_bytes:
                    raise IngestionError("too_large", "GLB exceeds the 50 MB upload limit.", 413)
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if received == 0:
            raise IngestionError("invalid_glb", "The uploaded GLB is empty.")

        validate_glb_structure(temporary_path, settings.limits)
        asset_id = uuid4()
        relative_path = Path("assets") / str(asset_id) / "model.glb"
        safe_filename = Path(original_filename).name.strip()[:120] or "model.glb"
        asset = AssetRecord(
            id=asset_id, item_id=item_id, sha256=digest.hexdigest(), byte_size=received,
            storage_path=relative_path.as_posix(), original_filename=safe_filename,
            stage=AssetStage.PROCESSING,
        )
        repository.save_asset(asset)
        parsed = await asyncio.to_thread(_run_worker, temporary_path, settings)
        target = settings.runtime_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=False)
        os.replace(temporary_path, target)
        asset = asset.model_copy(update={
            "stage": AssetStage.INGESTED,
            "bounds": AssetBounds(minimum_m=tuple(parsed["bounds_min_m"]), maximum_m=tuple(parsed["bounds_max_m"])),
            "vertex_count": parsed["vertex_count"], "face_count": parsed["face_count"],
            "mesh_instance_count": parsed["mesh_instance_count"],
        })
        repository.save_asset(asset)
        return IngestionResult(asset=asset, duplicate_of=repository.find_duplicate(asset.sha256, asset.id))
    except IngestionError as error:
        if asset is not None:
            repository.update_asset_failure(asset.id, error.code)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)
