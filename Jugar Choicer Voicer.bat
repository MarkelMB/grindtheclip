@echo off
title GrindTheClip - Local Server
echo Arrancando el motor local (Backend Flask + WebSocket)...
start http://127.0.0.1:5000
.\.venv\Scripts\python.exe server.py
pause
