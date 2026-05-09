#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _request_json(url, method="GET", payload=None, headers=None):
    data = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def _post_chunk(url, chunk, chunk_hash):
    headers = {
        "Content-Type": "application/octet-stream",
        "X-Chunk-SHA256": chunk_hash,
    }
    req = urllib.request.Request(url, data=chunk, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _sha256_bytes(buf):
    return hashlib.sha256(buf).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Chunked upload demo for SkyDaddy")
    parser.add_argument("--file", required=True, help="Path to the file to upload")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Server base URL")
    args = parser.parse_args()

    file_path = args.file
    if not os.path.isfile(file_path):
        print("File not found:", file_path, file=sys.stderr)
        return 1

    size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)
    base_url = args.base_url.rstrip("/")

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
    file_sha256 = sha256.hexdigest()

    t0 = time.time()
    try:
        ping = _request_json(base_url + "/api/ping")
        _ = ping.get("ok")
    except Exception:
        pass
    rtt_ms = int((time.time() - t0) * 1000)

    init = _request_json(
        base_url + "/api/upload/init",
        method="POST",
        payload={"filename": filename, "size": size, "rtt_ms": rtt_ms, "file_sha256": file_sha256},
    )

    upload_id = init["upload_id"]
    chunk_size = int(init["chunk_size"])
    total_chunks = int(init["total_chunks"])

    print("Upload ID:", upload_id)
    print("Chunks:", total_chunks, "Chunk size:", chunk_size)

    with open(file_path, "rb") as f:
        for idx in range(total_chunks):
            start = idx * chunk_size
            f.seek(start)
            chunk = f.read(min(chunk_size, size - start))
            chunk_hash = _sha256_bytes(chunk)
            _post_chunk(
                base_url + f"/api/upload/chunk/{upload_id}/{idx}",
                chunk,
                chunk_hash,
            )
            pct = int(((idx + 1) / total_chunks) * 100)
            print(f"Uploaded chunk {idx + 1}/{total_chunks} ({pct}%)")

    finalize = _request_json(base_url + f"/api/upload/finalize/{upload_id}", method="POST")
    print("Final code:", finalize.get("code"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

