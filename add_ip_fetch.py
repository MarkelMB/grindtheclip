import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Add a fetch call to update the network-ip-display on start
new_code = '''
// Fetch network info for multiplayer
fetch('/api/network_info')
    .then(r => r.json())
    .then(data => {
        const el = document.getElementById('network-ip-display');
        if(el) {
            el.innerText = 'http://' + data.local_ip + ':' + data.port;
        }
    })
    .catch(e => console.error('Error fetching network info', e));
'''

# append it after socket initialization or at the top level
js = js + '\n' + new_code

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
