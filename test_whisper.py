import os
import sys
from ai_pipeline import extract_audio_from_video, transcribe_and_segment

def test_whisper(video_path):
    print("Extracting audio...")
    audio_path = "test_vid.wav"
    extract_audio_from_video(video_path, audio_path)
    
    print("Transcribing...")
    segments = transcribe_and_segment(audio_path)
    print(f"Extracted {len(segments)} segments.")
    for i, seg in enumerate(segments):
        print(f"[{i}] {seg['start']:.2f}s - {seg['end']:.2f}s: {seg['text']}")

if __name__ == "__main__":
    test_whisper("test_vid.mp4")
