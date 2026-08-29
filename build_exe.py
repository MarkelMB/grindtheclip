import os
import sys
import subprocess

def build():
    print("Instalando PyInstaller en el entorno virtual si es necesario...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=GrindTheClip",
        "--noconfirm",
        "--clean",
        "--icon=logo.ico",
        "--add-data=templates;templates",
        "--add-data=static;static",
        "--hidden-import=engineio.async_drivers.threading",
        "--hidden-import=flask_socketio",
        "--hidden-import=socketio",
        "server.py"
    ]
    
    if os.path.exists("cloudflared.exe"):
        cmd.insert(cmd.index("server.py"), "--add-data=cloudflared.exe;.")
        
    print("Ejecutando PyInstaller para empaquetar la aplicación...")
    subprocess.run(cmd, check=True)
    print("\n¡Éxito! El ejecutable se ha creado en la carpeta 'dist/GrindTheClip/GrindTheClip.exe'")

if __name__ == "__main__":
    build()
