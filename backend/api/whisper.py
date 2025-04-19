import os
import tempfile
import subprocess
import json
import time
import uuid
import threading
import requests
from pathlib import Path

# Dictionary to store job status and results
transcription_jobs = {}
# Add a lock to prevent race conditions when accessing the dictionary
jobs_lock = threading.Lock()

def get_job_status(job_id):
    """
    Get the current status of a transcription job
    """
    with jobs_lock:
        if job_id not in transcription_jobs:
            return None
        
        return transcription_jobs[job_id].copy()

def audio_to_text_async(audio_file_path):
    """
    Start an asynchronous transcription job.
    Returns a job ID that can be used to check progress.
    """
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job status with lock
    with jobs_lock:
        transcription_jobs[job_id] = {
            'status': 'processing',
            'progress': 0,
            'result': None,
            'error': None,
            'file_size': "0.00MB"
        }
    
    # Start processing in a separate thread
    thread = threading.Thread(
        target=process_audio_job,
        args=(audio_file_path, job_id)
    )
    thread.daemon = True
    thread.start()
    
    return job_id

def process_audio_job(audio_file_path, job_id):
    """
    Process the audio transcription job using AssemblyAI
    """
    temp_dir = None
    compressed_file = None
    
    try:
        # Get file size in MB
        file_size = os.path.getsize(audio_file_path) / (1024 * 1024)
        
        # Update job status with lock
        with jobs_lock:
            transcription_jobs[job_id]['file_size'] = f"{file_size:.2f}MB"
            transcription_jobs[job_id]['progress'] = 10
        
        # Initialize AssemblyAI client
        headers = {
            "authorization": os.getenv("ASSEMBLYAI_API_KEY", "")
        }
        
        # Compress the file if it's large to improve upload speed
        if file_size > 30:  # 30MB threshold
            temp_dir = tempfile.mkdtemp()
            compressed_file = os.path.join(temp_dir, "compressed_audio.mp3")
            
            # Compress the audio file
            compress_cmd = [
                'ffmpeg', '-y', '-i', audio_file_path,
                '-ac', '1',                  # Convert to mono
                '-ar', '16000',              # Reduce sample rate to 16kHz
                '-codec:a', 'libmp3lame',    # Use MP3 codec
                '-b:a', '32k',               # Low bitrate
                compressed_file
            ]
            
            try:
                subprocess.run(compress_cmd, capture_output=True)
                audio_file_path = compressed_file
            except Exception as e:
                print(f"Compression failed: {e}")
                # Continue with original file
        
        # Upload the file to AssemblyAI
        with jobs_lock:
            transcription_jobs[job_id]['progress'] = 20
            
        with open(audio_file_path, "rb") as f:
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                data=f
            )
            
        if upload_response.status_code != 200:
            raise Exception(f"Upload failed: {upload_response.text}")
            
        audio_url = upload_response.json()["upload_url"]
        
        # Request transcription with diarization
        with jobs_lock:
            transcription_jobs[job_id]['progress'] = 40
            
        data = {
            "audio_url": audio_url,
            "speaker_labels": True,       # Enable diarization (speaker identification)
            "language_code": "pt",        # Use Portuguese
            "punctuate": True,            # Add punctuation
            "format_text": True,          # Format text with proper capitalization
            "word_boost": [],             # Boost specific words if needed
        }
        
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json=data,
            headers=headers
        )
        
        if transcript_response.status_code != 200:
            raise Exception(f"Transcription request failed: {transcript_response.text}")
            
        transcript_id = transcript_response.json()['id']
        
        # Poll for results
        completed = False
        retry_count = 0
        max_retries = 100
        
        while not completed and retry_count < max_retries:
            with jobs_lock:
                # Calculate dynamic progress based on retries (40-95%)
                progress = min(95, 40 + int(retry_count * 55 / max_retries))
                transcription_jobs[job_id]['progress'] = progress
            
            # Get the status of the transcription
            polling_response = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers
            )
            
            if polling_response.status_code != 200:
                retry_count += 1
                time.sleep(3)
                continue
                
            polling_result = polling_response.json()
            status = polling_result['status']
            
            if status == 'completed':
                # Transcription is ready
                result = polling_result
                
                # Update status with lock
                with jobs_lock:
                    transcription_jobs[job_id]['status'] = 'completed'
                    transcription_jobs[job_id]['progress'] = 100
                    transcription_jobs[job_id]['result'] = result
                
                completed = True
            
            elif status == 'error':
                error_message = polling_result.get('error', 'Unknown error occurred')
                with jobs_lock:
                    transcription_jobs[job_id]['status'] = 'failed'
                    transcription_jobs[job_id]['error'] = error_message
                
                completed = True
            
            elif status in ['queued', 'processing']:
                # Still processing
                retry_count += 1
                time.sleep(3)
            
            else:
                with jobs_lock:
                    transcription_jobs[job_id]['status'] = 'failed'
                    transcription_jobs[job_id]['error'] = f"Unknown status: {status}"
                
                completed = True
        
        # Check if we exceeded retry limit
        if retry_count >= max_retries and not completed:
            with jobs_lock:
                transcription_jobs[job_id]['status'] = 'failed'
                transcription_jobs[job_id]['error'] = "Processing timed out"
        
    except Exception as e:
        error_msg = f"Error in audio processing: {e}"
        print(error_msg)
        
        with jobs_lock:
            if job_id in transcription_jobs:
                transcription_jobs[job_id]['status'] = 'failed'
                transcription_jobs[job_id]['error'] = error_msg
            else:
                transcription_jobs[job_id] = {
                    'status': 'failed',
                    'progress': 0,
                    'result': None,
                    'error': error_msg,
                    'file_size': "0.00MB"
                }
    
    finally:
        # Clean up
        try:
            if compressed_file and os.path.exists(compressed_file):
                os.unlink(compressed_file)
                
            if temp_dir and os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            print(f"Error cleaning up temporary files: {e}")

def audio_to_text(audio_file_path, format_type="text"):
    """
    Synchronous version of transcription with diarization.
    format_type can be "text" (default) or "json" for detailed output with timestamps and speakers
    """
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize the job with lock
    with jobs_lock:
        transcription_jobs[job_id] = {
            'status': 'processing',
            'progress': 0,
            'result': None,
            'error': None,
            'file_size': "0.00MB"
        }
    
    # Process directly in the current thread
    try:
        process_audio_job(audio_file_path, job_id)
    
        # Get the result with lock
        with jobs_lock:
            job_status = transcription_jobs.get(job_id, {}).copy()
        
        if job_status.get('status') == 'completed':
            result = job_status.get('result', "")
            
            # Se o formato solicitado for texto simples
            if format_type == "text" and isinstance(result, dict):
                return result.get("text", "")
            
            return result
        else:
            error_msg = job_status.get('error', "Transcription failed with unknown error")
            raise Exception(error_msg)
    except Exception as e:
        error_msg = str(e)
        if error_msg == job_id:
            error_msg = "Transcription processing failed"
        raise Exception(error_msg)