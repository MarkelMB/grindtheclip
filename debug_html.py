import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the section from the play view closing tag to the audio tag
# We'll insert new creator views between </div>\n\n and <audio
marker_start = html.find('    <!-- ========== NEW CREATOR VIEWS ========== -->')
if marker_start == -1:
    # Find after the view-play closing div
    marker_start = html.find('\n\n\n    <audio id="menu-music"')
    if marker_start == -1:
        marker_start = html.find('\n\n    <audio id="menu-music"')
    
    new_content = html[:marker_start]
else:
    # Find end of old creator views section (before audio tag)
    marker_end = html.find('\n\n\n    <audio id="menu-music"')
    if marker_end == -1:
        marker_end = html.find('\n\n    <audio id="menu-music"')
    new_content = html[:marker_start]
    html = new_content + html[marker_end:]

print(f"Marker found at position: {marker_start}")
print(f"HTML length: {len(html)}")
print("Preview around marker:")
print(repr(html[max(0,marker_start-30):marker_start+50]))
