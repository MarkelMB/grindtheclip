import re
with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Fix the specific corrupted strings
js = re.sub(r'const status = p\.ready \? ''.*?Listo'' : ''.*?Esperando'';', "const status = p.ready ? '✅ Listo' : '⏳ Esperando';", js)
js = re.sub(r'li\.innerText = .*? \$\{p\.name\} - \$\{status\};', "li.innerText = 🎤  - ;", js)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
