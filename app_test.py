"""
Pytest module for testing SkyDaddy: hashing, file validation, and Flask routes.

MIT License

Copyright (c) 2023 Saket Upadhyay
"""

import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

import pytest

import app as app_module
from app import (
    ALLOWED_EXT,
    MAX_CHUNK_BYTES,
    MID_CHUNK_BYTES,
    MIN_CHUNK_BYTES,
    SHORT_CODE_LEN,
    _choose_chunk_profile,
    _generate_short_code,
    _is_hex_sha256,
    _reconcile_map,
    allowed_file,
    get_sha256,
)
from app import app as flask_app


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with fully isolated temp directories."""
    upload = tmp_path / "uploads"
    resumable = tmp_path / "resumable"
    sessions = tmp_path / "flask_sessions"
    map_file = tmp_path / "file_map.json"

    upload.mkdir()
    resumable.mkdir()
    sessions.mkdir()

    monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload)
    monkeypatch.setattr(app_module, "PERMA_FOLDER", tmp_path / "perma")
    monkeypatch.setattr(app_module, "RESUMABLE_FOLDER", resumable)
    monkeypatch.setattr(app_module, "MAP_FILE", map_file)
    monkeypatch.setattr(app_module, "ADMIN_TOKEN", "")

    flask_app.config["UPLOAD_FOLDER"] = str(upload)
    flask_app.config["SESSION_FILE_DIR"] = str(sessions)
    flask_app.config["TESTING"] = True

    with flask_app.test_client() as c:
        yield c


# ── unit: hashing ─────────────────────────────────────────────────────────────

class TestHash:
    def test_hash(self):
        content = b"skydaddy test content"
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            assert get_sha256(tmp) == expected
        finally:
            tmp.unlink(missing_ok=True)

    def test_hash_large(self):
        content = os.urandom(200_000)
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            assert get_sha256(tmp) == expected
        finally:
            tmp.unlink(missing_ok=True)


# ── unit: allowed_file ────────────────────────────────────────────────────────

class TestAllowedExt:
    def test_allowed_extensions(self):
        for ext in ALLOWED_EXT:
            assert allowed_file("somefile." + ext)
            assert allowed_file("somefile." + ext.upper())

    def test_blocked_extensions(self):
        for ext in ("exe", "sh", "bat", "js", "php", "py"):
            assert not allowed_file("malicious." + ext)

    def test_no_extension(self):
        assert not allowed_file("nodotfile")

    def test_empty_string(self):
        assert not allowed_file("")


# ── unit: _is_hex_sha256 ──────────────────────────────────────────────────────

class TestIsHexSha256:
    def test_valid(self):
        assert _is_hex_sha256("a" * 64) is True

    def test_all_hex_digits(self):
        assert _is_hex_sha256("0123456789abcdef" * 4) is True

    def test_too_short(self):
        assert _is_hex_sha256("a" * 63) is False

    def test_too_long(self):
        assert _is_hex_sha256("a" * 65) is False

    def test_non_hex_char(self):
        assert _is_hex_sha256("g" * 64) is False

    def test_uppercase_rejected(self):
        # Implementation only accepts lowercase
        assert _is_hex_sha256("A" * 64) is False

    def test_empty(self):
        assert _is_hex_sha256("") is False


# ── unit: _choose_chunk_profile ───────────────────────────────────────────────

class TestChooseChunkProfile:
    def test_none_rtt(self):
        size, conc = _choose_chunk_profile(None)
        assert size == MAX_CHUNK_BYTES
        assert conc == 4

    def test_high_rtt(self):
        size, conc = _choose_chunk_profile(3000)
        assert size == MIN_CHUNK_BYTES
        assert conc == 1

    def test_medium_high_rtt(self):
        size, conc = _choose_chunk_profile(1200)
        assert size == MID_CHUNK_BYTES
        assert conc == 1

    def test_medium_rtt(self):
        size, conc = _choose_chunk_profile(800)
        assert size == MID_CHUNK_BYTES
        assert conc == 2

    def test_low_rtt(self):
        size, conc = _choose_chunk_profile(100)
        assert size == MAX_CHUNK_BYTES
        assert conc == 4

    def test_boundary_2500(self):
        size, conc = _choose_chunk_profile(2500)
        assert size == MIN_CHUNK_BYTES
        assert conc == 1


# ── unit: _generate_short_code ────────────────────────────────────────────────

class TestGenerateShortCode:
    def test_length(self):
        code = _generate_short_code("a" * 64, {})
        assert len(code) == SHORT_CODE_LEN

    def test_avoids_existing(self):
        first = _generate_short_code("a" * 64, {})
        second = _generate_short_code("a" * 64, {first: {}})
        assert second != first

    def test_avoids_reserved_names(self):
        for _ in range(30):
            code = _generate_short_code(os.urandom(32).hex(), {})
            assert code not in {"RESETCACHE", "SAVELOCAL"}


# ── unit: _reconcile_map ─────────────────────────────────────────────────────

class TestReconcileMap:
    def test_removes_stale_reservation(self, tmp_path, monkeypatch):
        map_file = tmp_path / "file_map.json"
        upload = tmp_path / "uploads"
        upload.mkdir()
        old_ts = "2020-01-01T00:00:00+00:00"
        map_file.write_text(
            json.dumps({"STALE001": {"reserved": True, "reserved_at": old_ts, "file": None}})
        )
        monkeypatch.setattr(app_module, "MAP_FILE", map_file)
        monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload)
        monkeypatch.setattr(app_module, "RESERVATION_TTL_SECONDS", 1)

        _reconcile_map()

        assert "STALE001" not in json.loads(map_file.read_text())

    def test_removes_missing_file_entry(self, tmp_path, monkeypatch):
        map_file = tmp_path / "file_map.json"
        upload = tmp_path / "uploads"
        upload.mkdir()
        map_file.write_text(
            json.dumps({"CODE0001": {"file": "ghost.txt", "name": "ghost.txt"}})
        )
        monkeypatch.setattr(app_module, "MAP_FILE", map_file)
        monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload)

        _reconcile_map()

        assert "CODE0001" not in json.loads(map_file.read_text())

    def test_keeps_valid_reservation(self, tmp_path, monkeypatch):
        map_file = tmp_path / "file_map.json"
        upload = tmp_path / "uploads"
        upload.mkdir()
        from datetime import datetime, timezone
        fresh_ts = datetime.now(timezone.utc).isoformat()
        map_file.write_text(
            json.dumps({"FRESH01": {"reserved": True, "reserved_at": fresh_ts, "file": None}})
        )
        monkeypatch.setattr(app_module, "MAP_FILE", map_file)
        monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload)
        monkeypatch.setattr(app_module, "RESERVATION_TTL_SECONDS", 86400)

        _reconcile_map()

        assert "FRESH01" in json.loads(map_file.read_text())

    def test_keeps_existing_file(self, tmp_path, monkeypatch):
        map_file = tmp_path / "file_map.json"
        upload = tmp_path / "uploads"
        upload.mkdir()
        (upload / "abc.txt").write_bytes(b"data")
        map_file.write_text(
            json.dumps({"CODE0002": {"file": "abc.txt", "name": "abc.txt"}})
        )
        monkeypatch.setattr(app_module, "MAP_FILE", map_file)
        monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload)

        _reconcile_map()

        assert "CODE0002" in json.loads(map_file.read_text())

    def test_invalid_reserved_at_timestamp(self, tmp_path, monkeypatch):
        map_file = tmp_path / "file_map.json"
        upload = tmp_path / "uploads"
        upload.mkdir()
        map_file.write_text(
            json.dumps({"CODE0003": {"reserved": True, "reserved_at": "not-a-date", "file": None}})
        )
        monkeypatch.setattr(app_module, "MAP_FILE", map_file)
        monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload)
        monkeypatch.setattr(app_module, "RESERVATION_TTL_SECONDS", 1)

        _reconcile_map()  # should not raise; entry stays (reserved_at unreadable)


# ── route: GET /api/ping ──────────────────────────────────────────────────────

class TestPing:
    def test_ping(self, client):
        r = client.get("/api/ping")
        assert r.status_code == 200
        assert r.get_json() == {"ok": True}


# ── route: GET / and POST / ───────────────────────────────────────────────────

class TestUploadPage:
    def test_get(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_post_no_file_part_redirects(self, client):
        r = client.post("/", content_type="multipart/form-data", data={})
        assert r.status_code == 302

    def test_post_no_file_xhr(self, client):
        r = client.post(
            "/",
            content_type="multipart/form-data",
            data={},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_post_disallowed_ext_xhr(self, client):
        r = client.post(
            "/",
            content_type="multipart/form-data",
            data={"file": (io.BytesIO(b"evil"), "malware.exe")},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert r.status_code == 415

    def test_post_valid_file_xhr(self, client):
        r = client.post(
            "/",
            content_type="multipart/form-data",
            data={"file": (io.BytesIO(b"hello world"), "test.txt")},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert "code" in body
        assert len(body["code"]) == SHORT_CODE_LEN

    def test_post_valid_file_html(self, client):
        r = client.post(
            "/",
            content_type="multipart/form-data",
            data={"file": (io.BytesIO(b"report content"), "report.pdf")},
        )
        assert r.status_code == 200

    def test_post_empty_filename_xhr(self, client):
        r = client.post(
            "/",
            content_type="multipart/form-data",
            data={"file": (io.BytesIO(b"data"), "")},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert r.status_code == 400

    def test_post_file_too_large_xhr(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "MAX_UPLOAD_BYTES", 5)
        r = client.post(
            "/",
            content_type="multipart/form-data",
            data={"file": (io.BytesIO(b"too much data"), "big.txt")},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Content-Length": "13",
            },
        )
        assert r.status_code == 413

    def test_post_deduplicate_same_content(self, client):
        content = b"duplicate content"
        for _ in range(2):
            r = client.post(
                "/",
                content_type="multipart/form-data",
                data={"file": (io.BytesIO(content), "dup.txt")},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert r.status_code == 200


# ── route: POST /api/upload/init ─────────────────────────────────────────────

class TestResumableUploadInit:
    def test_missing_size(self, client):
        r = client.post("/api/upload/init", json={"filename": "test.txt"})
        assert r.status_code == 400

    def test_invalid_size_zero(self, client):
        r = client.post("/api/upload/init", json={"filename": "test.txt", "size": 0})
        assert r.status_code == 400

    def test_invalid_size_negative(self, client):
        r = client.post("/api/upload/init", json={"filename": "test.txt", "size": -1})
        assert r.status_code == 400

    def test_size_too_large(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "MAX_UPLOAD_BYTES", 100)
        r = client.post("/api/upload/init", json={"filename": "test.txt", "size": 9999})
        assert r.status_code == 413

    def test_invalid_filename_empty(self, client):
        r = client.post("/api/upload/init", json={"filename": "", "size": 1000})
        assert r.status_code == 400

    def test_disallowed_extension(self, client):
        r = client.post("/api/upload/init", json={"filename": "virus.exe", "size": 1000})
        assert r.status_code == 415

    def test_invalid_file_sha256(self, client):
        r = client.post(
            "/api/upload/init",
            json={"filename": "doc.pdf", "size": 1000, "file_sha256": "tooshort"},
        )
        assert r.status_code == 400

    def test_valid_init(self, client):
        r = client.post("/api/upload/init", json={"filename": "doc.pdf", "size": 1000})
        assert r.status_code == 200
        body = r.get_json()
        assert "upload_id" in body
        assert "chunk_size" in body
        assert "total_chunks" in body
        assert "code" in body

    def test_valid_init_with_rtt(self, client):
        r = client.post(
            "/api/upload/init",
            json={"filename": "video.mp4", "size": 50_000, "rtt_ms": 3000},
        )
        assert r.status_code == 200

    def test_valid_init_with_sha256(self, client):
        sha = "a" * 64
        r = client.post(
            "/api/upload/init",
            json={"filename": "doc.txt", "size": 100, "file_sha256": sha},
        )
        assert r.status_code == 200
        assert "upload_id" in r.get_json()


# ── route: GET /api/upload/status/<id> ───────────────────────────────────────

class TestResumableUploadStatus:
    def test_not_found(self, client):
        r = client.get("/api/upload/status/doesnotexist")
        assert r.status_code == 404

    def test_found(self, client):
        init = client.post(
            "/api/upload/init", json={"filename": "test.txt", "size": 500}
        ).get_json()
        uid = init["upload_id"]
        r = client.get(f"/api/upload/status/{uid}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["upload_id"] == uid
        assert body["original_name"] == "test.txt"
        assert body["size"] == 500


# ── route: POST /api/upload/chunk/<id>/<index> ────────────────────────────────

class TestResumableUploadChunk:
    def _init(self, client, size=100, filename="test.txt"):
        return client.post(
            "/api/upload/init", json={"filename": filename, "size": size}
        ).get_json()

    def test_not_found(self, client):
        r = client.post(
            "/api/upload/chunk/badid/0",
            data=b"data",
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": "a" * 64},
        )
        assert r.status_code == 404

    def test_invalid_index_negative(self, client):
        init = self._init(client)
        uid = init["upload_id"]
        r = client.post(
            f"/api/upload/chunk/{uid}/-1",
            data=b"data",
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": "a" * 64},
        )
        assert r.status_code == 404  # Flask rejects negative int in URL

    def test_invalid_index_out_of_range(self, client):
        init = self._init(client)
        uid = init["upload_id"]
        total = init["total_chunks"]
        r = client.post(
            f"/api/upload/chunk/{uid}/{total}",
            data=b"data",
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": "a" * 64},
        )
        assert r.status_code == 400

    def test_missing_hash_header(self, client):
        init = self._init(client)
        uid = init["upload_id"]
        r = client.post(
            f"/api/upload/chunk/{uid}/0",
            data=b"x" * 100,
            content_type="application/octet-stream",
        )
        assert r.status_code == 400

    def test_hash_mismatch(self, client):
        content = b"x" * 100
        init = self._init(client, size=100)
        uid = init["upload_id"]
        r = client.post(
            f"/api/upload/chunk/{uid}/0",
            data=content,
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": "a" * 64},
        )
        assert r.status_code == 400

    def test_valid_chunk(self, client):
        content = b"x" * 100
        digest = hashlib.sha256(content).hexdigest()
        init = self._init(client, size=100)
        uid = init["upload_id"]
        r = client.post(
            f"/api/upload/chunk/{uid}/0",
            data=content,
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": digest},
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_duplicate_chunk_skipped(self, client):
        content = b"x" * 100
        digest = hashlib.sha256(content).hexdigest()
        init = self._init(client, size=100)
        uid = init["upload_id"]
        client.post(
            f"/api/upload/chunk/{uid}/0",
            data=content,
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": digest},
        )
        r = client.post(
            f"/api/upload/chunk/{uid}/0",
            data=content,
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": digest},
        )
        assert r.status_code == 200
        assert r.get_json().get("skipped") is True

    def test_chunk_too_large(self, client):
        init = self._init(client, size=50)
        uid = init["upload_id"]
        big = b"y" * 200
        digest = hashlib.sha256(big).hexdigest()
        r = client.post(
            f"/api/upload/chunk/{uid}/0",
            data=big,
            content_type="application/octet-stream",
            headers={"X-Chunk-SHA256": digest, "Content-Length": "200"},
        )
        assert r.status_code == 413


# ── route: POST /api/upload/finalize/<id> ────────────────────────────────────

class TestResumableUploadFinalize:
    def _upload_all(self, client, content=b"hello upload finalize", filename="test.txt"):
        size = len(content)
        init = client.post(
            "/api/upload/init", json={"filename": filename, "size": size}
        ).get_json()
        uid = init["upload_id"]
        chunk_sz = init["chunk_size"]
        total = init["total_chunks"]
        for i in range(total):
            chunk = content[i * chunk_sz: (i + 1) * chunk_sz]
            digest = hashlib.sha256(chunk).hexdigest()
            client.post(
                f"/api/upload/chunk/{uid}/{i}",
                data=chunk,
                content_type="application/octet-stream",
                headers={"X-Chunk-SHA256": digest},
            )
        return uid, init["code"]

    def test_not_found(self, client):
        r = client.post("/api/upload/finalize/badid")
        assert r.status_code == 404

    def test_missing_chunks(self, client):
        init = client.post(
            "/api/upload/init", json={"filename": "test.txt", "size": 500}
        ).get_json()
        r = client.post(f"/api/upload/finalize/{init['upload_id']}")
        assert r.status_code == 409

    def test_valid_finalize(self, client):
        uid, code = self._upload_all(client)
        r = client.post(f"/api/upload/finalize/{uid}")
        assert r.status_code == 200
        assert r.get_json()["code"] == code

    def test_hash_mismatch_finalize(self, client):
        content = b"mismatch test"
        size = len(content)
        wrong_hash = "b" * 64
        init = client.post(
            "/api/upload/init",
            json={"filename": "test.txt", "size": size, "file_sha256": wrong_hash},
        ).get_json()
        uid = init["upload_id"]
        chunk_sz = init["chunk_size"]
        for i in range(init["total_chunks"]):
            chunk = content[i * chunk_sz: (i + 1) * chunk_sz]
            digest = hashlib.sha256(chunk).hexdigest()
            client.post(
                f"/api/upload/chunk/{uid}/{i}",
                data=chunk,
                content_type="application/octet-stream",
                headers={"X-Chunk-SHA256": digest},
            )
        r = client.post(f"/api/upload/finalize/{uid}")
        assert r.status_code == 500

    def test_finalize_dedup_existing_file(self, client):
        content = b"duplicate file data for dedup"
        uid1, code1 = self._upload_all(client, content=content, filename="a.txt")
        client.post(f"/api/upload/finalize/{uid1}")

        uid2, code2 = self._upload_all(client, content=content, filename="b.txt")
        r = client.post(f"/api/upload/finalize/{uid2}")
        assert r.status_code == 200


# ── route: GET /uploads/<name> ────────────────────────────────────────────────

class TestDownloadAndAdmin:
    def test_no_such_code(self, client):
        r = client.get("/uploads/XXXXXXXX")
        assert r.status_code == 404

    def test_upload_then_download(self, client):
        content = b"download me please"
        resp = client.post(
            "/",
            content_type="multipart/form-data",
            data={"file": (io.BytesIO(content), "dl.txt")},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        code = resp.get_json()["code"]
        dl = client.get(f"/uploads/{code}")
        assert dl.status_code == 200
        assert dl.data == content

    def test_resetcache_unauthorized(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "ADMIN_TOKEN", "secret")
        r = client.get("/uploads/RESETCACHE")
        assert r.status_code == 401

    def test_resetcache_authorized(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "ADMIN_TOKEN", "secret")
        r = client.get("/uploads/RESETCACHE?token=secret")
        assert r.status_code == 200
        assert b"OK" in r.data

    def test_resetcache_no_auth_needed_when_token_empty(self, client):
        r = client.get("/uploads/RESETCACHE")
        assert r.status_code == 200
        assert b"OK" in r.data

    def test_savelocal_unauthorized(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "ADMIN_TOKEN", "secret")
        r = client.get("/uploads/SAVELOCAL")
        assert r.status_code == 401

    def test_savelocal_ok(self, client):
        r = client.get("/uploads/SAVELOCAL")
        assert r.status_code == 200
        assert b"OK" in r.data

    def test_resetcache_clears_uploads(self, client):
        client.post(
            "/",
            content_type="multipart/form-data",
            data={"file": (io.BytesIO(b"will be cleared"), "clear.txt")},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        client.get("/uploads/RESETCACHE")
        upload_dir = app_module.UPLOAD_FOLDER
        remaining = [f for f in upload_dir.iterdir() if f.is_file()]
        assert remaining == []
