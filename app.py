import hashlib
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory
from flask_session import Session
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", "./UPLOADS"))
PERMA_FOLDER = Path(os.environ.get("PERMA_FOLDER", "./PERMA"))
MAP_FILE = Path(os.environ.get("MAP_FILE", "./file_map.json"))
ALLOWED_EXT = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'h', 'cpp',
    'zip', 'tar', 'xz', '7z', 'iso',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'json', 'xml', 'md',
    'mkv', 'mp4', 'avi', 'mov', 'mp3', 'wav', 'flac', 'ogg',
}
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())
Session(app)

BUF_SIZE = 65536
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


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
    stale = [code for code, entry in mapping.items()
             if not (UPLOAD_FOLDER / entry["file"]).exists()]
    if stale:
        for code in stale:
            del mapping[code]
        save_map(mapping)
        logger.info("Removed %d stale map entries: %s", len(stale), stale)


_reconcile_map()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def get_sha1(path: Path) -> str:
    sha1 = hashlib.sha1()
    with path.open("rb") as f:
        while chunk := f.read(BUF_SIZE):
            sha1.update(chunk)
    return sha1.hexdigest()


def _is_xhr() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _handle_upload():
    xhr = _is_xhr()

    def err(msg, status=400):
        if xhr:
            return jsonify({"error": msg}), status
        flash(msg)
        return redirect(request.url)

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
        code = get_sha1(tmp_path)
        final_path = UPLOAD_FOLDER / f"{code}{ext}"
        tmp_path.rename(final_path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    mapping = load_map()
    if code not in mapping:
        mapping[code] = {"file": final_path.name, "name": original_name}
        save_map(mapping)
        logger.info("Stored: %s as %s", original_name, code)
    else:
        final_path.unlink(missing_ok=True)
        logger.info("Deduplicated: %s -> %s", original_name, code)

    if xhr:
        return jsonify({"code": code})
    return render_template("postload.html", FCODE=code)


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        return _handle_upload()
    return render_template("uploadtemplate.html")


def _admin_authorized() -> bool:
    if not ADMIN_TOKEN:
        return True
    return request.args.get("token") == ADMIN_TOKEN


def _cmd_resetcache():
    try:
        for f in UPLOAD_FOLDER.iterdir():
            if f.is_file():
                f.unlink()
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
