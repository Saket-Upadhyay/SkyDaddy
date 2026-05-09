$('#file-upload').change(function () {
    var m = this.value.match(/([^\/\\]+)$/);
    $('#filename').text(m ? m[1] : 'no file selected');
});

$('#upload-form').on('submit', function (e) {
    e.preventDefault();

    var fileInput = document.getElementById('file-upload');
    if (!fileInput.files.length) return;

    document.getElementById('progress-container').style.display = 'block';
    document.getElementById('upload-result').style.display = 'none';
    setProgress(0);
    startResumableUpload(fileInput.files[0]);
});

var BAR_WIDTH = 28;

function setProgress(pct) {
    var filled = Math.round(pct / 100 * BAR_WIDTH);
    var bar = '[' +
        '█'.repeat(filled) +
        '░'.repeat(BAR_WIDTH - filled) +
        '] ' + String(pct).padStart(3) + '%';
    document.getElementById('progress-ascii').textContent = 'XFER: ' + bar;
}

function copyInline(el) {
    var text = el.textContent.trim();
    navigator.clipboard.writeText(text).then(function () {
        var orig = el.textContent;
        el.textContent = '[ COPIED ]';
        setTimeout(function () { el.textContent = orig; }, 1500);
    });
}

function callDownCode() {
    var code = document.getElementById('downloadcode').value.trim();
    if (code) window.open('/uploads/' + code, '_blank');
}

async function startResumableUpload(file) {
    var result = document.getElementById('upload-result');
    if (!window.crypto || !window.crypto.subtle) {
        result.innerHTML = '[ERR] SECURE CONTEXT REQUIRED FOR SHA256';
        result.className = 'result-err';
        result.style.display = 'block';
        document.getElementById('progress-container').style.display = 'none';
        return;
    }
    var key = 'skydaddy_upload_' + file.name + '_' + file.size;
    var uploadId = localStorage.getItem(key);
    var status = null;

    if (uploadId) {
        var statusResp = await fetch('/api/upload/status/' + uploadId);
        if (statusResp.ok) {
            status = await statusResp.json();
            if (status.size !== file.size) {
                status = null;
                uploadId = null;
            }
        } else {
            uploadId = null;
        }
    }

    if (!uploadId) {
        var rtt = await measureRtt();
        var initResp = await fetch('/api/upload/init', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: file.name, size: file.size, rtt_ms: Math.round(rtt) })
        });
        if (!initResp.ok) {
            return showError(initResp, result);
        }
        status = await initResp.json();
        uploadId = status.upload_id;
        localStorage.setItem(key, uploadId);
    }

    var chunkSize = status.chunk_size;
    var totalChunks = status.total_chunks;
    var received = status.received || {};
    var uploadedBytes = 0;
    var completed = new Set();

    Object.keys(received).forEach(function (idx) {
        completed.add(Number(idx));
        uploadedBytes += received[idx].size || chunkSize;
    });

    var maxInFlight = status.concurrency || 4;
    var inFlight = 0;
    var nextIndex = 0;
    var rttAvg = null;
    var failed = false;

    function updateProgress() {
        setProgress(Math.min(100, Math.round((uploadedBytes / file.size) * 100)));
    }

    function updateConcurrency(rtt) {
        if (!rtt) return;
        rttAvg = rttAvg ? (rttAvg * 0.8 + rtt * 0.2) : rtt;
        var target = rttAvg > 1500 ? 1 : (rttAvg > 900 ? 2 : 4);
        maxInFlight = target;
    }

    function nextChunkIndex() {
        while (nextIndex < totalChunks && completed.has(nextIndex)) {
            nextIndex += 1;
        }
        return nextIndex;
    }

    async function uploadChunk(index, attempt) {
        inFlight += 1;
        var start = index * chunkSize;
        var end = Math.min(start + chunkSize, file.size);
        var blob = file.slice(start, end);
        var t0 = performance.now();
        try {
            var hash = await sha256Blob(blob);
            var resp = await fetch('/api/upload/chunk/' + uploadId + '/' + index, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/octet-stream',
                    'X-Chunk-SHA256': hash
                },
                body: blob
            });
            if (!resp.ok) {
                throw new Error('Chunk upload failed');
            }
            uploadedBytes += blob.size;
            completed.add(index);
            updateProgress();
            updateConcurrency(performance.now() - t0);
        } catch (err) {
            if (attempt < 3) {
                setTimeout(function () { uploadChunk(index, attempt + 1); }, 500 * attempt);
                inFlight -= 1;
                return;
            }
            failed = true;
            result.innerHTML = '[ERR] CHUNK UPLOAD FAILED';
            result.className = 'result-err';
            result.style.display = 'block';
        }
        inFlight -= 1;
        queue();
    }

    async function finalizeUpload() {
        var resp = await fetch('/api/upload/finalize/' + uploadId, { method: 'POST' });
        document.getElementById('progress-container').style.display = 'none';
        if (!resp.ok) {
            return showError(resp, result);
        }
        var data = await resp.json();
        localStorage.removeItem(key);
        result.innerHTML =
            'TRANSFER COMPLETE &mdash; FILE CODE:<br>' +
            '<code title="Click to copy" onclick="copyInline(this)">' + data.code + '</code>' +
            '<div class="copy-hint">&gt; CLICK CODE TO COPY</div>';
        result.className = 'result-ok';
        result.style.display = 'block';
    }

    function queue() {
        if (failed) return;
        if (completed.size >= totalChunks && inFlight === 0) {
            finalizeUpload();
            return;
        }
        while (inFlight < maxInFlight) {
            var idx = nextChunkIndex();
            if (idx >= totalChunks) return;
            uploadChunk(idx, 1);
            nextIndex += 1;
        }
    }

    updateProgress();
    queue();
}

async function measureRtt() {
    var t0 = performance.now();
    try {
        await fetch('/api/ping', { cache: 'no-store' });
    } catch (_) {
        return 0;
    }
    return performance.now() - t0;
}

async function sha256Blob(blob) {
    var buf = await blob.arrayBuffer();
    var hash = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(hash))
        .map(function (b) { return b.toString(16).padStart(2, '0'); })
        .join('');
}

async function showError(resp, resultEl) {
    var msg = 'TRANSFER FAILED';
    try {
        var data = await resp.json();
        msg = (data.error || msg).toUpperCase();
    } catch (_) {}
    document.getElementById('progress-container').style.display = 'none';
    resultEl.innerHTML = '[ERR] ' + msg;
    resultEl.className = 'result-err';
    resultEl.style.display = 'block';
}
