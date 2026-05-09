import hashlib
import json
import logging
import math
import os
import secrets
import shutil
import tempfile
import string
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory
from flask_session import Session
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover - Windows fallback
    fcntl = None

app = Flask(__name__)

UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", "./UPLOADS"))
PERMA_FOLDER = Path(os.environ.get("PERMA_FOLDER", "./PERMA"))
MAP_FILE = Path(os.environ.get("MAP_FILE", "./file_map.json"))
RESUMABLE_FOLDER = Path(os.environ.get("RESUMABLE_FOLDER", UPLOAD_FOLDER / ".resumable"))
ALLOWED_EXT = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'h', 'cpp',
    'zip', 'tar', 'xz', '7z', 'iso',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'json', 'xml', 'md',
    'mkv', 'mp4', 'avi', 'mov', 'mp3', 'wav', 'flac', 'ogg',
}
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 ** 3)))
MAX_CHUNK_BYTES = int(os.environ.get("MAX_CHUNK_BYTES", str(32 * 1024 ** 2)))
MID_CHUNK_BYTES = int(os.environ.get("MID_CHUNK_BYTES", str(16 * 1024 ** 2)))
MIN_CHUNK_BYTES = int(os.environ.get("MIN_CHUNK_BYTES", str(8 * 1024 ** 2)))
SHORT_CODE_LEN = 8
SHORT_CODE_ALPHABET = string.ascii_uppercase + string.digits
RESERVATION_TTL_SECONDS = int(os.environ.get("RESERVATION_TTL_SECONDS", str(24 * 60 * 60)))

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
Session(app)

BUF_SIZE = 65536
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
RESUMABLE_FOLDER.mkdir(parents=True, exist_ok=True)


def load_map() -> dict:
    if MAP_FILE.exists():
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    return {}


