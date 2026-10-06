"""SQLite implementation of the small Supabase surface used by Kitch.

This module intentionally mirrors the ``table(...).select/update/...`` and
``rpc(...)`` calls made by :mod:`app.supabase_client`.  Keeping that boundary
lets both persistence backends share Kitch's existing normalization and domain
logic while SQLite owns the transactional behavior previously implemented by
PostgreSQL functions.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator
from uuid import uuid4


JSON_COLUMNS = {
    "recipe_grocery_plans": {
        "scope", "recipe_cards", "ingredients", "pantry_considerations",
    },
    "grocery_cart_items": {"pantry_allocation"},
    "provider_checkout_drafts": {
        "selected_native_item_ids", "native_items", "mapped_items",
        "matched_items", "unavailable_items", "replacements", "changes",
        "provider_cart", "cart_summary", "checkout_context", "store_context",
        "payment_options", "selected_payment_method", "payment_state",
        "provider_order_ids", "order_results", "order_blockers",
    },
    "provider_oauth_clients": {"registration"},
    "pending_agent_actions": {"payload", "impact_summary"},
}

BOOL_COLUMNS = {
    "recipe_grocery_plans": {"updates_cart"},
    "grocery_cart_items": {"checked"},
    "provider_checkout_drafts": {
        "order_review_acknowledged", "can_place_order", "ambiguous_order",
    },
}

UUID_ID_TABLES = {
    "recipe_grocery_plans", "provider_checkout_drafts", "provider_connections",
    "provider_oauth_clients", "provider_oauth_flows", "pending_agent_actions",
}

CREATED_UPDATED_TABLES = {
    "meal_plans", "recipe_grocery_plans", "grocery_cart_items",
    "provider_checkout_drafts", "provider_oauth_clients",
    "pending_agent_actions",
}
UPDATED_ONLY_TABLES = {
    "nutrition_targets", "provider_selection_state", "pantry_stock",
    "macro_diary",
}


MIGRATION_1_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_household (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    owner_profile_id TEXT NOT NULL,
    timezone_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    household_size INTEGER NOT NULL DEFAULT 1 CHECK (household_size >= 1),
    timezone_name TEXT NOT NULL,
    pantry_revision INTEGER NOT NULL DEFAULT 0,
    pantry_reviewed_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nutrition_targets (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    daily_calorie_target INTEGER NOT NULL DEFAULT 2000,
    protein_target_g INTEGER NOT NULL DEFAULT 150,
    carbs_target_g INTEGER NOT NULL DEFAULT 200,
    fat_target_g INTEGER NOT NULL DEFAULT 67,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_selection_state (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    selected_provider TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meal_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    plan_date TEXT NOT NULL,
    breakfast_name TEXT,
    lunch_name TEXT,
    dinner_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(profile_id, plan_date)
);
CREATE TABLE IF NOT EXISTS pantry_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL COLLATE NOCASE,
    amount REAL NOT NULL DEFAULT 0 CHECK (amount >= 0),
    unit TEXT NOT NULL DEFAULT 'piece',
    updated_at TEXT NOT NULL,
    UNIQUE(profile_id, ingredient_name)
);
CREATE TABLE IF NOT EXISTS recipe_grocery_plans (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    scope TEXT NOT NULL DEFAULT '{}',
    request_text TEXT NOT NULL DEFAULT '',
    recipe_cards TEXT NOT NULL DEFAULT '[]',
    ingredients TEXT NOT NULL DEFAULT '[]',
    pantry_considerations TEXT NOT NULL DEFAULT '[]',
    household_size INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'agent',
    updates_cart INTEGER NOT NULL DEFAULT 0,
    cart_item_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS grocery_cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    recipe_grocery_plan_id TEXT REFERENCES recipe_grocery_plans(id) ON DELETE SET NULL,
    ingredient_name TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 1 CHECK (amount >= 0),
    unit TEXT NOT NULL DEFAULT 'piece',
    category TEXT NOT NULL DEFAULT 'General',
    source TEXT NOT NULL DEFAULT 'agent',
    checked INTEGER NOT NULL DEFAULT 0,
    purchase_amount REAL NOT NULL DEFAULT 1 CHECK (purchase_amount >= 0),
    purchase_unit TEXT NOT NULL DEFAULT 'piece',
    pantry_allocation TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS macro_diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    meal_name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    unit TEXT NOT NULL DEFAULT 'serving',
    meal_type TEXT NOT NULL,
    calories INTEGER NOT NULL DEFAULT 0,
    protein_g INTEGER NOT NULL DEFAULT 0,
    carbs_g INTEGER NOT NULL DEFAULT 0,
    fat_g INTEGER NOT NULL DEFAULT 0,
    fiber_g INTEGER NOT NULL DEFAULT 0,
    consumed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_checkout_drafts (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL DEFAULT 'production',
    capability_version TEXT NOT NULL DEFAULT '',
    selected_address_id TEXT NOT NULL DEFAULT '',
    selected_native_item_ids TEXT NOT NULL DEFAULT '[]',
    native_items TEXT NOT NULL DEFAULT '[]',
    mapped_items TEXT NOT NULL DEFAULT '[]',
    matched_items TEXT NOT NULL DEFAULT '[]',
    unavailable_items TEXT NOT NULL DEFAULT '[]',
    replacements TEXT NOT NULL DEFAULT '[]',
    changes TEXT NOT NULL DEFAULT '[]',
    provider_cart TEXT,
    cart_summary TEXT NOT NULL DEFAULT '{}',
    checkout_context TEXT NOT NULL DEFAULT '{}',
    store_context TEXT NOT NULL DEFAULT '{}',
    payment_options TEXT NOT NULL DEFAULT '[]',
    selected_payment_method_id TEXT,
    selected_payment_method TEXT,
    payment_state TEXT NOT NULL DEFAULT '{}',
    order_review_acknowledged INTEGER NOT NULL DEFAULT 0,
    can_place_order INTEGER NOT NULL DEFAULT 0,
    order_blockers TEXT NOT NULL DEFAULT '[]',
    confirmation_token TEXT,
    snapshot_hash TEXT NOT NULL DEFAULT '',
    checkout_attempt_id TEXT,
    provider_order_ids TEXT NOT NULL DEFAULT '[]',
    order_results TEXT NOT NULL DEFAULT '[]',
    ambiguous_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    last_validated_at TEXT,
    operation_id TEXT,
    lease_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(profile_id, provider, provider_environment)
);
CREATE TABLE IF NOT EXISTS provider_connections (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL,
    access_token_ciphertext TEXT NOT NULL,
    token_type TEXT NOT NULL DEFAULT 'Bearer',
    scope TEXT NOT NULL DEFAULT '',
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'connected',
    last_error_code TEXT,
    connected_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(profile_id, provider, provider_environment)
);
CREATE TABLE IF NOT EXISTS provider_oauth_clients (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL,
    client_id TEXT NOT NULL,
    registration TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(provider, provider_environment)
);
CREATE TABLE IF NOT EXISTS provider_oauth_flows (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL,
    state_hash TEXT NOT NULL UNIQUE,
    code_verifier_ciphertext TEXT NOT NULL,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_agent_actions (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    active_user TEXT NOT NULL DEFAULT '',
    action_type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    impact_summary TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meal_plan_date ON meal_plans(profile_id, plan_date);
CREATE INDEX IF NOT EXISTS idx_pantry_profile ON pantry_stock(profile_id);
CREATE INDEX IF NOT EXISTS idx_cart_profile ON grocery_cart_items(profile_id);
CREATE INDEX IF NOT EXISTS idx_diary_profile_date ON macro_diary(profile_id, consumed_at);
CREATE INDEX IF NOT EXISTS idx_oauth_expiry ON provider_oauth_flows(expires_at);
"""

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (1, MIGRATION_1_SCHEMA),
    (2, """
        ALTER TABLE profiles ADD COLUMN member_order INTEGER NOT NULL DEFAULT 0;
        UPDATE profiles
        SET member_order = CASE
            WHEN id = (
                SELECT owner_profile_id FROM local_household WHERE singleton = 1
            ) THEN 0
            ELSE rowid
        END;
    """),
    (3, """
        ALTER TABLE provider_checkout_drafts ADD COLUMN expires_at TEXT;
        UPDATE provider_checkout_drafts
        SET expires_at = strftime('%Y-%m-%dT%H:%M:%f+00:00', updated_at, '+24 hours')
        WHERE expires_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_provider_checkout_drafts_expiry
            ON provider_checkout_drafts(expires_at);
    """),
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(table: str, column: str) -> Any:
    if column in {
        "scope", "pantry_allocation", "cart_summary", "checkout_context",
        "store_context", "payment_state", "registration", "payload",
        "impact_summary",
    }:
        return {}
    return []


