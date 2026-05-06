$('#file-upload').change(function () {
    var m = this.value.match(/([^\/\\]+)$/);
    $('#filename').text(m ? m[1] : 'Select your file');
});

$('form').on('submit', function (e) {
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
            result.innerHTML = 'File code: <code>' + data.code + '</code>';
            result.className = 'result-ok';
        } else {
            var msg = 'Upload failed';
            try { msg = JSON.parse(xhr.responseText).error || msg; } catch (_) {}
            result.innerHTML = msg;
            result.className = 'result-err';
        }
        result.style.display = 'block';
    });

    xhr.addEventListener('error', function () {
        document.getElementById('progress-container').style.display = 'none';
        var result = document.getElementById('upload-result');
        result.innerHTML = 'Network error — upload failed';
        result.className = 'result-err';
        result.style.display = 'block';
    });

    xhr.open('POST', '/');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.send(formData);
});

function setProgress(pct) {
    document.getElementById('progress-bar').style.width = pct + '%';
    document.getElementById('progress-text').textContent = pct + '%';
}

function callDownCode() {
    var code = document.getElementById('downloadcode').value.trim();
    if (code) window.open('/uploads/' + code, '_blank');
}
