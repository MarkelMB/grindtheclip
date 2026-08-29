import os
import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix btnSave translation
content = content.replace("'Downloading' + '.'.repeat(dotCount)", "'Exportando' + '.'.repeat(dotCount)")
content = content.replace("btnSave.innerText = 'Done!';", "btnSave.innerText = '¡Guardado!';")

# 2. Fix the oncanplay hang in btnSave
old_save_video_wait = """        await new Promise((resolve) => {
            sceneVideo.oncanplay = resolve;
            sceneVideo.load();
        });"""

new_save_video_wait = """        if (sceneVideo.readyState >= 3) {
            // Already loaded
        } else {
            await new Promise((resolve) => {
                sceneVideo.oncanplay = resolve;
                sceneVideo.onerror = resolve; // Don't hang on error
                sceneVideo.load();
            });
        }"""

content = content.replace(old_save_video_wait, new_save_video_wait)


# 3. We also need to add playbackSources to btnSave so it cleans up if they exit early, but wait, btnSave doesn't start them on audioContext.destination, it starts them on audioDest. If we stop them, the media recorder might just record silence, which is fine if they exit. Let's just focus on the hang.

# Let's check btnWatch for the same hang.
old_watch_video_wait = """        await new Promise((resolve) => {
            sceneVideo.oncanplay = resolve;
            sceneVideo.load();
        });"""

new_watch_video_wait = """        if (sceneVideo.readyState >= 3) {
            // Already loaded
        } else {
            await new Promise((resolve) => {
                sceneVideo.oncanplay = resolve;
                sceneVideo.onerror = resolve;
                sceneVideo.load();
            });
        }"""
        
content = content.replace(old_watch_video_wait, new_watch_video_wait)

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("app.js patched for video readyState.")
