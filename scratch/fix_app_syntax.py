import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the syntax error in calculateFinalScore
bad_syntax = """        }
        }, 1000);
    });
    
    socket.on('error', (data) => {"""

good_syntax = """        }
        
    } catch(e) {
        clearInterval(calcInterval);
        console.error(e);
    }
}

btnSave.onclick = async () => {
    btnSave.disabled = true;
    btnSave.innerText = 'Procesando...';
    
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
            // already ready
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
        
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'mi_doblaje.webm';
        a.click();
        
        btnSave.disabled = false;
        btnSave.innerText = 'Descargar Vídeo Final';
    };
    mediaRecorder.start();
    
    setTimeout(() => {
        mediaRecorder.stop();
        if (packHasVideo) sceneVideo.pause();
    }, maxTime * 1000);
};

// Start of setupSocket and socket events that were lost
function setupSocket() {
    socket.on('error', (data) => {"""

content = content.replace(bad_syntax, good_syntax)

# Check if we successfully replaced it
if good_syntax in content:
    with open(app_js_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed syntax error and restored btnSave.onclick!")
else:
    print("Failed to replace!")
