import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import time
import json
import warnings
import threading
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit
try:
    import numpy as np
except Exception as _e:
    print(f"[Warning] numpy import warning: {_e}")
    np = None

try:
    import librosa
    import soundfile as sf
except Exception as _e:
    print(f"[Warning] Audio scoring module import warning: {_e}")
    librosa = None
    sf = None
import io
import shutil
from werkzeug.utils import secure_filename
try:
    import ai_pipeline
except Exception as _ai_err:
    print(f'[Warning] ai_pipeline import error: {_ai_err}')
    ai_pipeline = None

warnings.filterwarnings('ignore', category=UserWarning)

app = Flask(__name__)
# Add config for large uploads
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500 MB max
# Keep default=0 so we control caching explicitly per-route (socket.io must NOT be cached)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
try:
    import gevent
    async_mode_str = "gevent"
except Exception:
    async_mode_str = "threading"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode_str)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

# ==============================================================================
# ROOM & STATE MANAGER (Re-architected Modular Room State)
# ==============================================================================

class RoomManager:
    """Centralized manager for room state, players, modes, and votes."""
    def __init__(self):
        self.rooms = {}

    def create_room(self, code, pack_name, mode='cooperativo', scoring_mode='ia'):
        code = code.upper()
        self.rooms[code] = {
            "code": code,
            "pack_name": pack_name,
            "mode": mode,
            "scoring_mode": scoring_mode,
            "score_sensitivity": "normal",
            "playback_mode": "premiere",
            "state": "waiting",
            "players": {},
            "characters": {},
            "coop_data": {},
            "comp_data": {},
            "votes": {}
        }
        return self.rooms[code]

    def get_room(self, code):
        if not code:
            return None
        return self.rooms.get(code.upper())

    def get_room_state(self, code):
        r = self.get_room(code)
        if not r:
            return None
        return {
            "code": r["code"],
            "pack_name": r["pack_name"],
            "mode": r["mode"],
            "scoring_mode": r.get("scoring_mode", "ia"),
            "score_sensitivity": r.get("score_sensitivity", "normal"),
            "playback_mode": r.get("playback_mode", "premiere"),
            "state": r["state"],
            "players": list(r["players"].values()),
            "characters": r["characters"]
        }

room_mgr = RoomManager()
rooms = room_mgr.rooms

# Detect cloud environment (Render sets RENDER=true)
IS_CLOUD = os.getenv('RENDER') or os.getenv('PORT')
if IS_CLOUD:
    PACKS_DIR = os.path.join(os.path.dirname(__file__), 'packs_voice')
else:
    user_appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    PACKS_DIR = os.path.join(user_appdata, 'YeahMaybe', 'ChoicerVoicer', 'game', 'packs_voice')
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
USERS_DIR = os.path.join(os.path.dirname(__file__), 'data', 'users')
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PACKS_DIR, exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)

# Store global progress for jobs
creator_jobs = {}

import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_user(username):
    safe = secure_filename(username.lower())
    user_file = os.path.join(USERS_DIR, f'{safe}.json')
    if os.path.exists(user_file):
        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_user(user_data):
    safe = secure_filename(user_data['username'].lower())
    user_file = os.path.join(USERS_DIR, f'{safe}.json')
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

def extract_features(y, sr, n_mfcc=8):
    if librosa is None:
        return np.zeros(10), np.zeros(10, dtype=bool), np.zeros(10), np.zeros((n_mfcc, 10))
    f0, voiced_flag, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr)
    rms = librosa.feature.rms(y=y)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    return f0, voiced_flag, rms, mfcc

def normalize(arr):
    arr_min = np.nanmin(arr)
    arr_max = np.nanmax(arr)
    if arr_max == arr_min: return arr
    return (arr - arr_min) / (arr_max - arr_min)

def calculate_correlation(arr1, arr2):
    if np.std(arr1) == 0 or np.std(arr2) == 0:
        return 0.0
    return float(np.corrcoef(arr1, arr2)[0, 1])

