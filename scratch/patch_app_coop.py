import os
import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add multiplayer state variables
state_vars = """
let isHost = false;
let multiplayerGameMode = 'competitivo';
let roomCharacters = {}; // char_name -> sid
let claimedCharacters = []; // List of char names claimed by me
let allPackCharacters = [];
let coopVideoUrl = null;
let playersReadyForCoop = 0;
let expectedPlayersForCoop = 0;
let hostCoopClips = {}; // sid -> { index: blobUrl }
"""
content = re.sub(r'let currentCreatorJobId = null;', 'let currentCreatorJobId = null;\n' + state_vars, content)

# 2. Modify `createRoom` to start the tunnel and fetch characters
create_room_regex = r'async function createRoom\(packName\) \{.*?\n\}'
new_create_room = """
async function createRoom(packName) {
    const res = await fetch('/api/create_room', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack_name: packName, mode: 'competitivo' })
    });
    const data = await res.json();
    if (data.error) {
        alert(data.error);
        return;
    }
    
    currentRoom = data.room_code;
    currentPack = data.pack_name;
    isHost = true;
    
    // Fetch unique characters for this pack
    await fetchPackClips(); 
    
    document.getElementById('lobby-pack-name').innerText = `Sala: ${currentRoom} (${currentPack})`;
    showView('view-lobby');
    
    const tunnelEl = document.getElementById('lobby-tunnel-link');
    tunnelEl.style.display = 'block';
    tunnelEl.innerHTML = 'Generando enlace mÃ¡gico...';
    
    // Start Serveo tunnel
    fetch('/api/start_tunnel', {method: 'POST'})
        .then(r => r.json())
        .then(d => {
            if (d.url) {
                tunnelEl.innerHTML = `Pasa este enlace a tus amigos: <br><a href="${d.url}" target="_blank" style="color:#00e5ff;font-weight:bold;">${d.url}</a>`;
            } else {
                tunnelEl.innerHTML = 'Juego en red local.';
            }
        });
        
    // Enable mode selector
    const modeContainer = document.getElementById('lobby-mode-container');
    modeContainer.style.display = 'block';
    const modeSelect = document.getElementById('lobby-mode-select');
    modeSelect.style.display = 'block';
    document.getElementById('lobby-mode-display').style.display = 'none';
    
    modeSelect.onchange = (e) => {
        socket.emit('change_mode', { room: currentRoom, mode: e.target.value });
    };
    
    socket.emit('join', { room: currentRoom, name: 'AnfitriÃ³n' });
}

async function fetchPackClips() {
    const r = await fetch(`/api/packs/${currentPack}/clips`);
    const d = await r.json();
    clipsList = d.clips || [];
    const chars = new Set();
    clipsList.forEach(c => {
        if(c.character) chars.add(c.character);
    });
    allPackCharacters = Array.from(chars);
}
"""
content = re.sub(create_room_regex, new_create_room.strip(), content, flags=re.DOTALL)

# 3. Modify `joinRoom` to fetch characters
join_room_regex = r'async function joinRoom\(code\) \{.*?\n\}'
new_join_room = """
async function joinRoom(code) {
    if (!code) return;
    const res = await fetch(`/api/check_room/${code}`);
    const data = await res.json();
    
    if (data.valid) {
        currentRoom = code;
        currentPack = data.pack_name;
        isHost = false;
        
        await fetchPackClips();
        
        document.getElementById('lobby-pack-name').innerText = `Sala: ${currentRoom} (${currentPack})`;
        showView('view-lobby');
        
        document.getElementById('lobby-tunnel-link').style.display = 'none';
        
        const modeContainer = document.getElementById('lobby-mode-container');
        modeContainer.style.display = 'block';
        document.getElementById('lobby-mode-select').style.display = 'none';
        document.getElementById('lobby-mode-display').style.display = 'block';
        
        socket.emit('join', { room: currentRoom, name: document.getElementById('player-name').value || 'Jugador' });
    } else {
        alert(data.reason || 'CÃ³digo invÃ¡lido');
    }
}
"""
content = re.sub(join_room_regex, new_join_room.strip(), content, flags=re.DOTALL)

# 4. Modify `room_update` to handle Game Mode and Characters UI
room_update_regex = r'socket\.on\(\'room_update\', \(data\) => \{.*?\}\);'
new_room_update = """
socket.on('room_update', (data) => {
    const list = document.getElementById('lobby-players');
    list.innerHTML = '';
    data.players.forEach(p => {
        const li = document.createElement('li');
        let text = p.name;
        if (p.ready) text += ' (Listo)';
        if (p.score !== null) text += ` - PuntuaciÃ³n: ${p.score.toFixed(1)}`;
        li.innerText = text;
        li.style.color = p.ready ? '#00e5ff' : '#fff';
        list.appendChild(li);
    });
    
    multiplayerGameMode = data.mode || 'competitivo';
    roomCharacters = data.characters || {};
    
    if (!isHost) {
        document.getElementById('lobby-mode-display').innerText = multiplayerGameMode === 'competitivo' ? 
            'Modo Competitivo' : 'Modo Cooperativo (Elige personaje)';
    } else {
        document.getElementById('lobby-mode-select').value = multiplayerGameMode;
    }
    
    const charsContainer = document.getElementById('lobby-characters-container');
    const charsList = document.getElementById('lobby-characters');
    
    if (multiplayerGameMode === 'cooperativo') {
        charsContainer.style.display = 'block';
        charsList.innerHTML = '';
        allPackCharacters.forEach(c => {
            const row = document.createElement('div');
            row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:#121a24; padding:10px; border-radius:6px;';
            
            const nameEl = document.createElement('span');
            nameEl.innerText = c;
            nameEl.style.color = '#fff';
            
            const actionEl = document.createElement('div');
            const claimedBy = roomCharacters[c];
            
            if (claimedBy) {
                if (claimedBy === socket.id) {
                    // I claimed it
                    const btn = document.createElement('button');
                    btn.innerText = 'Quitar';
                    btn.className = 'btn-secondary';
                    btn.style.padding = '5px 10px';
                    btn.onclick = () => socket.emit('claim_character', {room: currentRoom, character: c, claim: false});
                    actionEl.appendChild(btn);
                    nameEl.style.color = '#00e5ff';
                    if (!claimedCharacters.includes(c)) claimedCharacters.push(c);
                } else {
                    // Someone else claimed it
                    const player = data.players.find(p => p.sid === claimedBy);
                    const span = document.createElement('span');
                    span.innerText = `Reclamado por ${player ? player.name : 'Otro'}`;
                    span.style.color = '#ff1744';
                    span.style.fontSize = '0.8rem';
                    actionEl.appendChild(span);
                    claimedCharacters = claimedCharacters.filter(ch => ch !== c);
                }
            } else {
                // Available
                const btn = document.createElement('button');
                btn.innerText = 'Elegir';
                btn.className = 'btn-primary';
                btn.style.padding = '5px 10px';
                btn.onclick = () => socket.emit('claim_character', {room: currentRoom, character: c, claim: true});
                actionEl.appendChild(btn);
                claimedCharacters = claimedCharacters.filter(ch => ch !== c);
            }
            
            row.appendChild(nameEl);
            row.appendChild(actionEl);
            charsList.appendChild(row);
        });
    } else {
        charsContainer.style.display = 'none';
        claimedCharacters = [];
    }
});
"""
content = re.sub(room_update_regex, new_room_update.strip(), content, flags=re.DOTALL)

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched app.js with coop lobby logic")
