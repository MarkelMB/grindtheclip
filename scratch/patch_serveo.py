import re

server_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\server.py'
with open(server_path, 'r', encoding='utf-8') as f:
    content = f.read()

pinggy_code = r"""@app\.route\('/api/start_tunnel', methods=\['POST'\]\)
def start_tunnel\(\):.*?return jsonify\(\{"url": None, "error": str\(e\)\}\)"""

serveo_code = """@app.route('/api/start_tunnel', methods=['POST'])
def start_tunnel():
    global tunnel_url, tunnel_process
    if tunnel_url:
        return jsonify({"url": tunnel_url})
    
    try:
        if tunnel_process is None or tunnel_process.poll() is not None:
            # Start serveo
            cmd = ["ssh", "-R", "80:localhost:5000", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "serveo.net"]
            tunnel_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
        # Read output to find URL
        url = None
        for i in range(15):
            line = tunnel_process.stdout.readline()
            if not line:
                break
            
            # Serveo outputs: Forwarding HTTP traffic from https://xxxx.serveousercontent.com
            if "https://" in line and ".serveousercontent.com" in line:
                match = re.search(r'https://[a-zA-Z0-9-]+\.serveousercontent\.com', line)
                if match:
                    url = match.group(0)
                    break
                
            time.sleep(0.5)
            
        if url:
            tunnel_url = url
            return jsonify({"url": tunnel_url})
        else:
            return jsonify({"url": None, "error": "Could not extract serveo URL."})
            
    except Exception as e:
        return jsonify({"url": None, "error": str(e)})"""

if re.search(pinggy_code, content, flags=re.DOTALL):
    content = re.sub(pinggy_code, serveo_code, content, flags=re.DOTALL)
    with open(server_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Switched to serveo")
else:
    print("Regex failed")
