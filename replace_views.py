with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open('new_creator_views.txt', 'r', encoding='utf-8') as f:
    creator_html = f.read()

start = html.find('    <!-- ========== TALLER DE ESCENAS ========== -->')
audio_pos = html.rfind('    <audio id="menu-music"')

new_html = html[:start] + creator_html + html[audio_pos:]

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print(f'Done. Lines: {len(new_html.splitlines())}')
