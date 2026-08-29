with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# The old broken content starts just after the view-play closes
# (which is the </div>\n    </div>\n just before the leftover Export footer)
# and ends just before the new TALLER DE ESCENAS section

old_junk_start = html.find('\n                \n                <!-- Export controls footer -->')
new_views_start = html.find('    <!-- ========== TALLER DE ESCENAS ========== -->')

if old_junk_start == -1:
    print('ERROR: old junk start not found')
    exit(1)
if new_views_start == -1:
    print('ERROR: new views start not found')
    exit(1)

print(f'Removing chars {old_junk_start} to {new_views_start}')
print('Junk preview:', repr(html[old_junk_start:old_junk_start+80]))
print('New start preview:', repr(html[new_views_start:new_views_start+60]))

new_html = html[:old_junk_start] + '\n\n    ' + html[new_views_start:]

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print(f'Done. Lines: {len(new_html.splitlines())}')
