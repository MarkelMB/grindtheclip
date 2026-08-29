import os
import re

server_py_path = r'C:\Users\marke\.gemini\antigravity\scratch\voice_choicer\server.py'

with open(server_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add time import if not present
if 'import time' not in content:
    content = content.replace("import uuid", "import uuid\nimport time")

# 2. Add auto-save to process_auto_build_job
auto_save_code = """        job["result"] = result
        
        # Save project.json automatically
        project_file = os.path.join(job_dir, "project.json")
        try:
            rel_path = os.path.relpath(video_path, UPLOADS_DIR).replace('\\\\', '/')
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
            
        job["status"] = "Completado\""""

content = content.replace(
    '        job["result"] = result\n        job["status"] = "Completado"',
    auto_save_code
)

# 3. Add endpoints for save and projects
endpoints_code = """
@app.route('/api/creator/save/<job_id>', methods=['POST'])
def save_project(job_id):
    data = request.json
    job_dir = os.path.join(UPLOADS_DIR, secure_filename(job_id))
    if not os.path.exists(job_dir):
        return jsonify({"error": "Proyecto no encontrado"}), 404
        
    project_file = os.path.join(job_dir, "project.json")
    with open(project_file, 'w', encoding='utf-8') as f:
        json.dump({
            "job_id": job_id,
            "pack_name": data.get('pack_name', 'Sin título'),
            "lines": data.get('lines', []),
            "characters": data.get('characters', []),
            "video_url": data.get('video_url', ''),
            "updated_at": time.time()
        }, f, ensure_ascii=False)
    
    # Update memory cache too
    if job_id not in creator_jobs:
        creator_jobs[job_id] = {"job_dir": job_dir}
    if "result" not in creator_jobs[job_id]:
        creator_jobs[job_id]["result"] = {}
    creator_jobs[job_id]["result"]["lines"] = data.get('lines', [])
    creator_jobs[job_id]["result"]["characters"] = data.get('characters', [])
    creator_jobs[job_id]["pack_name"] = data.get('pack_name', 'Sin título')
    
    return jsonify({"success": True})

@app.route('/api/creator/projects', methods=['GET'])
def get_projects():
    projects = []
    if os.path.exists(UPLOADS_DIR):
        for job_id in os.listdir(UPLOADS_DIR):
            job_dir = os.path.join(UPLOADS_DIR, job_id)
            if os.path.isdir(job_dir):
                project_file = os.path.join(job_dir, "project.json")
                if os.path.exists(project_file):
                    try:
                        with open(project_file, 'r', encoding='utf-8') as f:
                            projects.append(json.load(f))
                    except:
                        pass
    # Sort by updated_at descending
    projects.sort(key=lambda x: x.get('updated_at', 0), reverse=True)
    return jsonify({"projects": projects})

# ==========================================
"""

content = content.replace("# ==========================================\n# API: SCORING (Librosa)", endpoints_code + "# API: SCORING (Librosa)")

with open(server_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("server.py patched with projects logic.")
