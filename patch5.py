import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find("socket.on('game_start_countdown'")
# Find the next function or socket.on after game_start_countdown
next_func = content.find("// Bind ready button", start)

if start != -1 and next_func != -1:
    new_block = """socket.on('game_start_countdown', async (data) => {
    // Show a loading/countdown indicator
    const btn = document.getElementById('btn-ready');
    if(btn) btn.innerText = "⏳ PREPARANDO JUEGO...";
    
    const packName = data.pack_name;
    
    // 1. Check for video
    try {
        let vRes = await fetch(`/media/${packName}/dub_video.mp4?t=` + Date.now(), {method: 'HEAD'});
        if (vRes.ok) {
            packHasVideo = true;
            window.currentPackVideo = `/media/${packName}/dub_video.mp4`;
        } else {
            let vRes2 = await fetch(`/media/${packName}/dub_video.ogv?t=` + Date.now(), {method: 'HEAD'});
            if (vRes2.ok) {
                packHasVideo = true;
                window.currentPackVideo = `/media/${packName}/dub_video.ogv`;
            } else {
                packHasVideo = false;
            }
        }
    } catch(e) {
        packHasVideo = false;
    }
    
    if (packHasVideo) {
        sceneVideo.src = window.currentPackVideo;
        sceneVideo.load();
    }
    
    // 2. Fetch pack info for backing track
    const res = await fetch(`/api/packs/${packName}/clips`);
    const packData = await res.json();
    hasBackingTrack = packData.has_backing_track;
    
    if (audioContext.state === 'suspended') await audioContext.resume();
    
    if (hasBackingTrack) {
        const bgRes = await fetch(`/media/${packName}/_backing_track.mp3`);
        const bgArray = await bgRes.arrayBuffer();
        backingBuffer = await audioContext.decodeAudioData(bgArray);
    } else {
        backingBuffer = null;
    }
    
    userRecordings = new Array(clipsList.length).fill(null);
    clipOriginalBuffers = new Array(clipsList.length).fill(null);
    currentClipIndex = 0;
    
    // 3. Set characters to dub
    if (multiplayerGameMode === 'cooperativo') {
        // Only dub characters I claimed
        selectedCharacters = claimedCharacters;
        if (selectedCharacters.length === 0) {
            alert("No has elegido ningún personaje. Dubbearás todos como espectador/comodín.");
            selectedCharacters = allPackCharacters;
            claimedCharacters = allPackCharacters; // FIX: Ensure they are uploaded!
        }
    } else {
        // Competitive: dub everything
        selectedCharacters = allPackCharacters;
        claimedCharacters = allPackCharacters; // FIX: Ensure they are uploaded!
    }
    
    // 4. Start game UI
    showView('view-play');
    sceneVideo.style.display = 'none';
    sceneVideo.classList.add('hidden');
    clipImage.style.display = 'block';
    
    const panelButtons = document.querySelector('.panel-buttons');
    if(panelButtons) panelButtons.style.display = 'flex';
    
    const finishedControls = document.getElementById('finished-controls');
    if(finishedControls) finishedControls.classList.add('hidden');
    if(scoreCard) {
        scoreCard.style.opacity = '0';
        scoreCard.style.transform = 'scale(0.8)';
    }
    
    if (!menuMusic.paused) {
        fadeOutMusic();
    }
    
    // 5. Load first clip
    advanceToNextSelectedClip(-1);
});

"""
    content = content[:start] + new_block + content[next_func:]
    with open('static/app.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched app.js successfully.")
else:
    print("Could not find start or next_func")
