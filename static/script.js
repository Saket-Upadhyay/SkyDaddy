$('#file-upload').change(function () {
    var m = this.value.match(/([^\/\\]+)$/);
    $('#filename').text(m ? m[1] : 'no file selected');
});

$('#upload-form').on('submit', function (e) {
    e.preventDefault();

    var fileInput = document.getElementById('file-upload');
    if (!fileInput.files.length) return;

    var xhr = new XMLHttpRequest();
    var formData = new FormData(this);

    document.getElementById('progress-container').style.display = 'block';
    document.getElementById('upload-result').style.display = 'none';
    setProgress(0);

    xhr.upload.addEventListener('progress', function (e) {
        if (e.lengthComputable) {
            setProgress(Math.round((e.loaded / e.total) * 100));
        }
    });

    xhr.addEventListener('load', function () {
        document.getElementById('progress-container').style.display = 'none';
        var result = document.getElementById('upload-result');
        if (xhr.status === 200) {
            var data = JSON.parse(xhr.responseText);
            result.innerHTML =
                'TRANSFER COMPLETE &mdash; FILE CODE:<br>' +
                '<code title="Click to copy" onclick="copyInline(this)">' + data.code + '</code>' +
                '<div class="copy-hint">&gt; CLICK CODE TO COPY</div>';
            result.className = 'result-ok';
        } else {
            var msg = 'TRANSFER FAILED';
            try { msg = (JSON.parse(xhr.responseText).error || msg).toUpperCase(); } catch (_) {}
            result.innerHTML = '[ERR] ' + msg;
            result.className = 'result-err';
        }
        result.style.display = 'block';
    });

    xhr.addEventListener('error', function () {
        document.getElementById('progress-container').style.display = 'none';
        var result = document.getElementById('upload-result');
        result.innerHTML = '[ERR] NETWORK ERROR — TRANSFER FAILED';
        result.className = 'result-err';
        result.style.display = 'block';
    });

    xhr.open('POST', '/');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.send(formData);
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
