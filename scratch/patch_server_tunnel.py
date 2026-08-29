import re
import os

server_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\server.py'

with open(server_path, 'r', encoding='utf-8') as f:
    content = f.read()

tunnel_code = """
import subprocess
import time
import re

tunnel_url = None
tunnel_process = None

@app.route('/api/start_tunnel', methods=['POST'])
def start_tunnel():
    global tunnel_url, tunnel_process
    if tunnel_url:
        return jsonify({"url": tunnel_url})
    
    try:
        if tunnel_process is None or tunnel_process.poll() is not None:
            # Start pinggy
            cmd = ["ssh", "-p", "443", "-R0:localhost:5000", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "a.pinggy.io"]
            tunnel_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
        # Read output to find URL
        url = None
        for i in range(15):
            line = tunnel_process.stdout.readline()
            if not line:
                break
            
            # Pinggy outputs something like: http://rnzha-2a02-2e02-xxxx.a.free.pinggy.link
            match = re.search(r'https?://[a-zA-Z0-9-]+\.a\.free\.pinggy\.link', line)
            if match:
                url = match.group(0)
                break
                
            time.sleep(0.5)
            
        if url:
            tunnel_url = url
            # Need to swap http for https because pinggy provides both on the same domain usually, but https is better
            tunnel_url = tunnel_url.replace("http://", "https://")
            return jsonify({"url": tunnel_url})
        else:
            return jsonify({"url": None, "error": "Could not extract pinggy URL. Make sure SSH is installed."})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"url": None, "error": str(e)})
"""

if "/api/start_tunnel" not in content:
    # Inject it before the last block (if __name__ == '__main__')
    content = content.replace("if __name__ == '__main__':", tunnel_code + "\nif __name__ == '__main__':")
    with open(server_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Injected /api/start_tunnel")
else:
    print("Already injected")
