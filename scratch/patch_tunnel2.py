import os
import re

server_py_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\server.py'

with open(server_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

tunnel_code = """
import subprocess
import threading
import time
import re

serveo_url = None
serveo_process = None

def run_serveo():
    global serveo_url, serveo_process
    serveo_process = subprocess.Popen(
        ['ssh', '-R', '80:localhost:5000', 'serveo.net', '-o', 'StrictHostKeyChecking=no'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    for line in serveo_process.stdout:
        print("[SERVEO]", line.strip())
        match = re.search(r'Forwarding HTTP traffic from (https://[a-zA-Z0-9.-]+\.serveousercontent\.com)', line)
        if match:
            serveo_url = match.group(1)

@app.route('/api/start_tunnel', methods=['POST'])
def start_tunnel():
    global serveo_url, serveo_process
    if serveo_url:
        return jsonify({"url": serveo_url})
    
    if serveo_process is None:
        t = threading.Thread(target=run_serveo, daemon=True)
        t.start()
        
    # Wait up to 10 seconds for the URL
    for _ in range(20):
        if serveo_url:
            return jsonify({"url": serveo_url})
        time.sleep(0.5)
        
    return jsonify({"error": "No se pudo crear el tunnel (timeout)"}), 500

# MULTIPLAYER LOBBY ENDPOINTS
"""

# Replace the previous tunnel code
# We find everything from 'ngrok_url = None' to '# MULTIPLAYER LOBBY ENDPOINTS'
pattern = re.compile(r'ngrok_url = None.*?# MULTIPLAYER LOBBY ENDPOINTS', re.DOTALL)
content = pattern.sub(tunnel_code.strip(), content)

with open(server_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Serveo tunnel logic added to server.py")
