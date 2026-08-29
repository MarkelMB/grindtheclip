import os

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update stopAudio
stop_audio_old = """function stopAudio() {
    if (sourceOriginal) { sourceOriginal.stop(); sourceOriginal.disconnect(); sourceOriginal = null; }
    if (sourceBacking) { sourceBacking.stop(); sourceBacking.disconnect(); sourceBacking = null; }"""

stop_audio_new = """function stopAudio() {
    if (sourceOriginal) { try { sourceOriginal.stop(); sourceOriginal.disconnect(); } catch(e){} sourceOriginal = null; }
    if (sourceBacking) { try { sourceBacking.stop(); sourceBacking.disconnect(); } catch(e){} sourceBacking = null; }
    
    if (window.playbackSources) {
        window.playbackSources.forEach(src => { try { src.stop(); src.disconnect(); } catch(e){} });
        window.playbackSources = [];
    }
    if (window.playbackTimeout) {
        clearTimeout(window.playbackTimeout);
        window.playbackTimeout = null;
    }"""

content = content.replace(stop_audio_old, stop_audio_new)

# 2. Update btnWatch.onclick
content = content.replace("const sources = [];", "window.playbackSources = [];")
content = content.replace("sources.push(src);", "window.playbackSources.push(src);")
content = content.replace("sources[i].start(", "window.playbackSources[i].start(")

content = content.replace(
    "// Wait for the whole scene to finish playing\n    setTimeout(() => {",
    "// Wait for the whole scene to finish playing\n    window.playbackTimeout = setTimeout(() => {"
)

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("app.js exit playback patched successfully.")
