import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace calculateFinalScore completely
old_func_regex = re.compile(r'async function calculateFinalScore\(\) \{.*?\n\}\n', re.DOTALL)
new_func = """async function calculateFinalScore() {
    const formData = new FormData();
    let idx = 0;
    for (let i = 0; i < clipsList.length; i++) {
        if (userRecordings[i] && userRecordings[i].blob) {
            // Only upload if it's my character (in coop) or if competitive/solo
            if (multiplayerGameMode !== 'cooperativo' || claimedCharacters.includes(clipsList[i].character)) {
                formData.append(`user_audio_${idx}`, userRecordings[i].blob, `user_${idx}.wav`);
                formData.append(`ref_audio_path_${idx}`, `${currentPack}/${clipsList[i].audio_file}`);
                formData.append(`char_name_${idx}`, clipsList[i].character);
                idx++;
            }
        }
    }
    formData.append('count', idx);

    if (isMultiplayer && multiplayerGameMode === 'cooperativo') {
        // COOP MODE: Send to server for mixing, then wait
        formData.append('room', currentRoom);
        formData.append('player_name', myName);
        formData.append('pack_name', currentPack);
        
        document.getElementById('coop-waiting-overlay').style.display = 'flex';
        
        try {
            await fetch('/api/coop_submit', { method: 'POST', body: formData });
        } catch(e) {
            console.error(e);
            alert("Error enviando audios coop");
        }
        return; // Wait for socket events
    }

    // SOLO / COMPETITIVE MODE
    scoreCard.classList.remove('hidden');
    scoreRank.innerText = '?';
    verdictText.innerText = 'Calculando';
    verdictText.style.color = '#fff';
    finalScore.innerText = '0';
    
    let dots = 0;
    const calcInterval = setInterval(() => {
        dots = (dots + 1) % 4;
        verdictText.innerText = 'Calculando' + '.'.repeat(dots);
    }, 400);
    
    try {
        const res = await fetch('/api/score_bulk', { method: 'POST', body: formData });
        const data = await res.json();
        
        clearInterval(calcInterval);
        if (data.error) throw new Error(data.error);
        
        const targetScore = data.score;
        finalScore.innerText = "0";
        scoreRank.style.opacity = "0";
        scoreRank.style.transition = "opacity 0.5s ease, transform 0.5s ease";
        scoreRank.style.transform = "scale(0.5)";
        
        let startTimestamp = null;
        const duration = 2000;
        
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const easeOut = 1 - Math.pow(1 - progress, 3);
            finalScore.innerText = Math.floor(easeOut * targetScore);
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                finalScore.innerText = targetScore;
                if (targetScore >= 95) { 
                    scoreRank.innerText = 'S'; scoreRank.style.color = '#00ffff'; verdictText.innerText = '¡NIVEL DIOS!'; verdictText.style.color = '#00ffff'; 
                } else if (targetScore >= 85) { 
                    scoreRank.innerText = 'A'; scoreRank.style.color = '#00e676'; verdictText.innerText = '¡EXCELENTE!'; verdictText.style.color = '#00e676'; 
                } else if (targetScore >= 70) { 
                    scoreRank.innerText = 'B'; scoreRank.style.color = '#ffea00'; verdictText.innerText = 'MUY BUENO'; verdictText.style.color = '#ffea00'; 
                } else if (targetScore >= 50) { 
                    scoreRank.innerText = 'C'; scoreRank.style.color = '#ff9100'; verdictText.innerText = 'ACEPTABLE'; verdictText.style.color = '#ff9100'; 
                } else { 
                    scoreRank.innerText = 'F'; scoreRank.style.color = '#ff1744'; verdictText.innerText = 'DESASTRE TOTAL'; verdictText.style.color = '#ff1744'; 
                }
                scoreRank.style.opacity = "1";
                scoreRank.style.transform = "scale(1)";
            }
        };
        window.requestAnimationFrame(step);
        
        if (isMultiplayer && currentRoom && multiplayerGameMode === 'competitivo') {
            socket.emit('submit_score', { room: currentRoom, score: targetScore });
            setTimeout(() => {
                showView('view-leaderboard');
                stopAudio();
                if(packHasVideo) sceneVideo.pause();
                mainLayout.classList.remove('finished-state');
                finishedControls.classList.add('hidden');
            }, 5000);
        }
    } catch(e) {
        clearInterval(calcInterval);
        console.error(e);
    }
}
"""

# Replace calculateFinalScore
if "async function calculateFinalScore()" in content:
    content = old_func_regex.sub(new_func, content, count=1)
else:
    print("Could not find calculateFinalScore!")

# Remove old uploadCoopClips
old_upload_regex = re.compile(r'async function uploadCoopClips\(\) \{.*?\}\n', re.DOTALL)
content = old_upload_regex.sub('', content)

# Remove old coop socket listeners (player_clips_ready, coop_video_ready)
ready_regex = re.compile(r'socket\.on\(\'player_clips_ready\'.*?\}\);\n', re.DOTALL)
content = ready_regex.sub('', content)

video_ready_regex = re.compile(r'socket\.on\(\'coop_video_ready\'.*?\}\);\n', re.DOTALL)
content = video_ready_regex.sub('', content)

# Remove the broken fetch logic I injected earlier (if it's there)
# Actually my previous patch failed to inject fetch('/api/coop_submit') because the string didn't match.

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied successfully.")
