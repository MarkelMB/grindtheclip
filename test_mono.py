import subprocess
import imageio_ffmpeg
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

# Create a MONO audio file
subprocess.run([ffmpeg_exe, "-y", "-f", "lavfi", "-i", "aevalsrc=0:d=10", "backing.mp3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run([ffmpeg_exe, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2", "-ac", "1", "mono.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

cmd = [ffmpeg_exe, "-y", "-i", "backing.mp3", "-i", "mono.wav"]
filter_complex = "[1:a]adelay=1000|1000[s1];[0:a][s1]amix=inputs=2:duration=first:normalize=0[aout]"
cmd.extend(["-filter_complex", filter_complex, "-map", "[aout]", "out.mp3"])

res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    print("FAILED")
    print(res.stderr)
else:
    print("SUCCESS")
