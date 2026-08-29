# -*- coding: utf-8 -*-
with open('templates/index.html', 'r', encoding='utf-8') as f:
    original = f.read()

import re
idx = original.find('    <!-- View: Multiplayer Leaderboard -->')
if idx != -1:
    rest_of_file = original[idx:]
else:
    rest_of_file = ""

new_top = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GrindTheClip</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <!-- Socket.IO -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
</head>
<body>
    <div class="background-waves"></div>

    <!-- View: Main Menu -->
    <div id="view-start" class="view active">
        <h2 style="margin-top:20px; font-weight:300; letter-spacing:2px; color:var(--magenta);">GRIND THE CLIP</h2>
        <div class="menu-options" style="margin-top: 40px; display: flex; flex-direction: column; gap: 20px;">
            <button class="btn btn-cyan" id="btn-play-single">JUGAR EN SOLITARIO</button>
            <button class="btn btn-magenta" id="btn-play-online">JUGAR ONLINE 🌐</button>
            <button class="btn" style="background:transparent; border:1px solid rgba(255,255,255,0.2);" id="btn-create-scene">TALLER DE ESCENAS</button>
        </div>
    </div>

    <!-- VIEW ONLINE MENU -->
    <div id="view-online-menu" class="view">
        <button onclick="showView('view-start')" class="btn-back-small">◀ Volver</button>
        <h2 class="neon-text">MULTIJUGADOR</h2>
        
        <div id="network-info-box" style="margin-top: 20px; background: rgba(0, 188, 212, 0.1); border: 1px solid var(--cyan); padding: 15px; border-radius: 10px; max-width: 400px; text-align: center; display: inline-block;">
            <p style="color: #aaa; margin: 0; font-size: 0.9rem;">Para que jueguen otros en la misma red Wi-Fi:</p>
            <p id="network-ip-display" style="color: var(--cyan); font-size: 1.2rem; font-weight: bold; margin: 10px 0 0 0; letter-spacing: 1px;">Cargando IP...</p>
        </div>

        <div style="display: flex; flex-direction: column; gap: 20px; margin-top: 30px; align-items: center;">
            <button class="btn btn-magenta" id="btn-create-room">CREAR SALA</button>
            <h3 style="color: gray;">- o -</h3>
            <button class="btn btn-cyan" id="btn-join-room-menu">UNIRSE A SALA</button>
        </div>
    </div>

    <!-- View: Pack Selection -->
    <div id="view-packs" class="view">
        <button id="btn-back-from-packs" class="btn-back-small">◀ Volver</button>
        <h1 class="glow-text text-center title-medium">GrindTheClip</h1>
        <h1>Catálogo de Escenas</h1>
        <div class="packs-grid" id="packs-grid">
            <!-- Packs load here dynamically -->
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <button class="btn-pill btn-cyan" onclick="showView('view-creator-input')" style="font-size: 1.2rem; padding: 15px 30px;">
                🤖 Taller de Escenas (Nuevo Pack)
            </button>
        </div>
    </div>

    <!-- View: Multiplayer Join -->
    <div id="view-join" class="view" style="text-align: center; max-width: 500px; margin: 0 auto; padding-top: 100px;">
        <button onclick="showView('view-online-menu')" class="btn-back-small">◀ Volver</button>
        <h1 class="glow-text">Unirse a Sala</h1>
        <div class="creator-card" style="background: rgba(10,12,16,0.85); border: 2px solid var(--cyan); padding: 40px; border-radius: 20px;">
            <input type="text" id="join-name" placeholder="Tu Nickname" style="width: 100%; padding: 15px; margin-bottom: 20px; background: #1a202c; color: white; border: 1px solid var(--cyan); border-radius: 8px; font-size: 1.2rem; text-align: center;">
            <input type="text" id="join-code" placeholder="Código de 4 Letras (ej: ABCD)" maxlength="4" style="text-transform: uppercase; width: 100%; padding: 15px; margin-bottom: 30px; background: #1a202c; color: white; border: 1px solid var(--cyan); border-radius: 8px; font-size: 1.2rem; text-align: center; letter-spacing: 5px;">
            <button class="btn-pill btn-cyan" onclick="joinMultiplayerRoom()" style="font-size: 1.3rem; padding: 15px 40px; width: 100%;">Entrar ►</button>
        </div>
    </div>

    <!-- View: Multiplayer Lobby -->
    <div id="view-lobby" class="view" style="text-align: center; max-width: 600px; margin: 0 auto; padding-top: 50px;">
        <button onclick="leaveLobby()" class="btn-back-small">◀ Salir</button>
        <h1 class="glow-text" style="font-size: 3rem; margin-bottom: 5px;">SALA: <span id="lobby-code-display" style="color: #fff;">----</span></h1>
        <h3 id="lobby-pack-display" style="color: var(--cyan); margin-bottom: 30px;">Escena: ...</h3>
        
        <div class="creator-card" style="background: rgba(10,12,16,0.85); border: 2px solid #333; padding: 20px; border-radius: 20px; min-height: 250px; text-align: left;">
            <ul id="lobby-players-list" style="list-style: none; padding: 0; margin: 0; color: white; font-size: 1.2rem;">
                <!-- Players injected here -->
            </ul>
        </div>
        
        <div style="margin-top: 40px;">
            <button id="btn-lobby-ready" onclick="setReady()" class="btn-ready-red">NO ESTOY LISTO</button>
        </div>
    </div>
'''

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(new_top + '\n' + rest_of_file)
    
print("Successfully wrote new_top + rest_of_file")
