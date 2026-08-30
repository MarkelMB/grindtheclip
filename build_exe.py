import os
import sys
import subprocess

def build():
    print("Instalando PyInstaller en el entorno virtual si es necesario...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name=GrindTheClip",
        "--noconfirm",
        "--clean",
        "--icon=logo.ico",
        "--add-data=templates;templates",
        "--add-data=static;static",
        "--exclude-module=matplotlib",
        "--exclude-module=torch",
        "--exclude-module=transformers",
        "--exclude-module=tensorflow",
        "--hidden-import=engineio.async_drivers.threading",
        "--hidden-import=flask_socketio",
        "--hidden-import=socketio",
        "--hidden-import=engineio",
        "--hidden-import=bidict",
        "--hidden-import=simple_websocket",
        "--hidden-import=wsproto",
        "--hidden-import=gevent",
        "--hidden-import=geventwebsocket",
        "server.py"
    ]
    
    if os.path.exists("cloudflared.exe"):
        cmd.insert(cmd.index("server.py"), "--add-data=cloudflared.exe;.")
        
    print("Ejecutando PyInstaller para empaquetar la aplicación en un ejecutable único...")
    subprocess.run(cmd, check=True)
    print("\n¡Éxito! El ejecutable se ha creado en 'dist/GrindTheClip.exe'")

if __name__ == "__main__":
    build()
