import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

create_regex = r'async function createMultiplayerRoom\(packName\) \{.*?catch\(e\) \{\s*alert\("Error al crear sala"\);\s*\}\s*\}'

new_create_room = """async function createMultiplayerRoom(packName) {
    let name = prompt("Introduce tu Nickname para la sala:");
    if (!name) return;
    
    try {
        const res = await fetch('/api/create_room', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pack_name: packName, mode: 'competitivo' })
        });
        const data = await res.json();
        
        isMultiplayer = true;
        currentRoom = data.room_code;
        currentPack = packName;
        myName = name;
        isHost = true;
        
        // Fetch unique characters for this pack
        await fetchPackClips(); 
        
        document.getElementById('lobby-pack-name').innerText = `Sala: ${currentRoom} (${currentPack})`;
        showView('view-lobby');
        
        const tunnelEl = document.getElementById('lobby-tunnel-link');
        tunnelEl.style.display = 'block';
        tunnelEl.innerHTML = 'Generando enlace mágico...';
        
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
        
        socket.emit('join', { room: currentRoom, name: myName });
        
    } catch(e) {
        console.error(e);
        alert("Error al crear sala");
    }
}
"""

content = re.sub(create_regex, new_create_room, content, flags=re.DOTALL)

join_regex = r'async function joinMultiplayerRoom\(\) \{.*?catch\(e\) \{\s*alert\("Error de conexi[^\"]+buscar la sala\."\);\s*\}\s*\}'

new_join_room = """async function joinMultiplayerRoom() {
    const name = document.getElementById('join-name').value.trim();
    const code = document.getElementById('join-code').value.trim().toUpperCase();
    
    if (!name || !code) {
        alert("Rellena nombre y código");
        return;
    }
    
    try {
        const res = await fetch(`/api/check_room/${code}`);
        const data = await res.json();
        
        if (!data.valid) {
            alert(data.reason);
            return;
        }
        
        isMultiplayer = true;
        currentRoom = code;
        currentPack = data.pack_name;
        myName = name;
        isHost = false;
        
        await fetchPackClips();
        
        fadeOutMusic();
        
        document.getElementById('lobby-pack-name').innerText = `Sala: ${currentRoom} (${currentPack})`;
        showView('view-lobby');
        
        document.getElementById('lobby-tunnel-link').style.display = 'none';
        
        const modeContainer = document.getElementById('lobby-mode-container');
        modeContainer.style.display = 'block';
        document.getElementById('lobby-mode-select').style.display = 'none';
        document.getElementById('lobby-mode-display').style.display = 'block';
        
        socket.emit('join', { room: currentRoom, name: myName });
        
    } catch(e) {
        console.error(e);
        alert("Error de conexión al buscar la sala.");
    }
}
"""

content = re.sub(join_regex, new_join_room, content, flags=re.DOTALL)

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched createMultiplayerRoom and joinMultiplayerRoom")
