import os
import sys
import subprocess
import json
import re
import logging
import time
import uuid
from pathlib import Path
import shutil
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.expanduser("~"), ".env"))
except Exception:
    pass

def get_ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

CONFIG_GEMINI_FILE = os.path.join(os.path.dirname(__file__), "gemini_config.json")

def get_gemini_api_key():
    key = os.getenv("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()
    if os.path.exists(CONFIG_GEMINI_FILE):
        try:
            with open(CONFIG_GEMINI_FILE, "r") as f:
                data = json.load(f)
                k = data.get("gemini_api_key", "").strip()
                if k:
                    return k
        except Exception:
            pass
    return ""

def set_gemini_api_key(key):
    key = key.strip()
    os.environ["GEMINI_API_KEY"] = key
    try:
        with open(CONFIG_GEMINI_FILE, "w") as f:
            json.dump({"gemini_api_key": key}, f, indent=2)
    except Exception:
        pass
    return True

# Gemini Client Setup
GEMINI_AVAILABLE = False
client = None

try:
    from google import genai
    from google.genai import types
    gemini_key = get_gemini_api_key()
    if gemini_key:
        client = genai.Client(api_key=gemini_key)
        GEMINI_AVAILABLE = True
        logging.info("Gemini SDK cargado correctamente.")
    else:
        logging.warning("GEMINI_API_KEY no configurada.")
except Exception as e:
    logging.warning(f"Error inicializando Gemini SDK: {e}")

def extract_audio_from_video(video_path, output_audio_path):
    ffmpeg_exe = get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-y", "-i", video_path, 
        "-q:a", "0", "-map", "a", output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def separate_vocals(audio_path, output_dir):
    """
    Uses demucs to separate vocals from the audio.
    Saves to output_dir/htdemucs/filename/
    """
    logging.info(f"Separating vocals for {audio_path}")
    
    # Use sys.executable to ensure we use the same Python environment (the one uv spawned)
    cmd = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs",
        "--two-stems", "vocals",
        "--segment", "7", # Max for htdemucs is 7.8
        "-d", "cpu", # Force CPU to avoid CUDA OOM for some users
        "-o", output_dir,
        audio_path
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        base_name = Path(audio_path).stem
        vocals_path = os.path.join(output_dir, "htdemucs", base_name, "vocals.wav")
        no_vocals_path = os.path.join(output_dir, "htdemucs", base_name, "no_vocals.wav")
        
        if not os.path.exists(no_vocals_path) or not os.path.exists(vocals_path):
            raise Exception("Demucs did not output the expected wav files")
            
        return vocals_path, no_vocals_path
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, 'stderr') and e.stderr:
            err_msg = e.stderr.decode('utf-8', errors='ignore')
        logging.error(f"Demucs failed, falling back to original audio: {err_msg}")
        
        # Fallback: Just use the original audio for both vocals and no_vocals
        # This guarantees the pipeline won't crash and the user still gets a scene
        vocals_path = os.path.join(output_dir, "vocals_fallback.wav")
        no_vocals_path = os.path.join(output_dir, "no_vocals_fallback.wav")
        shutil.copy(audio_path, vocals_path)
        shutil.copy(audio_path, no_vocals_path)
        
        return vocals_path, no_vocals_path

def transcribe_and_segment(vocals_path, language=None):
    """
    Uses faster-whisper with improved VAD to return a list of segments.
    Captures shouts, onomatopoeia and short utterances better.
    """
    logging.info("Transcribing and segmenting vocals")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            vocals_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=300,
                speech_pad_ms=400,
                threshold=0.35,
            ),
            hallucination_silence_threshold=2.0,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.4,
        )
    except Exception as e:
        logging.warning(f"WhisperModel import error: {e}. Returning empty segments fallback.")
        segments = []
    
    results = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        results.append({
            "start": segment.start,
            "end": segment.end,
            "text": text
        })
        
    return results

