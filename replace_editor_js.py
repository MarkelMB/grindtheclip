with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Find where editor code starts (the creatorJobId declaration)
start_marker = '// ===========================================\n// EDITOR DE ESCENAS'
if start_marker in js:
    start_idx = js.index(start_marker)
else:
    start_idx = js.index('let creatorJobId = null;')

# Find where it ends (last function in editor = exportPack closing brace before end of file)
# Everything after exportPack is the network info code we want to keep
network_marker = '// Fetch network info for multiplayer'
if network_marker in js:
    end_idx = js.index(network_marker)
else:
    end_idx = len(js)

with open('new_editor_js.txt', 'r', encoding='utf-8') as f:
    new_editor = f.read()

new_js = js[:start_idx] + new_editor + '\n' + js[end_idx:]

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(new_js)
    
print(f'Done. Total lines: {len(new_js.splitlines())}')
