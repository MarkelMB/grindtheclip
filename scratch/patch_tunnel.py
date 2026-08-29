import os
import re

server_py_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\server.py'

with open(server_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

tunnel_code = """
ngrok_url = None

@app.route('/api/start_tunnel', methods=['POST'])
def start_tunnel():
    global ngrok_url
    if ngrok_url:
        return jsonify({"url": ngrok_url})
    
    try:
        from pyngrok import ngrok
        tunnel = ngrok.connect(5000)
        ngrok_url = tunnel.public_url
        return jsonify({"url": ngrok_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# MULTIPLAYER LOBBY ENDPOINTS
"""

content = content.replace("# MULTIPLAYER LOBBY ENDPOINTS\n", tunnel_code)

with open(server_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Tunnel logic added to server.py")
