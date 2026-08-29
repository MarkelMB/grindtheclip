import os

with open('ai_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace diarize_with_gemini with transcribe_and_diarize_with_gemini
old_diarize = content[content.find("def diarize_with_gemini"):content.find("def auto_process")]

new_diarize = """def transcribe_and_diarize_with_gemini(video_path):
    \"\"\"
    Sends the video to Gemini for native transcription and multimodal diarization.
    Returns the mapped lines.
    \"\"\"
    try:
        from google import genai
        from google.genai import types
        import json
        import uuid
        import time
        import logging
    except ImportError:
        raise ImportError("Falta instalar google-genai. Ejecuta: pip install google-genai")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no encontrada en .env")
        
    client = genai.Client(api_key=api_key)
    
    # Upload file
    logging.info("Subiendo vídeo a Gemini...")
    uploaded_file = client.files.upload(file=video_path)
    
    # Wait for processing if needed
    while uploaded_file.state.name == "PROCESSING":
        logging.info("Esperando a que Gemini procese el vídeo...")
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise ValueError("Fallo al procesar el vídeo en Gemini.")
    
    prompt = \"\"\"
    Watch this video carefully. Transcribe all the spoken dialogue.
    Identify who is speaking for each line of dialogue.
    Provide the start and end timestamps (in seconds as floats) for each line.
    
    Return ONLY a valid JSON array of objects with the following format:
    [
      {
        "character": "Name of the character",
        "caption": "The spoken text",
        "start": 0.0,
        "end": 2.5
      }
    ]
    \"\"\"
    
    logging.info("Llamando a Gemini 3.6 Flash para transcripción y diarización nativa...")
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=[uploaded_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2
        )
    )
    
    # Cleanup file
    client.files.delete(name=uploaded_file.name)
    
    # Parse JSON
    try:
        lines = json.loads(response.text)
        # Add UUIDs
        for line in lines:
            line["id"] = str(uuid.uuid4())
            # Ensure proper types
            line["start"] = float(line["start"])
            line["end"] = float(line["end"])
    except Exception as e:
        logging.error(f"Error parseando JSON de Gemini: {response.text}")
        raise e
        
    return lines

"""
content = content.replace(old_diarize, new_diarize)

# 2. Update auto_process
old_auto_process = content[content.find("def auto_process"):content.find("def build_pack")]

new_auto_process = """def auto_process(video_path, temp_dir, status_callback=None):
    \"\"\"
    Full automated pipeline: separate vocals and transcribe/diarize in parallel!
    Returns a dict with lines, vocals_path, and no_vocals_path.
    \"\"\"
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
                
    t_demucs.join()
    t_gemini.join()
    
    if results["demucs_error"]:
        raise results["demucs_error"]
    if results["gemini_error"]:
        raise results["gemini_error"]
        
    vocals_path, no_vocals_path = results["demucs"]
    lines = results["gemini"]
    
    if not lines:
        raise ValueError("La IA no detectó ningún diálogo en el vídeo.")

    unique_chars = sorted(list(set(l["character"] for l in lines)))
    COLORS = ["#6c8cff", "#e5636b", "#4caf7d", "#d9a441", "#c471ed", "#41c7d9", "#f27b9b", "#8bc34a"]
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

"""
content = content.replace(old_auto_process, new_auto_process)

with open('ai_pipeline.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched ai_pipeline.py successfully.")
