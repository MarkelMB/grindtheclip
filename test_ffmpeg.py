import subprocess
import os

# Create dummy audio files
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc=0:d=10", "backing.mp3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2", "clip1.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=400:duration=2", "clip2.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

cmd = ["ffmpeg", "-y", "-i", "backing.mp3", "-i", "clip1.wav", "-i", "clip2.wav"]
filter_complex = "[1:a]adelay=1000|1000[s1];[2:a]adelay=4000|4000[s2];[0:a][s1][s2]amix=inputs=3:duration=first:normalize=0[aout]"
cmd.extend(["-filter_complex", filter_complex, "-map", "[aout]", "out.mp3"])

print("Running command:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    print("ERROR:", res.stderr)
else:
    print("SUCCESS")
