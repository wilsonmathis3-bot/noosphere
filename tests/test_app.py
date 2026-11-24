"""API tests for Noosphere. Each test run uses its own temp DB and upload dir."""
import importlib
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def make_client(tmp_path, monkeypatch, admin_token=""):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ADMIN_TOKEN", admin_token)
    monkeypatch.setenv("MAX_UPLOAD_MB", "0.01")  # ~10 KB keeps the size test fast
    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    return TestClient(main.app), main


@pytest.fixture
def client(tmp_path, monkeypatch):
    c, _ = make_client(tmp_path, monkeypatch)
    return c


def post(client, **kw):
    data = {"title": kw.pop("title", "Idea"), "content": kw.pop("content", "Body"), **kw.pop("data", {})}
    return client.post("/thoughts", data=data, files=kw.pop("files", None))


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_create_list_get(client):
    r = post(client, title="  Hello  ", content="World", data={"author": ""})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["title"] == "Hello" and t["author"] == "Anonymous" and t["image_url"] is None
    assert [x["id"] for x in client.get("/thoughts").json()] == [t["id"]]
    assert client.get(f"/thoughts/{t['id']}").json()["content"] == "World"
    assert client.get("/thoughts/9999").status_code == 404


def test_validation(client):
    assert post(client, title=" ", content="x").status_code == 400
    assert post(client, title="x" * 201).status_code == 400
    assert post(client, data={"author": "a" * 101}).status_code == 400
    assert post(client, files={"image": ("evil.svg", b"<svg/>", "image/svg+xml")}).status_code == 400


def test_image_upload_and_size_limit(tmp_path, monkeypatch):
    client, main = make_client(tmp_path, monkeypatch)
    r = post(client, files={"image": ("pic.png", io.BytesIO(PNG_1PX), "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["image_url"]
    assert client.get(url).content == PNG_1PX

    big = post(client, files={"image": ("big.png", b"0" * 20_000, "image/png")})
    assert big.status_code == 413
    assert len(list(main.UPLOAD_DIR.iterdir())) == 1  # partial upload cleaned up


def test_list_limit_is_capped(client):
    for i in range(3):
        post(client, title=f"t{i}")
    assert len(client.get("/thoughts?limit=2").json()) == 2
    assert len(client.get("/thoughts?limit=100000&skip=-5").json()) == 3


def test_delete_disabled_without_admin_token(client):
    tid = post(client).json()["id"]
    assert client.delete(f"/thoughts/{tid}").status_code == 403
    assert client.get(f"/thoughts/{tid}").status_code == 200


def test_delete_with_admin_token_removes_post_and_image(tmp_path, monkeypatch):
    client, main = make_client(tmp_path, monkeypatch, admin_token="s3cret")
    t = post(client, files={"image": ("pic.png", PNG_1PX, "image/png")}).json()
    assert client.delete(f"/thoughts/{t['id']}").status_code == 401
    assert client.delete(f"/thoughts/{t['id']}", headers={"X-Admin-Token": "nope"}).status_code == 401
    assert client.delete(f"/thoughts/{t['id']}", headers={"X-Admin-Token": "s3cret"}).json() == {"deleted": True}
    assert client.get(f"/thoughts/{t['id']}").status_code == 404
    assert list(main.UPLOAD_DIR.iterdir()) == []


def test_spa_fallback_serves_frontend(client):
    r = client.get("/some/client/route")
    assert r.status_code == 200 and "Noosphere" in r.text
