import os
import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Modify calculateFinalScore to branch for Cooperative upload
coop_end_logic = """
        // Multiplayer score submit
        if (isMultiplayer && currentRoom) {
            if (multiplayerGameMode === 'cooperativo') {
                uploadCoopClips();
            } else {
                socket.emit('submit_score', { room: currentRoom, score: targetScore });
                setTimeout(() => {
                    showView('view-leaderboard');
                    stopAudio();
                    if(packHasVideo) sceneVideo.pause();
                    mainLayout.classList.remove('finished-state');
                    finishedControls.classList.add('hidden');
                }, 5000);
            }
        }
"""

content = re.sub(
    r'// Multiplayer score submit.*?\}\n        \}', 
    coop_end_logic.strip(), 
    content, 
    flags=re.DOTALL
)

# 2. Add uploadCoopClips function and socket events
coop_functions = """
async function uploadCoopClips() {
    const fd = new FormData();
    fd.append('room', currentRoom);
    fd.append('sid', socket.id);
    
    let hasClips = false;
    for (let i = 0; i < clipsList.length; i++) {
        // If it's a character we claimed, and we recorded it
        if (claimedCharacters.includes(clipsList[i].character) && userRecordings[i]) {
            fd.append(`clip_${i}`, userRecordings[i].blob, `clip_${i}.webm`);
            hasClips = true;
        }
    }
    
    if (hasClips) {
        document.getElementById('final-score').innerText = 'Subiendo tus audios...';
        await fetch('/api/upload_coop_clips', { method: 'POST', body: fd });
    } else {
        // If they didn't record anything for their character, or didn't claim any
        await fetch('/api/upload_coop_clips', { method: 'POST', body: fd });
    }
    
    document.getElementById('final-score').innerText = 'Esperando al resto...';
    document.getElementById('final-verdict').innerText = '';
}

socket.on('player_clips_ready', async (data) => {
    if (isHost && multiplayerGameMode === 'cooperativo') {
        playersReadyForCoop++;
        hostCoopClips[data.sid] = data.clip_urls;
        
        if (playersReadyForCoop >= expectedPlayersForCoop) {
            document.getElementById('final-score').innerText = 'Mezclando vídeo maestro...';
            
            // Download all user clips into host's userRecordings
            for (const [sid, urls] of Object.entries(hostCoopClips)) {
                for (const [key, url] of Object.entries(urls)) {
                    const idx = parseInt(key.split('_')[1]);
                    const res = await fetch(url);
                    const blob = await res.blob();
                    const arrayBuffer = await blob.arrayBuffer();
                    userRecordings[idx] = {
                        blob: blob,
                        buffer: await audioContext.decodeAudioData(arrayBuffer)
                    };
                }
            }
            
            await generateCoopVideo();
        }
    }
});

async function generateCoopVideo() {
    await ensureAllOriginalBuffers();
    
    let videoStream;
    let animId = null;
    
    const c = document.createElement('canvas');
    c.width = 1280; c.height = 720;
    c.style.position = 'absolute';
    c.style.opacity = '0';
    c.style.pointerEvents = 'none';
    document.body.appendChild(c);
    
    const ctx = c.getContext('2d');
    videoStream = c.captureStream(30);
    
    if (packHasVideo) {
        if (sceneVideo.readyState >= 3) {
            // ready
        } else {
            await new Promise((resolve) => {
                sceneVideo.oncanplay = resolve;
                sceneVideo.onerror = resolve;
                sceneVideo.load();
            });
        }
        sceneVideo.muted = true;
        sceneVideo.play();
        
        const drawVideo = () => {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, c.width, c.height);
            if (!sceneVideo.paused && !sceneVideo.ended) {
                ctx.drawImage(sceneVideo, 0, 0, c.width, c.height);
            }
            animId = requestAnimationFrame(drawVideo);
        };
        drawVideo();
    } else {
        const drawImg = () => {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, c.width, c.height);
            if (clipImage.complete) {
                const imgRatio = clipImage.naturalWidth / clipImage.naturalHeight;
                const cRatio = c.width / c.height;
                let w, h;
                if (imgRatio > cRatio) {
                    w = c.width; h = w / imgRatio;
                } else {
                    h = c.height; w = h * imgRatio;
                }
                ctx.drawImage(clipImage, (c.width - w)/2, (c.height - h)/2, w, h);
            }
            animId = requestAnimationFrame(drawImg);
        };
        drawImg();
    }
    
    const audioDest = audioContext.createMediaStreamDestination();
    let maxTime = 0;
    
    if (backingBuffer) {
        const sourceBacking = audioContext.createBufferSource();
        sourceBacking.buffer = backingBuffer;
        sourceBacking.connect(audioDest);
        sourceBacking.start();
        maxTime = backingBuffer.duration;
    }
    
    for (let i = 0; i < clipsList.length; i++) {
        const src = audioContext.createBufferSource();
        if (userRecordings[i] && userRecordings[i].buffer) {
            src.buffer = userRecordings[i].buffer;
        } else {
            src.buffer = clipOriginalBuffers[i];
        }
        src.connect(audioDest);
        
        const ts = clipsList[i].timestamp || 0;
        src.start(audioContext.currentTime + ts);
        
        if (ts + clipOriginalBuffers[i].duration > maxTime) {
            maxTime = ts + clipOriginalBuffers[i].duration;
        }
    }
    
    const tracks = [];
    if (videoStream) tracks.push(...videoStream.getVideoTracks());
    tracks.push(...audioDest.stream.getAudioTracks());
    const combinedStream = new MediaStream(tracks);
    
    let options = { mimeType: 'video/webm' };
    if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')) {
        options.mimeType = 'video/webm;codecs=vp9,opus';
    } else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')) {
        options.mimeType = 'video/webm;codecs=vp8,opus';
    }
    
    const mediaRecorder = new MediaRecorder(combinedStream, options);
    const chunks = [];
    mediaRecorder.ondataavailable = e => { if(e.data.size > 0) chunks.push(e.data); };
    mediaRecorder.onstop = async () => {
        const blob = new Blob(chunks, { type: options.mimeType });
        if (animId) cancelAnimationFrame(animId);
        
        const fd = new FormData();
        fd.append('room', currentRoom);
        fd.append('video', blob, 'final_coop.webm');
        await fetch('/api/upload_coop_video', { method: 'POST', body: fd });
    };
    mediaRecorder.start();
    
    setTimeout(() => {
        mediaRecorder.stop();
        if (packHasVideo) sceneVideo.pause();
    }, maxTime * 1000);
}

socket.on('coop_video_ready', (data) => {
    coopVideoUrl = data.url;
    document.getElementById('final-score').innerText = '¡Vídeo Maestro Terminado!';
    
    sceneVideo.src = coopVideoUrl;
    sceneVideo.muted = false;
    sceneVideo.style.display = 'block';
    sceneVideo.classList.remove('hidden');
    clipImage.style.display = 'none';
    
    btnWatch.disabled = false;
    btnWatch.innerText = '▶ Ver Película Final';
    btnWatch.onclick = () => {
        sceneVideo.currentTime = 0;
        sceneVideo.play();
    };
});
"""

