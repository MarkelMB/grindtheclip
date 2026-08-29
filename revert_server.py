import re

with open('server.py', 'r', encoding='utf-8') as f:
    py = f.read()

# Remove get_local_ips and get_network_info
py = re.sub(r'import socket\ndef get_local_ips\(\):.*?return list\(ips\)\n\n@app\.route\(''/api/network_info'', methods=\[''GET''\]\)\ndef get_network_info\(\):\n    return jsonify\(\{"local_ips": get_local_ips\(\), "port": 5000\}\)', '', py, flags=re.DOTALL)

# Revert the if __name__ block
old_main = '''if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
'''
py = re.sub(r"if __name__ == '__main__':.*?allow_unsafe_werkzeug=True\)", old_main.strip(), py, flags=re.DOTALL)

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(py)
