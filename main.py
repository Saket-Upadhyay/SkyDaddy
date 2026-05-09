import subprocess
import sys
import os

CERT_FILE = "server.crt"
KEY_FILE = "server.key"


def dev():
    """
    Run Flask app in development mode over HTTPS using uvicorn.
    If server.crt or server.key do not exist, generate them automatically.
    """
    # Check if cert and key exist
    if not (os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)):
        print("Certificate or key not found. Generating self-signed certificate...")
        subprocess.run([
            "openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
            "-subj", "/CN=drdope.local",
            "-keyout", KEY_FILE,
            "-out", CERT_FILE
        ], check=True)

    # Run Flask app over HTTPS
    returncode = subprocess.run(
        [
            "uv", "run", "-m", "flask", "--app", "app.py",
            "run",
            "--host", "0.0.0.0",
            "--port", "8080",
            "--cert", CERT_FILE,
            "--key", KEY_FILE
        ]
    ).returncode

    sys.exit(returncode)
