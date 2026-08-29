import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Normalize clipsList immediately after fetching
norm_code = """
    // Normalize clip format to always have .character and .name
    clipsList.forEach((clip, i) => {
        if (!clip.character && clip.name) {
            let parts = clip.name.split('_');
            clip.character = parts.length > 1 ? parts.slice(1).join('_').replace('.wav', '') : clip.name;
        }
        if (!clip.name && clip.character) {
            clip.name = `clip_${i}_${clip.character}.wav`;
        }
    });
"""

# Patch fetchPackClips
content = re.sub(r'clipsList = d\.clips \|\| \[\];', f'clipsList = d.clips || [];{norm_code}', content)

# Patch selectPack
content = re.sub(r'hasBackingTrack = data\.has_backing_track;', f'hasBackingTrack = data.has_backing_track;{norm_code}', content)

# Replace all name parsing with clip.character
# In selectPack:
content = re.sub(
    r"let parts = clip\.name\.split\('_'\);\s*let charName = parts\.length > 1 \? parts\.slice\(1\)\.join\('_'\) : clip\.name;",
    r"let charName = clip.character;",
    content
)

# In advanceToNextSelectedClip:
content = re.sub(
    r"let parts = clipsList\[index\]\.name\.split\('_'\);\s*let charName = parts\.length > 1 \? parts\.slice\(1\)\.join\('_'\) : clipsList\[index\]\.name;",
    r"let charName = clipsList[index].character;",
    content
)

# In isLastSelectedClip:
content = re.sub(
    r"let parts = clipsList\[i\]\.name\.split\('_'\);\s*let charName = parts\.length > 1 \? parts\.slice\(1\)\.join\('_'\) : clipsList\[i\]\.name;",
    r"let charName = clipsList[i].character;",
    content
)

# In loadClip (part 1):
content = re.sub(
    r"let parts = clipsList\[i\]\.name\.split\('_'\);\s*let charName = parts\.length > 1 \? parts\.slice\(1\)\.join\('_'\) : clipsList\[i\]\.name;",
    r"let charName = clipsList[i].character;",
    content
)

# In loadClip (part 2):
content = re.sub(
    r"let parts = clip\.name\.split\('_'\);\s*let charName = parts\.length > 1 \? parts\.slice\(1\)\.join\('_'\) : clip\.name;",
    r"let charName = clip.character;",
    content
)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched app.js with clip normalization.")
