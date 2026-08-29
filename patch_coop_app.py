import os
import re

filepath = 'static/app.js'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update calculateFinalScore
old_fetch = """        const res = await fetch('/api/score_bulk', {
            method: 'POST',
            body: fd
        });"""

new_fetch = """
        if (isMultiplayer && multiplayerGameMode === 'cooperativo') {
            fd.append('room', currentRoom);
            fd.append('player_name', myName);
            fd.append('pack_name', currentPack);
            
            document.getElementById('coop-waiting-overlay').style.display = 'flex';
            
            const res = await fetch('/api/coop_submit', {
                method: 'POST',
                body: fd
            });
            return; // Stop here, wait for sockets
        }
        
        const res = await fetch('/api/score_bulk', {
            method: 'POST',
            body: fd
        });"""

content = content.replace(old_fetch, new_fetch)

# 2. Add Socket Listeners
socket_listeners = """
// COOP MULTIPLAYER SYNC
socket.on('coop_waiting_update', (data) => {
    const text = document.getElementById('coop-waiting-text');
    if (text) {
        text.innerText = `${data.finished} / ${data.total} Jugadores Listos`;
    }
});

socket.on('coop_game_over', (data) => {
    document.getElementById('coop-waiting-overlay').style.display = 'none';
    
    if (data.error) {
        alert("Error al mezclar: " + data.error);
        return;
    }
    
    // Show ranking modal
    const rankingModal = document.getElementById('coop-ranking-modal');
    const rankingList = document.getElementById('coop-ranking-list');
    rankingList.innerHTML = '';
    
    data.ranking.forEach((r, i) => {
        let color = '#fff';
        if (i===0) color = '#FFD700';
        else if (i===1) color = '#C0C0C0';
        else if (i===2) color = '#CD7F32';
        
        const li = document.createElement('li');
        li.style.display = 'flex';
        li.style.justifyContent = 'space-between';
        li.style.padding = '15px';
        li.style.background = 'rgba(255,255,255,0.05)';
        li.style.borderRadius = '10px';
        li.style.border = `1px solid ${color}`;
        
        li.innerHTML = `
            <span style="color: ${color}; font-weight: bold; font-size: 1.2rem;">#${i+1} ${r.name}</span>
            <span style="color: var(--cyan); font-weight: bold; font-size: 1.2rem;">${r.score} pts</span>
        `;
        rankingList.appendChild(li);
    });
    
    rankingModal.style.display = 'flex';
    
    document.getElementById('btn-watch-final').onclick = () => {
        rankingModal.style.display = 'none';
        
        // Setup video player for the final mix
        const finalVideoUrl = data.video_url;
        sceneVideo.src = finalVideoUrl;
        sceneVideo.style.display = 'block';
        clipImage.style.display = 'none';
        
        document.querySelector('.panel-buttons').style.display = 'none';
        document.getElementById('finished-controls').classList.remove('hidden');
        scoreCard.style.opacity = '0'; // Hide local score card
        
        sceneVideo.currentTime = 0;
        sceneVideo.play();
    };
});
"""

# Append listeners to the end of the file
if 'coop_waiting_update' not in content:
    content += "\n" + socket_listeners

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched app.js with coop logic!")
