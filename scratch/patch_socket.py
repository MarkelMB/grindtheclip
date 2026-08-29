import sys

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

missing_handlers = """
// ---------------- MULTIPLAYER HANDLERS ----------------
socket.on('room_update', (data) => {
    multiplayerGameMode = data.mode;
    if (!isHost) {
        document.getElementById('lobby-mode-display').innerText = 'Modo: ' + data.mode.toUpperCase();
    }
    
    const playersDiv = document.getElementById('lobby-players');
    if(playersDiv) {
        playersDiv.innerHTML = '';
        data.players.forEach(p => {
            const pdiv = document.createElement('div');
            pdiv.style.padding = '10px';
            pdiv.style.marginBottom = '5px';
            pdiv.style.background = p.ready ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 255, 255, 0.05)';
            pdiv.style.border = p.ready ? '1px solid #00e676' : '1px solid #2a3f54';
            pdiv.style.borderRadius = '5px';
            
            let html = `<strong style="color: ${p.ready ? '#00e676' : '#fff'}">${p.name}</strong> `;
            if(p.ready) html += ' - LSTO';
            pdiv.innerHTML = html;
            playersDiv.appendChild(pdiv);
        });
    }
    
    // Update chars if coop
    claimedCharacters = [];
    if(data.characters) {
        Object.keys(data.characters).forEach(charName => {
            claimedCharacters.push(charName);
        });
    }
    
    if (multiplayerGameMode === 'cooperativo') {
        const charsContainer = document.getElementById('lobby-chars-container');
        const charsList = document.getElementById('lobby-chars-list');
        if (charsContainer && charsList && allPackCharacters) {
            charsContainer.style.display = 'block';
            charsList.innerHTML = '';
            
            allPackCharacters.forEach(c => {
                const row = document.createElement('div');
                row.style.display = 'flex';
                row.style.alignItems = 'center';
                row.style.justifyContent = 'space-between';
                row.style.padding = '8px 12px';
                row.style.background = '#121a24';
                row.style.borderRadius = '6px';
                row.style.marginBottom = '6px';
                
                const nameSpan = document.createElement('span');
                nameSpan.innerText = c;
                nameSpan.style.color = '#fff';
                
                const btnClaim = document.createElement('button');
                btnClaim.className = 'btn-pill';
                
                if (data.characters && data.characters[c]) {
                    if (data.characters[c] === socket.id) {
                        btnClaim.innerText = 'Tuyo';
                        btnClaim.style.background = '#00e5ff';
                        btnClaim.style.color = '#000';
                        btnClaim.onclick = () => socket.emit('claim_character', {room: currentRoom, character: c, claim: false});
                    } else {
                        const owner = data.players.find(p => p.sid === data.characters[c]);
                        btnClaim.innerText = owner ? owner.name : 'Ocupado';
                        btnClaim.disabled = true;
                        btnClaim.style.background = '#37474f';
                        btnClaim.style.color = '#fff';
                    }
                } else {
                    btnClaim.innerText = 'Elegir';
                    btnClaim.style.background = '#ff4081';
                    btnClaim.style.color = '#fff';
                    btnClaim.onclick = () => socket.emit('claim_character', {room: currentRoom, character: c, claim: true});
                }
                
                row.appendChild(nameSpan);
                row.appendChild(btnClaim);
                charsList.appendChild(row);
            });
        }
    } else {
        const charsContainer = document.getElementById('lobby-chars-container');
        if (charsContainer) charsContainer.style.display = 'none';
    }
});

socket.on('game_start_countdown', (data) => {
    showView('view-play');
    document.getElementById('recording-controls').style.display = 'flex';
    document.getElementById('finished-controls').classList.add('hidden');
    document.getElementById('final-score-container').style.opacity = '0';
    document.getElementById('final-score-container').style.transform = 'scale(0.8)';
    
    // Auto-start recording logic
    document.getElementById('btn-record').click();
});
"""

if "socket.on('room_update'" not in content:
    content += missing_handlers
    with open(app_js_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Injected multiplayer handlers.")
else:
    print("Multiplayer handlers already present.")