@dataclass
class SQLiteResponse:
    data: Any


class SQLiteKitchClient:
    def __init__(self, path: str | Path):
        raw = Path(path).expanduser()
        if not raw.is_absolute():
            raw = Path(__file__).resolve().parents[2] / raw
        self.path = raw.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def migrate(self) -> None:
        with self._lock:
            conn = self.connect()
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
                )
                applied = {
                    int(row["version"])
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations"
                    ).fetchall()
                }
                for version, migration in MIGRATIONS:
                    if version in applied:
                        continue
                    conn.executescript(migration)
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                        (version, utcnow()),
                    )
                conn.execute("PRAGMA journal_mode = WAL")
            finally:
                conn.close()

    def table(self, table: str) -> "SQLiteQuery":
        return SQLiteQuery(self, table)

    def rpc(self, name: str, params: dict[str, Any]) -> "SQLiteRPC":
        return SQLiteRPC(self, name, params)

    def bootstrap_status(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT owner_profile_id, timezone_name FROM local_household WHERE singleton=1"
            ).fetchone()
            if not row:
                return {"initialized": False, "members": [], "timezone": None}
            members = conn.execute(
                "SELECT id, full_name FROM profiles "
                "ORDER BY member_order, created_at, full_name"
            ).fetchall()
        return {
            "initialized": True,
            "owner_profile_id": row["owner_profile_id"],
            "timezone": row["timezone_name"],
            "members": [{"id": item["id"], "name": item["full_name"]} for item in members],
        }

    def bootstrap_household(self, members: list[str], timezone_name: str) -> dict[str, Any]:
        cleaned = [str(name).strip() for name in members if str(name).strip()]
        if not cleaned:
            raise ValueError("At least one household member is required.")
        if len({name.casefold() for name in cleaned}) != len(cleaned):
            raise ValueError("Household member names must be unique.")
        now = utcnow()
        identities = [{"id": str(uuid4()), "name": name} for name in cleaned]
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM local_household WHERE singleton=1").fetchone():
                raise RuntimeError("The local household is already initialized.")
            for member_order, member in enumerate(identities):
                conn.execute(
                    "INSERT INTO profiles("
                    "id,full_name,household_size,timezone_name,created_at,member_order"
                    ") VALUES(?,?,?,?,?,?)",
                    (
                        member["id"], member["name"], len(identities),
                        timezone_name, now, member_order,
                    ),
                )
                conn.execute(
                    "INSERT INTO nutrition_targets(profile_id,updated_at) VALUES(?,?)",
                    (member["id"], now),
                )
            conn.execute(
                "INSERT INTO local_household(singleton,owner_profile_id,timezone_name,created_at) VALUES(1,?,?,?)",
                (identities[0]["id"], timezone_name, now),
            )
        return self.bootstrap_status()

    def owner_id(self) -> str:
        state = self.bootstrap_status()
        if not state["initialized"]:
            raise RuntimeError("The local household has not been initialized.")
        return str(state["owner_profile_id"])

    def user_id(self, name: str | None) -> str:
        state = self.bootstrap_status()
        if not state["initialized"]:
            raise RuntimeError("The local household has not been initialized.")
        wanted = str(name or "").strip().casefold()
        for member in state["members"]:
            if member["name"].casefold() == wanted:
                return str(member["id"])
        return str(state["owner_profile_id"])

    def canonical_name(self, name: str | None) -> str:
        state = self.bootstrap_status()
        if not state["initialized"]:
            return ""
        wanted = str(name or "").strip().casefold()
        for member in state["members"]:
            if member["name"].casefold() == wanted:
                return str(member["name"])
        owner = next(
            member for member in state["members"]
            if member["id"] == state["owner_profile_id"]
        )
        return str(owner["name"])

    def decode_row(self, table: str, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for column in JSON_COLUMNS.get(table, set()):
            if column not in result:
                continue
            value = result[column]
            if value is None:
                continue
            if isinstance(value, str):
                try:
                    result[column] = json.loads(value)
                except json.JSONDecodeError:
                    result[column] = _json_default(table, column)
        for column in BOOL_COLUMNS.get(table, set()):
            if column in result:
                result[column] = bool(result[column])
        return result

    def encode_value(self, table: str, column: str, value: Any) -> Any:
        if column in JSON_COLUMNS.get(table, set()) and value is not None:
            return json.dumps(value, separators=(",", ":"))
        if column in BOOL_COLUMNS.get(table, set()) and value is not None:
            return int(bool(value))
        return value


class SQLiteQuery:
    def __init__(self, client: SQLiteKitchClient, table: str):
        self.client = client
        self.table = table
        self.operation = "select"
        self.columns = "*"
        self.payload: Any = None
        self.filters: list[tuple[str, str, Any]] = []
        self.orders: list[tuple[str, bool]] = []
        self.row_limit: int | None = None
        self.conflict_columns: list[str] = []

    def select(self, columns: str = "*") -> "SQLiteQuery":
        self.operation, self.columns = "select", columns
        return self

    def insert(self, payload: Any) -> "SQLiteQuery":
        self.operation, self.payload = "insert", payload
        return self

    def upsert(self, payload: Any, on_conflict: str = "") -> "SQLiteQuery":
        self.operation, self.payload = "upsert", payload
        self.conflict_columns = [part.strip() for part in on_conflict.split(",") if part.strip()]
        return self

    def update(self, payload: dict[str, Any]) -> "SQLiteQuery":
        self.operation, self.payload = "update", payload
        return self

    def delete(self) -> "SQLiteQuery":
        self.operation = "delete"
        return self

    def eq(self, column: str, value: Any) -> "SQLiteQuery":
        self.filters.append((column, "=", value))
        return self

    def lt(self, column: str, value: Any) -> "SQLiteQuery":
        self.filters.append((column, "<", value))
        return self

    def lte(self, column: str, value: Any) -> "SQLiteQuery":
        self.filters.append((column, "<=", value))
        return self

    def gt(self, column: str, value: Any) -> "SQLiteQuery":
        self.filters.append((column, ">", value))
        return self

    def gte(self, column: str, value: Any) -> "SQLiteQuery":
        self.filters.append((column, ">=", value))
        return self

    def is_(self, column: str, value: Any) -> "SQLiteQuery":
        self.filters.append((column, "IS", None if str(value).lower() == "null" else value))
        return self

    def order(self, column: str, desc: bool = False) -> "SQLiteQuery":
        self.orders.append((column, desc))
        return self

    def limit(self, value: int) -> "SQLiteQuery":
        self.row_limit = int(value)
        return self

    def _where(self) -> tuple[str, list[Any]]:
        if not self.filters:
            return "", []
        clauses, params = [], []
        for column, operator, value in self.filters:
            if operator == "IS" and value is None:
                clauses.append(f'"{column}" IS NULL')
            else:
                clauses.append(f'"{column}" {operator} ?')
                params.append(self.client.encode_value(self.table, column, value))
        return " WHERE " + " AND ".join(clauses), params

    def _select_sql(self) -> tuple[str, list[Any]]:
        columns = "*" if self.columns == "*" else ",".join(
            f'"{part.strip()}"' for part in self.columns.split(",") if part.strip()
        )
        where, params = self._where()
        sql = f'SELECT {columns} FROM "{self.table}"{where}'
        if self.orders:
            sql += " ORDER BY " + ",".join(
                f'"{column}" {"DESC" if desc else "ASC"}' for column, desc in self.orders
            )
        if self.row_limit is not None:
            sql += " LIMIT ?"
            params.append(self.row_limit)
        return sql, params

    def execute(self) -> SQLiteResponse:
        with self.client.transaction() as conn:
            if self.operation == "select":
                sql, params = self._select_sql()
                rows = conn.execute(sql, params).fetchall()
                return SQLiteResponse([self.client.decode_row(self.table, row) for row in rows])

            if self.operation in {"insert", "upsert"}:
                payloads = self.payload if isinstance(self.payload, list) else [self.payload]
                saved: list[dict[str, Any]] = []
                for raw in payloads:
                    row = dict(raw)
                    now = utcnow()
                    if self.table in UUID_ID_TABLES:
                        row.setdefault("id", str(uuid4()))
                    if self.table in CREATED_UPDATED_TABLES:
                        row.setdefault("created_at", now)
                        row.setdefault("updated_at", now)
                    if self.table in UPDATED_ONLY_TABLES:
                        row.setdefault("updated_at", now)
                    if self.table == "provider_connections":
                        row.setdefault("connected_at", now)
                        row.setdefault("updated_at", now)
                    if self.table == "provider_oauth_flows":
                        row.setdefault("created_at", now)
                    if self.table == "pending_agent_actions":
                        row.setdefault(
                            "expires_at",
                            (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                        )
                    if self.table == "provider_checkout_drafts":
                        row.setdefault(
                            "expires_at",
                            (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                        )
                    columns = list(row)
                    values = [self.client.encode_value(self.table, column, row[column]) for column in columns]
                    placeholders = ",".join("?" for _ in columns)
                    column_sql = ",".join(f'"{column}"' for column in columns)
                    sql = f'INSERT INTO "{self.table}" ({column_sql}) VALUES ({placeholders})'
                    if self.operation == "upsert":
                        conflicts = self.conflict_columns or (["id"] if "id" in row else [])
                        if not conflicts:
                            raise ValueError("SQLite upsert requires conflict columns.")
                        updates = [
                            column for column in columns
                            if column not in conflicts and column not in {"id", "created_at", "connected_at"}
                        ]
                        sql += " ON CONFLICT(" + ",".join(f'"{c}"' for c in conflicts) + ")"
                        sql += " DO UPDATE SET " + ",".join(
                            f'"{column}"=excluded."{column}"' for column in updates
                        )
                    cursor = conn.execute(sql, values)
                    if "id" not in row and cursor.lastrowid:
                        row["id"] = cursor.lastrowid
                    lookup_column = "id" if "id" in row else self.conflict_columns[0]
                    stored = conn.execute(
                        f'SELECT * FROM "{self.table}" WHERE "{lookup_column}"=? LIMIT 1',
                        (row[lookup_column],),
                    ).fetchone()
                    saved.append(self.client.decode_row(self.table, stored))
                return SQLiteResponse(saved)

            sql, params = self._select_sql()
            existing = conn.execute(sql, params).fetchall()
            where, where_params = self._where()
            if self.operation == "delete":
                conn.execute(f'DELETE FROM "{self.table}"{where}', where_params)
                return SQLiteResponse([self.client.decode_row(self.table, row) for row in existing])
            if self.operation == "update":
                values = dict(self.payload)
                assignments = ",".join(f'"{column}"=?' for column in values)
                encoded = [self.client.encode_value(self.table, column, value) for column, value in values.items()]
                conn.execute(
                    f'UPDATE "{self.table}" SET {assignments}{where}', encoded + where_params,
                )
                updated = []
                for row in existing:
                    materialized = self.client.decode_row(self.table, row)
                    materialized.update(values)
                    updated.append(materialized)
                return SQLiteResponse(updated)
            raise ValueError(f"Unsupported SQLite operation: {self.operation}")


class SQLiteRPC:
    def __init__(self, client: SQLiteKitchClient, name: str, params: dict[str, Any]):
        self.client, self.name, self.params = client, name, params

    def execute(self) -> SQLiteResponse:
        handler = getattr(self, f"rpc_{self.name}", None)
        if handler is None:
            raise ValueError(f"Unsupported SQLite RPC: {self.name}")
        with self.client.transaction() as conn:
            return SQLiteResponse(handler(conn, **self.params))

    def _rows(self, conn: sqlite3.Connection, table: str, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [self.client.decode_row(table, row) for row in conn.execute(sql, params).fetchall()]

    def rpc_replace_meal_plan_range(self, conn, p_profile_id, p_start_date, p_end_date, p_days):
        conn.execute(
            "DELETE FROM meal_plans WHERE profile_id=? AND plan_date BETWEEN ? AND ?",
            (p_profile_id, p_start_date, p_end_date),
        )
        now = utcnow()
        for plan in p_days or []:
            values = [plan.get(slot) for slot in ("breakfast", "lunch", "dinner")]
            if any(str(value or "").strip() for value in values):
                conn.execute(
                    "INSERT INTO meal_plans(profile_id,plan_date,breakfast_name,lunch_name,dinner_name,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (p_profile_id, plan["plan_date"], *values, now, now),
                )
        return self._rows(conn, "meal_plans", "SELECT * FROM meal_plans WHERE profile_id=? AND plan_date BETWEEN ? AND ? ORDER BY plan_date", (p_profile_id, p_start_date, p_end_date))

    def rpc_apply_meal_plan_edits(self, conn, p_profile_id, p_edits):
        now = utcnow()
        for edit in p_edits or []:
            plan_date = edit["plan_date"]
            existing = conn.execute("SELECT * FROM meal_plans WHERE profile_id=? AND plan_date=?", (p_profile_id, plan_date)).fetchone()
            values = {slot: (existing[f"{slot}_name"] if existing else None) for slot in ("breakfast", "lunch", "dinner")}
            slot = str(edit.get("meal_slot") or "").lower()
            if slot not in values:
                raise ValueError("Invalid meal slot.")
            values[slot] = str(edit.get("meal_name") or "").strip() or None
            if any(values.values()):
                conn.execute(
                    "INSERT INTO meal_plans(profile_id,plan_date,breakfast_name,lunch_name,dinner_name,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(profile_id,plan_date) DO UPDATE SET breakfast_name=excluded.breakfast_name,lunch_name=excluded.lunch_name,dinner_name=excluded.dinner_name,updated_at=excluded.updated_at",
                    (p_profile_id, plan_date, values["breakfast"], values["lunch"], values["dinner"], now, now),
                )
            else:
                conn.execute("DELETE FROM meal_plans WHERE profile_id=? AND plan_date=?", (p_profile_id, plan_date))
        dates = [edit["plan_date"] for edit in p_edits or []]
        if not dates:
            return []
        marks = ",".join("?" for _ in dates)
        return self._rows(conn, "meal_plans", f"SELECT * FROM meal_plans WHERE profile_id=? AND plan_date IN ({marks}) ORDER BY plan_date", tuple([p_profile_id, *dates]))

    def rpc_remove_future_meal_plan_entries(self, conn, p_profile_id, p_operations):
        profile = conn.execute("SELECT timezone_name FROM profiles WHERE id=?", (p_profile_id,)).fetchone()
        try:
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo(profile["timezone_name"])).date()
        except Exception:
            today = date.today()
        affected: set[str] = set()
        for operation in p_operations or []:
            action = str(operation.get("action") or "").lower()
            start = date.fromisoformat(operation["start_date"])
            end = date.fromisoformat(operation.get("end_date") or operation["start_date"])
            if start < today or end < start:
                raise ValueError("Only valid non-past dates may be removed.")
            day = start
            while day <= end:
                affected.add(day.isoformat())
                day += timedelta(days=1)
            if action == "slot":
                slot = str(operation.get("meal_slot") or "").lower()
                if start != end or slot not in {"breakfast", "lunch", "dinner"}:
                    raise ValueError("Invalid meal-slot removal.")
                conn.execute(f"UPDATE meal_plans SET {slot}_name=NULL, updated_at=? WHERE profile_id=? AND plan_date=?", (utcnow(), p_profile_id, start.isoformat()))
                conn.execute("DELETE FROM meal_plans WHERE profile_id=? AND plan_date=? AND breakfast_name IS NULL AND lunch_name IS NULL AND dinner_name IS NULL", (p_profile_id, start.isoformat()))
            elif action in {"date", "range"}:
                conn.execute("DELETE FROM meal_plans WHERE profile_id=? AND plan_date BETWEEN ? AND ?", (p_profile_id, start.isoformat(), end.isoformat()))
            else:
                raise ValueError("Unsupported meal removal action.")
        return {"affected_dates": sorted(affected)}

    def rpc_apply_pantry_inventory_change(self, conn, p_profile_id, p_expected_revision, p_mode, p_items):
        profile = conn.execute("SELECT pantry_revision,pantry_reviewed_at FROM profiles WHERE id=?", (p_profile_id,)).fetchone()
        if not profile or int(profile["pantry_revision"]) != int(p_expected_revision):
            raise RuntimeError("pantry revision conflict")
        now = utcnow()
        if p_mode == "replace":
            conn.execute("DELETE FROM pantry_stock WHERE profile_id=?", (p_profile_id,))
            for item in p_items or []:
                name = str(item.get("name") or "").strip()
                amount = float(item.get("amount") or 0)
                if not name or amount < 0:
                    raise ValueError(
                        "Replacement items require a name and nonnegative amount."
                    )
                if amount > 0:
                    conn.execute("INSERT INTO pantry_stock(profile_id,ingredient_name,amount,unit,updated_at) VALUES(?,?,?,?,?)", (p_profile_id, name, amount, item.get("unit") or "piece", now))
            reviewed_at = now
        elif p_mode == "patch":
            if not p_items:
                raise ValueError("patch requires at least one operation")
            for item in p_items:
                action = str(item.get("action") or "").lower()
                item_id, name = item.get("id"), str(item.get("name") or "").strip()
                where = "id=?" if item_id is not None else "lower(ingredient_name)=lower(?)"
                target = item_id if item_id is not None else name
                row = conn.execute(f"SELECT * FROM pantry_stock WHERE profile_id=? AND {where}", (p_profile_id, target)).fetchone()
                amount = float(item.get("amount") or 0)
                if action == "add":
                    if not name or amount <= 0:
                        raise ValueError("Pantry add requires a name and positive amount.")
                    if row:
                        conn.execute("UPDATE pantry_stock SET amount=amount+?,updated_at=? WHERE id=?", (amount, now, row["id"]))
                    else:
                        conn.execute("INSERT INTO pantry_stock(profile_id,ingredient_name,amount,unit,updated_at) VALUES(?,?,?,?,?)", (p_profile_id, name, amount, item.get("unit") or "piece", now))
                elif action in {"set", "adjust"}:
                    if action == "set" and amount < 0:
                        raise ValueError("Pantry set amount cannot be negative.")
                    if not row and action == "set" and name and amount > 0:
                        conn.execute("INSERT INTO pantry_stock(profile_id,ingredient_name,amount,unit,updated_at) VALUES(?,?,?,?,?)", (p_profile_id, name, amount, item.get("unit") or "piece", now))
                    elif not row:
                        raise ValueError("Pantry operation referenced an unknown row.")
                    else:
                        next_amount = amount if action == "set" else max(0, float(row["amount"]) + amount)
                        conn.execute("UPDATE pantry_stock SET ingredient_name=?,amount=?,unit=?,updated_at=? WHERE id=?", (name or row["ingredient_name"], next_amount, item.get("unit") or row["unit"], now, row["id"]))
                        conn.execute("DELETE FROM pantry_stock WHERE id=? AND amount<=0", (row["id"],))
                elif action in {"remove", "delete"}:
                    if not row:
                        raise ValueError("Pantry remove referenced an unknown row.")
                    conn.execute("DELETE FROM pantry_stock WHERE id=?", (row["id"],))
                else:
                    raise ValueError("Unsupported pantry action.")
            reviewed_at = profile["pantry_reviewed_at"]
        else:
            raise ValueError("pantry mode must be patch or replace")
        revision = int(p_expected_revision) + 1
        conn.execute("UPDATE profiles SET pantry_revision=?,pantry_reviewed_at=? WHERE id=?", (revision, reviewed_at, p_profile_id))
        pantry = self._rows(conn, "pantry_stock", "SELECT * FROM pantry_stock WHERE profile_id=? ORDER BY ingredient_name", (p_profile_id,))
        return {"revision": revision, "reviewed_at": reviewed_at, "pantry": pantry}

    def rpc_apply_pantry_cart_reconciliation(self, conn, p_profile_id, p_expected_revision, p_cart_reconciliation):
        profile = conn.execute("SELECT pantry_revision FROM profiles WHERE id=?", (p_profile_id,)).fetchone()
        if not profile or int(profile["pantry_revision"]) != int(p_expected_revision):
            raise RuntimeError("pantry revision conflict")
        rows = conn.execute("SELECT * FROM grocery_cart_items WHERE profile_id=?", (p_profile_id,)).fetchall()
        if len(rows) != len(p_cart_reconciliation or []):
            raise RuntimeError("native cart changed during pantry reconciliation")
        changed = False
        now = utcnow()
        for item in p_cart_reconciliation or []:
            row = conn.execute("SELECT * FROM grocery_cart_items WHERE profile_id=? AND id=?", (p_profile_id, int(item["id"]))).fetchone()
            if not row:
                raise ValueError("cart reconciliation referenced an unknown row")
            amount = float(item["purchase_amount"])
            unit = item.get("purchase_unit") or item["required_unit"]
            changed = changed or float(row["purchase_amount"]) != amount or row["purchase_unit"] != unit
            conn.execute("UPDATE grocery_cart_items SET purchase_amount=?,purchase_unit=?,pantry_allocation=?,updated_at=? WHERE id=?", (amount, unit, json.dumps(item.get("pantry_allocation") or {}), now, row["id"]))
        if changed:
            conn.execute("DELETE FROM provider_checkout_drafts WHERE profile_id=?", (p_profile_id,))
        cart = self._rows(conn, "grocery_cart_items", "SELECT * FROM grocery_cart_items WHERE profile_id=? ORDER BY category,ingredient_name", (p_profile_id,))
        return {"pantry_revision": int(p_expected_revision), "provider_review_invalidated": changed, "grocery_cart": cart}

    def rpc_apply_native_grocery_cart_changes(self, conn, p_profile_id, p_changes):
        now = utcnow()
        for change in p_changes or []:
            action = str(change.get("action") or "add").lower()
            name = str(change.get("name") or change.get("item") or "").strip()
            unit = change.get("unit") or "piece"
            item_id = change.get("item_id") or change.get("id")
            if action == "add":
                amount = float(change.get("amount", change.get("quantity", 1)))
                matches = conn.execute("SELECT * FROM grocery_cart_items WHERE profile_id=? AND lower(ingredient_name)=lower(?) AND lower(unit)=lower(?)", (p_profile_id, name, unit)).fetchall()
                if len(matches) > 1:
                    raise ValueError("ambiguous native cart row")
                if matches:
                    conn.execute("UPDATE grocery_cart_items SET amount=amount+?,purchase_amount=purchase_amount+?,updated_at=? WHERE id=?", (amount, amount, now, matches[0]["id"]))
                else:
                    conn.execute("INSERT INTO grocery_cart_items(profile_id,ingredient_name,amount,unit,category,source,checked,purchase_amount,purchase_unit,pantry_allocation,created_at,updated_at) VALUES(?,?,?,?,?,'manual',?,?,?,?,?,?)", (p_profile_id, name, amount, unit, change.get("category") or "General", int(bool(change.get("checked", False))), amount, unit, "{}", now, now))
            else:
                if item_id is None:
                    matches = conn.execute("SELECT * FROM grocery_cart_items WHERE profile_id=? AND lower(ingredient_name)=lower(?)", (p_profile_id, name)).fetchall()
                    if len(matches) != 1:
                        raise ValueError("native cart row not uniquely identified")
                    item_id = matches[0]["id"]
                if action in {"remove", "delete"}:
                    conn.execute("DELETE FROM grocery_cart_items WHERE profile_id=? AND id=?", (p_profile_id, item_id))
                elif action in {"set", "update"}:
                    row = conn.execute("SELECT * FROM grocery_cart_items WHERE profile_id=? AND id=?", (p_profile_id, item_id)).fetchone()
                    if not row:
                        raise ValueError("native cart row not found")
                    amount = float(change.get("amount", row["amount"]))
                    conn.execute("UPDATE grocery_cart_items SET ingredient_name=?,amount=?,unit=?,category=?,checked=?,purchase_amount=?,purchase_unit=?,pantry_allocation=?,updated_at=? WHERE id=?", (change.get("name", row["ingredient_name"]), amount, change.get("unit", row["unit"]), change.get("category", row["category"]), int(change.get("checked", row["checked"])), float(change.get("purchase_amount", amount)), change.get("unit", row["purchase_unit"]), "{}" if "amount" in change or "unit" in change else row["pantry_allocation"], now, item_id))
                else:
                    raise ValueError("unsupported native-cart action")
        conn.execute("DELETE FROM provider_checkout_drafts WHERE profile_id=?", (p_profile_id,))
        return self._rows(conn, "grocery_cart_items", "SELECT * FROM grocery_cart_items WHERE profile_id=? ORDER BY category,ingredient_name", (p_profile_id,))

    def rpc_replace_planned_grocery_cart(self, conn, p_profile_id, p_cart_items=None, p_recipe_grocery_plan_id=None):
        if p_recipe_grocery_plan_id:
            conn.execute("DELETE FROM grocery_cart_items WHERE profile_id=? AND source='agent' AND recipe_grocery_plan_id=?", (p_profile_id, p_recipe_grocery_plan_id))
        else:
            conn.execute("DELETE FROM grocery_cart_items WHERE profile_id=? AND source='agent'", (p_profile_id,))
        now = utcnow()
        for item in p_cart_items or []:
            amount = float(item.get("amount") or 1)
            unit = item.get("unit") or "piece"
            conn.execute("INSERT INTO grocery_cart_items(profile_id,recipe_grocery_plan_id,ingredient_name,amount,unit,category,source,checked,purchase_amount,purchase_unit,pantry_allocation,created_at,updated_at) VALUES(?,?,?,?,?,?,'agent',?,?,?,?,?,?)", (p_profile_id, p_recipe_grocery_plan_id, item["ingredient_name"], amount, unit, item.get("category") or "General", int(bool(item.get("checked", False))), float(item.get("purchase_amount", amount)), item.get("purchase_unit") or unit, json.dumps(item.get("pantry_allocation") or {}), now, now))
        conn.execute("DELETE FROM provider_checkout_drafts WHERE profile_id=?", (p_profile_id,))
        return self._rows(conn, "grocery_cart_items", "SELECT * FROM grocery_cart_items WHERE profile_id=? ORDER BY id", (p_profile_id,))

    def rpc_save_recipe_grocery_plan_with_cart(self, conn, **p):
        plan_id, profile_id = p["p_plan_id"], p["p_profile_id"]
        existed = conn.execute("SELECT 1 FROM recipe_grocery_plans WHERE id=? AND profile_id=?", (plan_id, profile_id)).fetchone() is not None
        values = (
            plan_id, profile_id, json.dumps(p.get("p_scope") or {}), p.get("p_request_text") or "",
            json.dumps(p.get("p_recipe_cards") or []), json.dumps(p.get("p_ingredients") or []),
            json.dumps(p.get("p_pantry_considerations") or []), p.get("p_household_size") or 1,
            p.get("p_notes") or "", p.get("p_source") or "agent", int(bool(p.get("p_updates_cart"))),
            len(p.get("p_cart_items") or []) if p.get("p_updates_cart") else 0,
            p.get("p_created_at") or utcnow(), p.get("p_updated_at") or utcnow(),
        )
        conn.execute("INSERT INTO recipe_grocery_plans(id,profile_id,scope,request_text,recipe_cards,ingredients,pantry_considerations,household_size,notes,source,updates_cart,cart_item_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET scope=excluded.scope,request_text=excluded.request_text,recipe_cards=excluded.recipe_cards,ingredients=excluded.ingredients,pantry_considerations=excluded.pantry_considerations,household_size=excluded.household_size,notes=excluded.notes,source=excluded.source,updates_cart=excluded.updates_cart,cart_item_count=excluded.cart_item_count,updated_at=excluded.updated_at", values)
        if p.get("p_updates_cart"):
            if not existed:
                conn.execute("DELETE FROM grocery_cart_items WHERE profile_id=? AND source='agent'", (profile_id,))
            cart = self.rpc_replace_planned_grocery_cart(conn, profile_id, p.get("p_cart_items") or [], plan_id)
        else:
            cart = self._rows(conn, "grocery_cart_items", "SELECT * FROM grocery_cart_items WHERE profile_id=? ORDER BY id", (profile_id,))
        plan = self._rows(conn, "recipe_grocery_plans", "SELECT * FROM recipe_grocery_plans WHERE id=?", (plan_id,))[0]
        return {"plan": plan, "cart": cart}

    def rpc_delete_recipe_grocery_plan(self, conn, p_profile_id, p_plan_id):
        conn.execute("DELETE FROM grocery_cart_items WHERE profile_id=? AND recipe_grocery_plan_id=?", (p_profile_id, p_plan_id))
        cursor = conn.execute("DELETE FROM recipe_grocery_plans WHERE profile_id=? AND id=?", (p_profile_id, p_plan_id))
        if cursor.rowcount:
            conn.execute("DELETE FROM provider_checkout_drafts WHERE profile_id=?", (p_profile_id,))
        return bool(cursor.rowcount)

    def rpc_claim_provider_checkout_operation(self, conn, p_profile_id, p_provider, p_provider_environment, p_operation_id, p_lease_seconds=120):
        now = utcnow()
        lease_expires = (
            datetime.now(timezone.utc) + timedelta(seconds=max(1, int(p_lease_seconds)))
        ).isoformat()
        existing = conn.execute(
            "SELECT id FROM provider_checkout_drafts WHERE profile_id=? AND provider=? AND provider_environment=?",
            (p_profile_id, p_provider, p_provider_environment),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO provider_checkout_drafts(id,profile_id,provider,provider_environment,created_at,updated_at,expires_at) VALUES(?,?,?,?,?,?,?)",
                (
                    str(uuid4()), p_profile_id, p_provider, p_provider_environment,
                    now, now,
                    (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                ),
            )
        cursor = conn.execute(
            "UPDATE provider_checkout_drafts SET operation_id=?,lease_expires_at=?,updated_at=? WHERE profile_id=? AND provider=? AND provider_environment=? AND (operation_id IS NULL OR lease_expires_at IS NULL OR lease_expires_at<=? OR operation_id=?)",
            (p_operation_id, lease_expires, now, p_profile_id, p_provider, p_provider_environment, now, p_operation_id),
        )
        return bool(cursor.rowcount)

    def rpc_release_provider_checkout_operation(self, conn, p_profile_id, p_provider, p_provider_environment, p_operation_id):
        cursor = conn.execute("UPDATE provider_checkout_drafts SET operation_id=NULL,lease_expires_at=NULL,updated_at=? WHERE profile_id=? AND provider=? AND provider_environment=? AND operation_id=?", (utcnow(), p_profile_id, p_provider, p_provider_environment, p_operation_id))
        return bool(cursor.rowcount)

    def rpc_claim_pending_agent_action(self, conn, p_profile_id, p_action_id):
        now = utcnow()
        cursor = conn.execute("UPDATE pending_agent_actions SET status='executing',updated_at=? WHERE profile_id=? AND id=? AND status='pending' AND expires_at>?", (now, p_profile_id, p_action_id, now))
        if not cursor.rowcount:
            return None
        rows = self._rows(conn, "pending_agent_actions", "SELECT * FROM pending_agent_actions WHERE id=?", (p_action_id,))
        return rows[0] if rows else None


_CLIENTS: dict[str, SQLiteKitchClient] = {}
_CLIENTS_LOCK = threading.RLock()


def create_sqlite_client(path: str | None = None) -> SQLiteKitchClient:
    configured = path or os.environ.get("KITCH_SQLITE_PATH", ".kitch/kitch.sqlite3")
    key = str(configured)
    with _CLIENTS_LOCK:
        if key not in _CLIENTS:
            _CLIENTS[key] = SQLiteKitchClient(configured)
        return _CLIENTS[key]
