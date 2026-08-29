import os

filepath = 'static/app.js'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("document.getElementById('recording-controls')", "document.querySelector('.panel-buttons')")
content = content.replace("document.getElementById('final-score-container')", "scoreCard")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched app.js successfully.")