def slice_media(media_path, start, end, output_path, is_video=False):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if is_video:
        # Extract a single frame at the middle of the segment
        mid = (start + end) / 2
        cmd = [
            ffmpeg_exe, "-y",
            "-ss", str(mid),
            "-i", media_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
    else:
        cmd = [
            ffmpeg_exe, "-y", 
            "-ss", str(start), 
            "-to", str(end), 
            "-i", media_path,
            "-c:a", "libmp3lame", "-q:a", "2", output_path
        ]
        
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def download_youtube(url, output_dir):
    """
    Uses yt-dlp to download a video from YouTube directly via Python API.
    Returns the path to the downloaded mp4 file.
    """
    import yt_dlp
    
    output_path = os.path.join(output_dir, "yt_video.mp4")
    
    # Try multiple YouTube client configurations to bypass HTTP 403 Forbidden bot protection
    client_configs = [
        ['mweb', 'android', 'web'],
        ['android', 'ios'],
        ['web', 'mweb']
    ]
    
    last_error = None
    for player_clients in client_configs:
        try:
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'outtmpl': output_path,
                'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
                'quiet': True,
                'no_warnings': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': player_clients
                    }
                },
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logging.info(f"yt-dlp download complete using clients {player_clients}: {output_path}")
                return output_path
        except Exception as e:
            logging.warning(f"yt-dlp download failed with clients {player_clients}: {e}")
            last_error = e

    # Fallback to subprocess if direct API attempts failed
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--extractor-args", "youtube:player_client=mweb,android,web",
        "--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe(),
        "-o", output_path,
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except Exception as e:
        last_error = e

    raise RuntimeError(f"Error al descargar el vídeo de YouTube: {last_error}")