def compute_score(ref_y, user_y, sr, n_mfcc=8):
    ref_f0, ref_voiced, ref_rms, ref_mfcc = extract_features(ref_y, sr, n_mfcc=n_mfcc)
    user_f0, user_voiced, user_rms, user_mfcc = extract_features(user_y, sr, n_mfcc=n_mfcc)
    
    min_len = min(len(ref_f0), len(user_f0))
    
    voiced_mask = ref_voiced[:min_len] & user_voiced[:min_len]
    if np.sum(voiced_mask) > 5:
        metric_a = calculate_correlation(ref_f0[:min_len][voiced_mask], user_f0[:min_len][voiced_mask])
    else:
        metric_a = 0.0
        
    metric_b = calculate_correlation(normalize(ref_rms[:min_len]), normalize(user_rms[:min_len]))
    
    mfcc_corrs = [calculate_correlation(ref_mfcc[i, :min_len], user_mfcc[i, :min_len]) for i in range(n_mfcc)]
    metric_c = float(np.mean(mfcc_corrs))
    
    # Make scoring more generous: 
    # boost correlations by taking the square root of positive values (curves them up)
    def boost(m):
        return max(0.0, m) ** 0.5
        
    boost_a = boost(metric_a)
    boost_b = boost(metric_b)
    boost_c = boost(metric_c)
    
    # Max possible from metrics = 100.
    # Weight: pitch=50, rhythm=30, timbre=20
    score = (50 * boost_a) + (30 * boost_b) + (20 * boost_c)
    unclamped = min(100, int(round(score)))
    
    return unclamped, metric_a, metric_b, metric_c

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        if not username or not password:
            return jsonify({'error': 'Usuario y contraseña requeridos'}), 400
        if len(username) < 3:
            return jsonify({'error': 'El nombre debe tener al menos 3 caracteres'}), 400
        if len(password) < 4:
            return jsonify({'error': 'La contraseña debe tener al menos 4 caracteres'}), 400
        existing = get_user(username)
        if existing:
            return jsonify({'error': 'Ese nombre de usuario ya existe'}), 409
        user_data = {
            'username': username,
            'password_hash': hash_password(password),
            'gemini_api_key': '',
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')
        }
        save_user(user_data)
        return jsonify({'success': True, 'username': username})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        if not username or not password:
            return jsonify({'error': 'Usuario y contraseña requeridos'}), 400
        user = get_user(username)
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        if user['password_hash'] != hash_password(password):
            return jsonify({'error': 'Contraseña incorrecta'}), 401
        return jsonify({'success': True, 'username': user['username']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')


# --- EDITOR INTEGRATION ---
@app.route('/editor')
def view_editor():
    return render_template('editor.html')

import subprocess
import uuid
import time
from werkzeug.utils import secure_filename

@app.route('/api/editor/load_media', methods=['POST'])
def api_editor_load_media():
    try:
        video_file = request.files.get('video')
        youtube_url = request.form.get('youtube_url')
        
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(UPLOADS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        if video_file and video_file.filename != '':
            video_ext = os.path.splitext(video_file.filename)[1]
            if not video_ext: video_ext = ".mp4"
            video_path = os.path.join(job_dir, f"source{video_ext}")
            video_file.save(video_path)
            
            return jsonify({
                "video_url": f"/uploads/{job_id}/source{video_ext}",
                "local_video_path": video_path
            })
            
        elif youtube_url:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            output_template = os.path.join(job_dir, "source.%(ext)s")
            cmd = [
                sys.executable, '-m', 'yt_dlp',
                '--ffmpeg-location', ffmpeg_exe,
                '-f', 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][vcodec^=avc1]/best',
                '--merge-output-format', 'mp4',
                '-o', output_template,
                youtube_url
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            video_path = os.path.join(job_dir, "source.mp4")
            if not os.path.exists(video_path):
                # Try finding any mp4
                for f in os.listdir(job_dir):
                    if f.endswith(".mp4"):
                        video_path = os.path.join(job_dir, f)
                        break
                        
            return jsonify({
                "video_url": f"/uploads/{job_id}/{os.path.basename(video_path)}",
                "local_video_path": video_path
            })
        else:
            return jsonify({"error": "No video provided"}), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/check_gemini_key', methods=['GET'])
def check_gemini_key():
    username = request.args.get('username', '').strip()
    if username:
        user = get_user(username)
        if user and user.get('gemini_api_key'):
            return jsonify({'has_key': True})
    key = ai_pipeline.get_gemini_api_key() if ai_pipeline else ''
    return jsonify({'has_key': bool(key)})

@app.route('/api/save_gemini_key', methods=['POST'])
def save_gemini_key():
    try:
        data = request.get_json() or {}
        key = data.get('api_key', '').strip()
        username = data.get('username', '').strip()
        if key:
            if ai_pipeline:
                ai_pipeline.set_gemini_api_key(key)
            if username:
                user = get_user(username)
                if user:
                    user['gemini_api_key'] = key
                    save_user(user)
            return jsonify({'success': True, 'message': 'Clave API guardada correctamente'})
        return jsonify({'error': 'Clave API inválida'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

CREATOR_PROJECTS = {}
PROJECTS_DIR = os.path.join(UPLOADS_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

@app.route('/api/creator/projects', methods=['GET'])
@app.route('/api/projects', methods=['GET', 'POST'])
def api_projects_handler():
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name') or data.get('pack_name') or 'Untitled'
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        proj_file = os.path.join(PROJECTS_DIR, f"{safe_name}.json")
        try:
            with open(proj_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print("Error writing project file:", e)
        CREATOR_PROJECTS[name] = data
        return jsonify({"success": True, "name": name})
    
    # GET: Load disk projects + job projects + memory projects
    all_projects = {}
    
    # 1. Scan PROJECTS_DIR
    if os.path.exists(PROJECTS_DIR):
        for f_name in os.listdir(PROJECTS_DIR):
            if f_name.endswith('.json'):
                try:
                    f_path = os.path.join(PROJECTS_DIR, f_name)
                    with open(f_path, 'r', encoding='utf-8') as f:
                        p_data = json.load(f)
                        p_name = p_data.get('pack_name') or p_data.get('title') or p_data.get('name') or f_name[:-5]
                        all_projects[p_name] = p_data
                except Exception as e:
                    print(f"Error reading project file {f_name}: {e}")
                    
    # 2. Scan uploads/*/project.json
    if os.path.exists(UPLOADS_DIR):
        for item in os.listdir(UPLOADS_DIR):
            job_dir = os.path.join(UPLOADS_DIR, item)
            p_json = os.path.join(job_dir, "project.json")
            if os.path.isdir(job_dir) and os.path.exists(p_json):
                try:
                    with open(p_json, 'r', encoding='utf-8') as f:
                        p_data = json.load(f)
                        p_name = p_data.get('pack_name') or p_data.get('title') or item
                        if p_name not in all_projects:
                            all_projects[p_name] = p_data
                except Exception as e:
                    print(f"Error reading job project.json {item}: {e}")
                    
    # 3. Add memory CREATOR_PROJECTS
    for name, p_data in CREATOR_PROJECTS.items():
        if name not in all_projects:
            all_projects[name] = p_data
            
    # Format list output for frontend
    project_list = []
    for p_name, p in all_projects.items():
        project_list.append({
            "job_id": p.get("job_id") or p.get("jobId") or p_name,
            "name": p_name,
            "pack_name": p.get("pack_name") or p.get("title") or p_name,
            "updated_at": p.get("updated_at") or time.time(),
            "lines": p.get("lines") or [],
            "video_url": p.get("video_url") or p.get("video") or "",
            "characters": p.get("characters") or []
        })
        
    project_list.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return jsonify({"projects": project_list, "success": True})

@app.route('/api/projects/<path:name>', methods=['GET', 'POST', 'DELETE'])
def api_project_detail(name):
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    proj_file = os.path.join(PROJECTS_DIR, f"{safe_name}.json")
    
    if request.method == 'DELETE':
        CREATOR_PROJECTS.pop(name, None)
        if os.path.exists(proj_file):
            try: os.remove(proj_file)
            except: pass
        # Also remove if job_id folder matches
        job_dir = os.path.join(UPLOADS_DIR, name)
        if os.path.exists(job_dir):
            try: shutil.rmtree(job_dir)
            except: pass
        return jsonify({"success": True})
    elif request.method == 'POST':
        data = request.get_json() or {}
        CREATOR_PROJECTS[name] = data
        try:
            with open(proj_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print("Error writing project file:", e)
        return jsonify({"success": True})
    else:
        if name in CREATOR_PROJECTS:
            return jsonify(CREATOR_PROJECTS[name])
        if os.path.exists(proj_file):
            try:
                with open(proj_file, 'r', encoding='utf-8') as f:
                    return jsonify(json.load(f))
            except: pass
        return jsonify({})

@app.route('/api/packs/<path:pack_name>', methods=['DELETE'])
def delete_pack(pack_name):
    try:
        from werkzeug.utils import secure_filename
        safe_name = os.path.basename(pack_name)
        pack_path = os.path.join(PACKS_DIR, safe_name)
        if os.path.exists(pack_path):
            shutil.rmtree(pack_path)
            return jsonify({"success": True, "message": f"Escena '{safe_name}' eliminada correctamente"})
        else:
            return jsonify({"error": "Escena no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<path:name>/export', methods=['POST'])
def api_project_export(name):
    proj = CREATOR_PROJECTS.get(name)
    if not proj: return jsonify({"error": "Project not found"}), 404
    video_url = proj.get('video')
    if not video_url: return jsonify({"error": "No video"}), 400
    
    if video_url.startswith('/uploads/'):
        parts = video_url.split('/uploads/')
        if len(parts) > 1:
            rel_path = parts[1]
            video_path = os.path.join(UPLOADS_DIR, os.path.normpath(rel_path))
        else:
            video_path = proj.get('local_video_path')
    else:
        video_path = proj.get('local_video_path')
        if not video_path: return jsonify({"error": "Cannot find local video"}), 400
        
    try:
        from ai_pipeline import build_pack
        
        lines = proj.get('lines', [])
        takes_data = []
        for l in lines:
            takes_data.append({
                "character": l.get("character", "Unknown"),
                "start_time": l.get("start", 0),
                "end_time": l.get("end", 0),
                "subtitle": l.get("caption", "")
            })
            
        build_pack(
            video_path=video_path,
            pack_id=proj.get('name'),
            pack_title=proj.get('title'),
            takes_data=takes_data,
            output_base_dir=PACKS_DIR,
            status_callback=None,
            lines=lines,
            vocals_path=proj.get('vocals_path'),
            no_vocals_path=proj.get('no_vocals_path'),
            authors=proj.get('authors', ''),
            readme=proj.get('readme', '')
        )
        return jsonify({"success": True, "pack": proj.get('name')})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/packs')
def get_packs():
    if not os.path.exists(PACKS_DIR):
        return jsonify({"error": "Directory not found"}), 404
        
    requested_user = request.args.get('user', '').strip().lower()
    
    packs = []
    for item in os.listdir(PACKS_DIR):
        item_path = os.path.join(PACKS_DIR, item)
        if os.path.isdir(item_path):
            owner_file = os.path.join(item_path, "_owner.json")
            pack_owner = None
            if os.path.exists(owner_file):
                try:
                    with open(owner_file, "r", encoding="utf-8") as f:
                        pack_owner = json.load(f).get("owner", "").strip().lower()
                except Exception:
                    pass
            
            # Personal Catalog Filtering:
            # If pack has an owner tag, only show it if the requested user is the owner!
            # Built-in default packs (no owner tag) show in everyone's catalog.
            if pack_owner and requested_user and pack_owner != requested_user:
                continue

            icon_url = None
            if os.path.exists(os.path.join(item_path, "icon.png")):
                icon_url = f"/media/{item}/icon.png"
            elif os.path.exists(os.path.join(item_path, "icon.jpg")):
                icon_url = f"/media/{item}/icon.jpg"
            else:
                for f in os.listdir(item_path):
                    if (f.endswith('.jpg') or f.endswith('.png')) and not f.startswith('_'):
                        icon_url = f"/media/{item}/{f}"
                        break
                        
            packs.append({
                "name": item,
                "icon_url": icon_url,
                "owner": pack_owner
            })
    return jsonify(packs)

@app.route('/api/packs/<pack_name>/clips')
def get_clips(pack_name):
    pack_path = os.path.join(PACKS_DIR, pack_name)
    if not os.path.exists(pack_path):
        return jsonify({"error": "Pack not found"}), 404
        
    files = os.listdir(pack_path)
    
    # Agrupar archivos por prefix (01_Erwin -> mp3, png, txt)
    clips_dict = {}
    for f in files:
        if f.startswith('_') or f == 'icon.png' or f.endswith('.ogv') or f.endswith('.mp4'): continue
        name, ext = os.path.splitext(f)
        if name not in clips_dict:
            clips_dict[name] = {"name": name, "audio": False, "audio_file": "", "image": False, "image_file": "", "text": False, "subtitle": "", "timestamp": 0.0}
            
        if ext in ['.mp3', '.wav']:
            clips_dict[name]["audio"] = True
            clips_dict[name]["audio_file"] = f
        elif ext in ['.png', '.jpg', '.jpeg']:
            clips_dict[name]["image"] = True
            clips_dict[name]["image_file"] = f
        elif ext in ['.txt', '.ini']:
            clips_dict[name]["text"] = True
            with open(os.path.join(pack_path, f), 'r', encoding='utf-8', errors='ignore') as txt_f:
                raw_text = txt_f.read().strip()
                import re
                match = re.search(r'caption\s*=\s*"?([^"\n]+)"?', raw_text)
                if match:
                    clips_dict[name]["subtitle"] = match.group(1).strip('\u201c\u201d')
                else:
                    clips_dict[name]["subtitle"] = raw_text
                
                ts_match = re.search(r'dub_timestamps=\[([0-9.]+)\]', raw_text)
                if ts_match:
                    clips_dict[name]["timestamp"] = float(ts_match.group(1))
                else:
                    clips_dict[name]["timestamp"] = 0.0
    # Solo devolver los que tengan audio
    valid_clips = [v for k, v in clips_dict.items() if v["audio"]]
    # Ordenar por nombre
    valid_clips.sort(key=lambda x: x['name'])
    
    total_duration = 0.0
    for clip in valid_clips:
        try:
            info = sf.info(os.path.join(pack_path, clip["audio_file"]))
            total_duration += info.duration
        except Exception:
            pass
            
    has_backing_track = any(f == '_backing_track.mp3' for f in files)
    
    return jsonify({
        "clips": valid_clips, 
        "has_backing_track": has_backing_track,
        "total_duration": total_duration
    })

MIME_MAP = {
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.ogg': 'audio/ogg',
    '.ogv': 'video/ogg',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.txt': 'text/plain',
    '.json': 'application/json',
}

@app.after_request
def add_no_transform(response):
    """Prevent Cloudflare from re-encoding binary responses (audio/video).
    Also ensures socket.io polling responses are never cached."""
    path = request.path if request else ''
    # Never cache socket.io handshake/polling — it contains session-specific data
    if path.startswith('/socket.io'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, no-transform'
        response.headers['Pragma'] = 'no-cache'
        return response
    # For all other responses, add no-transform so Cloudflare doesn't compress binaries
    cc = response.headers.get('Cache-Control', '')
    if 'no-transform' not in cc:
        new_cc = (cc + ', no-transform').lstrip(', ')
        response.headers['Cache-Control'] = new_cc
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.route('/media/<pack_name>/<filename>', methods=['GET', 'HEAD'])
def serve_media(pack_name, filename):
    pack_path = os.path.join(PACKS_DIR, pack_name)
    filepath = os.path.join(pack_path, filename)

    # Fallback search if exact filename not found (e.g. dub_video.mp4 vs dub_video.webm vs dub_video.ogv)
    if not os.path.exists(filepath):
        base_stem = os.path.splitext(filename)[0]
        for alt_ext in ['.mp4', '.webm', '.ogv', '.mkv', '.avi']:
            alt_path = os.path.join(pack_path, base_stem + alt_ext)
            if os.path.exists(alt_path):
                filepath = alt_path
                filename = os.path.basename(alt_path)
                break

    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found', 'path': filename}), 404

    ext = os.path.splitext(filename)[1].lower()
    mime = MIME_MAP.get(ext, 'application/octet-stream')
    file_size = os.path.getsize(filepath)

    # Range request support for HTML5 video/audio playback
    range_header = request.headers.get('Range', None)
    if range_header and mime.startswith(('video/', 'audio/')):
        try:
            byte_start, byte_end = 0, file_size - 1
            m = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if m:
                byte_start = int(m.group(1))
                if m.group(2):
                    byte_end = int(m.group(2))
            chunk_size = byte_end - byte_start + 1
            with open(filepath, 'rb') as f:
                f.seek(byte_start)
                data = f.read(chunk_size)
            resp = app.response_class(
                data,
                status=206,
                mimetype=mime,
                direct_passthrough=True
            )
            resp.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
            resp.headers['Accept-Ranges'] = 'bytes'
            resp.headers['Content-Length'] = str(chunk_size)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
        except Exception as e:
            print(f"[MEDIA RANGE] Error serving range request: {e}")

    directory = os.path.dirname(filepath)
    fname = os.path.basename(filepath)
    resp = send_from_directory(directory, fname, mimetype=mime, max_age=3600)
    resp.headers['Accept-Ranges'] = 'bytes'
    resp.headers['Content-Length'] = str(file_size)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/uploads/<path:filename>', methods=['GET', 'HEAD'])
def serve_upload(filename):
    import math
    clean_fn = filename.replace('\\', '/')
    filepath = os.path.join(UPLOADS_DIR, os.path.normpath(clean_fn))
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found', 'path': filename}), 404
    ext = os.path.splitext(os.path.basename(clean_fn))[1].lower()
    mime = MIME_MAP.get(ext, 'application/octet-stream')
    
    # For video/audio files, support HTTP Range requests so browsers can seek properly
    file_size = os.path.getsize(filepath)
    range_header = request.headers.get('Range', None)
    
    if range_header and mime.startswith(('video/', 'audio/')):
        try:
            byte_start, byte_end = 0, file_size - 1
            m = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if m:
                byte_start = int(m.group(1))
                if m.group(2):
                    byte_end = int(m.group(2))
            chunk_size = byte_end - byte_start + 1
            with open(filepath, 'rb') as f:
                f.seek(byte_start)
                data = f.read(chunk_size)
            resp = app.response_class(
                data,
                status=206,
                mimetype=mime,
                direct_passthrough=True
            )
            resp.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
            resp.headers['Accept-Ranges'] = 'bytes'
            resp.headers['Content-Length'] = str(chunk_size)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
        except Exception as e:
            print(f"[RANGE] Error serving range request: {e}")
    
    directory = os.path.dirname(filepath)
    fname = os.path.basename(filepath)
    resp = send_from_directory(directory, fname, mimetype=mime)
    resp.headers['Accept-Ranges'] = 'bytes'
    resp.headers['Content-Length'] = str(file_size)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp



@app.route('/api/score', methods=['POST'])
def score_audio():
    if 'user_audio' not in request.files or 'ref_audio_path' not in request.form:
        return jsonify({"error": "Missing data"}), 400
        
    user_audio_file = request.files['user_audio']
    ref_audio_rel = request.form['ref_audio_path'] # ex: Erwin's Speech/01_Erwin.mp3
    
    ref_path = os.path.join(PACKS_DIR, ref_audio_rel)
    if not os.path.exists(ref_path):
        return jsonify({"error": "Ref audio not found"}), 404
        
    if librosa is None or sf is None:
        import random
        return jsonify({"score": random.randint(75, 92), "metric_a": 0.8, "metric_b": 0.8, "metric_c": 0.8})
        
    try:
        # Load ref audio
        ref_y, sr = librosa.load(ref_path, sr=None, mono=True)
        
        # Read WAV from browser via soundfile memory
        user_audio_bytes = user_audio_file.read()
        user_y, user_sr = sf.read(io.BytesIO(user_audio_bytes))
        
        if len(user_y.shape) > 1:
            user_y = user_y.mean(axis=1) # to mono
            
        # Resample if needed
        if user_sr != sr:
            user_y = librosa.resample(user_y, orig_sr=user_sr, target_sr=sr)
            
        # Calculate
        score, a, b, c = compute_score(ref_y, user_y, sr)
        
        return jsonify({
            "score": score,
            "metric_a": a,
            "metric_b": b,
            "metric_c": c
        })
    except Exception as e:
        print(f"Error during scoring: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/score_bulk', methods=['POST'])
def score_audio_bulk():
    try:
        count = int(request.form.get('count', 0))
        if count == 0:
            return jsonify({"error": "No data"}), 400
            
        total_score = 0
        total_a = 0
        total_b = 0
        total_c = 0
        
        TARGET_SR = 16000  # Force 16kHz for ~3x faster scoring
        
        for i in range(count):
            user_audio_file = request.files.get(f'user_audio_{i}')
            ref_audio_rel = request.form.get(f'ref_audio_path_{i}')
            
            if not user_audio_file or not ref_audio_rel:
                continue
                
            ref_path = os.path.join(PACKS_DIR, ref_audio_rel)
            if not os.path.exists(ref_path):
                continue
                
            if librosa is None or sf is None:
                import random
                score = random.randint(78, 94)
                a, b, c = 0.82, 0.85, 0.80
            else:
                try:
                    ref_y, sr = librosa.load(ref_path, sr=TARGET_SR, mono=True)
                    user_audio_bytes = user_audio_file.read()
                    user_y, user_sr = sf.read(io.BytesIO(user_audio_bytes))
                    if len(user_y.shape) > 1:
                        user_y = user_y.mean(axis=1)
                    if user_sr != TARGET_SR:
                        user_y = librosa.resample(user_y, orig_sr=user_sr, target_sr=TARGET_SR)
                    score, a, b, c = compute_score(ref_y, user_y, TARGET_SR, n_mfcc=8)
                except Exception:
                    import random
                    score = random.randint(75, 90)
                    a, b, c = 0.8, 0.8, 0.8
            total_score += score
            total_a += a
            total_b += b
            total_c += c
            
            # Save user audio for competitive video generation if room is provided
            room = request.form.get('room')
            player_name = request.form.get('player_name')
            player_sid = request.form.get('player_sid')
            if room and player_name:
                p_slug = secure_filename(player_name) or 'player'
                player_dir = os.path.join(UPLOADS_DIR, f"room_{room}_player_{p_slug}")
                os.makedirs(player_dir, exist_ok=True)
                clip_name = os.path.splitext(os.path.basename(ref_audio_rel))[0]
                save_path = os.path.join(player_dir, f"{clip_name}.wav")
                with open(save_path, "wb") as f:
                    f.write(user_audio_bytes)
            
        avg_score = max(0, min(100, int(round(total_score / count))))
        
        # If competitive multiplayer, record score & spawn video mixing thread
        room = request.form.get('room')
        player_name = request.form.get('player_name')
        player_sid = request.form.get('player_sid')
        pack_name = request.form.get('pack_name')

        if room and room in rooms and player_name:
            comp_data = rooms[room].setdefault('comp_data', {
                'expected_players': list(set(p['name'] for p in rooms[room]['players'].values())),
                'sid_name_map': {},
                'scores': {},
                'result': None
            })
            comp_data.setdefault('scores', {})[player_name] = avg_score
            socketio.emit('comp_waiting_update', {
                'player_name': player_name,
                'player_sid': player_sid,
                'scored': True,
                'score': avg_score,
                'submitted_players': list(comp_data['scores'].keys())
            }, to=room)
            _check_and_trigger_competitive_game_over(room)

        if room and player_name and pack_name:
            p_slug = secure_filename(player_name) or 'player'
            player_dir = os.path.join(UPLOADS_DIR, f"room_{room}_player_{p_slug}")
            threading.Thread(target=mix_competitive_video_thread, args=(room, player_name, player_sid, pack_name, player_dir)).start()
        
        return jsonify({
            "score": avg_score,
            "metric_a": total_a / count,
            "metric_b": total_b / count,
            "metric_c": total_c / count
        })
    except Exception as e:
        print(f"Error during bulk scoring: {e}")
        return jsonify({"error": str(e)}), 500

def mix_competitive_video_thread(room, player_name, player_sid, pack_name, player_dir):
    vid_url = None
    FFMPEG_TIMEOUT = 120  # seconds — never hang longer than this
    try:
        print(f"\n[COMP] START mixing for {player_name} room={room}")
        pack_path = os.path.join(PACKS_DIR, pack_name)
        p_slug = secure_filename(player_name) or 'player'
        rel_player_dir = f"room_{room}_player_{p_slug}"
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        # --- Step 1: Read pack clips ---
        original_clips = {}
        for f in os.listdir(pack_path):
            if f.endswith('.txt'):
                name = os.path.splitext(f)[0]
                try:
                    with open(os.path.join(pack_path, f), 'r', encoding='utf-8', errors='ignore') as txt_f:
                        raw_text = txt_f.read().strip()
                        ts_match = re.search(r'dub_timestamps=\[([0-9.]+)\]', raw_text)
                        ts = float(ts_match.group(1)) if ts_match else 0.0
                        original_clips[name] = {'timestamp': ts}
                except Exception as e:
                    print(f"[COMP] Warning reading clip txt {f}: {e}")

        print(f"[COMP] {player_name}: found {len(original_clips)} clips in pack")

        # --- Step 2: Player's recorded WAVs ---
        final_clips = []
        for name, data in original_clips.items():
            uploaded_path = os.path.join(player_dir, f"{name}.wav")
            if os.path.exists(uploaded_path):
                final_clips.append((uploaded_path, data['timestamp']))

        print(f"[COMP] {player_name}: player recorded {len(final_clips)} / {len(original_clips)} clips")

        # --- Step 3: Assets ---
        backing_track = os.path.join(pack_path, "_backing_track.mp3")
        original_video = os.path.join(pack_path, "dub_video.mp4")
        if not os.path.exists(original_video):
            original_video = os.path.join(pack_path, "dub_video.ogv")
        has_video = os.path.exists(original_video)
        has_backing = os.path.exists(backing_track)
        print(f"[COMP] {player_name}: has_video={has_video}, has_backing={has_backing}")

        final_video = os.path.join(player_dir, f"final_{p_slug}.mp4")
        output_audio = os.path.join(player_dir, "final_mix.mp3")

        # --- Step 4: Mix audio ---
        if has_backing and final_clips:
            print(f"[COMP] {player_name}: mixing backing + {len(final_clips)} clips...")
            cmd = [ffmpeg_exe, "-y", "-i", backing_track]
            for c in final_clips:
                cmd.extend(["-i", c[0]])
            filter_parts = []
            for i, c in enumerate(final_clips):
                delay_ms = int(c[1] * 1000)
                filter_parts.append(f"[{i+1}]adelay={delay_ms}|{delay_ms}[s{i+1}];")
            filter_parts.append(
                "[0]" + "".join(f"[s{i+1}]" for i in range(len(final_clips))) +
                f"amix=inputs={len(final_clips)+1}:duration=first:normalize=0[aout]"
            )
            cmd.extend(["-filter_complex", "".join(filter_parts), "-map", "[aout]", output_audio])
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT)
                if result.returncode != 0:
                    err = result.stderr.decode('utf-8', errors='ignore')[-600:]
                    print(f"[COMP] {player_name}: audio mix FAILED (rc={result.returncode}): {err}")
                    import shutil
                    shutil.copy2(backing_track, output_audio)  # fallback
                else:
                    print(f"[COMP] {player_name}: audio mix OK")
            except subprocess.TimeoutExpired:
                print(f"[COMP] {player_name}: audio mix TIMED OUT after {FFMPEG_TIMEOUT}s, using backing track")
                import shutil
                shutil.copy2(backing_track, output_audio)

        elif has_backing and not final_clips:
            print(f"[COMP] {player_name}: no clips recorded, copying backing track")
            import shutil
            shutil.copy2(backing_track, output_audio)

        elif not has_backing and final_clips:
            # No backing track: mix clips with a short silence base
            print(f"[COMP] {player_name}: no backing track, generating silence base...")
            # Estimate duration from the latest clip timestamp + 30s padding
            max_ts = max(c[1] for c in final_clips)
            duration = int(max_ts) + 30
            silence = os.path.join(player_dir, "silence.mp3")
            try:
                subprocess.run(
                    [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                     "-t", str(duration), silence],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30
                )
            except subprocess.TimeoutExpired:
                print(f"[COMP] {player_name}: silence gen timed out")
            cmd = [ffmpeg_exe, "-y", "-i", silence]
            for c in final_clips:
                cmd.extend(["-i", c[0]])
            filter_parts = []
            for i, c in enumerate(final_clips):
                delay_ms = int(c[1] * 1000)
                filter_parts.append(f"[{i+1}]adelay={delay_ms}|{delay_ms}[s{i+1}];")
            filter_parts.append(
                "[0]" + "".join(f"[s{i+1}]" for i in range(len(final_clips))) +
                f"amix=inputs={len(final_clips)+1}:duration=first:normalize=0[aout]"
            )
            cmd.extend(["-filter_complex", "".join(filter_parts), "-map", "[aout]", output_audio])
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=FFMPEG_TIMEOUT)
            except subprocess.TimeoutExpired:
                print(f"[COMP] {player_name}: clip mix timed out")

        else:
            # Nothing at all — generate 5s silence
            print(f"[COMP] {player_name}: no backing, no clips — generating silence")
            try:
                subprocess.run(
                    [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                     "-t", "5", output_audio],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30
                )
            except subprocess.TimeoutExpired:
                print(f"[COMP] {player_name}: silence timed out")

        # --- Step 5: Combine with video ---
        print(f"[COMP] {player_name}: combining audio+video (has_video={has_video}, audio_exists={os.path.exists(output_audio)})...")
        if has_video and os.path.exists(output_audio):
            cmd2 = [ffmpeg_exe, "-y", "-i", original_video, "-i", output_audio,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-c:a", "aac",
                    "-map", "0:v?", "-map", "1:a?", "-shortest", final_video]
            try:
                result2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT)
                if result2.returncode == 0 and os.path.exists(final_video):
                    vid_url = f"/uploads/{rel_player_dir}/{os.path.basename(final_video)}"
                    print(f"[COMP] {player_name}: video OK -> {vid_url}")
                else:
                    err2 = result2.stderr.decode('utf-8', errors='ignore')[-600:]
                    print(f"[COMP] {player_name}: video combine FAILED (rc={result2.returncode}): {err2}")
                    vid_url = f"/uploads/{rel_player_dir}/final_mix.mp3"
            except subprocess.TimeoutExpired:
                print(f"[COMP] {player_name}: video combine TIMED OUT, serving audio only")
                vid_url = f"/uploads/{rel_player_dir}/final_mix.mp3"
        elif os.path.exists(output_audio):
            vid_url = f"/uploads/{rel_player_dir}/final_mix.mp3"
            print(f"[COMP] {player_name}: no video, serving audio only -> {vid_url}")
        else:
            print(f"[COMP] {player_name}: no output at all!")
            vid_url = None

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[COMP] EXCEPTION for {player_name}: {e}")
        vid_url = None

    finally:
        if room in rooms:
            if 'comp_videos' not in rooms[room]:
                rooms[room]['comp_videos'] = {}
            if vid_url:
                rooms[room]['comp_videos'][player_sid] = vid_url
                rooms[room]['comp_videos'][player_name] = vid_url

        payload = {
            'player_name': player_name,
            'player_sid': player_sid,
            'video_url': vid_url,
            'error': vid_url is None
        }
        socketio.emit('player_video_ready', payload, room=room)
        print(f"[COMP] EMITTED player_video_ready for {player_name}: {vid_url}")


# ==========================================
# MULTIPLAYER COOP MIXING
# ==========================================
import threading
try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None
import json

def mix_coop_video_thread(room, pack_name):
    try:
        print(f"Mixing coop video for room {room}...")
        room_data = rooms[room]['coop_data']
        pack_path = os.path.join(PACKS_DIR, pack_name)
        room_dir = os.path.join(UPLOADS_DIR, f"room_{room}")
        os.makedirs(room_dir, exist_ok=True)
        
        # 1. Identify which clips were uploaded vs which are original
        files = os.listdir(pack_path)
        original_clips = {}
        for f in files:
            if f.endswith('.txt'):
                name = os.path.splitext(f)[0]
                with open(os.path.join(pack_path, f), 'r', encoding='utf-8', errors='ignore') as txt_f:
                    raw_text = txt_f.read().strip()
                    ts_match = re.search(r'dub_timestamps=\[([0-9.]+)\]', raw_text)
                    ts = float(ts_match.group(1)) if ts_match else 0.0
                    
                    char_match = re.search(r'dub_characters=\["([^"]+)"\]', raw_text)
                    char_name = char_match.group(1) if char_match else name
                    
                    # Find matching original audio file (.mp3, .wav, .ogg)
                    orig_audio = None
                    for ext in ['.mp3', '.wav', '.ogg']:
                        candidate = os.path.join(pack_path, f"{name}{ext}")
                        if os.path.exists(candidate):
                            orig_audio = candidate
                            break
                            
                    original_clips[name.lower()] = {
                        'audio_path': orig_audio,
                        'timestamp': ts,
                        'character': char_name,
                        'name': name
                    }
        
        # 2. Determine final clips to use
        final_clips = []
        for norm_name, data in original_clips.items():
            uploaded_path = None
            # Search across all players' uploaded clips for a match
            for p_name, clips in room_data.get('player_clips', {}).items():
                for c in clips:
                    c_norm = c['name'].lower()
                    if c_norm == norm_name or norm_name in c_norm or c_norm in norm_name:
                        if os.path.exists(c['file']):
                            uploaded_path = c['file']
                            print(f"[COOP MIX] Player {p_name} provided audio for clip '{data['name']}' -> {uploaded_path}")
                            break
                if uploaded_path:
                    break
            
            if uploaded_path:
                final_clips.append((uploaded_path, data['timestamp']))
            elif data['audio_path'] and os.path.exists(data['audio_path']):
                print(f"[COOP MIX] Using ORIGINAL audio for clip '{data['name']}' -> {data['audio_path']}")
                final_clips.append((data['audio_path'], data['timestamp']))
            else:
                print(f"[COOP MIX] WARNING: No audio found for clip '{data['name']}'")
        
        # Base backing track
        backing_track = os.path.join(pack_path, "_backing_track.mp3")
        if not os.path.exists(backing_track):
            backing_track = None

        # Mix audios with ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        output_audio = os.path.join(room_dir, "final_mix.mp3")
        
        cmd = [ffmpeg_exe, "-y", "-i", backing_track]
        for c in final_clips:
            cmd.extend(["-i", c[0]])
            
        filter_parts = []
        for i, c in enumerate(final_clips):
            delay_ms = int(c[1] * 1000)
            filter_parts.append(f"[{i+1}]adelay={delay_ms}|{delay_ms}[s{i+1}];")
            
        # amix lowers volume depending on inputs, so we compensate with volume filter if needed
        # Or just use amix=inputs=...
        filter_parts.append(f"[0]" + "".join(f"[s{i+1}]" for i in range(len(final_clips))) + f"amix=inputs={len(final_clips)+1}:duration=first:normalize=0[aout]")
        filter_complex = "".join(filter_parts)
        
        cmd.extend(["-filter_complex", filter_complex, "-map", "[aout]", output_audio])
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Merge with video
        original_video = os.path.join(pack_path, "dub_video.mp4")
        if not os.path.exists(original_video):
            original_video = os.path.join(pack_path, "dub_video.ogv")
            
        final_video = os.path.join(room_dir, "final_video.mp4")
        if os.path.exists(original_video):
            cmd2 = [ffmpeg_exe, "-y", "-i", original_video, "-i", output_audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-c:a", "aac", "-map", "0:v?", "-map", "1:a?", "-shortest", final_video]
            subprocess.run(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            vid_url = f"/uploads/room_{room}/{os.path.basename(final_video)}"
        else:
            vid_url = f"/uploads/room_{room}/{os.path.basename(output_audio)}"
            
        print(f"Mixing complete. Video URL: {vid_url}")
        
        # Sort scores
        sorted_scores = sorted(room_data['scores'], key=lambda x: x['score'], reverse=True)
        
        # Store result in room_data for HTTP polling fallback
        room_data['result'] = {
            'video_url': vid_url,
            'ranking': sorted_scores
        }
        room_data['status'] = 'done'
        
        # Broadcast finished event
        socketio.emit('coop_game_over', room_data['result'], to=room)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        if room in rooms and 'coop_data' in rooms[room]:
            rooms[room]['coop_data']['status'] = 'error'
            rooms[room]['coop_data']['error'] = str(e)
        socketio.emit('coop_game_over', {'error': str(e)}, to=room)


@app.route('/api/coop_status/<room>', methods=['GET'])
def coop_status(room):
    room = room.upper()
    if room not in rooms or 'coop_data' not in rooms[room]:
        return jsonify({"status": "not_found"}), 404
        
    cdata = rooms[room]['coop_data']
    if cdata.get('status') == 'done' and 'result' in cdata:
        return jsonify({
            "status": "done",
            "video_url": cdata['result']['video_url'],
            "ranking": cdata['result']['ranking']
        })
    elif cdata.get('status') == 'error':
        return jsonify({"status": "error", "error": cdata.get('error', 'Error al mezclar')})
    else:
        expected = cdata.get('expected_players', [])
        p_status = cdata.get('player_status', {})
        players_list = [{'name': p, 'status': p_status.get(p, 'recording')} for p in expected]
        return jsonify({
            "status": "processing",
            "finished": cdata.get('finished_count', 0),
            "total": cdata.get('total_players', 0),
            "players": players_list
        })


@app.route('/api/competitive_status/<room>', methods=['GET'])
def competitive_status(room):
    room = room.upper()
    if room not in rooms:
        return jsonify({"status": "not_found"}), 404

    comp_data = rooms[room].get('comp_data', {})
    result = comp_data.get('result')
    if result:
        return jsonify({"status": "done", "scores": result["scores"], "mode": result["mode"]})

    if _check_and_trigger_competitive_game_over(room):
        result = comp_data.get('result')
        return jsonify({"status": "done", "scores": result["scores"], "mode": result["mode"]})

    expected = comp_data.get('expected_players', [])
    scores_dict = comp_data.get('scores', {})
    submitted = list(scores_dict.keys())
    live_players = [p["name"] for p in rooms[room]["players"].values()]

    return jsonify({
        "status": "waiting",
        "submitted": submitted,
        "scores": scores_dict,
        "expected": expected,
        "total": len(expected) if len(expected) > 0 else len(live_players),
        "finished": len(submitted)
    })


@app.route('/api/force_advance/<room>', methods=['POST'])
def force_advance(room):
    """Host endpoint to force game progression when some players are stuck."""
    room = room.upper()
    if room not in rooms:
        return jsonify({"error": "Room not found"}), 404

    r = rooms[room]
    mode = r.get('mode', 'cooperativo')
    pack_name = r.get('pack_name', '')

    if mode == 'cooperativo':
        cd = r.get('coop_data', {})
        if not cd:
            return jsonify({"error": "No coop game in progress"}), 400
        finished = [p for p in cd.get('expected_players', []) if cd.get('player_status', {}).get(p) == 'finished']
        if not finished:
            return jsonify({"error": "No players have finished yet"}), 400
        # Trim expected to only finished players and trigger mix
        cd['expected_players'] = finished
        cd['total_players'] = len(finished)
        cd['finished_count'] = len(finished)
        socketio.emit('coop_waiting_update', {
            'finished': len(finished), 'total': len(finished),
            'players': [{'name': p, 'status': 'finished'} for p in finished]
        }, to=room)
        socketio.emit('coop_processing', {'message': 'Host ha forzado el avance. Mezclando con jugadores disponibles...'}, to=room)
        if pack_name:
            t = threading.Thread(target=mix_coop_video_thread, args=(room, pack_name))
            t.start()
        return jsonify({"ok": True})
    else:  # competitivo
        cd = r.get('comp_data', {})
        if not cd:
            return jsonify({"error": "No competitive game in progress"}), 400
        expected_players = cd.get('expected_players', [])
        if not expected_players:
            expected_players = list(cd.get('scores', {}).keys())
        if not expected_players:
            return jsonify({"error": "No players in game"}), 400
        frozen_map = cd.get('sid_name_map', {})
        name_to_sid = {v: k for k, v in frozen_map.items()}
        scores_list = []
        for name in expected_players:
            s = cd.get('scores', {}).get(name, 0)
            sid = name_to_sid.get(name) or next((k for k, p in r['players'].items() if p['name'] == name), name)
            scores_list.append({'name': name, 'score': s, 'sid': sid})
        scores_list.sort(key=lambda x: x['score'], reverse=True)
        cd['result'] = {'scores': scores_list, 'mode': mode}
        socketio.emit('competitive_game_over', cd['result'], to=room)
        return jsonify({"ok": True})




@app.route('/api/singleplayer_mix', methods=['POST'])
def singleplayer_mix():
    """Generates an MP4 video of the singleplayer dubbing session super fast using FFmpeg."""
    try:
        pack_name = request.form.get('pack_name')
        count = int(request.form.get('count', 0))
        if not pack_name:
            return jsonify({"error": "Falta el nombre de la escena"}), 400

        pack_path = os.path.join(PACKS_DIR, pack_name)
        if not os.path.exists(pack_path):
            return jsonify({"error": "Escena no encontrada"}), 404

        job_id = str(uuid.uuid4())
        job_dir = os.path.join(UPLOADS_DIR, f"singleplayer_{job_id[:8]}")
        os.makedirs(job_dir, exist_ok=True)

        # 1. Identify all scene clips in order
        files = os.listdir(pack_path)
        original_clips = {}
        for f in files:
            if f.endswith('.txt'):
                name = os.path.splitext(f)[0]
                with open(os.path.join(pack_path, f), 'r', encoding='utf-8', errors='ignore') as txt_f:
                    raw_text = txt_f.read().strip()
                    ts_match = re.search(r'dub_timestamps=\[([0-9.]+)\]', raw_text)
                    ts = float(ts_match.group(1)) if ts_match else 0.0

                    orig_audio = None
                    for ext in ['.mp3', '.wav', '.ogg']:
                        candidate = os.path.join(pack_path, f"{name}{ext}")
                        if os.path.exists(candidate):
                            orig_audio = candidate
                            break

                    original_clips[name.lower()] = {
                        'audio_path': orig_audio,
                        'timestamp': ts,
                        'name': name
                    }

        # 2. Save user uploaded audio files
        user_clips_map = {}
        for i in range(count):
            user_audio_file = request.files.get(f'user_audio_{i}')
            ref_audio_rel = request.form.get(f'ref_audio_path_{i}')
            if not user_audio_file or not ref_audio_rel:
                continue

            clip_name = os.path.splitext(os.path.basename(ref_audio_rel))[0]
            save_path = os.path.join(job_dir, f"user_{clip_name}.wav")
            with open(save_path, "wb") as f:
                f.write(user_audio_file.read())
            user_clips_map[clip_name.lower()] = save_path

        # 3. Determine final clips to use
        final_clips = []
        for norm_name, data in original_clips.items():
            if norm_name in user_clips_map:
                final_clips.append((user_clips_map[norm_name], data['timestamp']))
            elif data['audio_path'] and os.path.exists(data['audio_path']):
                final_clips.append((data['audio_path'], data['timestamp']))

        # 4. FFmpeg mix
        backing_track = os.path.join(pack_path, "_backing_track.mp3")
        if not os.path.exists(backing_track):
            backing_track = None

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        output_audio = os.path.join(job_dir, "final_mix.mp3")

        cmd = [ffmpeg_exe, "-y"]
        if backing_track:
            cmd.extend(["-i", backing_track])
            has_backing = True
        else:
            has_backing = False

        for c in final_clips:
            cmd.extend(["-i", c[0]])

        filter_parts = []
        offset = 1 if has_backing else 0
        for i, c in enumerate(final_clips):
            delay_ms = int(c[1] * 1000)
            filter_parts.append(f"[{i+offset}]adelay={delay_ms}|{delay_ms}[s{i}];")

        inputs_str = ("[0]" if has_backing else "") + "".join(f"[s{i}]" for i in range(len(final_clips)))
        filter_parts.append(f"{inputs_str}amix=inputs={len(final_clips)+(1 if has_backing else 0)}:duration=first:normalize=0[aout]")
        filter_complex = "".join(filter_parts)

        cmd.extend(["-filter_complex", filter_complex, "-map", "[aout]", output_audio])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 5. Merge audio with video
        original_video = os.path.join(pack_path, "dub_video.mp4")
        if not os.path.exists(original_video):
            original_video = os.path.join(pack_path, "dub_video.ogv")

        final_video = os.path.join(job_dir, "final_video.mp4")
        if os.path.exists(original_video):
            cmd2 = [ffmpeg_exe, "-y", "-i", original_video, "-i", output_audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-c:a", "aac", "-map", "0:v?", "-map", "1:a?", "-shortest", final_video]
            subprocess.run(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            vid_url = f"/uploads/singleplayer_{job_id[:8]}/final_video.mp4"
        else:
            vid_url = f"/uploads/singleplayer_{job_id[:8]}/final_mix.mp3"

        download_filename = f"GrindTheClip_{pack_name}_Doblaje.mp4"
        return jsonify({
            "success": True,
            "video_url": vid_url,
            "filename": download_filename
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/coop_submit', methods=['POST'])
def coop_submit():
    try:
        room = request.form.get('room')
        player_name = request.form.get('player_name')
        pack_name = request.form.get('pack_name')
        count = int(request.form.get('count', 0))
        
        if not room or room not in rooms or not player_name:
            return jsonify({"error": "Invalid room or player"}), 400

        # coop_data should already be initialized at game start; fallback just in case
        if 'coop_data' not in rooms[room]:
            names = list(set(p["name"] for p in rooms[room]["players"].values()))
            if "characters" in rooms[room]:
                names = list(set(names).union(set(rooms[room]["characters"].values())))
            rooms[room]['coop_data'] = {
                'scores': [],
                'player_clips': {},
                'player_status': {},
                'expected_players': names,
                'finished_count': 0,
                'total_players': len(names),
            }

        room_data = rooms[room]['coop_data']
        room_dir = os.path.join(UPLOADS_DIR, f"room_{room}")
        os.makedirs(room_dir, exist_ok=True)
        
        player_clips = []
        total_score = 0
        TARGET_SR = 16000
        valid_clips_count = 0
        
        for i in range(count):
            user_audio_file = request.files.get(f'user_audio_{i}')
            ref_audio_rel = request.form.get(f'ref_audio_path_{i}')
            char_name = request.form.get(f'char_name_{i}', 'Unknown')
            
            if not user_audio_file or not ref_audio_rel:
                continue
                
            ref_path = os.path.join(PACKS_DIR, ref_audio_rel)
            if not os.path.exists(ref_path):
                continue
                
            # Score it
            ref_y, sr = librosa.load(ref_path, sr=TARGET_SR, mono=True)
            user_audio_bytes = user_audio_file.read()
            user_y, user_sr = sf.read(io.BytesIO(user_audio_bytes))
            if len(user_y.shape) > 1: user_y = user_y.mean(axis=1)
            if user_sr != TARGET_SR: user_y = librosa.resample(user_y, orig_sr=user_sr, target_sr=TARGET_SR)
            
            score, _, _, _ = compute_score(ref_y, user_y, TARGET_SR, n_mfcc=8)
            total_score += score
            valid_clips_count += 1
            
            # Save file
            clip_name = os.path.splitext(os.path.basename(ref_audio_rel))[0]
            save_path = os.path.join(room_dir, f"{player_name}_{clip_name}.wav")
            with open(save_path, "wb") as f:
                f.write(user_audio_bytes)
                
            player_clips.append({
                'name': clip_name,
                'character': char_name,
                'file': save_path
            })
            
        avg_score = int(round(total_score / valid_clips_count)) if valid_clips_count > 0 else 0
        
        room_data['player_clips'][player_name] = player_clips
        # Replace or append score
        existing_score = next((s for s in room_data['scores'] if s['name'] == player_name), None)
        if existing_score:
            existing_score['score'] = avg_score
        else:
            room_data['scores'].append({'name': player_name, 'score': avg_score})
            
        room_data['player_status'][player_name] = 'finished'
        
        # Calculate actual finished count based on unique expected names
        expected_players = room_data.get('expected_players', [])
        if not expected_players:
            expected_players = list(set(p["name"] for p in rooms[room]["players"].values()))
            if "characters" in rooms[room]:
                expected_players = list(set(expected_players).union(set(rooms[room]["characters"].values())))
            room_data['expected_players'] = expected_players
            room_data['total_players'] = len(expected_players)

        total_players = len(expected_players)
        finished_players = [p for p in expected_players if room_data['player_status'].get(p) == 'finished']
        finished_count = len(finished_players)
        room_data['finished_count'] = finished_count

        # Build status list of all expected players
        players_status_list = []
        for p_name in expected_players:
            st = room_data['player_status'].get(p_name, 'recording')
            players_status_list.append({'name': p_name, 'status': st})

        # Broadcast real-time waiting update to all clients in room
        socketio.emit('coop_waiting_update', {
            'finished': finished_count,
            'total': total_players,
            'players': players_status_list,
            'last_finished': player_name
        }, room=room)

        print(f"[{room}] Coop: {finished_count}/{total_players} finished. Statuses: {room_data['player_status']}")

        # Only trigger mix when ALL expected players have submitted
        if finished_count >= total_players and total_players > 0:
            print(f"[{room}] All {total_players} players ({expected_players}) finished. Starting mix...")
            socketio.emit('coop_processing', {'message': 'Todos los jugadores han terminado. Mezclando escena grupal...'}, room=room)
            t = threading.Thread(target=mix_coop_video_thread, args=(room, pack_name))
            t.start()
            
        return jsonify({"success": True})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==========================================
# PACK STUDIO (AI Pipeline) Endpoints
# ==========================================

@app.route('/api/creator/build', methods=['POST'])
def creator_build():
    try:
        pack_id = request.form.get('pack_id')
        pack_title = request.form.get('pack_title')
        takes_json = request.form.get('takes')
        video_file = request.files.get('video')
        
        if not pack_id or not pack_title or not takes_json or not video_file:
            return jsonify({"error": "Faltan datos"}), 400
            
        takes_data = json.loads(takes_json)
        
        job_id = str(uuid.uuid4())
        creator_jobs[job_id] = {"status": "Subiendo vídeo...", "progress": 10, "error": False}
        
        # Save video
        video_ext = os.path.splitext(video_file.filename)[1]
        video_path = os.path.join(UPLOADS_DIR, f"{job_id}{video_ext}")
        video_file.save(video_path)
        
        # Start background processing
        t = threading.Thread(target=process_build_job, args=(job_id, video_path, pack_id, pack_title, takes_data))
        t.start()
        
        return jsonify({"job_id": job_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/creator/auto_build', methods=['POST'])
def creator_auto_build():
    try:
        pack_name = request.form.get('pack_name', 'auto_pack')
        youtube_url = request.form.get('youtube_url', '').strip()
        video_file = request.files.get('video')
        
        if not video_file and not youtube_url:
            return jsonify({"error": "Se necesita un vídeo o una URL de YouTube"}), 400
        
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(UPLOADS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        creator_jobs[job_id] = {
            "status": "Preparando...",
            "progress": 5,
            "error": False,
            "result": None,
            "pack_name": pack_name,
            "video_path": None,
            "job_dir": job_dir,
        }
        
        if video_file:
            # Save uploaded video
            video_ext = os.path.splitext(video_file.filename)[1] or '.mp4'
            video_path = os.path.join(job_dir, f"source{video_ext}")
            video_file.save(video_path)
            creator_jobs[job_id]["video_path"] = video_path
            creator_jobs[job_id]["status"] = "Vídeo subido"
            creator_jobs[job_id]["progress"] = 10
        
        # Start background processing
        t = threading.Thread(
            target=process_auto_build_job,
            args=(job_id, youtube_url)
        )
        t.start()
        
        return jsonify({"job_id": job_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/creator/result/<job_id>', methods=['GET'])
def creator_result(job_id):
    if job_id not in creator_jobs:
        return jsonify({"error": "Job no encontrado"}), 404
    
    job = creator_jobs[job_id]
    response = {
        "status": job["status"],
        "progress": job["progress"],
        "error": job.get("error", False),
    }
    
    if job.get("result") is not None:
        response["result"] = job["result"]
        if job.get("video_path"):
            rel_path = os.path.relpath(job["video_path"], UPLOADS_DIR).replace('\\', '/')
            response["video_url"] = f"/uploads/{rel_path}"
    
    return jsonify(response)

@app.route('/api/creator/export', methods=['POST'])
def creator_export():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        job_id = data.get('job_id')
        pack_name = data.get('pack_name')
        lines = data.get('lines', [])
        characters = data.get('characters', [])
        
        if not job_id or not pack_name or not lines:
            return jsonify({"error": "Faltan datos (job_id, pack_name, lines)"}), 400
        
        if job_id not in creator_jobs:
            return jsonify({"error": "Job no encontrado"}), 404
        
        job = creator_jobs[job_id]
        result = job.get("result")
        if not result:
            return jsonify({"error": "El job aún no tiene resultados"}), 400
        
        video_path = job.get("video_path")
        if not video_path or not os.path.exists(video_path):
            return jsonify({"error": "Vídeo original no encontrado"}), 404
        
        vocals_path = result.get("vocals_path")
        no_vocals_path = result.get("no_vocals_path")
        
        # Run build_pack in pre-processed mode
        ai_pipeline.build_pack(
            video_path=video_path,
            pack_id=pack_name,
            pack_title=pack_name,
            takes_data=None,
            output_base_dir=PACKS_DIR,
            lines=lines,
            vocals_path=vocals_path,
            no_vocals_path=no_vocals_path,
        )
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error during export: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/creator/status/<job_id>', methods=['GET'])
def creator_status(job_id):
    if job_id not in creator_jobs:
        return jsonify({"error": "Job no encontrado"}), 404
    return jsonify(creator_jobs[job_id])

def process_build_job(job_id, video_path, pack_id, pack_title, takes_data):
    try:
        creator_jobs[job_id]['status'] = "Preparando carpetas..."
        creator_jobs[job_id]['progress'] = 20
        
        ai_pipeline.build_pack(
            video_path=video_path,
            pack_id=pack_id,
            pack_title=pack_title,
            takes_data=takes_data,
            output_base_dir=PACKS_DIR,
            status_callback=lambda status, prog: update_job_status(job_id, status, prog)
        )
        
        creator_jobs[job_id]['status'] = "Completado"
        creator_jobs[job_id]['progress'] = 100
    except Exception as e:
        creator_jobs[job_id]['status'] = str(e)
        creator_jobs[job_id]['error'] = True

def process_auto_build_job(job_id, youtube_url):
    try:
        job = creator_jobs[job_id]
        job_dir = job["job_dir"]
        
        # Step 0: Download from YouTube if needed
        if youtube_url:
            job["status"] = "Descargando vídeo de YouTube..."
            job["progress"] = 10
            video_path = ai_pipeline.download_youtube(youtube_url, job_dir)
            job["video_path"] = video_path
        else:
            video_path = job["video_path"]
        
        if not video_path or not os.path.exists(video_path):
            raise RuntimeError("No se encontró el archivo de vídeo")
        
        # Run the full auto pipeline
        result = ai_pipeline.auto_process(
            video_path=video_path,
            temp_dir=job_dir,
            status_callback=lambda status, prog: update_job_status(job_id, status, prog)
        )
        
        job["result"] = result
        
        # Save project.json automatically
        project_file = os.path.join(job_dir, "project.json")
        try:
            rel_path = os.path.relpath(video_path, UPLOADS_DIR).replace('\\', '/')
            video_url = f"/uploads/{rel_path}"
        except:
            video_url = ""
            
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump({
                "job_id": job_id,
                "pack_name": job.get("pack_name", "Automático"),
                "lines": result.get("lines", []),
                "characters": result.get("characters", []),
                "video_url": video_url,
                "updated_at": time.time()
            }, f, ensure_ascii=False)
            
        job["status"] = "Completado"
        job["progress"] = 100
    except Exception as e:
        creator_jobs[job_id]["status"] = str(e)
        creator_jobs[job_id]["error"] = True
        print(f"[auto_build] Error for job {job_id}: {e}")
        
def update_job_status(job_id, status, progress):
    if job_id in creator_jobs:
        creator_jobs[job_id]['status'] = status
        creator_jobs[job_id]['progress'] = progress

# ==========================================
# MULTIPLAYER LOBBY ENDPOINTS
# ==========================================

import random
import string


def get_pack_character_count(pack_name):
    if not pack_name:
        return 4
    pack_path = os.path.join(PACKS_DIR, pack_name)
    if not os.path.exists(pack_path):
        return 4
    for json_file in ['characters.json', 'manifest.json', 'project.json']:
        j_path = os.path.join(pack_path, json_file)
        if os.path.exists(j_path):
            try:
                with open(j_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    chars = data.get('characters', [])
                    if isinstance(chars, list) and len(chars) > 0:
                        return len(chars)
            except Exception:
                pass
    chars = set()
    for f in os.listdir(pack_path):
        if f.endswith('.txt') and not f.startswith('_'):
            try:
                with open(os.path.join(pack_path, f), 'r', encoding='utf-8', errors='ignore') as txt_f:
                    raw = txt_f.read()
                    char_match = re.search(r'dub_characters=\["([^"]+)"\]', raw)
                    if char_match:
                        chars.add(char_match.group(1).strip())
            except Exception:
                pass
    if len(chars) > 0:
        return len(chars)
    return 4

def get_room_state(room):
    max_p = rooms[room].get("max_players") or get_pack_character_count(rooms[room]["pack_name"])
    return {
        "pack_name": rooms[room]["pack_name"],
        "mode": rooms[room].get("mode", "competitivo"),
        "scoring_mode": rooms[room].get("scoring_mode", "ia"),
        "score_sensitivity": rooms[room].get("score_sensitivity", "normal"),
        "playback_mode": rooms[room].get("playback_mode", "premiere"),
        "players": list(rooms[room]["players"].values()),
        "characters": rooms[room].get("characters", {}),
        "host_name": rooms[room].get("host_name"),
        "max_players": max_p
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
    max_p = get_pack_character_count(pack_name)
    rooms[code] = {
        "pack_name": pack_name,
        "mode": data.get("mode", "competitivo"),
        "scoring_mode": data.get("scoring_mode", "ia"),
        "score_sensitivity": data.get("score_sensitivity", "normal"),
        "playback_mode": data.get("playback_mode", "premiere"),
        "players": {},
        "characters": {}, # char_name -> sid
        "state": "waiting",
        "votes": {},
        "max_players": max_p
    }
    return jsonify({"room_code": code, "pack_name": pack_name, "max_players": max_p})

@app.route('/api/check_room/<code>', methods=['GET'])
def check_room(code):
    code = code.upper()
    if code not in rooms:
        return jsonify({"valid": False, "reason": "Sala no encontrada"})
    if rooms[code]['state'] != 'waiting':
        return jsonify({"valid": False, "reason": "La partida ya ha empezado"})
    max_p = get_pack_character_count(rooms[code]["pack_name"])
    return jsonify({"valid": True, "pack_name": rooms[code]['pack_name'], "mode": rooms[code].get("mode", "competitivo"), "max_players": max_p})

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

@app.route('/api/upload_single_take', methods=['POST'])
def upload_single_take():
    room = request.form.get('room', '').upper()
    sid = request.form.get('sid')
    player_name = request.form.get('player_name', '')
    clip_name = request.form.get('clip_name', '')
    file = request.files.get('audio')
    
    if not file or not clip_name:
        return jsonify({"error": "Missing audio or clip_name"}), 400
        
    upload_subdir = f"room_{room}" if room else "singleplayer_temp"
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], upload_subdir)
    os.makedirs(target_dir, exist_ok=True)
    
    safe_clip = os.path.basename(clip_name)
    save_filename = f"{sid or 'local'}_{safe_clip}"
    if not save_filename.endswith('.webm') and not save_filename.endswith('.wav'):
        save_filename += '.webm'
        
    filepath = os.path.join(target_dir, save_filename)
    file.save(filepath)
    
    url = f"/uploads/{upload_subdir}/{save_filename}"
    
    if room and room in rooms:
        if 'coop_data' in rooms[room]:
            p_clips = rooms[room]['coop_data'].setdefault('player_clips', {}).setdefault(player_name or sid, [])
            existing = next((c for c in p_clips if c.get('name') == clip_name), None)
            if existing:
                existing['file'] = filepath
                existing['url'] = url
            else:
                p_clips.append({'name': clip_name, 'file': filepath, 'url': url})
        
        socketio.emit('take_uploaded_progress', {
            'player_name': player_name,
            'clip_name': clip_name,
            'url': url
        }, to=room)
        
    return jsonify({"success": True, "url": url, "filename": save_filename})

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

@socketio.on('join')
def on_join(data):
    room = data.get('room', '').upper()
    name = str(data.get('name', 'Jugador')).strip()[:32] or 'Jugador'
    
    if not room or room not in rooms:
        emit('error', {'message': 'Sala no encontrada'})
        return

    comp_data = rooms[room].get('comp_data', {})
    coop_data = rooms[room].get('coop_data', {})
    expected_players = comp_data.get('expected_players', []) or coop_data.get('expected_players', [])
    existing_player = (name in expected_players) or (request.sid in rooms[room]['players']) or any(p.get('name') == name for p in rooms[room]['players'].values())
        
    if rooms[room]['state'] != 'waiting' and not existing_player:
        emit('error', {'message': 'La partida ya ha empezado'})
        return
        
    join_room(room)
    
    rooms[room]["players"][request.sid] = {
        "name": name,
        "ready": True if rooms[room]['state'] == 'playing' else False,
        "score": comp_data.get('scores', {}).get(name),
        "sid": request.sid
    }

    if comp_data:
        comp_data.setdefault('sid_name_map', {})[request.sid] = name

    if rooms[room].get('host_name') == name or not rooms[room].get('host_sid'):
        rooms[room]['host_sid'] = request.sid
        rooms[room]['host_name'] = name
    
    # Broadcast to room that someone joined
    emit('room_update', get_room_state(room), to=room)
    print(f"[{room}] {name} joined/reconnected (sid: {request.sid}, state: {rooms[room]['state']}).")
    print(f"[{room}] {name} joined.")

@socketio.on('toggle_ready')
def on_toggle_ready(data):
    room = data.get('room', '').upper()
    is_ready = data.get('ready', True)
    if room in rooms and request.sid in rooms[room]["players"]:
        player_name = rooms[room]["players"][request.sid]["name"]
        mode = rooms[room].get("mode", "competitivo")

        # In cooperative mode, player must have claimed at least 1 character to be ready
        if mode == 'cooperativo' and is_ready:
            claimed_by_player = [c for c, p in rooms[room].get("characters", {}).items() if p == player_name]
            if not claimed_by_player:
                print(f"[{room}] {player_name} tried to set ready without claiming a character!")
                rooms[room]["players"][request.sid]["ready"] = False
                emit('room_update', get_room_state(room), to=room)
                return

        rooms[room]["players"][request.sid]["ready"] = is_ready
        
        emit('room_update', get_room_state(room), to=room)
        
        print(f"[{room}] {rooms[room]['players'][request.sid]['name']} is ready.")
        
        # Check if everyone is ready
        all_ready = all(p["ready"] for p in rooms[room]["players"].values())
        if all_ready and len(rooms[room]["players"]) > 0:
            total_players = len(rooms[room]["players"])
            pack_name = rooms[room].get("pack_name", "")
            num_chars = get_pack_character_count(pack_name)

            if mode == 'cooperativo' and total_players > num_chars:
                print(f"[{room}] Coop start blocked: {total_players} players in room, but scene has {num_chars} characters.")
                for p in rooms[room]["players"].values():
                    p["ready"] = False
                socketio.emit('mode_capacity_error', {
                    'message': f'⚠️ En Modo Cooperativo sólo pueden participar {num_chars} personas a la vez (tantos como personajes hay en la escena). Hay {total_players} personas en la sala.\n\n👉 Cambiad a Modo Competitivo para jugar todos juntos sin ningún límite.'
                }, to=room)
                emit('room_update', get_room_state(room), to=room)
                return

            print(f"[{room}] Everyone is ready! Starting game in 3 seconds...")
            rooms[room]['state'] = 'playing'
            rooms[room]['votes'] = {}

            # Freeze unique player names for BOTH coop and competitive modes
            player_names = list(set(p["name"] for p in rooms[room]["players"].values()))
            sid_name_map = {sid: p["name"] for sid, p in rooms[room]["players"].items()}

            # -- Coop: freeze by player name only (NOT character names, those are roles not players) --
            coop_names = list(player_names)  # Only actual connected players
            rooms[room]['coop_data'] = {
                'scores': [],
                'player_clips': {},
                'player_status': {},
                'expected_players': coop_names,
                'finished_count': 0,
                'total_players': len(coop_names),
            }

            # -- Competitive: freeze expected player names and sid->name map --
            rooms[room]['comp_data'] = {
                'expected_players': player_names,       # list of unique names
                'sid_name_map': sid_name_map,           # frozen sid->name at game start
                'scores': {},                           # name -> score
                'result': None,                        # set to scores list when all done
            }

            print(f"[{room}] Game data initialized with {len(player_names)} players: {player_names}")
            emit('game_start_countdown', {"seconds": 3, "pack_name": rooms[room]["pack_name"]}, to=room)


@socketio.on('change_mode')
def on_change_mode(data):
    room = data.get('room', '').upper()
    mode = data.get('mode', 'competitivo')
    if room in rooms:
        rooms[room]['mode'] = mode
        emit('room_update', get_room_state(room), to=room)

@socketio.on('change_scoring_mode')
def on_change_scoring_mode(data):
    room = data.get('room', '').upper()
    scoring_mode = data.get('scoring_mode', 'ia')
    if room in rooms:
        rooms[room]['scoring_mode'] = scoring_mode
        emit('room_update', get_room_state(room), to=room)

@socketio.on('change_score_sensitivity')
def on_change_score_sensitivity(data):
    room = data.get('room', '').upper()
    sensitivity = data.get('sensitivity', 'normal')
    if room in rooms:
        rooms[room]['score_sensitivity'] = sensitivity
        emit('room_update', get_room_state(room), to=room)

@socketio.on('change_playback_mode')
def on_change_playback_mode(data):
    room = data.get('room', '').upper()
    pb_mode = data.get('playback_mode', 'premiere')
    if room in rooms:
        rooms[room]['playback_mode'] = pb_mode
        emit('room_update', get_room_state(room), to=room)

@socketio.on('send_chat_message')
def on_send_chat_message(data):
    room = str(data.get('room', '')).strip().upper()
    msg = str(data.get('message', '')).strip()[:250]
    if room in rooms and msg:
        sender_info = rooms[room]['players'].get(request.sid, {})
        sender_name = sender_info.get('name', 'Jugador')
        payload = {
            'sender': sender_name,
            'message': msg,
            'sid': request.sid,
            'time': time.strftime("%H:%M")
        }
        socketio.emit('chat_message_received', payload, to=room)

@socketio.on('submit_vote')
def on_submit_vote(data):
    room = data.get('room', '').upper()
    voter = data.get('voter')
    target = data.get('target')

    if room not in rooms or not voter or not target:
        return

    if voter == target:
        print(f"[{room}] Self-vote rejected for player {voter}")
        return

    if 'votes' not in rooms[room]:
        rooms[room]['votes'] = {}

    rooms[room]['votes'][voter] = target
    print(f"[{room}] Vote submitted: {voter} -> {target} ({len(rooms[room]['votes'])} votes total)")

    r = rooms[room]
    mode = r.get('mode', 'competitivo')

    if mode == 'competitivo':
        expected = r.get('comp_data', {}).get('expected_players', [])
    else:
        expected = r.get('coop_data', {}).get('expected_players', [])

    if not expected:
        expected = list(set(p['name'] for p in r['players'].values()))

    # Check if all active expected players have voted
    if len(expected) > 0 and all(p in rooms[room]['votes'] for p in expected):
        print(f"[{room}] All {len(expected)} active players voted! Computing results...")

        vote_counts = {p: 0 for p in expected}
        for v, t in rooms[room]['votes'].items():
            if t in vote_counts:
                vote_counts[t] += 1

        # Fetch AI scores for tie-breaker
        if mode == 'competitivo':
            comp_data = r.get('comp_data', {})
            ai_scores = comp_data.get('scores', {})
            frozen_map = comp_data.get('sid_name_map', {})
            name_to_sid = {v: k for k, v in frozen_map.items()}
        else:
            coop_scores = r.get('coop_data', {}).get('scores', [])
            ai_scores = {c['name']: c['score'] for c in coop_scores}
            name_to_sid = {}

        ranking = []
        for p_name in expected:
            v_count = vote_counts.get(p_name, 0)
            ai_s = ai_scores.get(p_name, 0)
            sid_val = name_to_sid.get(p_name) or p_name
            ranking.append({
                "name": p_name,
                "player_name": p_name,
                "votes": v_count,
                "score": ai_s,
                "sid": sid_val,
                "player_sid": sid_val
            })

        # Primary sort: votes DESC, Secondary sort: AI score DESC (tie-breaker)
        ranking.sort(key=lambda x: (x["votes"], x["score"]), reverse=True)

        result_payload = {
            "ranking": ranking,
            "scores": ranking,
            "mode": mode,
            "scoring_mode": "voting"
        }

        if mode == 'competitivo' and 'comp_data' in r:
            r['comp_data']['result'] = result_payload
        elif 'coop_data' in r:
            r['coop_data']['result'] = result_payload
            r['coop_data']['status'] = 'done'

        socketio.emit('voting_completed', result_payload, to=room)

@socketio.on('claim_character')
def on_claim_character(data):
    room = data.get('room', '').upper()
    char_name = data.get('character')
    claim = data.get('claim', True)
    
    if room in rooms and request.sid in rooms[room]["players"]:
        player_name = rooms[room]["players"][request.sid]["name"]
        if claim:
            # Only claim if not already claimed
            if char_name not in rooms[room]["characters"]:
                rooms[room]["characters"][char_name] = player_name
        else:
            if rooms[room]["characters"].get(char_name) == player_name:
                del rooms[room]["characters"][char_name]

        # Reset ready status if player unclaims all characters in coop mode
        if rooms[room].get("mode") == 'cooperativo':
            has_claimed = any(p == player_name for p in rooms[room]["characters"].values())
            if not has_claimed:
                rooms[room]["players"][request.sid]["ready"] = False
                
        emit('room_update', get_room_state(room), to=room)

def _check_and_trigger_competitive_game_over(room):
    if room not in rooms:
        return False
    comp_data = rooms[room].get('comp_data')
    if not comp_data:
        return False

    if comp_data.get('result'):
        return True

    expected = comp_data.get('expected_players', [])
    scores_dict = comp_data.get('scores', {})

    if not expected:
        expected = list(set(p['name'] for p in rooms[room]['players'].values()))
        comp_data['expected_players'] = expected

    all_scored = bool(expected and all(p in scores_dict for p in expected))

    # Auto-advance timeout for players with slow / disconnected Wi-Fi
    if not all_scored and len(scores_dict) > 0 and not comp_data.get('timeout_timer_started'):
        comp_data['timeout_timer_started'] = True
        def _auto_advance_timeout():
            time.sleep(45)
            if room in rooms:
                cd = rooms[room].get('comp_data', {})
                if cd and not cd.get('result'):
                    print(f"[{room}] Auto-advance 45s timeout reached for slow/disconnected Wi-Fi players!")
                    f_map = cd.get('sid_name_map', {})
                    n_to_s = {v: k for k, v in f_map.items()}
                    c_vids = rooms[room].get('comp_videos', {})
                    exp = cd.get('expected_players', [])
                    s_dict = cd.get('scores', {})
                    s_list = []
                    for name in exp:
                        s = s_dict.get(name, 0)
                        sid = n_to_s.get(name) or next((k for k, p in rooms[room]["players"].items() if p['name'] == name), name)
                        v_url = c_vids.get(sid) or c_vids.get(name)
                        s_list.append({'name': name, 'score': s, 'sid': sid, 'video_url': v_url})
                    s_list.sort(key=lambda x: x['score'], reverse=True)
                    m = rooms[room].get('mode', 'competitivo')
                    res_payload = {'scores': s_list, 'mode': m}
                    cd['result'] = res_payload
                    socketio.emit('competitive_game_over', res_payload, to=room)
        threading.Thread(target=_auto_advance_timeout, daemon=True).start()

    if all_scored:
        frozen_map = comp_data.get('sid_name_map', {})
        name_to_sid = {v: k for k, v in frozen_map.items()}
        comp_vids = rooms[room].get('comp_videos', {})
        scores_list = []
        for name in expected:
            s = scores_dict.get(name, 0)
            sid = name_to_sid.get(name) or next((k for k, p in rooms[room]["players"].items() if p['name'] == name), name)
            v_url = comp_vids.get(sid) or comp_vids.get(name)
            scores_list.append({'name': name, 'score': s, 'sid': sid, 'video_url': v_url})
        scores_list.sort(key=lambda x: x['score'], reverse=True)
        mode = rooms[room].get('mode', 'competitivo')
        result = {'scores': scores_list, 'mode': mode}
        comp_data['result'] = result
        print(f"[{room}] All {len(expected)} scores submitted! Emitting competitive_game_over: {scores_list}")
        socketio.emit('competitive_game_over', result, to=room)
        return True
    return False

@socketio.on('submit_score')
def on_submit_score(data):
    room = data.get('room', '').upper()
    score = data.get('score', 0)
    if room not in rooms:
        return

    comp_data = rooms[room].get('comp_data', {})
    frozen_map = comp_data.get('sid_name_map', {})
    player_name = data.get('player_name') or data.get('name') or frozen_map.get(request.sid)
    if not player_name and request.sid in rooms[room]["players"]:
        player_name = rooms[room]["players"][request.sid]["name"]
    if not player_name:
        print(f"[{room}] submit_score: unknown sid {request.sid} and no player_name provided, ignoring")
        return

    if not comp_data:
        expected = list(set(p["name"] for p in rooms[room]["players"].values()))
        comp_data = {'expected_players': expected, 'sid_name_map': {}, 'scores': {}, 'result': None}
        rooms[room]['comp_data'] = comp_data

    comp_data.setdefault('scores', {})[player_name] = score

    if request.sid in rooms[room]["players"]:
        rooms[room]["players"][request.sid]["score"] = score

    emit('room_update', get_room_state(room), to=room)
    
    socketio.emit('comp_waiting_update', {
        'player_name': player_name,
        'player_sid': request.sid,
        'scored': True,
        'score': score,
        'submitted_players': list(comp_data['scores'].keys())
    }, to=room)

    print(f"[{room}] {player_name} scored {score:.1f} ({len(comp_data['scores'])}/{len(comp_data.get('expected_players', []))} submitted)")
    _check_and_trigger_competitive_game_over(room)

@socketio.on('host_video_sync')
def on_host_video_sync(data):
    """Host broadcasts video index changes and play/pause commands to all players."""
    room = data.get('room', '').upper()
    if room not in rooms:
        return
    # Rebroadcast to everyone in the room (client-side restricts who can send this)
    socketio.emit('video_sync', data, to=room)

@socketio.on('disconnect')
def on_player_disconnect():
    for room in list(rooms.keys()):
        if request.sid in rooms[room]["players"]:
            p_name = rooms[room]["players"][request.sid]["name"]
            if rooms[room].get('state') == 'waiting':
                _remove_player_from_all_rooms(request.sid)
            else:
                print(f"[{room}] Socket disconnected for {p_name} during active game (preserving game slot).")

def _handle_player_exit_active_game(room, player_name):
    if room not in rooms:
        return
    r = rooms[room]
    pack_name = r.get('pack_name')

    # 1. Competitive Mode: Remove AFK/exited player from expected_players & scores
    comp_data = r.get('comp_data')
    if comp_data:
        expected = comp_data.get('expected_players', [])
        if player_name in expected:
            expected.remove(player_name)
        if player_name in comp_data.get('scores', {}):
            del comp_data['scores'][player_name]

        # Check if all remaining players have submitted
        if expected and all(p in comp_data['scores'] for p in expected):
            frozen_map = comp_data.get('sid_name_map', {})
            name_to_sid = {v: k for k, v in frozen_map.items()}
            scores = []
            for name in expected:
                s = comp_data['scores'].get(name, 0)
                sid_val = name_to_sid.get(name) or next((k for k, p in r["players"].items() if p["name"] == name), name)
                scores.append({"name": name, "score": s, "sid": sid_val})
            scores.sort(key=lambda x: x["score"], reverse=True)
            mode = r.get('mode', 'competitivo')
            comp_data['result'] = {"scores": scores, "mode": mode}
            socketio.emit('competitive_game_over', comp_data['result'], to=room)

    # 2. Cooperative Mode: Remove AFK/exited player & trigger mix if remaining players are done
    coop_data = r.get('coop_data')
    if coop_data:
        expected_coop = coop_data.get('expected_players', [])
        if player_name in expected_coop:
            expected_coop.remove(player_name)
        
        if 'player_status' in coop_data and player_name in coop_data['player_status']:
            del coop_data['player_status'][player_name]

        total_players = len(expected_coop)
        finished_players = [p for p in expected_coop if coop_data.get('player_status', {}).get(p) == 'finished']
        finished_count = len(finished_players)
        coop_data['finished_count'] = finished_count
        coop_data['total_players'] = total_players

        # Build status list of remaining expected players
        players_status_list = []
        for p_name in expected_coop:
            st = coop_data.get('player_status', {}).get(p_name, 'recording')
            players_status_list.append({'name': p_name, 'status': st})

        # Broadcast waiting update to remaining players so they see updated count and player list
        socketio.emit('coop_waiting_update', {
            'finished': finished_count,
            'total': total_players,
            'players': players_status_list,
            'last_finished': player_name
        }, to=room)

        socketio.emit('coop_player_afk_kicked', {
            "player": player_name,
            "expected_players": expected_coop
        }, to=room)

        # Trigger mix if all remaining players have finished
        if finished_count >= total_players and total_players > 0 and pack_name:
            print(f"[{room}] All {total_players} remaining players finished after AFK exit. Starting mix...")
            socketio.emit('coop_processing', {'message': 'Jugador inactivo expulsado. Mezclando escena con voces originales...'}, to=room)
            t = threading.Thread(target=mix_coop_video_thread, args=(room, pack_name))
            t.start()

def on_disconnect():
    _remove_player_from_all_rooms(request.sid)

@socketio.on('leave_room')
def on_leave_room(data):
    _remove_player_from_all_rooms(request.sid)

def _remove_player_from_all_rooms(sid):
    for room in list(rooms.keys()):
        if sid in rooms[room]["players"]:
            name = rooms[room]["players"][sid]["name"]
            is_leaving_host = (sid == rooms[room].get("host_sid") or name == rooms[room].get("host_name"))
            
            del rooms[room]["players"][sid]
            
            # Remove any character claims held by this player name
            if "characters" in rooms[room]:
                to_del = [c for c, p in rooms[room]["characters"].items() if p == name]
                for c in to_del:
                    del rooms[room]["characters"][c]
            
            # Handle active game cleanup if game is in progress
            _handle_player_exit_active_game(room, name)

            # Transfer host role to top remaining active player if host left/kicked
            if is_leaving_host and len(rooms[room]["players"]) > 0:
                remaining_players = list(rooms[room]["players"].values())
                best_player = None
                best_score = -1

                comp_scores = rooms[room].get('comp_data', {}).get('scores', {})
                coop_scores = rooms[room].get('coop_data', {}).get('scores', [])

                for p in remaining_players:
                    p_name = p['name']
                    s = comp_scores.get(p_name, -1)
                    if s == -1:
                        coop_s = next((c['score'] for c in coop_scores if c.get('name') == p_name), -1)
                        s = coop_s
                    if s > best_score:
                        best_score = s
                        best_player = p

                if not best_player:
                    best_player = remaining_players[0]

                new_host_sid = best_player['sid']
                new_host_name = best_player['name']
                rooms[room]['host_sid'] = new_host_sid
                rooms[room]['host_name'] = new_host_name

                print(f"[{room}] Host transfer: New host is {new_host_name} (score: {best_score})")
                socketio.emit('host_changed', {
                    "host_name": new_host_name,
                    "host_sid": new_host_sid,
                    "reason": "El host anterior se ha desconectado o ha sido expulsado por inactividad"
                }, to=room)

            # Use flask_socketio's leave_room
            from flask_socketio import leave_room as socketio_leave_room
            socketio_leave_room(room)
            
            emit('room_update', get_room_state(room), to=room)
            
            print(f"[{room}] {name} left.")
            if len(rooms[room]["players"]) == 0:
                del rooms[room]

import socket
def get_local_ips():
    ips = set()
    # Get standard IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    # Get all interfaces
    try:
        host_name = socket.gethostname()
        host_ips = socket.gethostbyname_ex(host_name)[2]
        for ip in host_ips:
            if not ip.startswith('127.'):
                ips.add(ip)
    except Exception:
        pass
    
    if not ips:
        ips.add('127.0.0.1')
    return list(ips)

@app.route('/api/network_info', methods=['GET'])
def get_network_info():
    return jsonify({"local_ips": get_local_ips(), "port": 5000})


import subprocess
import time
import re

tunnel_url = None
tunnel_process = None

def _drain_tunnel_stdout(proc):
    """Continuously read cloudflared process stdout to prevent pipe buffer deadlock."""
    try:
        while proc and proc.poll() is None:
            line = proc.stdout.readline()
            if not line:
                break
    except Exception:
        pass

@app.route('/api/start_tunnel', methods=['POST'])
def start_tunnel():
    global tunnel_url, tunnel_process
    
    # If tunnel process exists and is alive, return cached URL
    if tunnel_process is not None and tunnel_process.poll() is None and tunnel_url:
        return jsonify({"url": tunnel_url})
        
    # Reset state if process died
    tunnel_url = None
    if tunnel_process is not None:
        try:
            tunnel_process.kill()
        except Exception:
            pass
        tunnel_process = None

    try:
        import platform
        import urllib.request
        import subprocess
        import re
        import threading
        
        system = platform.system().lower()
        if system == 'windows':
            download_url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
            cloudflared_path = os.path.join(os.getcwd(), 'cloudflared.exe')
        else:
            return jsonify({"url": None, "error": "Túnel automático solo soportado en Windows."})
            
        # Clean up any leftover or hanging cloudflared.exe processes on host
        if system == 'windows':
            try:
                subprocess.run(['taskkill', '/F', '/IM', 'cloudflared.exe'], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception:
                pass

        if not os.path.exists(cloudflared_path):
            logging.info("Descargando cloudflared...")
            urllib.request.urlretrieve(download_url, cloudflared_path)
            
        # Direct to 127.0.0.1:5000 to avoid IPv6 resolution delays
        cmd = [cloudflared_path, "tunnel", "--url", "http://127.0.0.1:5000"]
        tunnel_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
        url = None
        start_time = time.time()
        while time.time() - start_time < 25:
            line = tunnel_process.stdout.readline()
            if not line:
                if tunnel_process.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            
            if "trycloudflare.com" in line:
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    url = match.group(0)
                    break
            
        if url:
            tunnel_url = url
            # Register room code with tunnel URL
            room_code = request.json.get('room') if request.is_json and request.json else request.form.get('room')
            if room_code:
                ROOM_REGISTRY[room_code.upper()] = {'url': tunnel_url, 'created_at': time.time()}
                try:
                    import urllib.request
                    req_data = json.dumps({'code': room_code.upper(), 'url': tunnel_url}).encode('utf-8')
                    req = urllib.request.Request('https://kvdb.io/4y2ZfX1G9q2wK9m2tP9v2c/room_' + room_code.upper(), data=req_data, headers={'Content-Type': 'application/json'}, method='PUT')
                    urllib.request.urlopen(req, timeout=3)
                except Exception:
                    pass

            # Start background thread to keep stdout drained, preventing Cloudflare Error 1033!
            t = threading.Thread(target=_drain_tunnel_stdout, args=(tunnel_process,), daemon=True)
            t.start()
            print(f"[TUNNEL] Active tunnel URL: {tunnel_url} for room {room_code}")
            return jsonify({"url": tunnel_url})
        else:
            if tunnel_process:
                try:
                    tunnel_process.kill()
                except Exception:
                    pass
                tunnel_process = None
            return jsonify({"url": None, "error": "No se pudo generar el enlace del túnel. Reintenta."})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        if tunnel_process:
            try:
                tunnel_process.kill()
            except Exception:
                pass
            tunnel_process = None
        tunnel_url = None
        return jsonify({"url": None, "error": str(e)})


# Central Room Registry for Cross-Network Room Code Joining
ROOM_REGISTRY = {} # code -> { url: str, pack_name: str, created_at: float }
RENDER_CLOUD_SERVER = "https://grindtheclip.onrender.com"

@app.route('/api/register_room_code', methods=['POST'])
def register_room_code():
    try:
        data = request.get_json() or {}
        code = data.get('code', '').upper()
        url = data.get('url', '')
        pack_name = data.get('pack_name', '')
        if code and url:
            ROOM_REGISTRY[code] = {
                'url': url,
                'pack_name': pack_name,
                'created_at': time.time()
            }
            # Also attempt registering to global Render cloud registry if available
            try:
                import urllib.request
                req_data = json.dumps({'code': code, 'url': url, 'pack_name': pack_name}).encode('utf-8')
                req = urllib.request.Request(f"{RENDER_CLOUD_SERVER}/api/register_room_code", data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
            return jsonify({"success": True})
        return jsonify({"error": "Invalid code or url"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/resolve_room_code/<code>', methods=['GET'])
def resolve_room_code(code):
    code = code.upper()
    if code in ROOM_REGISTRY:
        reg = ROOM_REGISTRY[code]
        return jsonify({"found": True, "url": reg['url'], "pack_name": reg['pack_name']})
    
    # Check Render cloud registry
    try:
        import urllib.request
        req = urllib.request.Request(f"{RENDER_CLOUD_SERVER}/api/resolve_room_code/{code}", headers={'Accept': 'application/json'}, method='GET')
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('found'):
                    return jsonify({"found": True, "url": data.get('url'), "pack_name": data.get('pack_name', '')})
    except Exception:
        pass
        
    return jsonify({"found": False}), 404


def launch_desktop_window():
    url = "http://127.0.0.1:5000"
    
    # 1. Try Microsoft Edge App Mode (Standalone borderless window on Windows 10/11 - 100% pre-installed)
    try:
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")
        ]
        for ep in edge_paths:
            if os.path.exists(ep):
                print(f"[GUI] Iniciando en modo Edge App: {ep}")
                profile_dir = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'GTC_EdgeProfile')
                subprocess.Popen([
                    ep,
                    f"--app={url}",
                    "--window-size=1280,780",
                    f"--user-data-dir={profile_dir}"
                ])
                return
    except Exception as e:
        print(f"[GUI] Edge App Mode warning: {e}")

    # 2. Try Google Chrome App Mode
    try:
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                print(f"[GUI] Iniciando en modo Chrome App: {cp}")
                profile_dir = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'GTC_ChromeProfile')
                subprocess.Popen([
                    cp,
                    f"--app={url}",
                    "--window-size=1280,780",
                    f"--user-data-dir={profile_dir}"
                ])
                return
    except Exception as e:
        print(f"[GUI] Chrome App Mode warning: {e}")

    # 3. Universal Fallback to default system browser
    print("[GUI] Abriendo navegador predeterminado...")
    import webbrowser
    webbrowser.open(url)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    use_gui = '--no-gui' not in sys.argv and not IS_CLOUD
    if use_gui:
        server_thread = threading.Thread(
            target=socketio.run,
            args=(app,),
            kwargs={'host': '0.0.0.0', 'port': port, 'debug': False, 'allow_unsafe_werkzeug': True},
            daemon=True
        )
        server_thread.start()
        time.sleep(1.0)
        launch_desktop_window()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)
    else:
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
