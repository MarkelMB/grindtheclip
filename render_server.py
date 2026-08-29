"""
GrindTheClip - Render Room Registry Server
Servidor minimalista para registrar y resolver codigos de sala
entre jugadores de distintas redes.
"""
import os
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'grindtheclip_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory room registry: { code: { host_ip, created_at } }
rooms = {}

ROOM_TTL_SECONDS = 3600  # Salas caducan tras 1 hora de inactividad


def cleanup_old_rooms():
    """Elimina salas antiguas que llevan más de 1h sin actividad."""
    now = time.time()
    expired = [c for c, r in rooms.items() if now - r.get('created_at', now) > ROOM_TTL_SECONDS]
    for c in expired:
        del rooms[c]


@app.route('/')
def index():
    return jsonify({'status': 'ok', 'service': 'GrindTheClip Room Registry', 'rooms': len(rooms)})


@app.route('/register_room', methods=['POST'])
def register_room():
    """Registra un codigo de sala con la IP del host."""
    data = request.get_json(force=True, silent=True) or {}
    code = data.get('code', '').strip().upper()
    host_ip = data.get('host_ip', request.remote_addr)

    if not code or len(code) != 4:
        return jsonify({'error': 'Codigo invalido'}), 400

    cleanup_old_rooms()
    rooms[code] = {
        'host_ip': host_ip,
        'created_at': time.time()
    }
    print(f"[Registry] Sala registrada: {code} -> {host_ip}")
    return jsonify({'success': True, 'code': code})


@app.route('/resolve_room/<code>', methods=['GET'])
def resolve_room(code):
    """Devuelve la IP del host para un codigo de sala."""
    code = code.strip().upper()
    cleanup_old_rooms()

    if code in rooms:
        host_ip = rooms[code]['host_ip']
        print(f"[Registry] Resolviendo sala: {code} -> {host_ip}")
        return jsonify({'success': True, 'host_ip': host_ip, 'code': code})
    else:
        return jsonify({'success': False, 'error': 'Sala no encontrada o expirada'}), 404


@app.route('/delete_room', methods=['POST'])
def delete_room():
    """Elimina una sala del registro (cuando el host cierra el juego)."""
    data = request.get_json(force=True, silent=True) or {}
    code = data.get('code', '').strip().upper()
    if code in rooms:
        del rooms[code]
        print(f"[Registry] Sala eliminada: {code}")
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Sala no encontrada'}), 404


@app.route('/list_rooms', methods=['GET'])
def list_rooms():
    """Lista todas las salas activas (para debugging)."""
    cleanup_old_rooms()
    return jsonify({'rooms': list(rooms.keys()), 'count': len(rooms)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
