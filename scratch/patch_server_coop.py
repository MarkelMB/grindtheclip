import os
import re

server_py_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\server.py'

with open(server_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace generate_room_code and everything below it until @socketio.on('join') with new create_room logic
new_create_room = """
def get_room_state(room):
    return {
        "pack_name": rooms[room]["pack_name"],
        "mode": rooms[room].get("mode", "competitivo"),
        "players": list(rooms[room]["players"].values()),
        "characters": rooms[room].get("characters", {})
    }

def generate_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code

@app.route('/api/create_room', methods=['POST'])
def create_room():
    data = request.json
    pack_name = data.get('pack_name')
    if not pack_name:
        return jsonify({"error": "Pack name missing"}), 400
        
    code = generate_room_code()
    rooms[code] = {
        "pack_name": pack_name,
        "mode": data.get("mode", "competitivo"),
        "players": {},
        "characters": {}, # char_name -> sid
        "state": "waiting"
    }
    return jsonify({"room_code": code, "pack_name": pack_name})

@app.route('/api/check_room/<code>', methods=['GET'])
def check_room(code):
    code = code.upper()
    if code not in rooms:
        return jsonify({"valid": False, "reason": "Sala no encontrada"})
    if rooms[code]['state'] != 'waiting':
        return jsonify({"valid": False, "reason": "La partida ya ha empezado"})
    return jsonify({"valid": True, "pack_name": rooms[code]['pack_name'], "mode": rooms[code].get("mode", "competitivo")})

@app.route('/api/upload_coop_clips', methods=['POST'])
def upload_coop_clips():
    room = request.form.get('room', '').upper()
    sid = request.form.get('sid')
    if room not in rooms or sid not in rooms[room]['players']:
        return jsonify({"error": "Invalid room/sid"}), 400
        
    # Expecting multiple files like clip_5, clip_7
    clip_urls = {}
    room_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"room_{room}")
    os.makedirs(room_dir, exist_ok=True)
    
    for key in request.files:
        if key.startswith('clip_'):
            file = request.files[key]
            filename = f"{sid}_{key}.webm"
            filepath = os.path.join(room_dir, filename)
            file.save(filepath)
            clip_urls[key] = f"/uploads/room_{room}/{filename}"
            
    # Notify host that this player's clips are ready
    # We find the host (the first player in the room is usually the host, but let's just broadcast to the room, the host can filter it)
    socketio.emit('player_clips_ready', {"sid": sid, "clip_urls": clip_urls}, to=room)
    return jsonify({"success": True})

@app.route('/api/upload_coop_video', methods=['POST'])
def upload_coop_video():
    room = request.form.get('room', '').upper()
    if room not in rooms:
        return jsonify({"error": "Invalid room"}), 400
        
    file = request.files.get('video')
    if not file:
        return jsonify({"error": "No video"}), 400
        
    room_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"room_{room}")
    os.makedirs(room_dir, exist_ok=True)
    
    filepath = os.path.join(room_dir, "final_coop_video.webm")
    file.save(filepath)
    
    url = f"/uploads/room_{room}/final_coop_video.webm"
    socketio.emit('coop_video_ready', {"url": url}, to=room)
    return jsonify({"success": True})

"""

content = re.sub(
    r'def generate_room_code\(\):.*?@socketio\.on\(\'join\'\)', 
    new_create_room + "@socketio.on('join')", 
    content, 
    flags=re.DOTALL
)

# Replace all emit('room_update', ...) with emit('room_update', get_room_state(room), to=room)
old_room_update = """        emit('room_update', {
            "pack_name": rooms[room]["pack_name"],
            "players": list(rooms[room]["players"].values())
        }, to=room)"""
new_room_update = "        emit('room_update', get_room_state(room), to=room)"
content = content.replace(old_room_update, new_room_update)

old_room_update2 = """    emit('room_update', {
        "pack_name": rooms[room]["pack_name"],
        "players": list(rooms[room]["players"].values())
    }, to=room)"""
new_room_update2 = "    emit('room_update', get_room_state(room), to=room)"
content = content.replace(old_room_update2, new_room_update2)

# Add change_mode and claim_character to socketio events
socket_events = """
@socketio.on('change_mode')
def on_change_mode(data):
    room = data.get('room', '').upper()
    mode = data.get('mode', 'competitivo')
    if room in rooms:
        rooms[room]['mode'] = mode
        emit('room_update', get_room_state(room), to=room)

@socketio.on('claim_character')
def on_claim_character(data):
    room = data.get('room', '').upper()
    char_name = data.get('character')
    claim = data.get('claim', True)
    
    if room in rooms and request.sid in rooms[room]["players"]:
        if claim:
            # Only claim if not already claimed
            if char_name not in rooms[room]["characters"]:
                rooms[room]["characters"][char_name] = request.sid
        else:
            if rooms[room]["characters"].get(char_name) == request.sid:
                del rooms[room]["characters"][char_name]
                
        emit('room_update', get_room_state(room), to=room)
"""
content = content.replace("@socketio.on('submit_score')", socket_events + "\n@socketio.on('submit_score')")

with open(server_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Server patched for Coop state and audio relays.")
