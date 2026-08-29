import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Make sure sceneVideo styles are correct when watching the full scene
js = js.replace("sceneVideo.classList.remove('hidden');", "sceneVideo.style.display = 'block';")
js = js.replace("clipImage.classList.add('hidden');", "clipImage.style.display = 'none';")

js = js.replace("sceneVideo.classList.add('hidden');", "sceneVideo.style.display = 'none';")
js = js.replace("clipImage.classList.remove('hidden');", "clipImage.style.display = 'block';")

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
