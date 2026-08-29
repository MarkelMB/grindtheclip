with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Fix references to the renamed panel div
js = js.replace(
    'document.getElementById(''line-edit-panel'')',
    'document.getElementById(''line-edit-panel-wrap'')'
)
js = js.replace(
    'getElementById(''line-edit-panel'')',
    'getElementById(''line-edit-panel-wrap'')'
)

# Fix the selectLine and deselectLine functions to use the correct panel id
# selectLine shows the panel
js = js.replace(
    "document.getElementById('no-line-selected').style.display = 'none';\n    document.getElementById('line-edit-panel').style.display = 'flex';",
    "const lp = document.getElementById('line-edit-panel-wrap');\n    if (lp) lp.style.display = 'block';"
)
# deselectLine hides the panel
js = js.replace(
    "document.getElementById('no-line-selected').style.display = 'block';\n    document.getElementById('line-edit-panel').style.display = 'none';",
    "const lp = document.getElementById('line-edit-panel-wrap');\n    if (lp) lp.style.display = 'none';"
)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
print('Done')
