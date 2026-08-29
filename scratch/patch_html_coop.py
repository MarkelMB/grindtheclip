import os

html_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\templates\index.html'

with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '<div id="view-lobby"'
end_marker = '<div id="view-leaderboard"'

if start_marker in content and end_marker in content:
    pre = content.split(start_marker)[0]
    post = end_marker + content.split(end_marker)[1]
    
    new_lobby = """<div id="view-lobby" class="view">
        <h2 id="lobby-pack-name" style="margin-bottom:10px;">Lobby</h2>
        <div id="lobby-tunnel-link" style="margin-bottom:20px; font-size:0.95rem; color:#00e5ff; display:none; background:#121a24; padding:10px; border-radius:8px; border:1px solid #00e5ff;">
            Generando enlace mágico para amigos...
        </div>
        
        <div id="lobby-mode-container" style="background:#1e3040; padding:15px; border-radius:12px; margin-bottom:20px; display:none;">
            <h3 style="margin:0 0 10px 0; font-size:1rem; color:#b0bec5;">Modo de Juego</h3>
            <select id="lobby-mode-select" style="width:100%; padding:10px; background:#121a24; border:1px solid #2a3f54; color:#fff; border-radius:8px; font-size:1rem; outline:none; cursor:pointer;">
                <option value="competitivo">Competitivo (Todos doblan todos los personajes)</option>
                <option value="cooperativo">Cooperativo (Cada jugador elige qué personajes dobla)</option>
            </select>
            <p id="lobby-mode-display" style="display:none; color:#00e5ff; font-weight:bold;"></p>
        </div>
        
        <div id="lobby-characters-container" style="background:#1e3040; padding:15px; border-radius:12px; display:none; margin-bottom:20px;">
            <h3 style="font-size:1rem; color:#b0bec5; margin-top:0; margin-bottom:10px;">Selecciona tus personajes:</h3>
            <div id="lobby-characters" style="display:flex; flex-direction:column; gap:8px;">
                <!-- Character list injected here -->
            </div>
        </div>

        <div style="background:#1e3040; padding:20px; border-radius:12px; margin-bottom:30px;">
            <h3 style="margin-top:0; color:#b0bec5; font-size:1.1rem; border-bottom:1px solid #2a3f54; padding-bottom:10px;">Jugadores en la sala</h3>
            <ul id="lobby-players" style="list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:10px;">
            </ul>
        </div>
        <div class="actions">
            <button id="btn-ready" class="btn btn-primary" style="width:100%; font-size:1.2rem; margin-bottom:10px;">¡Estoy Listo!</button>
            <button id="btn-leave-room" class="btn btn-secondary" style="width:100%;">Salir de la Sala</button>
        </div>
    </div>
"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(pre + new_lobby + post)
    print("Patched view-lobby in index.html")
else:
    print("Could not find markers in index.html")