def snap_timestamps_to_audio_energy(vocals_path, lines):
    """
    Refines the start/end timestamps of lines (which have characters assigned by Gemini)
    by snapping them to physical voice activity in vocals.wav without altering character assignments.
    """
    try:
        import wave
        import numpy as np
        
        with wave.open(vocals_path, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / float(framerate)
            
            raw_bytes = wf.readframes(n_frames)
            if sampwidth == 2:
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 4:
                samples = np.frombuffer(raw_bytes, dtype=np.float32)
            else:
                return lines
                
            if n_channels > 1:
                samples = samples[::n_channels]
                
            frame_size = int(framerate * 0.01)
            if frame_size == 0:
                return lines
                
            n_chunks = len(samples) // frame_size
            if n_chunks == 0:
                return lines
                
            chunk_samples = samples[:n_chunks * frame_size].reshape(n_chunks, frame_size)
            energies = np.sqrt(np.mean(chunk_samples**2, axis=1))
            
            # Lower threshold to capture quiet singing, humming, and vocal extensions
            sorted_e = np.sort(energies)
            silence_thresh = max(0.005, sorted_e[int(len(sorted_e) * 0.15)] * 2.0)
            
            for line in lines:
                orig_start = line["start"]
                orig_end = line["end"]
                
                # Search window: ±0.5s around estimated start
                search_start_sec = max(0.0, orig_start - 0.5)
                search_end_sec = min(duration, orig_start + 0.5)
                start_frame = int(search_start_sec * 100)
                end_frame = int(search_end_sec * 100)
                
                for f_idx in range(start_frame, min(end_frame, len(energies))):
                    if energies[f_idx] > silence_thresh:
                        snapped_start = round(f_idx * 0.01, 2)
                        if abs(snapped_start - orig_start) <= 0.4:
                            line["start"] = snapped_start
                        break
                        
                # Search window for end: search up to +0.8s later to not cut off singing/vowels
                search_start_sec_end = max(0.0, orig_end - 0.4)
                search_end_sec_end = min(duration, orig_end + 0.8)
                start_frame_e = int(search_start_sec_end * 100)
                end_frame_e = int(search_end_sec_end * 100)
                
                for f_idx in range(min(end_frame_e, len(energies) - 1), max(0, start_frame_e), -1):
                    if energies[f_idx] > silence_thresh:
                        snapped_end = round((f_idx + 1) * 0.01, 2)
                        if snapped_end > line["start"]:
                            line["end"] = snapped_end
                        break
                        
                # Generous padding (+0.35s) so sustained vowels and singing notes are NEVER cut short!
                line["start"] = max(0.0, round(line["start"] - 0.05, 2))
                line["end"] = min(round(duration, 2), round(line["end"] + 0.35, 2))
                
    except Exception as e:
        logging.warning(f"Audio energy snapping failed (non-critical): {e}")
        
    return lines

def canonicalize_character_names(lines):
    """
    Normalizes character names so that aliases like 'Gumball' and 'Gumball Watterson',
    'Mr. Small' and 'Señor Pequeño', 'Announcer' and 'Locutor' map to a single canonical character name.
    """
    if not lines:
        return lines

    KNOWN_ALIASES = {
        "gumball": "Gumball Watterson",
        "gumball watterson": "Gumball Watterson",
        "richard": "Richard Watterson",
        "richard watterson": "Richard Watterson",
        "darwin": "Darwin Watterson",
        "darwin watterson": "Darwin Watterson",
        "tobias": "Tobias Wilson",
        "tobias wilson": "Tobias Wilson",
        "harold": "Harold Wilson",
        "harold wilson": "Harold Wilson",
        "jackie": "Jackie Wilson",
        "jackie wilson": "Jackie Wilson",
        "mr. small": "Mr. Small",
        "mr small": "Mr. Small",
        "señor pequeño": "Mr. Small",
        "senor pequeno": "Mr. Small",
        "announcer": "Locutor",
        "locutor": "Locutor",
        "locutor de vídeo": "Locutor",
        "locutor de video": "Locutor",
        "voz del cassette": "Voz del cassette",
        "actor": "Actor",
        "persona de anuncio": "Persona de anuncio",
        "hector": "Hector"
    }

    existing_canonical = set()

    for line in lines:
        raw_char = line["character"].strip()
        lower_char = raw_char.lower()

        if lower_char in KNOWN_ALIASES:
            canon = KNOWN_ALIASES[lower_char]
            line["character"] = canon
            existing_canonical.add(canon)
        else:
            matched = False
            for existing in list(existing_canonical):
                ex_lower = existing.lower()
                if lower_char in ex_lower or ex_lower in lower_char:
                    chosen = existing if len(existing) >= len(raw_char) else raw_char
                    line["character"] = chosen
                    matched = True
                    break
            if not matched:
                line["character"] = raw_char
                existing_canonical.add(raw_char)

    return lines

def _transcribe_single_gemini_clip(client, video_path, video_duration, prompt_time_offset=0.0):
    """
    Helper function to send a single video clip to Gemini and parse dialogue lines.
    """
    from google.genai import types
    logging.info(f"Subiendo fragmento de vídeo ({video_duration:.1f}s) a Gemini...")
    uploaded_file = client.files.upload(file=video_path)
    
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(1.5)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise ValueError("Fallo al procesar el fragmento en Gemini.")

    prompt = f"""You are an elite Hollywood video dialogue editor and acoustic diarizer.
Analyze this video fragment and output a perfectly synchronized JSON transcript of ALL spoken dialogue, singing, sustained notes, shouts, screams, laughter, and vocal sounds.

CRITICAL INSTRUCTIONS FOR MAXIMUM PRECISION:

1. CAPTURE ALL SINGING, CANTO & VOCALIZATIONS:
   - Include ALL singing, sustained notes, chanting, humming, laughter, shouts, screams, gasps, and non-verbal vocal sounds (e.g. [canta], [humming], "La la la").
   - DO NOT stop transcribing or skip audio when a character transitions from speaking to singing!

2. SPEAKER DIARIZATION (IDENTIFY EVERY DISTINCT CHARACTER):
   - Listen to the voices and watch who speaks on screen.
   - Assign exact character names (e.g. "Gumball Watterson", "Richard Watterson", "Tobias Wilson", "Mr. Small", "Locutor", "Darwin Watterson", "Hector").
   - NEVER lump multiple characters into the same label. Each distinct person MUST have their own character name.

3. GRANULARITY & SHORT DIALOGUE:
   - Prefer SHORT lines of 1 to 4 seconds.
   - If a character speaks or sings continuously for more than 5 seconds, SPLIT it into separate consecutive JSON objects matching sentence/phrase boundaries.

4. TIMESTAMPS:
   - 'start': EXACT second when the vocalization/singing begins relative to clip start (e.g. 1.25).
   - 'end': EXACT second when the vocalization/singing ends relative to clip start (e.g. 3.40).

5. CONFIDENCE:
   - Include a 'confidence' float from 0.5 to 1.0.

Clip duration is EXACTLY {video_duration:.2f}s. No timestamps may exceed this.

Return ONLY a valid JSON array:
[
  {{
    "character": "Character Name",
    "caption": "Spoken or sung phrase",
    "start": 1.20,
    "end": 3.50,
    "confidence": 0.95
  }}
]
"""
    
    models_to_try = ["gemini-3.6-flash", "gemini-3.1-pro-preview"]
    response = None
    last_err = None
    
    for m in models_to_try:
        try:
            response = client.models.generate_content(
                model=m,
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            if response and response.text:
                break
        except Exception as e:
            last_err = e

    try:
        client.files.delete(name=uploaded_file.name)
    except Exception:
        pass

    if not response or not response.text:
        raise last_err or ValueError("No se pudo obtener respuesta de Gemini para el fragmento.")

    text_content = response.text.strip()
    match = re.search(r'\[\s*\{.*\}\s*\]', text_content, re.DOTALL)
    if match:
        text_content = match.group(0)
    else:
        text_content = text_content.replace("```json", "").replace("```", "").strip()

    raw_lines = json.loads(text_content)
    lines = []
    for line in raw_lines:
        try:
            raw_start = float(line["start"])
            raw_end = float(line["end"])
        except Exception:
            continue

        if video_duration < 999900 and raw_start >= (video_duration - 0.1):
            continue

        start_val = max(0.0, round(raw_start, 2))
        end_val = round(raw_end, 2)

        if end_val <= start_val:
            end_val = round(start_val + 0.6, 2)

        end_val = min(video_duration, end_val)
        conf = float(line.get("confidence", 0.9))

        lines.append({
            "id": str(uuid.uuid4()),
            "character": str(line.get("character", "Personaje 1")).strip() or "Personaje 1",
            "caption": str(line.get("caption", "")).strip(),
            "start": start_val,
            "end": end_val,
            "confidence": conf
        })
    return lines

def transcribe_and_diarize_with_gemini(video_path):
    """
    Sends the video to Gemini for native transcription and multimodal diarization.
    For videos longer than 40s, splits into 35s overlapping chunks to guarantee zero mega-blocks.
    """
    try:
        from google import genai
    except ImportError:
        raise ImportError("Falta instalar google-genai. Ejecuta: pip install google-genai")
    
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("No se ha configurado ninguna Clave API de Gemini. Por favor, introduce tu Clave API en el Taller de Escenas.")
        
    client = genai.Client(api_key=api_key)
    
    # Get total video duration
    video_duration = 999999.0
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        res = subprocess.run([ffmpeg_exe, "-i", video_path], capture_output=True, text=True)
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
        if match:
            hours, mins, secs = match.groups()
            video_duration = round(float(hours)*3600 + float(mins)*60 + float(secs), 2)
    except Exception:
        pass

    raw_all_lines = []

    # If video > 40 seconds, use sliding 35-second chunks for 100% LLM focus
    if video_duration > 40.0 and video_duration < 999900:
        CHUNK_SIZE = 35.0
        OVERLAP = 5.0
        
        chunk_starts = []
        curr = 0.0
        while curr < video_duration:
            chunk_starts.append(curr)
            if curr + CHUNK_SIZE >= video_duration:
                break
            curr += (CHUNK_SIZE - OVERLAP)

        temp_dir = os.path.dirname(video_path)
        logging.info(f"Vídeo de {video_duration:.1f}s dividido en {len(chunk_starts)} fragmentos de {CHUNK_SIZE}s para evitar desfasajes...")

        for i, c_start in enumerate(chunk_starts):
            c_end = min(video_duration, c_start + CHUNK_SIZE)
            c_dur = c_end - c_start
            if c_dur < 2.0:
                continue

            chunk_file = os.path.join(temp_dir, f"chunk_{i:02d}.mp4")
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe, "-y",
                "-ss", str(c_start),
                "-to", str(c_end),
                "-i", video_path,
                "-c", "copy",
                chunk_file
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except Exception:
                cmd_rec = [ffmpeg_exe, "-y", "-ss", str(c_start), "-to", str(c_end), "-i", video_path, "-preset", "ultrafast", chunk_file]
                subprocess.run(cmd_rec, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            logging.info(f"Procesando fragmento {i+1}/{len(chunk_starts)} ({c_start:.1f}s - {c_end:.1f}s)...")
            try:
                c_lines = _transcribe_single_gemini_clip(client, chunk_file, c_dur, c_start)
                for cl in c_lines:
                    cl["start"] = round(c_start + cl["start"], 2)
                    cl["end"] = round(c_start + cl["end"], 2)
                    raw_all_lines.append(cl)
            except Exception as e:
                logging.warning(f"Error en fragmento {i+1}: {e}")

            try:
                if os.path.exists(chunk_file):
                    os.remove(chunk_file)
            except Exception:
                pass
    else:
        # Short video: process whole file
        raw_all_lines = _transcribe_single_gemini_clip(client, video_path, video_duration, 0.0)

    if not raw_all_lines:
        raise ValueError("No se obtuvieron líneas de la IA para el vídeo.")

    # Canonicalize character aliases (e.g. Gumball vs Gumball Watterson -> Gumball Watterson)
    raw_all_lines = canonicalize_character_names(raw_all_lines)

    # Sort chronologically
    raw_all_lines.sort(key=lambda l: (l["start"], l["end"]))

    # ============================================================
    # POST-PROCESSING PASS 1: Deduplicate cross-track and chunk overlaps
    # ============================================================
    dedup_lines = []
    for line in raw_all_lines:
        if not dedup_lines:
            dedup_lines.append(line)
            continue
            
        dup_found = False
        for prev in reversed(dedup_lines[-5:]):
            same_char = (line["character"] == prev["character"])
            time_diff = abs(line["start"] - prev["start"])
            
            cap1 = line["caption"].lower().replace('¡','').replace('!','').replace('¿','').replace('?','').strip()
            cap2 = prev["caption"].lower().replace('¡','').replace('!','').replace('¿','').replace('?','').strip()
            
            words1 = set(cap1.split())
            words2 = set(cap2.split())
            common_words = words1.intersection(words2)
            word_sim = len(common_words) / max(1, min(len(words1), len(words2))) if words1 and words2 else 0.0
            
            text_match = (cap1 in cap2 or cap2 in cap1 or word_sim >= 0.5)
            
            if time_diff < 1.8 and (same_char or text_match):
                if len(line["caption"]) > len(prev["caption"]):
                    prev["caption"] = line["caption"]
                    prev["confidence"] = max(prev.get("confidence", 0.9), line.get("confidence", 0.9))
                dup_found = True
                break
                
        if not dup_found:
            dedup_lines.append(line)

    # ============================================================
    # POST-PROCESSING PASS 2: Spoken-duration capping & sentence splits
    # ============================================================
    split_lines = []
    MAX_LINE_DURATION = 6.0

    for line in dedup_lines:
        duration = line["end"] - line["start"]
        caption = line["caption"]
        words = [w for w in caption.split() if w]
        num_words = len(words)

        # Realistic speaking/singing duration: ~0.40s per word + 1.2s padding (max 6.5s)
        max_allowed_dur = max(1.8, min(6.5, num_words * 0.40 + 1.2))
        if duration > max_allowed_dur:
            line["end"] = round(line["start"] + max_allowed_dur, 2)
            duration = max_allowed_dur

        if duration <= MAX_LINE_DURATION:
            split_lines.append(line)
            continue

        sentences = re.split(r'(?<=[.!?…])\s+', caption)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            sentences = re.split(r'(?<=[,;:])\s+', caption)
            sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            chunk_words_cnt = max(1, len(words) // 2)
            sentences = [' '.join(words[:chunk_words_cnt]), ' '.join(words[chunk_words_cnt:])]
            sentences = [s.strip() for s in sentences if s.strip()]

        total_chars = sum(len(s) for s in sentences)
        if total_chars == 0:
            split_lines.append(line)
            continue

        cursor = line["start"]
        for sentence in sentences:
            proportion = len(sentence) / total_chars
            chunk_duration = duration * proportion
            chunk_start = round(cursor, 2)
            chunk_end = round(cursor + chunk_duration, 2)

            if video_duration < 999900:
                chunk_end = min(video_duration, chunk_end)
            if chunk_end - chunk_start < 0.4:
                chunk_end = round(chunk_start + 0.4, 2)

            split_lines.append({
                "id": str(uuid.uuid4()),
                "character": line["character"],
                "caption": sentence,
                "start": chunk_start,
                "end": chunk_end,
                "confidence": line.get("confidence", 0.9)
            })
            cursor = chunk_end

    split_lines.sort(key=lambda l: (l["start"], l["end"]))

    # Resolve overlapping lines on the same character track (minimum 0.05s gap)
    from collections import defaultdict
    char_groups = defaultdict(list)
    for line in split_lines:
        char_groups[line["character"]].append(line)

    for char_name, char_lines in char_groups.items():
        char_lines.sort(key=lambda l: l["start"])
        for i in range(1, len(char_lines)):
            prev = char_lines[i - 1]
            curr = char_lines[i]
            if curr["start"] < prev["end"]:
                prev["end"] = round(curr["start"] - 0.05, 2)
                if prev["end"] <= prev["start"]:
                    prev["end"] = round(prev["start"] + 0.2, 2)

    split_lines.sort(key=lambda l: (l["start"], l["end"]))
    return split_lines

def auto_process(video_path, temp_dir, status_callback=None):
    """
    Full automated pipeline: separate vocals and transcribe/diarize in parallel!
    Returns a dict with lines, vocals_path, and no_vocals_path.
    """
    import threading
    
    if status_callback:
        status_callback('Extrayendo audio del vídeo...', 5)
    audio_path = os.path.join(temp_dir, "temp_audio.wav")
    extract_audio_from_video(video_path, audio_path)
    if status_callback:
        status_callback('Audio extraído. Iniciando IA en paralelo...', 15)
    
    # Run demucs and Gemini in parallel threads!
    results = {"demucs": [None, None], "demucs_error": None, "gemini": None, "gemini_error": None}
    
    def run_demucs():
        try:
            v, nv = separate_vocals(audio_path, temp_dir)
            results["demucs"] = [v, nv]
        except Exception as e:
            results["demucs_error"] = e
            
    def run_gemini():
        try:
            lines = transcribe_and_diarize_with_gemini(video_path)
            results["gemini"] = lines
        except Exception as e:
            results["gemini_error"] = e

    t_demucs = threading.Thread(target=run_demucs)
    t_gemini = threading.Thread(target=run_gemini)
    
    t_demucs.start()
    t_gemini.start()
    
    progress = 15
    while t_demucs.is_alive() or t_gemini.is_alive():
        time.sleep(3)
        if progress < 90:
            progress += 3
            if status_callback:
                status_callback('Separando voces y transcribiendo diálogos (IA Paralela)...', progress)
                
    vocals_path, no_vocals_path = results["demucs"]
    if results["demucs_error"]:
        raise results["demucs_error"]

    lines = results["gemini"]
    if results["gemini_error"] or not lines:
        logging.warning(f"Gemini fallo o no devolvió líneas ({results['gemini_error']}), usando Whisper como alternativa local...")
        if status_callback:
            status_callback('Transcribiendo diálogos con Whisper (Local)...', 85)
        raw_segments = transcribe_and_segment(vocals_path)
        lines = []
        
        # Smart character grouping by time gaps instead of 1 single character
        char_idx = 1
        last_end = 0.0
        for seg in raw_segments:
            start_val = max(0.0, round(float(seg["start"]) - 0.1, 2))
            end_val = round(float(seg["end"]) + 0.1, 2)
            
            # If gap between segments > 1.5s, assign to next character speaker pool
            if start_val - last_end > 1.5 and len(lines) > 0:
                char_idx = (char_idx % 3) + 1  # Cycle Personaje 1, 2, 3
                
            last_end = end_val
            lines.append({
                "id": str(uuid.uuid4()),
                "character": f"Personaje {char_idx}",
                "caption": seg["text"],
                "start": start_val,
                "end": end_val,
                "confidence": 0.6
            })
    else:
        # Snap Gemini's character lines to physical voice energy in vocals_path!
        if status_callback:
            status_callback('Ajustando marcas de tiempo a la onda física de voz...', 92)
        lines = snap_timestamps_to_audio_energy(vocals_path, lines)
    
    if not lines:
        raise ValueError("No se pudo detectar ningún diálogo en el vídeo.")

    unique_chars = sorted(list(set(l["character"] for l in lines)))
    COLORS = ["#22d3ee", "#e5636b", "#4caf7d", "#d9a441", "#c471ed", "#41c7d9", "#f27b9b", "#8bc34a"]
    characters = []
    for i, char_name in enumerate(unique_chars):
        characters.append({
            "name": char_name,
            "color": COLORS[i % len(COLORS)]
        })

    if status_callback:
        status_callback('Completado', 100)
    
    return {
        "lines": lines,
        "characters": characters,
        "vocals_path": vocals_path,
        "no_vocals_path": no_vocals_path,
    }

def build_pack(video_path, pack_id, pack_title, takes_data, output_base_dir,
               status_callback=None, lines=None, vocals_path=None, no_vocals_path=None,
               authors="", readme=""):
    """
    Build a voice pack from video + take data.
    
    Can work in two modes:
      1. Traditional: provide takes_data (list of dicts with character, start_time, end_time, subtitle).
         Audio separation will be done from scratch.
      2. Pre-processed: provide lines (list of dicts with character, caption, start, end) plus
         vocals_path and no_vocals_path to skip re-processing.
    """
    from werkzeug.utils import secure_filename
    
    import shutil
    
    # 1. Prepare directories
    pack_folder = os.path.join(output_base_dir, secure_filename(pack_id))
    if os.path.exists(pack_folder):
        shutil.rmtree(pack_folder)
    os.makedirs(pack_folder, exist_ok=True)
    temp_dir = os.path.dirname(video_path)
    
    # Determine whether to use pre-processed paths or run separation
    if lines is not None and vocals_path and no_vocals_path:
        # Pre-processed mode: use provided vocals/no_vocals and lines
        vocals = vocals_path
        no_vocals = no_vocals_path
        
        if status_callback:
            status_callback("Procesando tomas...", 70)
        
        for i, line in enumerate(lines):
            char_name = line.get('character', 'Unknown')
            start = float(line['start'])
            end = float(line['end'])
            text = line.get('caption', '')
            
            safe_char = secure_filename(char_name)
            base_name = f"{i+1:02d}_{safe_char}"
            
            clip_path = os.path.join(pack_folder, f"{base_name}.mp3")
            txt_path = os.path.join(pack_folder, f"{base_name}.txt")
            png_path = os.path.join(pack_folder, f"{base_name}.png")
            
            slice_media(vocals, start, end, clip_path, is_video=False)
            slice_media(video_path, start, end, png_path, is_video=True)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f'[data]\n\ncaption="{text}"\nimage="{base_name}.png"\ndub_timestamps=[{start}]\ndub_characters=["{char_name}"]\n')
    else:
        # Traditional mode: run full audio extraction + separation
        audio_path = os.path.join(temp_dir, "temp_audio.wav")
        
        if status_callback:
            status_callback("Extrayendo audio...", 30)
        extract_audio_from_video(video_path, audio_path)
        
        if status_callback:
            status_callback("Separando voces (Demucs)...", 40)
        vocals, no_vocals = separate_vocals(audio_path, temp_dir)
        
        if status_callback:
            status_callback("Procesando tomas...", 70)
        
        for i, take in enumerate(takes_data):
            char_name = take.get('character', 'Unknown')
            start = float(take['start_time'])
            end = float(take['end_time'])
            text = take.get('subtitle', '')
            
            safe_char = secure_filename(char_name)
            base_name = f"{i+1:02d}_{safe_char}"
            
            clip_path = os.path.join(pack_folder, f"{base_name}.mp3")
            txt_path = os.path.join(pack_folder, f"{base_name}.txt")
            png_path = os.path.join(pack_folder, f"{base_name}.png")
            
            slice_media(vocals, start, end, clip_path, is_video=False)
            slice_media(video_path, start, end, png_path, is_video=True)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f'[data]\n\ncaption="{text}"\nimage="{base_name}.png"\ndub_timestamps=[{start}]\ndub_characters=["{char_name}"]\n')
            
    if status_callback:
        status_callback("Finalizando recursos...", 90)
    
    # Copy video and backing track
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
        shutil.copy(video_path, os.path.join(pack_folder, "dub_video.mp4"))
    
    shutil.copy(video_path, os.path.join(pack_folder, "dub_video.ogv")) # Fallback for godot 3
    shutil.copy(no_vocals, os.path.join(pack_folder, "_backing_track.mp3"))
    
    # Extract icon (first 5 seconds or middle of video)
    slice_media(video_path, 0, 5, os.path.join(pack_folder, "icon.png"), is_video=True)
    
    # Create _pack_info.ini
    with open(os.path.join(pack_folder, "_pack_info.ini"), "w", encoding="utf-8") as f:
        f.write(f'[pack]\nname="{pack_title}"\nauthor="{authors}"\ndescription="{readme}"\n')
    
    if status_callback:
        status_callback("Completado", 100)
