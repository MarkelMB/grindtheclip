import re
with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Replace the clipSubtitle innerText line with a clean one
js = re.sub(r'clipSubtitle\.innerText = clip\.text \? .*?clip\.subtitle.*? : .*?clip\.name.*?;', "clipSubtitle.innerText = clip.text ? \"\" : \"\";", js)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
