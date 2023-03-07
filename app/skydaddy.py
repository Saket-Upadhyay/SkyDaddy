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
FILEHISTPATH = "./FILEHIST/"
FILEHISTPATHFILE = "filehist.json"
MAX_CONTENT_LENGTH = 50 * 1000 * 1000  # 100 MB file limit size
ALLOWED_EXT = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'h', 'cpp', 'zip', 'tar', 'xz', '7z', 'iso'}

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
SESSION_KEY_RAND = base64.encodebytes(os.urandom(16))
app.config.update(SECRET_KEY=SESSION_KEY_RAND,
                  ENV='development')
Session(app)
BUF_SIZE = 65536


# Creating a dictionary to save hash-file relations
class my_big_dic(dict):
    def __init__(self):
        self = dict()

    def add(self, key, relation):
        self[key] = relation


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def getHash(file):
    sha1 = hashlib.sha1()
    with open(file, 'rb') as tarfile:
        while True:
            rwdata = tarfile.read(BUF_SIZE)
            if not rwdata:
                break
            sha1.update(rwdata)
    return sha1.hexdigest()


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    MAPOBJ = my_big_dic()
    if not os.path.exists(FILEHISTPATH):
        os.mkdir(UPLOAD_FOLDER)
    if not os.path.exists(UPLOAD_FOLDER):
        os.mkdir(UPLOAD_FOLDER)

    if os.path.exists(FILEHISTPATH + FILEHISTPATHFILE):
        with open(FILEHISTPATH + FILEHISTPATHFILE, "r") as fp:
            TEMPMAPOBJ = json.load(fp)
            for k in TEMPMAPOBJ.keys():
                MAPOBJ.add(k, TEMPMAPOBJ[k])

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
            FPATH = os.path.join(app.config['UPLOAD_FOLDER'] + filename)
            file.save(FPATH)
            flash("File Uploaded Succesfully")
            print(filename)
            CODE = getHash(FPATH)
            MAPOBJ.key = CODE
            MAPOBJ.relation = filename
            MAPOBJ.add(MAPOBJ.key, MAPOBJ.relation)
            with open(FILEHISTPATH + FILEHISTPATHFILE, "w") as fp:
                json.dump(MAPOBJ, fp)

            return render_template("postload.html", FCODE=CODE)

    return render_template("uploadtemplate.html", ALLOWEDEXTS=str(ALLOWED_EXT)[1:-1],
                           CONTENTLENGTH="< " + str(MAX_CONTENT_LENGTH / (1000 * 1000)), HOSTER=socket.gethostname(),
                           CLIENT=request.remote_addr)


@app.route('/uploads/<name>')
def download_file(name):
    MAPOBJ = my_big_dic()
    if os.path.exists(FILEHISTPATH + FILEHISTPATHFILE):
        with open(FILEHISTPATH + FILEHISTPATHFILE, "r") as fp:
            TEMPMAPOBJ = json.load(fp)
            for k in TEMPMAPOBJ.keys():
                MAPOBJ.add(k, TEMPMAPOBJ[k])

    if name == "RESETCACHE":
        try:
            for file in os.listdir(app.config["UPLOAD_FOLDER"]):
                if os.path.isfile(app.config["UPLOAD_FOLDER"] + "/" + file):
                    os.remove(app.config["UPLOAD_FOLDER"] + file)

            with open(FILEHISTPATH + FILEHISTPATHFILE, "w") as fp:
                my_temp_dic = {}
                json.dump(my_temp_dic, fp)
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
            return send_from_directory(app.config["UPLOAD_FOLDER"], MAPOBJ[name])
        except Exception as e:
            return "FILE NOT FOUND"


if __name__ == '__main__':
    app.run("0.0.0.0", 8000, debug=False)
