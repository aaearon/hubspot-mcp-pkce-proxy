"""Async SQLite database layer."""

from datetime import datetime, timezone

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    client_secret_hash TEXT NOT NULL,
    redirect_uris TEXT NOT NULL,
    client_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auth_states (
    state_key TEXT PRIMARY KEY,
    code_verifier TEXT NOT NULL,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    copilot_state TEXT,
    scope TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_codes (
    code TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type TEXT NOT NULL,
    expires_in INTEGER,
    client_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(_SCHEMA)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # --- Clients ---

    async def insert_client(
        self,
        client_id: str,
        client_secret_hash: str,
        redirect_uris: str,
        client_name: str | None = None,
    ) -> None:
        await self._db.execute(
            "INSERT INTO clients (client_id, client_secret_hash,"
            " redirect_uris, client_name) VALUES (?, ?, ?, ?)",
            (client_id, client_secret_hash, redirect_uris, client_name),
        )
        await self._db.commit()

    async def get_client(self, client_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # --- Auth States ---

    async def insert_auth_state(
        self,
        state_key: str,
        code_verifier: str,
        client_id: str,
        redirect_uri: str,
        copilot_state: str | None,
        scope: str | None,
        expires_at: str,
    ) -> None:
        await self._db.execute(
            "INSERT INTO auth_states (state_key, code_verifier,"
            " client_id, redirect_uri, copilot_state, scope,"
            " expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                state_key, code_verifier, client_id,
                redirect_uri, copilot_state, scope, expires_at,
            ),
        )
        await self._db.commit()

    async def get_auth_state(self, state_key: str) -> dict | None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "SELECT * FROM auth_states"
            " WHERE state_key = ? AND expires_at > ?",
            (state_key, now),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_auth_state(self, state_key: str) -> None:
        await self._db.execute(
            "DELETE FROM auth_states WHERE state_key = ?", (state_key,)
        )
        await self._db.commit()

    # --- Auth Codes ---

    async def insert_auth_code(
        self,
        code: str,
        access_token: str,
        refresh_token: str | None,
        token_type: str,
        expires_in: int | None,
        client_id: str,
        expires_at: str,
    ) -> None:
        await self._db.execute(
            "INSERT INTO auth_codes (code, access_token,"
            " refresh_token, token_type, expires_in, client_id,"
            " expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                code, access_token, refresh_token,
                token_type, expires_in, client_id, expires_at,
            ),
        )
        await self._db.commit()

    async def get_and_delete_auth_code(self, code: str) -> dict | None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "DELETE FROM auth_codes"
            " WHERE code = ? AND expires_at > ?"
            " RETURNING *",
            (code, now),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        await self._db.commit()
        return dict(row)

    # --- Cleanup ---

    async def cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "DELETE FROM auth_states WHERE expires_at < ?", (now,)
        )
        await self._db.execute(
            "DELETE FROM auth_codes WHERE expires_at < ?", (now,)
        )
        await self._db.commit()
