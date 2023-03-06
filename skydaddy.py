import pathlib
import shutil

from flask import Flask, flash, request, redirect, url_for, send_from_directory, render_template, session
import os
from flask_session import Session
import base64
from werkzeug.utils import secure_filename
import hashlib

app = Flask(__name__)

UPLOAD_FOLDER = "./UPLOADS/"
MAX_CONTENT_LENGTH=100 * 1000 * 1000  # 100 MB file limit size
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


class my_big_dic(dict):
    def __init__(self):
        self = dict()

    def add(self, key, relation):
        self[key] = relation


MAPOBJ = my_big_dic()




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
    if not os.path.exists(UPLOAD_FOLDER):
        os.mkdir(UPLOAD_FOLDER)

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
            return render_template("postload.html", FCODE=CODE)

            # return redirect(url_for('download_file',name=filename))

    return render_template("uploadtemplate.html",ALLOWEDEXTS=str(ALLOWED_EXT)[1:-1], CONTENTLENGTH="< "+str(MAX_CONTENT_LENGTH/(1000*1000)))


@app.route('/uploads/<name>')
def download_file(name):
    if name == "RESETCACHE":
        try:
            for file in os.listdir(app.config["UPLOAD_FOLDER"]):
                if os.path.isfile(app.config["UPLOAD_FOLDER"]+"/"+file):
                    os.remove(app.config["UPLOAD_FOLDER"]+file)
            return "COMMAND OK"
        except Exception:
            return "COMMAND FAIL"
    elif name == "SAVELOCAL":
        try:
            for file in os.listdir(app.config["UPLOAD_FOLDER"]):
                print(app.config["UPLOAD_FOLDER"]+"/"+file)
                shutil.copy(app.config["UPLOAD_FOLDER"]+file,"./PERMA/"+file)
            return "COMMAND OK"
        except Exception:
            return "COMMAND FAIL"
    else:
        try:
            return send_from_directory(app.config["UPLOAD_FOLDER"], MAPOBJ[name])
        except Exception:
            return "NO SUCH FILE"


if __name__ == '__main__':
    app.run("0.0.0.0", 8000, debug=True)
