import os
import sys
import subprocess

port = os.environ.get("PORT", "5000")
cmd = [
    sys.executable, "-m", "gunicorn",
    "--worker-class", "gthread",
    "-w", "1",
    "--threads", "8",
    "--timeout", "120",
    "--bind", f"0.0.0.0:{port}",
    "server:app"
]
print(f"[Launcher] Executing: {' '.join(cmd)}", flush=True)
subprocess.run(cmd)
