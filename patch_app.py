import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: onplaying for btnListen
old_listen = """        sceneVideo.onplaying = () => {
            sourceOriginal.start();
            if (backingBuffer) sourceBacking.start(0, clipsList[currentClipIndex].timestamp || 0);
            startPlayhead(originalBuffer.duration);
            sceneVideo.onplaying = null;
        };
        sceneVideo.play().catch(e => {
            sourceOriginal.start();
            if (backingBuffer) sourceBacking.start(0, clipsList[currentClipIndex].timestamp || 0);
            startPlayhead(originalBuffer.duration);
        });"""

new_listen = """        const startListen = () => {
            if (sourceOriginal) sourceOriginal.start();
            if (backingBuffer && sourceBacking) sourceBacking.start(0, clipsList[currentClipIndex].timestamp || 0);
            startPlayhead(originalBuffer.duration);
        };
        sceneVideo.play().then(startListen).catch(e => {
            console.warn("Autoplay block or error:", e);
            startListen();
        });"""
content = content.replace(old_listen, new_listen)

# Fix 2: onplaying for btnRecord
old_record = """        if (packHasVideo) {
            sceneVideo.muted = true;
            sceneVideo.style.display = 'block';
            sceneVideo.classList.remove('hidden');
            clipImage.style.display = 'none';
            sceneVideo.currentTime = clipsList[currentClipIndex].timestamp || 0;
            sceneVideo.onplaying = () => {
                startPlaybackAndRecord();
                sceneVideo.onplaying = null;
            };
            sceneVideo.play().catch(e => {
                startPlaybackAndRecord();
            });
        } else {"""

new_record = """        if (packHasVideo) {
            sceneVideo.muted = true;
            sceneVideo.style.display = 'block';
            sceneVideo.classList.remove('hidden');
            clipImage.style.display = 'none';
            sceneVideo.currentTime = clipsList[currentClipIndex].timestamp || 0;
            sceneVideo.play().then(() => {
                startPlaybackAndRecord();
            }).catch(e => {
                console.warn("Autoplay block or error:", e);
                startPlaybackAndRecord();
            });
        } else {"""
content = content.replace(old_record, new_record)

# Fix 3: onplaying for btnWatch (if applicable)
old_watch = """        sceneVideo.onplaying = () => {
            if (backingBuffer) sourceBacking.start();
            for (let i = 0; i < clipsList.length; i++) {
                window.playbackSources[i].start(audioContext.currentTime + (clipsList[i].timestamp || 0));
            }
            sceneVideo.onplaying = null;
        };
        sceneVideo.play().catch(e => {
            // Fallback if blocked
            if (backingBuffer) sourceBacking.start();
            for (let i = 0; i < clipsList.length; i++) {
                window.playbackSources[i].start(audioContext.currentTime + (clipsList[i].timestamp || 0));
            }
        });"""

new_watch = """        const startWatch = () => {
            if (backingBuffer) sourceBacking.start();
            for (let i = 0; i < clipsList.length; i++) {
                window.playbackSources[i].start(audioContext.currentTime + (clipsList[i].timestamp || 0));
            }
        };
        sceneVideo.play().then(startWatch).catch(e => {
            console.warn("Autoplay block or error:", e);
            startWatch();
        });"""
content = content.replace(old_watch, new_watch)

# Fix 4: URI Encoding in fetch
# We need to find fetch(`/media/${packName}/... and replace it.
content = re.sub(r'fetch\(`/media/\$\{packName\}/(.*?)\?t=`', r'fetch(`/media/${encodeURIComponent(packName)}/\1?t=`', content)
content = re.sub(r'fetch\(`/media/\$\{packName\}/(.*?)(?<!\?t=)`\)', r'fetch(`/media/${encodeURIComponent(packName)}/\1`)', content)

# Check if we missed any fetch for packName (without ?t=)
# There is fetch(`/api/packs/${packName}/clips`)
content = re.sub(r'fetch\(`/api/packs/\$\{packName\}/clips`\)', r'fetch(`/api/packs/${encodeURIComponent(packName)}/clips`)', content)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched app.js successfully.")
