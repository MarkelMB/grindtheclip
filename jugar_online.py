import subprocess
import sys
import time
import os

print("=" * 60)
print("[ONLINE] GRINDTHECLIP - SERVIDOR ONLINE INSTANTANEO")
print("=" * 60)

# 1. Launch backend server
print("\n[1/2] Iniciando servidor backend GrindTheClip...")
server_proc = subprocess.Popen([sys.executable, "server.py", "--no-gui"])
time.sleep(3)

# 2. Launch public HTTPS localtunnel
print("[2/2] Generando URL publica HTTPS para jugar online con amigos...\n")
cmd = ["cmd.exe", "/c", "npx --yes localtunnel --port 5000"]
tunnel_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

public_url = None
try:
    for line in tunnel_proc.stdout:
        print(line, end="")
        if "url is:" in line:
            public_url = line.split("url is:")[1].strip()
            print("\n" + "*" * 60)
            print(f"   [LINK] TU ENLACE ONLINE PUBLICO ES: {public_url}")
            print("   Comparte esta direccion con cualquier jugador para entrar.")
            print("*" * 60 + "\n")
            break
except KeyboardInterrupt:
    pass

try:
    tunnel_proc.wait()
finally:
    server_proc.terminate()
