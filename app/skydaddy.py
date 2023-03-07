"""
Main application module

MIT License

Copyright (c) 2023 Saket Upadhyay

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import base64
import hashlib
import json
import os
import shutil
import socket

from flask import Flask, flash, request, redirect, send_from_directory, render_template, session
from werkzeug.utils import secure_filename

from flask_session import Session

app = Flask(__name__)

UPLOAD_FOLDER = "./UPLOADS/"
FILE_HISTORY_FOLDER_PATH = "./FILEHIST/"
FILE_HISTORY_SHARED_RECORD = "filehist.json"
MAX_CONTENT_LENGTH = 50 * 1000 * 1000  # 100 MB file limit size
ALLOWED_EXT = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif',
               'h', 'cpp', 'zip', 'tar', 'xz', '7z', 'iso'}

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
SESSION_KEY_RAND = base64.encodebytes(os.urandom(16))
app.config.update(SECRET_KEY=SESSION_KEY_RAND,
                  ENV='development')
Session(app)
BUF_SIZE = 65536


# noinspection PyMethodFirstArgAssignment
class MyBigDic(dict):
    def __init__(self):
        self = dict()
        self.clear()

    def add(self, key, relation):
        self[key] = relation


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def gethash(file, mode):
    if mode == "sha1file":
        sha1 = hashlib.sha1()
        with open(file, 'rb') as tarfile:
            while True:
                rwdata = tarfile.read(BUF_SIZE)
                if not rwdata:
                    break
                sha1.update(rwdata)
        return sha1.hexdigest()
    if mode == "sha1text":
        sha1 = hashlib.sha1()
        rwdata = file.encode("utf-8")
        sha1.update(rwdata)
        return sha1.hexdigest()
    return None


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    mapobj = MyBigDic()
    if not os.path.exists(UPLOAD_FOLDER):
        os.mkdir(UPLOAD_FOLDER)
    if not os.path.exists(UPLOAD_FOLDER):
        os.mkdir(UPLOAD_FOLDER)

    if os.path.exists(FILE_HISTORY_FOLDER_PATH + FILE_HISTORY_SHARED_RECORD):
        with open(FILE_HISTORY_FOLDER_PATH + FILE_HISTORY_SHARED_RECORD,
                  "r",
                  encoding="utf-8") as filepointer:
            tempmapobj = json.load(filepointer)
            for k in tempmapobj.keys():
                mapobj.add(k, tempmapobj[k])

    session["user_name"] = "firstlastname"
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']

        if file.filename == '':
            flash("No file selected")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            fpath = os.path.join(app.config['UPLOAD_FOLDER'] + filename)
            file.save(fpath)
            flash("File Uploaded Succesfully")
            print(filename)
            filehash = gethash(fpath, "sha1")
            mapobj.key = filehash
            mapobj.relation = filename
            mapobj.add(mapobj.key, mapobj.relation)
            with open(FILE_HISTORY_FOLDER_PATH + FILE_HISTORY_SHARED_RECORD,
                      "w",
                      encoding="utf-8") as filepointer:
                json.dump(mapobj, filepointer)

            return render_template("postload.html", FCODE=filehash)

    return render_template("uploadtemplate.html",
                           ALLOWEDEXTS=str(ALLOWED_EXT)[1:-1],
                           CONTENTLENGTH="< " + str(MAX_CONTENT_LENGTH / (1000 * 1000)),
                           HOSTER=socket.gethostname(),
                           CLIENT=request.remote_addr)


@app.route('/uploads/<name>')
def download_file(name):
    mapobj = MyBigDic()
    if os.path.exists(FILE_HISTORY_FOLDER_PATH + FILE_HISTORY_SHARED_RECORD):
        with open(FILE_HISTORY_FOLDER_PATH + FILE_HISTORY_SHARED_RECORD,
                  "r",
                  encoding="utf-8") as filepointer:
            tempmapobj = json.load(filepointer)
            for k in tempmapobj.keys():
                mapobj.add(k, tempmapobj[k])

    if name == "RESETCACHE":
        try:
            for file in os.listdir(app.config["UPLOAD_FOLDER"]):
                if os.path.isfile(app.config["UPLOAD_FOLDER"] + "/" + file):
                    os.remove(app.config["UPLOAD_FOLDER"] + file)

            with open(FILE_HISTORY_FOLDER_PATH + FILE_HISTORY_SHARED_RECORD,
                      "w",
                      encoding="utf-8") as filepointer:
                my_temp_dic = {}
                json.dump(my_temp_dic, filepointer)
            return "COMMAND OK"

        except Exception:
            return "COMMAND FAIL"

    elif name == "SAVELOCAL":
        try:
            for file in os.listdir(app.config["UPLOAD_FOLDER"]):
                print(app.config["UPLOAD_FOLDER"] + "/" + file)
                shutil.copy(app.config["UPLOAD_FOLDER"] + file, "./PERMA/" + file)
            return "COMMAND OK"

        except Exception:
            return "COMMAND FAIL"

    else:
        try:
            return send_from_directory(app.config["UPLOAD_FOLDER"], mapobj[name])

        except Exception:
            return "COMMAND FAIL"


def test_results():
    # Testing Hash Function
    assert gethash("app/tests/hashtestfile5M", "sha1file")\
           == "5bd40acb51a030a338ec4fbcd0e814c8aa774573"
    assert gethash("app/tests/hashtestfile19M", "sha1file")\
           == "e629195b8667a1448077028ee679fb4561cc4f46"
    assert gethash("399d57923f81123f57c779d4bcad0539da76eb1e", "sha1text")\
           == "94f8bce571411d1a013e0446e47e5224fc3682b0"

    # Testing ALLOWED_EXT check
    for ext in ALLOWED_EXT:
        assert allowed_file(str(os.urandom(16))) is False
        assert allowed_file(str(os.urandom(16)) + "." + ext) is True


if __name__ == '__main__':
    app.run("0.0.0.0", 8000, debug=False)
