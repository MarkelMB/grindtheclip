with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the closing of view-play
play_end = html.rfind('</div>\n    </div>\n\n\n    <audio')
if play_end == -1:
    play_end = html.rfind('</div>\n\n\n    <audio')
if play_end == -1:
    play_end = html.rfind('    </div>\n\n    <audio')
    
print(f'play_end: {play_end}')
print(repr(html[play_end:play_end+60]))

audio_start = html.rfind('    <audio id="menu-music"')
print(f'audio_start: {audio_start}')
