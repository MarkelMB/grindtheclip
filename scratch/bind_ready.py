import sys

app_js_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\static\app.js'

with open(app_js_path, 'a', encoding='utf-8') as f:
    f.write("\n\n// Bind ready button\ndocument.getElementById('btn-ready').onclick = setReady;\n")
