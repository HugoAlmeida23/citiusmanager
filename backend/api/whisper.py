import os
from pathlib import Path
from openai import OpenAI

def audio_to_text(audio_file_path):
    """
    Convert audio file to text using OpenAI's Whisper API
    
    Args:
        audio_file_path: Path to the audio file
    
    Returns:
        Transcribed text from the audio file
    """
    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("WHISPER_API"))
    
    # Open and send the file for transcription
    with open(audio_file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",  # Whisper model for speech-to-text
            file=audio_file,
            response_format="text"  # Options: "text", "json", "srt", "verbose_json"
        )

    # Return the transcribed text
    return response