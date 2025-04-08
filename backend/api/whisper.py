import os
import tempfile
import subprocess
import math
import json
import time
import uuid
from pathlib import Path
from openai import OpenAI

# Dictionary to store job status and results
# In a production environment, use a database or Redis instead
transcription_jobs = {}

def get_job_status(job_id):
    """
    Get the current status of a transcription job
    """
    if job_id not in transcription_jobs:
        return None
    
    return transcription_jobs[job_id]

def audio_to_text_async(audio_file_path):
    """
    Start an asynchronous transcription job.
    Returns a job ID that can be used to check progress.
    """
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    transcription_jobs[job_id] = {
        'status': 'processing',
        'progress': 0,
        'result': None,
        'error': None
    }
    
    # Start processing in a separate thread
    import threading
    thread = threading.Thread(
        target=process_audio_job,
        args=(audio_file_path, job_id)
    )
    thread.daemon = True
    thread.start()
    
    return job_id

def process_audio_job(audio_file_path, job_id):
    """
    Process the audio transcription job and update status
    """
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=os.getenv("WHISPER_API"))
        
        # Get file size in MB
        file_size = os.path.getsize(audio_file_path) / (1024 * 1024)
        
        # Update job status
        transcription_jobs[job_id]['file_size'] = f"{file_size:.2f}MB"
        
        # If file is smaller than 25MB, process it directly
        if file_size < 25:
            transcription_jobs[job_id]['progress'] = 10
            with open(audio_file_path, "rb") as audio_file:
                try:
                    response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                    transcription_jobs[job_id]['status'] = 'completed'
                    transcription_jobs[job_id]['progress'] = 100
                    transcription_jobs[job_id]['result'] = response
                    return
                except Exception as e:
                    print(f"Direct transcription failed: {e}")
                    # Continue to segmentation approach
        
        print(f"File size: {file_size:.2f}MB. Processing in segments...")
        transcription_jobs[job_id]['progress'] = 15
        
        # For larger files, we need to split them
        # Calculate how many chunks we need
        chunk_size_mb = 10  # Use smaller chunks to avoid timeouts
        num_chunks = math.ceil(file_size / chunk_size_mb)
        
        # Create temporary directory for our working files
        temp_dir = tempfile.mkdtemp()
        transcriptions = []
        
        try:
            # Check if ffmpeg is available
            has_ffmpeg = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True).returncode == 0
        except:
            has_ffmpeg = False        
            
        # Pre-process: Compress the audio file to reduce size
        compressed_file = None
        
        print("Compressing audio to improve processing...")
        transcription_jobs[job_id]['progress'] = 20
        compressed_file = os.path.join(temp_dir, "compressed_audio.mp3")
        
        # Compress the audio file
        compress_cmd = [
            'ffmpeg', '-y', '-i', audio_file_path,
            '-ac', '1',                  # Convert to mono
            '-ar', '16000',              # Reduce sample rate to 16kHz
            '-codec:a', 'libmp3lame',    # Use MP3 codec
            '-b:a', '24k',               # Very low bitrate
            compressed_file
        ]
            
        try:
            subprocess.run(compress_cmd, capture_output=True)
            
            if os.path.exists(compressed_file):
                compressed_size = os.path.getsize(compressed_file) / (1024 * 1024)
                print(f"Compressed file size: {compressed_size:.2f}MB")
                
                # If compression brought the file under the limit, try processing it directly
                if compressed_size < 25:
                    print("Compression successful, trying to process the entire compressed file...")
                    transcription_jobs[job_id]['progress'] = 30
                    
                    with open(compressed_file, "rb") as audio_file:
                        try:
                            response = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                response_format="text",
                                timeout=60
                            )
                            transcription_jobs[job_id]['status'] = 'completed'
                            transcription_jobs[job_id]['progress'] = 100
                            transcription_jobs[job_id]['result'] = response
                            
                            # Clean up
                            os.unlink(compressed_file)
                            os.rmdir(temp_dir)
                            return
                        except Exception as e:
                            print(f"Compressed file transcription failed: {e}")
                            # Continue with segmentation
                
                # Use the compressed file for splitting
                audio_file_path = compressed_file
                file_size = compressed_size
                num_chunks = math.ceil(file_size / chunk_size_mb)
        except Exception as e:
            print(f"Compression failed: {e}")
            # Continue with original file
        
        # If ffmpeg failed or is not available, try fallback methods
        # This is just a summary - your existing fallback methods would go here
        transcription_jobs[job_id]['progress'] = 85
        transcription_jobs[job_id]['status'] = 'failed'
        transcription_jobs[job_id]['error'] = "Processing failed. Transcription service is temporarily unavailable."
        
        # Clean up
        try:
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                os.rmdir(temp_dir)
        except Exception as e:
            print(f"Error cleaning up temporary files: {e}")
            
    except Exception as e:
        print(f"Error in audio processing: {e}")
        transcription_jobs[job_id]['status'] = 'failed'
        transcription_jobs[job_id]['error'] = str(e)

def audio_to_text(audio_file_path):
    """
    Synchronous version of transcription for backward compatibility.
    Not recommended for large files.
    """
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Process directly in the current thread
    process_audio_job(audio_file_path, job_id)
    
    # Get the result
    if transcription_jobs[job_id]['status'] == 'completed':
        return transcription_jobs[job_id]['result']
    else:
        raise Exception(transcription_jobs[job_id].get('error', 'Transcription failed'))

# Cleanup function
def cleanup_temp_files(temp_dir):
    try:
        for file in os.listdir(temp_dir):
            os.unlink(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)
    except Exception as e:
        print(f"Error cleaning up temporary files: {e}")