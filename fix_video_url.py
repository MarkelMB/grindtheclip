import re

with open('server.py', 'r', encoding='utf-8') as f:
    py = f.read()

# Replace the video_url assignment
old_str = '''        if job.get("video_path"):
            video_filename = os.path.basename(job["video_path"])
            response["video_url"] = f"/uploads/{job_id}/{video_filename}"'''
            
new_str = '''        if job.get("video_path"):
            rel_path = os.path.relpath(job["video_path"], UPLOADS_DIR).replace('\\\\', '/')
            response["video_url"] = f"/uploads/{rel_path}"'''

py = py.replace(old_str, new_str)

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(py)
