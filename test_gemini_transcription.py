import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

def test_gemini(video_path):
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    print("Uploading video to Gemini...")
    uploaded_file = client.files.upload(file=video_path)
    
    while uploaded_file.state.name == "PROCESSING":
        print("Processing video...")
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    print(f"Video state: {uploaded_file.state.name}")
    
    prompt = """
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
    """
    
    print("Generating content...")
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=[uploaded_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2
        )
    )
    
    print("Response:")
    print(response.text)
    
    client.files.delete(name=uploaded_file.name)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_gemini(sys.argv[1])
    else:
        print("Please provide a video path.")
