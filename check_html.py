with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the creator views section and replace
start = html.find('    <!-- ========== TALLER DE ESCENAS ========== -->')
audio_pos = html.rfind('    <audio id="menu-music"')

print(f'start={start}, audio_pos={audio_pos}')
print('Between:')
print(repr(html[start:start+80]))
print('...')
print(repr(html[audio_pos-20:audio_pos+50]))
