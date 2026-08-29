import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# The game_start_countdown block is completely messed up now.
# Let's restore the whole block.
start_idx = content.find("if (audioContext.state === 'suspended') await audioContext.resume();")
if start_idx != -1:
    end_idx = content.find("const panelButtons = document.querySelector('.panel-buttons');", start_idx)
    
    if end_idx != -1:
        restored = """if (audioContext.state === 'suspended') await audioContext.resume();
    
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
        claimedCharacters = allPackCharacters; // FIX
    }
    
    // 4. Start game UI
    showView('view-play');
    sceneVideo.style.display = 'none';
    sceneVideo.classList.add('hidden');
    
    clipImage.style.display = 'block';
    if(scoreCard) scoreCard.classList.add('hidden');
    
    """
        
        new_content = content[:start_idx] + restored + content[end_idx:]
        with open('static/app.js', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Patched game_start_countdown successfully.")
    else:
        print("End idx not found")
else:
    print("Start idx not found")
