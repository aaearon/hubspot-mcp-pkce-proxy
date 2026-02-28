"""Tests for database layer."""

from datetime import datetime, timedelta, timezone

import pytest

from hubspot_mcp_proxy.db import Database


@pytest.fixture
async def db(tmp_path):
    """Provide an initialized in-memory-like temp database."""
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


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
