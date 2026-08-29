import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

js = re.sub(r'// Fetch network info for multiplayer.*?catch\(e => console\.error\(''Error fetching network info'', e\)\);\n?', '', js, flags=re.DOTALL)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(r'        <div id="network-info-box".*?</div>\n', '', html, flags=re.DOTALL)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
