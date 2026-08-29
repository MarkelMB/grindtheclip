import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the syntax error garbage block
# Find the end of checkServerTunnel block which ends with:
# .catch(e => console.error('Error fetching network info', e));
#
# }
#
# if (hasClips) {

# Let's match from `if (hasClips) {` down to `// ---------------- MULTIPLAYER HANDLERS`
start_marker = "if (hasClips) {"
end_marker = "// ---------------- MULTIPLAYER HANDLERS ----------------"

start_idx = content.find(start_marker)
# Go back a little to remove the stray }
if start_idx != -1:
    real_start = content.rfind("}", 0, start_idx) 
    end_idx = content.find(end_marker)
    if end_idx != -1:
        # Delete that entire block
        content = content[:real_start] + "\n\n" + content[end_idx:]

# 2. Fix 'btn-lobby-ready' inside leaveLobby()
# old: document.getElementById('btn-lobby-ready').disabled = false;
content = content.replace("document.getElementById('btn-lobby-ready').disabled = false;", 
                          "const b = document.getElementById('btn-ready'); if(b) b.disabled = false;")

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixes applied.")
