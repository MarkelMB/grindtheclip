import re

server_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\server.py'
with open(server_path, 'r', encoding='utf-8') as f:
    content = f.read()

serveo_code = r"""@app\.route\('/api/start_tunnel', methods=\['POST'\]\)
def start_tunnel\(\):.*?return jsonify\(\{"url": None, "error": str\(e\)\}\)"""

cf_code = """@app.route('/api/start_tunnel', methods=['POST'])
def start_tunnel():
    global tunnel_url, tunnel_process
    if tunnel_url:
        return jsonify({"url": tunnel_url})
    
    try:
        import urllib.request
        import os
        import platform
        
        # Download cloudflared if not exists
        exe_name = "cloudflared.exe" if platform.system() == "Windows" else "cloudflared"
        exe_path = os.path.join(os.path.dirname(__file__), exe_name)
        
        if not os.path.exists(exe_path):
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
            urllib.request.urlretrieve(url, exe_path)
            
        if tunnel_process is None or tunnel_process.poll() is not None:
            cmd = [exe_path, "tunnel", "--url", "http://127.0.0.1:5000"]
            # cloudflared logs to stderr
            tunnel_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
        url = None
        # read stderr to find trycloudflare.com link
        for i in range(30):
            line = tunnel_process.stderr.readline()
            if not line:
                break
            
            if "trycloudflare.com" in line:
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    url = match.group(0)
                    break
            time.sleep(0.5)
            
        if url:
            tunnel_url = url
            return jsonify({"url": tunnel_url})
        else:
            return jsonify({"url": None, "error": "No se pudo generar enlace de Cloudflare."})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"url": None, "error": str(e)})"""

if re.search(serveo_code, content, flags=re.DOTALL):
    content = re.sub(serveo_code, cf_code, content, flags=re.DOTALL)
    with open(server_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Switched to cloudflared")
else:
    print("Regex failed")
