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

def preprocess_audio(input_file, output_file):
    """
    Preprocess audio to enhance speech for difficult audio conditions
    """
    # First, check if the input file exists and is readable
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input audio file not found: {input_file}")
    
    # Check if the file is empty
    if os.path.getsize(input_file) == 0:
        raise ValueError(f"Input audio file is empty: {input_file}")
    
    # Simplified preprocessing for better compatibility
    # We'll use a more conservative approach that should work with more file types
    
    # Create temp directory to store intermediate file if needed
    temp_dir = tempfile.mkdtemp()
    normalized_input = os.path.join(temp_dir, "normalized_input.wav")
    
    try:
        # Step 1: First convert to WAV format to ensure compatibility
        conversion_cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            normalized_input
        ]
        
        conversion_result = subprocess.run(
            conversion_cmd, 
            capture_output=True, 
            text=True
        )
        
        if conversion_result.returncode != 0:
            print(f"Error normalizing input format: {conversion_result.stderr}")
            # If conversion fails, try using the original file
            normalized_input = input_file
        
        # Step 2: Apply more conservative audio enhancements
        cmd = [
            'ffmpeg', '-y', '-i', normalized_input,
            # Simple filter chain that should be more compatible
            '-af', 'highpass=f=80,lowpass=f=8000,volume=1.5',
            # Convert to mono and 16kHz (optimal for speech recognition)
            '-ac', '1', '-ar', '16000',
            # Use a high quality for the processing
            '-acodec', 'libmp3lame', '-b:a', '64k',
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Check if the command was successful
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            
            # If the enhanced processing fails, try a more minimal approach
            minimal_cmd = [
                'ffmpeg', '-y', '-i', normalized_input,
                # Only convert format, no filters
                '-ac', '1', '-ar', '16000',
                '-acodec', 'libmp3lame', '-b:a', '64k',
                output_file
            ]
            
            minimal_result = subprocess.run(minimal_cmd, capture_output=True, text=True)
            
            if minimal_result.returncode != 0:
                print(f"Minimal FFmpeg processing also failed: {minimal_result.stderr}")
                raise subprocess.CalledProcessError(
                    minimal_result.returncode, 
                    minimal_cmd, 
                    output=minimal_result.stdout, 
                    stderr=minimal_result.stderr
                )
        
        # Verify the output file exists and has content
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            raise Exception("Audio preprocessing failed to produce valid output file")
            
        return output_file
        
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg preprocessing error: {e.stderr}")
        raise
    finally:
        # Clean up temporary files
        if os.path.exists(normalized_input) and normalized_input != input_file:
            try:
                os.unlink(normalized_input)
            except:
                pass
                
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except:
                pass

def process_audio_job(audio_file_path, job_id):
    """
    Process the audio transcription job using AssemblyAI
    """
    temp_dir = None
    processed_file = None
    original_audio_path = audio_file_path  # Store original path
    
    try:
        # Verify the audio file exists
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
        # Get file size in MB
        file_size = os.path.getsize(audio_file_path) / (1024 * 1024)
        
        # Add debug info
        print(f"Processing audio file: {audio_file_path}")
        print(f"File size: {file_size:.2f}MB")
        
        # Update job status with lock
        with jobs_lock:
            transcription_jobs[job_id]['file_size'] = f"{file_size:.2f}MB"
            transcription_jobs[job_id]['progress'] = 5
        
        # Check API key first
        api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
        if not api_key:
            raise ValueError("AssemblyAI API key is missing. Set the ASSEMBLYAI_API_KEY environment variable.")
        
        # Initialize AssemblyAI client
        headers = {
            "authorization": api_key
        }
        
        # Verify API key is valid with a simple request
        print("Verifying API key...")
        test_response = requests.get(
            "https://api.assemblyai.com/v2/account",
            headers=headers
        )
        
        if test_response.status_code != 200:
            raise Exception(f"API key validation failed: {test_response.text}")
        else:
            print("API key verified successfully")
        
        # Create temp directory for preprocessing
        temp_dir = tempfile.mkdtemp()
        processed_file = os.path.join(temp_dir, "enhanced_audio.mp3")
        
        # IMPROVEMENT 1: Always preprocess the audio for difficult conditions
        with jobs_lock:
            transcription_jobs[job_id]['progress'] = 10
            
        """ try:
            # Apply audio enhancement
            print(f"Preprocessing audio to: {processed_file}")
            preprocess_audio(audio_file_path, processed_file)
            
            # Verify the processed file exists and has content
            if not os.path.exists(processed_file) or os.path.getsize(processed_file) == 0:
                raise Exception("Audio preprocessing failed to produce valid output file")
                
            # Use enhanced audio file
            audio_file_path = processed_file
            print("Audio preprocessing successful")
        except Exception as preprocess_error:
            print(f"Warning: Audio preprocessing failed: {preprocess_error}")
            print("Falling back to original audio file")
            # If preprocessing fails, fall back to the original file
            audio_file_path = original_audio_path """
        
        # Upload the enhanced file to AssemblyAI
        with jobs_lock:
            transcription_jobs[job_id]['progress'] = 20
        
        # Improved upload with retry mechanism
        max_upload_retries = 3
        upload_retry_count = 0
        upload_success = False
        
        print(f"Beginning upload to AssemblyAI (file size: {os.path.getsize(audio_file_path)/1024:.2f}KB)")
        
        while not upload_success and upload_retry_count < max_upload_retries:
            try:
                print(f"Upload attempt {upload_retry_count + 1}/{max_upload_retries}...")
                
                # Check file readability before upload
                if not os.access(audio_file_path, os.R_OK):
                    raise IOError(f"File is not readable: {audio_file_path}")
                
                # Read file in binary mode
                with open(audio_file_path, "rb") as f:
                    file_data = f.read()
                    
                    if len(file_data) == 0:
                        raise ValueError(f"File is empty: {audio_file_path}")
                    
                    # Try to upload in chunks for larger files
                    if len(file_data) > 10 * 1024 * 1024:  # If larger than 10MB
                        print("Large file detected, trying chunk upload")
                        # Try the direct upload with chunked encoding
                        upload_response = requests.post(
                            "https://api.assemblyai.com/v2/upload",
                            headers=headers,
                            data=f,  # File object will be read in chunks
                            timeout=120  # Longer timeout for large files
                        )
                    else:
                        # For smaller files, read all into memory
                        print(f"Uploading file ({len(file_data)/1024:.2f}KB)")
                        upload_response = requests.post(
                            "https://api.assemblyai.com/v2/upload",
                            headers=headers,
                            data=file_data,
                            timeout=60
                        )
                    
                # Check response
                if upload_response.status_code == 200:
                    upload_success = True
                    print("Upload successful!")
                else:
                    print(f"Upload attempt {upload_retry_count + 1} failed with status {upload_response.status_code}")
                    print(f"Response content: {upload_response.text}")
                    
                    # If we get a specific error about the file, try another method
                    if "file" in upload_response.text.lower():
                        print("Trying alternative upload method...")
                        
                        # Create a temporary file for multipart upload
                        temp_upload_file = os.path.join(temp_dir, "upload_file.mp3")
                        with open(temp_upload_file, "wb") as tf:
                            # Copy the file content
                            with open(audio_file_path, "rb") as src_file:
                                tf.write(src_file.read())
                        
                        # Try multipart form upload instead
                        with open(temp_upload_file, "rb") as f:
                            files = {'file': (os.path.basename(temp_upload_file), f, 'audio/mpeg')}
                            alternative_response = requests.post(
                                "https://api.assemblyai.com/v2/upload",
                                headers=headers,
                                files=files,
                                timeout=60
                            )
                            
                            if alternative_response.status_code == 200:
                                upload_response = alternative_response
                                upload_success = True
                                print("Alternative upload successful!")
                            else:
                                print(f"Alternative upload also failed: {alternative_response.status_code}: {alternative_response.text}")
                    
                    if not upload_success:
                        upload_retry_count += 1
                        time.sleep(5)  # Longer wait before retrying
                        
            except Exception as e:
                print(f"Upload attempt {upload_retry_count + 1} failed with exception: {str(e)}")
                upload_retry_count += 1
                time.sleep(5)  # Longer wait before retrying
        
        if not upload_success:
            raise Exception(f"Upload failed after {max_upload_retries} attempts")
            
        audio_url = upload_response.json()["upload_url"]
        print(f"Audio URL received: {audio_url}")
        
        # Request transcription with diarization
        with jobs_lock:
            transcription_jobs[job_id]['progress'] = 40
            
        # IMPROVEMENT 2: Enhanced parameters for difficult audio conditions
        data = {
            "audio_url": audio_url,
            "speaker_labels": True,  # This enables diarization
            "language_code": "pt", 
            "punctuate": True,
            "format_text": True,
            # IMPROVEMENT 4: Greatly expanded word_boost with courtroom terminology
            "word_boost": [
                # Court personnel
                "juiz", "advogado", "advogada", "promotor", "promotora", "defensora", "defensor", 
                "escrivão", "escrivã", "oficial", "perito", "perita", "testemunha", "depoente",
                
                # Formal address
                "doutor", "doutora", "excelência", "meritíssimo", "meritíssima", "senhor", "senhora", 
                "vossa", "excelentíssimo", "excelentíssima", "ilustríssimo", "ilustríssima",
                
                # Parties
                "autor", "autora", "réu", "ré", "requerente", "requerido", "requerida", "agravante",
                "agravado", "agravada", "reclamante", "reclamado", "reclamada", "querelante", "querelado",
                
                # Legal terms
                "tribunal", "processo", "sentença", "defesa", "acusação", "audiência", "prévia", "articulados",
                "saneador", "impercetível", "relação", "contratual", "estabelecida", "intervenção", "mencionado",
                "jurisprudência", "precedente", "acórdão", "despacho", "habeas corpus", "mandado", "liminar",
                "intimação", "citação", "auto", "autos", "diligência", "sustentação", "julgamento", "sessão",
                "plenário", "câmara", "turma", "instância", "recurso", "apelação", "agravo", "embargo",
                "prova", "testemunhal", "documental", "pericial", "exordial", "contestação", "réplica",
                "tréplica", "alegações", "memoriais", "procedente", "improcedente", "provimento", "desprovimento",
                
                
                # Common procedural phrases
                "sem prejuízo", "resultar", "notificar", "contrária", "posição", "prosseguir", "esclarecer",
                "marcar", "não costumo", "algumas dúvidas", "por escrito", "vista dos autos", "oitiva",
                "depoimento", "interrogatório", "em seguida", "adiamento", "suspensão", "para constar",
                "para registro", "procrastinação", "dilação", "prazo", "preclusão", "prescrição", "decadência",
                
                # Transition words commonly used
                "portanto", "entretanto", "contudo", "todavia", "outrossim", "ademais", "neste diapasão",
                "data venia", "não obstante", "conforme", "consoante", "segundo", "a priori", "a posteriori",
                "in limine", "ex officio", "in dubio", "jus postulandi", "sub judice", "mutatis mutandis"
            ],
            
            # IMPROVEMENT 5: Adjust speech parameters for low quality audio
            "filter_profanity": False,
            "speech_threshold": 0.1,  # Slightly higher than default to reduce false positives in noisy audio
            "boost_param": "high"
        }

        # Add retry logic for transcription request
        max_transcript_retries = 3
        transcript_retry_count = 0
        transcript_success = False
        
        while not transcript_success and transcript_retry_count < max_transcript_retries:
            try:
                transcript_response = requests.post(
                    "https://api.assemblyai.com/v2/transcript",
                    json=data,
                    headers=headers,
                    timeout=30  # 30-second timeout
                )
                
                if transcript_response.status_code == 200:
                    transcript_success = True
                else:
                    print(f"Transcript request attempt {transcript_retry_count + 1} failed with status {transcript_response.status_code}: {transcript_response.text}")
                    transcript_retry_count += 1
                    time.sleep(2)  # Wait before retrying
            except requests.exceptions.RequestException as e:
                print(f"Transcript request attempt {transcript_retry_count + 1} failed with exception: {e}")
                transcript_retry_count += 1
                time.sleep(2)  # Wait before retrying
        
        if not transcript_success:
            raise Exception(f"Transcription request failed after {max_transcript_retries} attempts")
            
        transcript_id = transcript_response.json()['id']
        
        # Poll for results
        completed = False
        retry_count = 0
        max_retries = 150  # IMPROVEMENT 6: Increased max retries for longer processing time
        
        while not completed and retry_count < max_retries:
            with jobs_lock:
                # Calculate dynamic progress based on retries (40-95%)
                progress = min(95, 40 + int(retry_count * 55 / max_retries))
                transcription_jobs[job_id]['progress'] = progress
            
            # Get the status of the transcription
            try:
                polling_response = requests.get(
                    f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                    headers=headers,
                    timeout=30  # 30-second timeout
                )
                
                if polling_response.status_code != 200:
                    print(f"Polling attempt {retry_count + 1} failed with status {polling_response.status_code}")
                    retry_count += 1
                    time.sleep(3)
                    continue
                    
                polling_result = polling_response.json()
                status = polling_result['status']
                
                if status == 'completed':
                    # Transcription is ready
                    result = polling_result
                    
                    # IMPROVEMENT 7: Basic post-processing of transcription text
                    if 'text' in result:
                        # Fix common issues in low quality transcriptions
                        text = result['text']
                        # Replace multiple spaces with a single space
                        text = ' '.join(text.split())
                        # Fix missing spaces after punctuation
                        for punct in ['.', ',', ';', ':', '!', '?']:
                            text = text.replace(f"{punct}", f"{punct} ")
                            text = text.replace(f"{punct}  ", f"{punct} ")
                        # Restore proper capitalization after sentences
                        for end_punct in ['.', '!', '?']:
                            parts = text.split(f"{end_punct} ")
                            for i in range(1, len(parts)):
                                if parts[i] and parts[i][0].islower():
                                    parts[i] = parts[i][0].upper() + parts[i][1:]
                            text = f"{end_punct} ".join(parts)
                        
                        result['text'] = text
                    
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
                    
            except requests.exceptions.RequestException as e:
                print(f"Polling attempt {retry_count + 1} failed with exception: {e}")
                retry_count += 1
                time.sleep(3)
        
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
            if processed_file and os.path.exists(processed_file):
                os.unlink(processed_file)
                
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

# IMPROVEMENT 8: Add a new function to split and transcribe in segments
def split_and_transcribe(audio_file_path, segment_duration=90, format_type="text"):
    """
    Split audio into smaller segments and transcribe each separately.
    This can improve results with difficult audio.
    
    segment_duration: Duration of each segment in seconds (default 90 seconds)
    format_type: "text" or "json"
    """
    temp_dir = tempfile.mkdtemp()
    segments = []
    full_result = ""
    
    try:
        # Check if file exists
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
        # Get duration using ffprobe
        probe_cmd = [
            'ffprobe', '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            audio_file_path
        ]
        
        try:
            duration_output = subprocess.check_output(probe_cmd, text=True)
            total_duration = float(duration_output.strip())
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error getting audio duration: {str(e)}")
        
        # Calculate number of segments
        num_segments = int(total_duration / segment_duration) + 1
        
        # Split audio into segments
        for i in range(num_segments):
            start_time = i * segment_duration
            segment_file = os.path.join(temp_dir, f"segment_{i}.mp3")
            
            # Use ffmpeg to extract segment
            split_cmd = [
                'ffmpeg', '-y', '-i', audio_file_path,
                '-ss', str(start_time),
                '-t', str(segment_duration),
                '-acodec', 'libmp3lame',
                '-ar', '16000',
                '-ac', '1',
                segment_file
            ]
            
            try:
                subprocess.run(split_cmd, capture_output=True, check=True)
                # Verify segment file was created successfully
                if os.path.exists(segment_file) and os.path.getsize(segment_file) > 0:
                    segments.append(segment_file)
                else:
                    print(f"Warning: Segment {i+1} was created but appears to be empty")
            except subprocess.CalledProcessError as e:
                print(f"Error creating segment {i+1}: {e.stderr}")
                # Continue with other segments
        
        if not segments:
            raise Exception("Failed to create any valid audio segments")
        
        # Process each segment
        all_results = []
        
        for i, segment_file in enumerate(segments):
            print(f"Processing segment {i+1}/{len(segments)}...")
            
            try:
                segment_result = audio_to_text(segment_file, format_type)
                
                if format_type == "text":
                    all_results.append(segment_result)
                else:
                    # For JSON format, accumulate results
                    all_results.append(segment_result)
            except Exception as e:
                print(f"Error processing segment {i+1}: {e}")
                all_results.append(f"[Erro na transcrição do segmento {i+1}]")
        
        # Combine results
        if format_type == "text":
            full_result = " ".join(all_results)
        else:
            # For JSON format we'd need to merge the utterances and words
            # This is a simplified version - may need more complex merging
            full_result = {"text": " ".join([r.get("text", "") for r in all_results if isinstance(r, dict)])}
            
            # If you want to merge the detailed utterances, that would require
            # adjusting timestamps and other data
        
        return full_result
        
    except Exception as e:
        raise Exception(f"Error in split-and-transcribe: {e}")
        
    finally:
        # Clean up
        for segment in segments:
            if os.path.exists(segment):
                try:
                    os.unlink(segment)
                except:
                    pass
        
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except:
                pass

# Simple function to test API key validity
def test_assemblyai_api_key(api_key=None):
    """
    Test if the AssemblyAI API key is valid.
    Returns (True, None) if valid, (False, error_message) if invalid.
    """
    if api_key is None:
        api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
        
    if not api_key:
        return False, "API key is missing. Set the ASSEMBLYAI_API_KEY environment variable."
        
    headers = {"authorization": api_key}
    
    try:
        response = requests.get(
            "https://api.assemblyai.com/v2/account",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "API key is valid"
        else:
            return False, f"API key validation failed: {response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"Connection error when validating API key: {e}"