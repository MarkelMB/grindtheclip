import re

with open('ai_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_copy = """        if video_path and os.path.exists(video_path):
            shutil.copy(video_path, os.path.join(pack_folder, "dub_video.mp4"))"""

new_copy = """        if video_path and os.path.exists(video_path):
            import subprocess
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-c", "copy",
                "-movflags", "+faststart",
                os.path.join(pack_folder, "dub_video.mp4")
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print("FFmpeg faststart failed, copying directly:", e)
                shutil.copy(video_path, os.path.join(pack_folder, "dub_video.mp4"))"""

if old_copy in content:
    content = content.replace(old_copy, new_copy)
    with open('ai_pipeline.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched ai_pipeline.py successfully.")
else:
    print("old_copy not found in ai_pipeline.py.")