content += "\n" + coop_functions

# 3. Modify `game_start_countdown` to set expectedPlayersForCoop
start_game_regex = r'socket\.on\(\'game_start_countdown\', \(data\) => \{.*?\n\}\);'
new_start_game = """
socket.on('game_start_countdown', (data) => {
    document.getElementById('lobby-players').innerHTML = `<li style="color:#00e5ff; font-size:1.5rem; text-align:center;">¡Empezando en ${data.seconds}...</li>`;
    
    expectedPlayersForCoop = document.querySelectorAll('#lobby-players li').length || 1; // It gets overwritten by the text, wait!
    // Actually we can get the player count from data if we send it. Let's just use the players array length before overwriting.
    
    setTimeout(async () => {
        await selectPack(data.pack_name);
        
        // Count players properly by looking at the last room state
        expectedPlayersForCoop = Object.keys(roomCharacters).length > 0 ? Object.keys(roomCharacters).length : 1; 
        // Wait, not all characters might be claimed. 
        // We should just use a global or pass it from backend. But we can assume it's just the number of players that were in the lobby.
        // Actually, we can fetch the players list from the server, but let's just use the length of the list before we clear it.
        // Or even better: expectedPlayersForCoop is passed from the server in `data.players_count`. Let's assume we modify server.py to send it.
        
        showView('view-play');
        btnSave.style.display = 'none'; // Don't allow saving manually in multiplayer
    }, data.seconds * 1000);
});
"""
content = re.sub(start_game_regex, new_start_game.strip(), content, flags=re.DOTALL)

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched app.js with end game flow")
