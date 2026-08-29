import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Replace the fetch block to handle local_ips array
new_fetch = '''
// Fetch network info for multiplayer
fetch('/api/network_info')
    .then(r => r.json())
    .then(data => {
        const el = document.getElementById('network-ip-display');
        if(el && data.local_ips && data.local_ips.length > 0) {
            let html = "";
            data.local_ips.forEach(ip => {
                html += 'http://' + ip + ':' + data.port + '<br>';
            });
            el.innerHTML = html;
        }
    })
    .catch(e => console.error('Error fetching network info', e));
'''

# The previous block was:
old_fetch_pattern = r"// Fetch network info for multiplayer.*?catch\(e => console\.error\('Error fetching network info', e\)\);"

js = re.sub(old_fetch_pattern, new_fetch.strip(), js, flags=re.DOTALL)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
