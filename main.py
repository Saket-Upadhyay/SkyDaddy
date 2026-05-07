import subprocess
import sys


def dev():
    raise SystemExit(
        subprocess.run(
            [sys.executable, "-m", "flask", "--app", "app",
             "run", "--debug", "--port", "8000"],
            check=False,
        ).returncode
    )


def prod():
    raise SystemExit(
        subprocess.run([sys.executable, "app.py"], check=False).returncode
    )
