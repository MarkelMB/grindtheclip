import os
import re

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Helper function to inject
helper_code = """
async function ensureAllOriginalBuffers() {
    const promises = [];
    for (let i = 0; i < clipsList.length; i++) {
        if (!clipOriginalBuffers[i]) {
            promises.push((async () => {
                const res = await fetch(`/media/${currentPack}/${clipsList[i].audio_file}`);
                const arrayBuffer = await res.arrayBuffer();
                clipOriginalBuffers[i] = await audioContext.decodeAudioData(arrayBuffer);
            })());
        }
    }
    await Promise.all(promises);
}

// 4. Watch Phase & Final Scoring
"""

# 1. Inject ensureAllOriginalBuffers right before btnWatch
content = content.replace("// 4. Watch Phase & Final Scoring\n", helper_code)

# 2. Add await ensureAllOriginalBuffers() inside btnWatch.onclick
content = content.replace(
    "btnWatch.onclick = async () => {\n    if (isPlaying || isRecording) return;\n    isPlaying = true;\n",
    "btnWatch.onclick = async () => {\n    if (isPlaying || isRecording) return;\n    isPlaying = true;\n    await ensureAllOriginalBuffers();\n"
)

# 3. Add await ensureAllOriginalBuffers() inside btnSave.onclick
content = content.replace(
    "btnSave.onclick = async () => {\n    if (isPlaying || isRecording) return;\n    isPlaying = true;\n",
    "btnSave.onclick = async () => {\n    if (isPlaying || isRecording) return;\n    isPlaying = true;\n    await ensureAllOriginalBuffers();\n"
)

# 4. Fix sceneVideo visibility (remove hidden class)
content = content.replace(
    "sceneVideo.style.display = 'block';",
    "sceneVideo.style.display = 'block';\n            sceneVideo.classList.remove('hidden');"
)
content = content.replace(
    "sceneVideo.style.display = 'none';",
    "sceneVideo.style.display = 'none';\n            sceneVideo.classList.add('hidden');"
)


with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("app.js patched successfully.")
