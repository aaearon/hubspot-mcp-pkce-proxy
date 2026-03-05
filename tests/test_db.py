"""Tests for database layer."""

from datetime import datetime, timedelta, timezone

from hubspot_mcp_proxy.db import Database


class TestDatabaseInit:
    async def test_busy_timeout_is_set(self, db):
        """busy_timeout pragma must be set after init."""
        cursor = await db._db.execute("PRAGMA busy_timeout")
        row = await cursor.fetchone()
        assert row[0] == 5000

    async def test_in_memory_database(self):
        """Database works with ':memory:' path."""
        db = Database(":memory:")
        await db.init()
        await db.insert_client(
            client_id="c1",
            client_secret_hash="hash1",
            redirect_uris='["https://example.com/cb"]',
            client_name="Test App",
        )
        row = await db.get_client("c1")
        assert row is not None
        assert row["client_id"] == "c1"
        await db.close()

    async def test_journal_mode_for_in_memory(self):
        """In-memory databases use 'memory' journal mode (WAL not applicable)."""
        db = Database(":memory:")
        await db.init()
        cursor = await db._db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0] == "memory"
        await db.close()


class TestSchemaInit:
    async def test_tables_exist_after_init(self, db):
        """Schema must create all tables during init."""
        cursor = await db._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        assert "auth_codes" in tables
        assert "auth_states" in tables
        assert "clients" in tables

    async def test_init_idempotent_on_existing_db(self, tmp_path):
        """Re-init on existing DB must not lose tables."""
        path = str(tmp_path / "idem.db")
        db1 = Database(path)
        await db1.init()
        await db1.close()

        db2 = Database(path)
        await db2.init()
        cursor = await db2._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        await db2.close()
        assert "auth_states" in tables


class TestClients:
    async def test_insert_and_get_client(self, db):
        await db.insert_client(
            client_id="c1",
            client_secret_hash="hash1",
            redirect_uris='["https://example.com/cb"]',
            client_name="Test App",
        )
        row = await db.get_client("c1")
        assert row is not None
        assert row["client_id"] == "c1"
        assert row["client_secret_hash"] == "hash1"
        assert row["client_name"] == "Test App"

    async def test_get_nonexistent_client(self, db):
        row = await db.get_client("nonexistent")
        assert row is None


class TestAuthStates:
    async def test_insert_and_get_auth_state(self, db):
        expires = datetime.now(timezone.utc) + timedelta(seconds=600)
        await db.insert_auth_state(
            state_key="s1",
            code_verifier="verifier1",
            client_id="c1",
            redirect_uri="https://example.com/cb",
            copilot_state="copilot-state-1",
            scope="contacts",
            expires_at=expires.isoformat(),
        )
        row = await db.get_auth_state("s1")
        assert row is not None
        assert row["code_verifier"] == "verifier1"
        assert row["copilot_state"] == "copilot-state-1"

    async def test_delete_auth_state(self, db):
        expires = datetime.now(timezone.utc) + timedelta(seconds=600)
        await db.insert_auth_state(
            state_key="s2",
            code_verifier="v2",
            client_id="c1",
            redirect_uri="https://example.com/cb",
            copilot_state="cs2",
            scope="contacts",
            expires_at=expires.isoformat(),
        )
        await db.delete_auth_state("s2")
        row = await db.get_auth_state("s2")
        assert row is None


class TestAuthCodes:
    async def test_insert_and_get_delete_auth_code(self, db):
        expires = datetime.now(timezone.utc) + timedelta(seconds=300)
        await db.insert_auth_code(
            code="code1",
            access_token="at1",
            refresh_token="rt1",
            token_type="bearer",
            expires_in=3600,
            client_id="c1",
            expires_at=expires.isoformat(),
        )
        row = await db.get_and_delete_auth_code("code1")
        assert row is not None
        assert row["access_token"] == "at1"
        assert row["refresh_token"] == "rt1"
        # Second retrieval should return None (consumed)
        row2 = await db.get_and_delete_auth_code("code1")
        assert row2 is None

    async def test_get_nonexistent_code(self, db):
        row = await db.get_and_delete_auth_code("nonexistent")
        assert row is None


class TestCleanup:
    async def test_cleanup_expired(self, db):
        past = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat()
        await db.insert_auth_state(
            state_key="expired",
            code_verifier="v",
            client_id="c1",
            redirect_uri="https://example.com/cb",
            copilot_state="cs",
            scope="contacts",
            expires_at=past,
        )
        await db.insert_auth_state(
            state_key="valid",
            code_verifier="v2",
            client_id="c1",
            redirect_uri="https://example.com/cb",
            copilot_state="cs2",
            scope="contacts",
            expires_at=future,
        )
        await db.cleanup_expired()
        assert await db.get_auth_state("expired") is None
        assert await db.get_auth_state("valid") is not None
