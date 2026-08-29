import os
import json
import logging
import urllib.request
import urllib.parse

CONFIG_FILE = "supabase_config.json"
SUPABASE_URL = "https://vdrqdmhjxwwmodsmqpgj.supabase.co"
SUPABASE_KEY = "sb_publishable_O8wJKVLa4HFms8Pu6gkylg_CC7Tb4bh"
SUPABASE_SECRET = "sb_secret_gdr_imXTBnGJW2olXuIclg_kZ85S7oL"

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            SUPABASE_URL = cfg.get("url", SUPABASE_URL)
            SUPABASE_KEY = cfg.get("key", SUPABASE_KEY)
            SUPABASE_SECRET = cfg.get("secret_key", SUPABASE_SECRET)
    except Exception:
        pass

def get_active_key():
    return SUPABASE_SECRET if SUPABASE_SECRET else SUPABASE_KEY

def is_cloud_enabled():
    return bool(SUPABASE_URL and get_active_key())

def configure_supabase(url, key, secret_key=""):
    global SUPABASE_URL, SUPABASE_KEY, SUPABASE_SECRET
    SUPABASE_URL = url.strip()
    SUPABASE_KEY = key.strip()
    if secret_key:
        SUPABASE_SECRET = secret_key.strip()
    with open(CONFIG_FILE, "w") as f:
        json.dump({"url": SUPABASE_URL, "key": SUPABASE_KEY, "secret_key": SUPABASE_SECRET}, f, indent=2)
    return True

def cloud_test_connection():
    if not is_cloud_enabled():
        return {"success": False, "error": "Falta URL o Key"}
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/"
        active_key = get_active_key()
        req = urllib.request.Request(url, headers={
            "apikey": active_key,
            "Authorization": f"Bearer {active_key}"
        })
        with urllib.request.urlopen(req, timeout=5) as response:
            return {"success": True, "status": response.status}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cloud_register_user(nickname, password):
    if not is_cloud_enabled():
        return {"success": False, "error": "Supabase no está configurado"}
    try:
        email = f"{nickname.lower().replace(' ', '_')}@grindtheclip.game"
        url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/signup"
        active_key = get_active_key()
        body = json.dumps({"email": email, "password": password, "data": {"nickname": nickname}}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "apikey": active_key,
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"success": True, "user": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cloud_login_user(nickname, password):
    if not is_cloud_enabled():
        return {"success": False, "error": "Supabase no está configurado"}
    try:
        email = f"{nickname.lower().replace(' ', '_')}@grindtheclip.game"
        url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
        active_key = get_active_key()
        body = json.dumps({"email": email, "password": password}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "apikey": active_key,
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"success": True, "token": data.get("access_token"), "user": data.get("user")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cloud_save_score(player_name, pack_name, score, mode):
    if not is_cloud_enabled():
        return False
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/leaderboard"
        active_key = get_active_key()
        body = json.dumps({
            "player_name": player_name,
            "pack_name": pack_name,
            "score": score,
            "mode": mode
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "apikey": active_key,
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status in (200, 201)
    except Exception as e:
        logging.warn(f"Cloud save score error: {e}")
        return False
