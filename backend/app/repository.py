from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import UUID

from .schemas import (
    AssetRecord, AssetStage, EnrichmentResult, Geometry, Item, ItemConfirmation,
    PackingPlan, PlanJob, PlanJobState, PreviewRecord, ProcessingJob, ProgressStage, StockTemplate, Suitcase, Trip, TripSnapshot,
)


class Repository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES items(id),
                    sha256 TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    storage_path TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    error_code TEXT,
                    bounds_json TEXT,
                    vertex_count INTEGER,
                    face_count INTEGER,
                    mesh_instance_count INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256);
                CREATE INDEX IF NOT EXISTS idx_assets_item_id ON assets(item_id);
                CREATE TABLE IF NOT EXISTS geometry_versions (
                    item_id TEXT NOT NULL REFERENCES items(id),
                    asset_id TEXT NOT NULL REFERENCES assets(id),
                    version INTEGER NOT NULL,
                    scale_correction REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(item_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_geometry_asset ON geometry_versions(asset_id);
                CREATE TABLE IF NOT EXISTS previews (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES items(id),
                    asset_id TEXT NOT NULL REFERENCES assets(id),
                    geometry_version INTEGER NOT NULL,
                    view TEXT NOT NULL,
                    renderer_version TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    storage_path TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(asset_id, geometry_version, view, renderer_version)
                );
                CREATE TABLE IF NOT EXISTS enrichment_cache (
                    cache_key TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES items(id),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS model_runs (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES items(id),
                    provider TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fallback_reason TEXT,
                    request_key TEXT NOT NULL,
                    response_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS item_confirmations (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES items(id),
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(item_id, version)
                );
                CREATE TABLE IF NOT EXISTS deleted_items (
                    item_id TEXT PRIMARY KEY REFERENCES items(id),
                    deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS stock_templates (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trips (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS trip_snapshots (
                    id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL REFERENCES trips(id),
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(trip_id, version)
                );
                CREATE TABLE IF NOT EXISTS suitcases (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL REFERENCES trips(id),
                    snapshot_id TEXT NOT NULL REFERENCES trip_snapshots(id),
                    predecessor_plan_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_plans_trip ON plans(trip_id, created_at);
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    request_hash TEXT,
                    response_json TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES items(id),
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_code TEXT,
                    request_key TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status, updated_at);
                CREATE TABLE IF NOT EXISTS demo_records (
                    table_name TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(table_name, record_id)
                );
                CREATE TABLE IF NOT EXISTS plan_jobs (
                    id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL REFERENCES trips(id),
                    snapshot_id TEXT NOT NULL REFERENCES trip_snapshots(id),
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_stage TEXT NOT NULL,
                    plan_id TEXT,
                    predecessor_plan_id TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    idempotency_key TEXT,
                    request_hash TEXT,
                    seed INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_plan_jobs_status ON plan_jobs(status, updated_at);
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(idempotency_keys)").fetchall()}
            if "request_hash" not in columns:
                connection.execute("ALTER TABLE idempotency_keys ADD COLUMN request_hash TEXT")
            processing_columns = {row[1] for row in connection.execute("PRAGMA table_info(processing_jobs)").fetchall()}
            for name, declaration in (("operation_type", "TEXT NOT NULL DEFAULT 'geometry'"), ("requested_scale_correction", "REAL"), ("renderer_version", "TEXT"), ("required_previews", "TEXT NOT NULL DEFAULT '[]'"), ("retry_count", "INTEGER NOT NULL DEFAULT 0"), ("stable_input_reference", "TEXT")):
                if name not in processing_columns:
                    connection.execute(f"ALTER TABLE processing_jobs ADD COLUMN {name} {declaration}")
            migration_dir = Path(__file__).resolve().parents[1] / "migrations"
            applied = {int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations").fetchall()}
            for migration in sorted(migration_dir.glob("[0-9][0-9][0-9]_*.sql")):
                version = int(migration.name[:3])
                if version in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute("INSERT INTO schema_migrations(version,name) VALUES (?,?)", (version, migration.stem[4:]))
            current_version = int(connection.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0])
            connection.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES ('schema_version',?)", (str(current_version),))
            connection.execute(f"PRAGMA user_version = {current_version}")

    def schema_version(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return int(row[0] or 0)

    def save_item(self, item: Item) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO items(id, payload_json) VALUES (?, ?)
                   ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json, updated_at=CURRENT_TIMESTAMP""",
                (str(item.id), item.model_dump_json()),
            )

    def get_item(self, item_id: UUID) -> Item | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM items WHERE id = ?", (str(item_id),)).fetchone()
        return Item.model_validate_json(row["payload_json"]) if row else None

    def list_items(self, include_deleted: bool = False) -> list[Item]:
        query = "SELECT i.payload_json FROM items i"
        if not include_deleted:
            query += " LEFT JOIN deleted_items d ON d.item_id=i.id WHERE d.item_id IS NULL"
        query += " ORDER BY i.updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [Item.model_validate_json(row["payload_json"]) for row in rows]

    def soft_delete_item(self, item_id: UUID) -> bool:
        with self.connect() as connection:
            exists = connection.execute("SELECT 1 FROM items WHERE id=?", (str(item_id),)).fetchone()
            if not exists:
                return False
            connection.execute("INSERT OR IGNORE INTO deleted_items(item_id) VALUES (?)", (str(item_id),))
        return True

    def is_item_deleted(self, item_id: UUID) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1 FROM deleted_items WHERE item_id=?", (str(item_id),)).fetchone() is not None

    def latest_confirmation(self, item_id: UUID) -> ItemConfirmation | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM item_confirmations WHERE item_id=? ORDER BY version DESC LIMIT 1",
                (str(item_id),),
            ).fetchone()
        return ItemConfirmation.model_validate_json(row["payload_json"]) if row else None

    def next_confirmation_version(self, item_id: UUID) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS version FROM item_confirmations WHERE item_id=?",
                (str(item_id),),
            ).fetchone()
        return int(row["version"])

    def confirm_item(self, item: Item, confirmation: ItemConfirmation) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO item_confirmations(id,item_id,version,payload_json,created_at) VALUES (?,?,?,?,?)",
                (str(confirmation.id), str(item.id), confirmation.version, confirmation.model_dump_json(), confirmation.confirmed_at.isoformat()),
            )
            connection.execute(
                """INSERT INTO items(id,payload_json) VALUES (?,?)
                   ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json,updated_at=CURRENT_TIMESTAMP""",
                (str(item.id), item.model_dump_json()),
            )

    def save_stock_templates(self, templates: list[StockTemplate]) -> None:
        with self.connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO stock_templates(id,payload_json) VALUES (?,?)",
                [(str(template.id), template.model_dump_json()) for template in templates],
            )

    def list_stock_templates(self) -> list[StockTemplate]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM stock_templates ORDER BY json_extract(payload_json,'$.name')").fetchall()
        return [StockTemplate.model_validate_json(row["payload_json"]) for row in rows]

    def get_stock_template(self, template_id: UUID) -> StockTemplate | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM stock_templates WHERE id=?", (str(template_id),)).fetchone()
        return StockTemplate.model_validate_json(row["payload_json"]) if row else None

    def save_trip(self, trip: Trip) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO trips(id,payload_json) VALUES (?,?)
                   ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json,updated_at=CURRENT_TIMESTAMP""",
                (str(trip.id), trip.model_dump_json()),
            )

    def get_trip(self, trip_id: UUID) -> Trip | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM trips WHERE id=?", (str(trip_id),)).fetchone()
        return Trip.model_validate_json(row["payload_json"]) if row else None

    def list_trips(self) -> list[Trip]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM trips ORDER BY updated_at DESC").fetchall()
        return [Trip.model_validate_json(row["payload_json"]) for row in rows]

    def save_trip_snapshot(self, snapshot: TripSnapshot) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO trip_snapshots(id,trip_id,version,payload_json,created_at) VALUES (?,?,?,?,?)",
                (str(snapshot.id), str(snapshot.trip_id), snapshot.version, snapshot.model_dump_json(), snapshot.created_at.isoformat()),
            )

    def next_trip_snapshot_version(self, trip_id: UUID) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS version FROM trip_snapshots WHERE trip_id=?", (str(trip_id),)
            ).fetchone()
        return int(row["version"])

    def list_trip_snapshots(self, trip_id: UUID) -> list[TripSnapshot]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM trip_snapshots WHERE trip_id=? ORDER BY version", (str(trip_id),)
            ).fetchall()
        return [TripSnapshot.model_validate_json(row["payload_json"]) for row in rows]

    def get_trip_snapshot(self, snapshot_id: UUID) -> TripSnapshot | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM trip_snapshots WHERE id=?", (str(snapshot_id),)).fetchone()
        return TripSnapshot.model_validate_json(row["payload_json"]) if row else None

    def save_suitcase(self, suitcase: Suitcase) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO suitcases(id,payload_json) VALUES (?,?)
                   ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json,updated_at=CURRENT_TIMESTAMP""",
                (str(suitcase.id), suitcase.model_dump_json()),
            )

    def list_suitcases(self) -> list[Suitcase]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM suitcases ORDER BY updated_at DESC").fetchall()
        return [Suitcase.model_validate_json(row["payload_json"]) for row in rows]

    def get_suitcase(self, suitcase_id: UUID) -> Suitcase | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM suitcases WHERE id=?", (str(suitcase_id),)).fetchone()
        return Suitcase.model_validate_json(row["payload_json"]) if row else None

    def delete_suitcase(self, suitcase_id: UUID) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM suitcases WHERE id=?", (str(suitcase_id),))
        return cursor.rowcount > 0

    def save_plan(self, plan: PackingPlan) -> None:
        if plan.snapshot_id is None:
            raise ValueError("persisted plans require a snapshot")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO plans(id,trip_id,snapshot_id,predecessor_plan_id,payload_json) VALUES (?,?,?,?,?)",
                (str(plan.id), str(plan.trip_id), str(plan.snapshot_id),
                 str(plan.predecessor_plan_id) if plan.predecessor_plan_id else None, plan.model_dump_json()),
            )

    def save_idempotent_response(self, key: str, operation: str, response: object, status_code: int, request_hash: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO idempotency_keys(key,operation,request_hash,response_json,status_code) VALUES (?,?,?,?,?)",
                (key, operation, request_hash, response.model_dump_json() if hasattr(response, "model_dump_json") else json.dumps(response), status_code),
            )

    def get_idempotent_response(self, key: str, operation: str) -> tuple[str, int, str | None] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT response_json,status_code,request_hash FROM idempotency_keys WHERE key=? AND operation=?", (key, operation)).fetchone()
        return (row["response_json"], int(row["status_code"]), row["request_hash"]) if row else None

    def save_processing_job(self, job: ProcessingJob) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO processing_jobs(id,item_id,stage,status,error_code,request_key,updated_at,operation_type,requested_scale_correction,renderer_version,required_previews,retry_count,stable_input_reference) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET stage=excluded.stage,status=excluded.status,error_code=excluded.error_code,request_key=excluded.request_key,updated_at=excluded.updated_at,operation_type=excluded.operation_type,requested_scale_correction=excluded.requested_scale_correction,renderer_version=excluded.renderer_version,required_previews=excluded.required_previews,retry_count=excluded.retry_count,stable_input_reference=excluded.stable_input_reference",
                (str(job.id), str(job.item_id), job.stage.value, job.status, job.error_code, job.request_key, job.updated_at.isoformat(), job.operation_type, job.requested_scale_correction, job.renderer_version, json.dumps([value.value for value in job.required_previews]), job.retry_count, job.stable_input_reference),
            )

    def list_processing_jobs(self, active_only: bool = False) -> list[ProcessingJob]:
        query = "SELECT * FROM processing_jobs" + (" WHERE status IN ('running','retryable')" if active_only else "") + " ORDER BY updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [ProcessingJob(id=row["id"], item_id=row["item_id"], stage=row["stage"], status=row["status"], error_code=row["error_code"], request_key=row["request_key"], updated_at=row["updated_at"], operation_type=row["operation_type"], requested_scale_correction=row["requested_scale_correction"], renderer_version=row["renderer_version"], required_previews=tuple(json.loads(row["required_previews"] or "[]")), retry_count=row["retry_count"], stable_input_reference=row["stable_input_reference"]) for row in rows]

    def get_processing_job(self, job_id: UUID) -> ProcessingJob | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM processing_jobs WHERE id=?", (str(job_id),)).fetchone()
        return ProcessingJob(id=row["id"], item_id=row["item_id"], stage=row["stage"], status=row["status"], error_code=row["error_code"], request_key=row["request_key"], updated_at=row["updated_at"], operation_type=row["operation_type"], requested_scale_correction=row["requested_scale_correction"], renderer_version=row["renderer_version"], required_previews=tuple(json.loads(row["required_previews"] or "[]")), retry_count=row["retry_count"], stable_input_reference=row["stable_input_reference"]) if row else None

    def save_plan_job(self, job: PlanJob) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO plan_jobs(id,trip_id,snapshot_id,kind,status,progress_stage,plan_id,predecessor_plan_id,error_code,error_message,idempotency_key,request_hash,seed,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,progress_stage=excluded.progress_stage,plan_id=excluded.plan_id,
                error_code=excluded.error_code,error_message=excluded.error_message,updated_at=excluded.updated_at""",
                (str(job.id), str(job.trip_id), str(job.snapshot_id), job.kind, job.status.value, job.progress_stage,
                 str(job.plan_id) if job.plan_id else None, str(job.predecessor_plan_id) if job.predecessor_plan_id else None,
                 job.error_code, job.error_message, job.idempotency_key, job.request_hash, job.seed,
                 job.created_at.isoformat(), job.updated_at.isoformat()),
            )

    def get_plan_job(self, job_id: UUID) -> PlanJob | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM plan_jobs WHERE id=?", (str(job_id),)).fetchone()
        if not row:
            return None
        return PlanJob(id=row["id"], trip_id=row["trip_id"], snapshot_id=row["snapshot_id"], kind=row["kind"], status=row["status"], progress_stage=row["progress_stage"], plan_id=row["plan_id"], predecessor_plan_id=row["predecessor_plan_id"], error_code=row["error_code"], error_message=row["error_message"], idempotency_key=row["idempotency_key"], request_hash=row["request_hash"], seed=row["seed"], created_at=row["created_at"], updated_at=row["updated_at"])

    def list_plan_jobs(self, trip_id: UUID | None = None) -> list[PlanJob]:
        with self.connect() as connection:
            if trip_id:
                rows = connection.execute("SELECT id FROM plan_jobs WHERE trip_id=? ORDER BY created_at", (str(trip_id),)).fetchall()
            else:
                rows = connection.execute("SELECT id FROM plan_jobs ORDER BY created_at").fetchall()
        return [job for row in rows if (job := self.get_plan_job(UUID(row["id"]))) is not None]

    def recover_processing_jobs(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute("UPDATE processing_jobs SET status='retryable', error_code='interrupted' WHERE status='running'")
        return cursor.rowcount

    def recover_plan_jobs(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute("UPDATE plan_jobs SET status='retryable', error_code='interrupted', error_message='The server restarted before this job completed.', updated_at=CURRENT_TIMESTAMP WHERE status IN ('queued','running')")
        return cursor.rowcount

    def mark_demo_record(self, table_name: str, record_id: UUID | str) -> None:
        with self.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO demo_records(table_name,record_id) VALUES (?,?)", (table_name, str(record_id)))

    def reset_demo_records(self) -> int:
        with self.connect() as connection:
            records = connection.execute("SELECT table_name,record_id FROM demo_records").fetchall()
            demo_trip_ids = [record_id for table_name, record_id in records if table_name == "trips"]
            removed = 0
            # Delete dependents first; only explicitly marked records are touched.
            for trip_id in demo_trip_ids:
                connection.execute("DELETE FROM plan_jobs WHERE trip_id=?", (trip_id,))
                connection.execute("DELETE FROM plans WHERE trip_id=?", (trip_id,))
                connection.execute("DELETE FROM trip_snapshots WHERE trip_id=?", (trip_id,))
            for table_name, record_id in records:
                if table_name == "plans": connection.execute("DELETE FROM plans WHERE id=?", (record_id,))
                elif table_name == "plan_jobs": connection.execute("DELETE FROM plan_jobs WHERE id=?", (record_id,))
                elif table_name == "trip_snapshots": connection.execute("DELETE FROM trip_snapshots WHERE id=?", (record_id,))
                elif table_name == "trips": connection.execute("DELETE FROM trips WHERE id=?", (record_id,))
                elif table_name == "suitcases": connection.execute("DELETE FROM suitcases WHERE id=?", (record_id,))
                removed += 1
            connection.execute("DELETE FROM demo_records")
        return removed

    def get_plan(self, plan_id: UUID) -> PackingPlan | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM plans WHERE id=?", (str(plan_id),)).fetchone()
        return PackingPlan.model_validate_json(row["payload_json"]) if row else None

    def list_plans(self, trip_id: UUID) -> list[PackingPlan]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM plans WHERE trip_id=? ORDER BY created_at", (str(trip_id),)).fetchall()
        return [PackingPlan.model_validate_json(row["payload_json"]) for row in rows]

    def save_asset(self, asset: AssetRecord) -> None:
        bounds_json = asset.bounds.model_dump_json() if asset.bounds else None
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO assets(
                    id,item_id,sha256,byte_size,storage_path,original_filename,stage,error_code,bounds_json,
                    vertex_count,face_count,mesh_instance_count,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    stage=excluded.stage,error_code=excluded.error_code,bounds_json=excluded.bounds_json,
                    vertex_count=excluded.vertex_count,face_count=excluded.face_count,
                    mesh_instance_count=excluded.mesh_instance_count""",
                (
                    str(asset.id), str(asset.item_id), asset.sha256, asset.byte_size, asset.storage_path,
                    asset.original_filename, asset.stage.value, asset.error_code, bounds_json,
                    asset.vertex_count, asset.face_count, asset.mesh_instance_count, asset.created_at.isoformat(),
                ),
            )

    def update_asset_failure(self, asset_id: UUID, error_code: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE assets SET stage = ?, error_code = ? WHERE id = ?",
                (AssetStage.FAILED.value, error_code, str(asset_id)),
            )

    def find_duplicate(self, digest: str, exclude_asset_id: UUID | None = None) -> UUID | None:
        query = "SELECT id FROM assets WHERE sha256 = ? AND stage = ?"
        params: list[str] = [digest, AssetStage.INGESTED.value]
        if exclude_asset_id is not None:
            query += " AND id != ?"
            params.append(str(exclude_asset_id))
        query += " ORDER BY created_at LIMIT 1"
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return UUID(row["id"]) if row else None

    def get_latest_asset(self, item_id: UUID) -> AssetRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE item_id = ? ORDER BY created_at DESC LIMIT 1", (str(item_id),)
            ).fetchone()
        if not row:
            return None
        bounds = json.loads(row["bounds_json"]) if row["bounds_json"] else None
        return AssetRecord(
            id=row["id"], item_id=row["item_id"], sha256=row["sha256"], byte_size=row["byte_size"],
            storage_path=row["storage_path"], original_filename=row["original_filename"], stage=row["stage"],
            error_code=row["error_code"], bounds=bounds, vertex_count=row["vertex_count"],
            face_count=row["face_count"], mesh_instance_count=row["mesh_instance_count"], created_at=row["created_at"],
        )

    def next_geometry_version(self, item_id: UUID) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM geometry_versions WHERE item_id = ?",
                (str(item_id),),
            ).fetchone()
        return int(row["version"])

    def save_geometry(self, item_id: UUID, geometry: Geometry) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO geometry_versions(item_id,asset_id,version,scale_correction,payload_json)
                   VALUES (?,?,?,?,?)""",
                (str(item_id), str(geometry.asset_id), geometry.version, geometry.scale_correction, geometry.model_dump_json()),
            )

    def get_latest_geometry(self, item_id: UUID) -> Geometry | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM geometry_versions WHERE item_id = ? ORDER BY version DESC LIMIT 1",
                (str(item_id),),
            ).fetchone()
        return Geometry.model_validate_json(row["payload_json"]) if row else None

    def find_preview(self, asset_id: UUID, geometry_version: int, view: str, renderer_version: str) -> PreviewRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT payload_json FROM previews
                   WHERE asset_id=? AND geometry_version=? AND view=? AND renderer_version=?""",
                (str(asset_id), geometry_version, view, renderer_version),
            ).fetchone()
        return PreviewRecord.model_validate_json(row["payload_json"]) if row else None

    def save_preview(self, preview: PreviewRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO previews(
                    id,item_id,asset_id,geometry_version,view,renderer_version,mime_type,byte_size,
                    width,height,storage_path,payload_json,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(preview.id), str(preview.item_id), str(preview.asset_id), preview.geometry_version,
                    preview.view.value, preview.renderer_version, preview.mime_type, preview.byte_size,
                    preview.width, preview.height, preview.storage_path, preview.model_dump_json(),
                    preview.created_at.isoformat(),
                ),
            )

    def list_previews(self, item_id: UUID, geometry_version: int | None = None) -> list[PreviewRecord]:
        query = "SELECT payload_json FROM previews WHERE item_id=?"
        params: list[object] = [str(item_id)]
        if geometry_version is not None:
            query += " AND geometry_version=?"
            params.append(geometry_version)
        query += " ORDER BY created_at, view"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [PreviewRecord.model_validate_json(row["payload_json"]) for row in rows]

    def get_preview(self, preview_id: UUID) -> PreviewRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM previews WHERE id=?", (str(preview_id),)).fetchone()
        return PreviewRecord.model_validate_json(row["payload_json"]) if row else None

    def get_cached_enrichment(self, cache_key: str) -> EnrichmentResult | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM enrichment_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
        if not row:
            return None
        result = EnrichmentResult.model_validate_json(row["payload_json"])
        return result.model_copy(update={"cached": True})

    def save_enrichment(self, cache_key: str, item_id: UUID, result: EnrichmentResult) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO enrichment_cache(cache_key,item_id,payload_json) VALUES (?,?,?)",
                (cache_key, str(item_id), result.model_dump_json()),
            )

    def save_model_run(
        self, run_id: UUID, item_id: UUID, provider: str, model_id: str, prompt_version: str,
        status: str, fallback_reason: str | None, request_key: str, response: dict | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO model_runs(
                    id,item_id,provider,model_id,prompt_version,status,fallback_reason,request_key,response_json
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    str(run_id), str(item_id), provider, model_id, prompt_version, status,
                    fallback_reason, request_key, json.dumps(response) if response is not None else None,
                ),
            )
