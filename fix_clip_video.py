import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Fix the loadClip function to show the video if packHasVideo is true
old_clip_logic = '''    if (clip.image) {
        sceneVideo.style.display = 'none';
        clipImage.style.display = 'block';
        clipImage.src = /media//;
    } else {
        sceneVideo.style.display = 'none';
        clipImage.style.display = 'block';
        clipImage.src = window.currentPackIcon;
    }'''

new_clip_logic = '''    if (packHasVideo) {
        sceneVideo.style.display = 'block';
        clipImage.style.display = 'none';
        sceneVideo.src = /media//dub_video.mp4;
        sceneVideo.currentTime = clip.timestamp || 0;
        sceneVideo.pause();
    } else if (clip.image) {
        sceneVideo.style.display = 'none';
        clipImage.style.display = 'block';
        clipImage.src = /media//;
    } else {
        sceneVideo.style.display = 'none';
        clipImage.style.display = 'block';
        clipImage.src = window.currentPackIcon || '';
    }'''

js = js.replace(old_clip_logic, new_clip_logic)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
