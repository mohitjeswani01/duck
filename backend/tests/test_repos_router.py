"""Phase 4 addition: GET /repos/{repo_id}/file-content, needed so the
frontend's hypothesis-evidence chips can show a code snippet. Uses the TestClient
directly against the real DB-backed app (repo_fixture provides a seeded repo).
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_get_repo_by_id_returns_owner_and_name(repo_fixture):
    async with await _client() as client:
        response = await client.get(f"/repos/{repo_fixture}")

    assert response.status_code == 200
    body = response.json()
    assert body["owner"] == "test"
    assert body["name"] == "repo"
    assert body["id"] == str(repo_fixture)


async def test_get_repo_by_id_404_when_missing():
    import uuid

    async with await _client() as client:
        response = await client.get(f"/repos/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_get_file_content_returns_real_content(repo_fixture):
    async with await _client() as client:
        response = await client.get(f"/repos/{repo_fixture}/file-content", params={"path": "auth.js"})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "auth.js"
    assert "isTokenExpired" in body["content"]
    assert body["total_lines"] > 0


async def test_get_file_content_404_for_missing_file(repo_fixture):
    async with await _client() as client:
        response = await client.get(f"/repos/{repo_fixture}/file-content", params={"path": "does/not/exist.js"})

    assert response.status_code == 404


async def test_get_file_content_404_for_missing_repo():
    import uuid

    async with await _client() as client:
        response = await client.get(f"/repos/{uuid.uuid4()}/file-content", params={"path": "auth.js"})

    assert response.status_code == 404


async def test_get_file_content_rejects_path_traversal(repo_fixture):
    async with await _client() as client:
        response = await client.get(f"/repos/{repo_fixture}/file-content", params={"path": "../../etc/passwd"})

    assert response.status_code == 422
