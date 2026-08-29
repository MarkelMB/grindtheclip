import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Replace http:// with https:// in the fetch callback
js = js.replace("'http://' + ip + ':' + data.port", "'https://' + ip + ':' + data.port")

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
