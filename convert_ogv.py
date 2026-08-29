import os
import subprocess
import imageio_ffmpeg

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
packs_dir = r"C:\Users\marke\AppData\Roaming\YeahMaybe\ChoicerVoicer\game\packs_voice"

for pack in os.listdir(packs_dir):
    pack_path = os.path.join(packs_dir, pack)
    if os.path.isdir(pack_path):
        ogv_path = os.path.join(pack_path, "dub_video.ogv")
        mp4_path = os.path.join(pack_path, "dub_video.mp4")
        if os.path.exists(ogv_path) and not os.path.exists(mp4_path):
            print(f"Converting {ogv_path} to mp4...")
            subprocess.run([ffmpeg_exe, "-i", ogv_path, "-c:v", "libx264", "-c:a", "aac", mp4_path])
            print(f"Done {pack}")
