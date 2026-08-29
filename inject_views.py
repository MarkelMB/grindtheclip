with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open('creator_views.txt', 'r', encoding='utf-8') as f:
    creator_html = f.read()

# Find where to insert (before audio tag)
audio_pos = html.rfind('    <audio id="menu-music"')
if audio_pos == -1:
    print('ERROR: audio tag not found')
    exit(1)

# Find the end of view-play closing div (just before audio)
# We want to insert the new views just before the audio tag
new_html = html[:audio_pos] + creator_html + html[audio_pos:]

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print('SUCCESS: inserted creator views')
print(f'Total lines: {len(new_html.splitlines())}')
