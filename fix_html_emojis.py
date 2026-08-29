import re
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(r'JUGAR ONLINE \?\?', 'JUGAR ONLINE 🌐', html)
html = re.sub(r'Taller de Escenas \(Nuevo Pack\)', 'Taller de Escenas (Nuevo Pack)', html) # just in case
# Also look for ?? Taller de Escenas
html = re.sub(r'\?\? Taller de Escenas', '🤖 Taller de Escenas', html)
html = re.sub(r'\?\? Subir archivo de v.deo:', '📁 Subir archivo de vídeo:', html)
html = re.sub(r'\?\? Enlace de YouTube:', '🔗 Enlace de YouTube:', html)
html = re.sub(r'\?\? CREAR ESCENA', '🚀 CREAR ESCENA', html)
html = re.sub(r'\?\? Volver', '◀ Volver', html)
html = re.sub(r'\? Volver', '◀ Volver', html)
html = re.sub(r'\? Volver', '◀ Volver', html)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