def save_map(mapping: dict) -> None:
    data = json.dumps(mapping)
    fd, tmp = tempfile.mkstemp(dir=MAP_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        Path(tmp).rename(MAP_FILE)
    except Exception:
        os.unlink(tmp)
        raise


def _reconcile_map() -> None:
    mapping = load_map()
    stale = []
    now = datetime.now(timezone.utc)
    for code, entry in mapping.items():
        if entry.get("reserved"):
            ts = entry.get("reserved_at")
            if ts:
                try:
                    reserved_at = datetime.fromisoformat(ts)
                except ValueError:
                    reserved_at = None
                if reserved_at and (now - reserved_at).total_seconds() > RESERVATION_TTL_SECONDS:
                    stale.append(code)
            continue
        if not (UPLOAD_FOLDER / entry["file"]).exists():
            stale.append(code)
    if stale:
        for code in stale:
            del mapping[code]
        save_map(mapping)
        logger.info("Removed %d stale map entries: %s", len(stale), stale)


_reconcile_map()


def _is_hex_sha256(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _generate_short_code(file_sha256: str, mapping: dict) -> str:
    for attempt in range(10_000):
        seed = f"{file_sha256}:{attempt}".encode("utf-8")
        digest = hashlib.sha256(seed).digest()
        num = int.from_bytes(digest, "big")
        chars = []
        for _ in range(SHORT_CODE_LEN):
            num, idx = divmod(num, len(SHORT_CODE_ALPHABET))
            chars.append(SHORT_CODE_ALPHABET[idx])
        code = "".join(chars)
        if code not in mapping and code not in {"RESETCACHE", "SAVELOCAL"}:
            return code
    raise RuntimeError("Unable to allocate unique code")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def get_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(BUF_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _choose_chunk_profile(rtt_ms: float | None) -> tuple[int, int]:
    if rtt_ms is None:
        return MAX_CHUNK_BYTES, 4
    if rtt_ms >= 2500:
        return MIN_CHUNK_BYTES, 1
    if rtt_ms >= 1200:
        return MID_CHUNK_BYTES, 1
    if rtt_ms >= 800:
        return MID_CHUNK_BYTES, 2
    return MAX_CHUNK_BYTES, 4


def _upload_dir(upload_id: str) -> Path:
    return RESUMABLE_FOLDER / upload_id


def _upload_meta_path(upload_id: str) -> Path:
    return _upload_dir(upload_id) / "upload.json"


def _load_upload_meta(upload_id: str) -> dict | None:
    meta_path = _upload_meta_path(upload_id)
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _save_upload_meta(upload_id: str, meta: dict) -> None:
    meta_path = _upload_meta_path(upload_id)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(meta)
    fd, tmp = tempfile.mkstemp(dir=meta_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        Path(tmp).rename(meta_path)
    except Exception:
        os.unlink(tmp)
        raise


def _locked_update_meta(upload_id: str, updater) -> dict:
    meta_path = _upload_meta_path(upload_id)
    if not meta_path.exists():
        raise FileNotFoundError("Upload metadata not found")
    with meta_path.open("r+", encoding="utf-8") as f:
        if fcntl is not None:
            fcntl.flock(f, fcntl.LOCK_EX)
        data = f.read()
        meta = json.loads(data) if data else {}
        updater(meta)
        f.seek(0)
        f.truncate()
        f.write(json.dumps(meta))
        f.flush()
        os.fsync(f.fileno())
        if fcntl is not None:
            fcntl.flock(f, fcntl.LOCK_UN)
    return meta


def _write_stream_with_sha256(stream, dest: Path, expected_size: int) -> tuple[str, int]:
    sha256 = hashlib.sha256()
    size = 0
    with dest.open("wb") as f:
        while True:
            chunk = stream.read(BUF_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > expected_size:
                raise ValueError("Chunk exceeds expected size")
            sha256.update(chunk)
            f.write(chunk)
    return sha256.hexdigest(), size


def _is_xhr() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _handle_upload():
    xhr = _is_xhr()

    def err(msg, status=400):
        if xhr:
            return jsonify({"error": msg}), status
        flash(msg)
        return redirect(request.url)

    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return err("File too large", 413)
    if "file" not in request.files:
        return err("No file part")
    file = request.files["file"]
    if not file.filename:
        return err("No file selected")
    if not allowed_file(file.filename):
        return err("File type not allowed", 415)

    original_name = secure_filename(file.filename)
    if not original_name:
        return err("Invalid filename")

    ext = Path(original_name).suffix.lower()

    fd, tmp = tempfile.mkstemp(dir=UPLOAD_FOLDER)
    try:
        with os.fdopen(fd, "wb") as f:
            file.save(f)
        tmp_path = Path(tmp)
        file_hash = get_sha256(tmp_path)
        final_path = UPLOAD_FOLDER / f"{file_hash}{ext}"
        tmp_path.rename(final_path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    mapping = load_map()
    short_code = _generate_short_code(file_hash, mapping)
    mapping[short_code] = {
        "file": final_path.name,
        "name": original_name,
        "sha256": file_hash,
    }
    save_map(mapping)
    logger.info("Stored: %s as %s", original_name, short_code)

    if xhr:
        return jsonify({"code": short_code})
    return render_template("postload.html", FCODE=short_code)


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        return _handle_upload()
    return render_template("uploadtemplate.html")


@app.route("/api/ping")
def api_ping():
    return jsonify({"ok": True})


@app.route("/api/upload/init", methods=["POST"])
def api_upload_init():
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    size = data.get("size")
    rtt_ms = data.get("rtt_ms")
    file_sha256_raw = (data.get("file_sha256") or "").strip().lower()
    file_sha256 = file_sha256_raw if file_sha256_raw else None

    if not isinstance(size, int) or size <= 0:
        return jsonify({"error": "Invalid file size"}), 400
    if size > MAX_UPLOAD_BYTES:
        return jsonify({"error": "File too large"}), 413
    if file_sha256 and not _is_hex_sha256(file_sha256):
        return jsonify({"error": "Invalid file hash"}), 400

    original_name = secure_filename(filename)
    if not original_name:
        return jsonify({"error": "Invalid filename"}), 400
    if not allowed_file(original_name):
        return jsonify({"error": "File type not allowed"}), 415

    chunk_size, concurrency = _choose_chunk_profile(
        float(rtt_ms) if isinstance(rtt_ms, (int, float)) else None
    )
    chunk_size = min(chunk_size, MAX_CHUNK_BYTES)
    total_chunks = int(math.ceil(size / chunk_size))
    upload_id = secrets.token_hex(16)

    meta = {
        "upload_id": upload_id,
        "original_name": original_name,
        "ext": Path(original_name).suffix.lower(),
        "size": size,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "concurrency": concurrency,
        "created_at": _utc_now_iso(),
        "chunks": {},
        "final_sha256": None,
        "file_sha256": file_sha256,
        "short_code": None,
    }
    mapping = load_map()
    reserved_code = _generate_short_code(file_sha256, mapping)
    mapping[reserved_code] = {
        "file": None,
        "name": original_name,
        "sha256": file_sha256,
        "reserved": True,
        "upload_id": upload_id,
        "reserved_at": _utc_now_iso(),
    }
    save_map(mapping)
    meta["short_code"] = reserved_code
    _save_upload_meta(upload_id, meta)
    return jsonify(
        {
            "upload_id": upload_id,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
            "concurrency": concurrency,
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "code": reserved_code,
        }
    )


@app.route("/api/upload/status/<upload_id>")
def api_upload_status(upload_id: str):
    meta = _load_upload_meta(upload_id)
    if not meta:
        return jsonify({"error": "No such upload"}), 404
    return jsonify(
        {
            "upload_id": upload_id,
            "original_name": meta.get("original_name"),
            "size": meta.get("size"),
            "chunk_size": meta.get("chunk_size"),
            "total_chunks": meta.get("total_chunks"),
            "concurrency": meta.get("concurrency"),
            "received": meta.get("chunks", {}),
        }
    )


@app.route("/api/upload/chunk/<upload_id>/<int:index>", methods=["POST"])
def api_upload_chunk(upload_id: str, index: int):
    meta = _load_upload_meta(upload_id)
    if not meta:
        return jsonify({"error": "No such upload"}), 404

    total_chunks = int(meta.get("total_chunks", 0))
    chunk_size = int(meta.get("chunk_size", MAX_CHUNK_BYTES))
    total_size = int(meta.get("size", 0))

    if index < 0 or index >= total_chunks:
        return jsonify({"error": "Invalid chunk index"}), 400

    start = index * chunk_size
    expected_size = min(chunk_size, total_size - start)
    if request.content_length and request.content_length > expected_size:
        return jsonify({"error": "Chunk too large"}), 413

    expected_hash = request.headers.get("X-Chunk-SHA256")
    if not expected_hash:
        return jsonify({"error": "Missing chunk hash"}), 400

    upload_dir = _upload_dir(upload_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = upload_dir / f"chunk_{index:08d}.part"
    if chunk_path.exists():
        def _update(meta_obj: dict) -> None:
            meta_obj.setdefault("chunks", {}).setdefault(
                str(index),
                {"sha256": None, "size": expected_size},
            )

        _locked_update_meta(upload_id, _update)
        return jsonify({"ok": True, "skipped": True})

    fd, tmp = tempfile.mkstemp(dir=upload_dir, suffix=".part")
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "wb") as _:
            pass
        digest, size = _write_stream_with_sha256(request.stream, tmp_path, expected_size)
        if size != expected_size:
            raise ValueError("Chunk size mismatch")
        if digest != expected_hash:
            raise ValueError("Chunk hash mismatch")
        tmp_path.rename(chunk_path)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        return jsonify({"error": str(e)}), 400

    def _update(meta_obj: dict) -> None:
        meta_obj.setdefault("chunks", {})[str(index)] = {"sha256": digest, "size": size}

    _locked_update_meta(upload_id, _update)
    return jsonify({"ok": True})


@app.route("/api/upload/finalize/<upload_id>", methods=["POST"])
def api_upload_finalize(upload_id: str):
    meta = _load_upload_meta(upload_id)
    if not meta:
        return jsonify({"error": "No such upload"}), 404

    total_chunks = int(meta.get("total_chunks", 0))
    chunk_size = int(meta.get("chunk_size", MAX_CHUNK_BYTES))
    total_size = int(meta.get("size", 0))
    received = meta.get("chunks", {})
    missing = [i for i in range(total_chunks) if str(i) not in received]
    if missing:
        return jsonify({"error": "Missing chunks", "missing": missing}), 409

    fd, tmp = tempfile.mkstemp(dir=UPLOAD_FOLDER)
    tmp_path = Path(tmp)
    sha256 = hashlib.sha256()
    written = 0
    try:
        with os.fdopen(fd, "wb") as out:
            for idx in range(total_chunks):
                chunk_path = _upload_dir(upload_id) / f"chunk_{idx:08d}.part"
                with chunk_path.open("rb") as f:
                    while chunk := f.read(BUF_SIZE):
                        sha256.update(chunk)
                        out.write(chunk)
                        written += len(chunk)
        if written != total_size:
            raise ValueError("Final size mismatch")
        file_hash = sha256.hexdigest()
        if meta.get("file_sha256") and file_hash != meta.get("file_sha256"):
            raise ValueError("Final hash mismatch")
        final_path = UPLOAD_FOLDER / f"{file_hash}{meta.get('ext', '')}"
        if final_path.exists():
            tmp_path.unlink(missing_ok=True)
        else:
            tmp_path.rename(final_path)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        return jsonify({"error": str(e)}), 500

    mapping = load_map()
    short_code = meta.get("short_code")
    reserved = mapping.get(short_code) if short_code else None
    if not reserved or not reserved.get("reserved") or reserved.get("upload_id") != upload_id:
        return jsonify({"error": "Upload code not reserved"}), 409
    mapping[short_code] = {
        "file": final_path.name,
        "name": meta.get("original_name"),
        "sha256": file_hash,
        "reserved": False,
        "upload_id": upload_id,
    }
    save_map(mapping)
    logger.info("Stored: %s as %s", meta.get("original_name"), short_code)

    _save_upload_meta(upload_id, {**meta, "final_sha256": file_hash})
    shutil.rmtree(_upload_dir(upload_id), ignore_errors=True)
    return jsonify({"code": short_code})


def _admin_authorized() -> bool:
    if not ADMIN_TOKEN:
        return True
    return request.args.get("token") == ADMIN_TOKEN


def _cmd_resetcache():
    try:
        for f in UPLOAD_FOLDER.iterdir():
            if f.is_file():
                f.unlink()
        shutil.rmtree(RESUMABLE_FOLDER, ignore_errors=True)
        RESUMABLE_FOLDER.mkdir(parents=True, exist_ok=True)
        save_map({})
        return "COMMAND OK"
    except Exception as e:
        logger.error("RESETCACHE failed: %s", e)
        return "COMMAND FAIL", 500


def _cmd_savelocal():
    try:
        PERMA_FOLDER.mkdir(parents=True, exist_ok=True)
        for f in UPLOAD_FOLDER.iterdir():
            if f.is_file():
                shutil.copy(f, PERMA_FOLDER / f.name)
        return "COMMAND OK"
    except Exception as e:
        logger.error("SAVELOCAL failed: %s", e)
        return "COMMAND FAIL", 500


@app.route("/uploads/<name>")
def download_file(name):
    if name == "RESETCACHE":
        if not _admin_authorized():
            return "UNAUTHORIZED", 401
        return _cmd_resetcache()

    if name == "SAVELOCAL":
        if not _admin_authorized():
            return "UNAUTHORIZED", 401
        return _cmd_savelocal()

    mapping = load_map()
    entry = mapping.get(name)
    if not entry:
        return "NO SUCH FILE", 404
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        entry["file"],
        download_name=entry["name"],
    )


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
