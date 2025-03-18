from celery.result import AsyncResult
from django.contrib.auth.models import User
from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .serializers import UserSerializer, ProcessoSerializer
from supabase import create_client, Client
from django.conf import settings
from .models import Processo
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
import json
import logging
import tempfile
import os
from rest_framework.decorators import api_view
from .models import CitiusAccount
from .serializers import CitiusAccountSerializer
from .tasks import scheduled_citius_scrape, test_citius_account
from django.http import HttpResponse
from .whisper import audio_to_text

logger = logging.getLogger('citius-app')


# Initialize Supabase client (not used for file upload directly but may be used for DB interaction)
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ACCESS_KEY  # Only two arguments needed for the Supabase client
)

logger = logging.getLogger('citius-app')

@csrf_exempt
def upload_audio(request):
    """
    API view to handle audio file upload and transcription
    """
    if request.method == 'POST':
        # Check if a file is in the request
        if 'audio_file' not in request.FILES:
            return JsonResponse({'error': 'No audio file provided'}, status=400)
        
        audio_file = request.FILES['audio_file']
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as temp_file:
            # Write the uploaded file to the temporary file
            for chunk in audio_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        try:
            # Process the audio file
            transcription = audio_to_text(temp_file_path)
            
            # Delete the temporary file
            os.unlink(temp_file_path)
            
            # Return the transcription
            return JsonResponse({'transcription': transcription})
        
        except Exception as e:
            # Delete the temporary file in case of error
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def download_transcription(request):
    """
    View to download the transcription as a text file
    """
    if request.method == 'POST':
        transcription = request.POST.get('transcription', '')
        
        # Create a response with the transcription as a text file
        response = HttpResponse(transcription, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="transcription.txt"'
        
        return response
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
@api_view(['POST'])
def refresh_notifications(request):
    """
    Endpoint to trigger the Citius scraper and refresh notifications
    """
    try:    
        # Em vez de chamar diretamente, iniciamos uma tarefa Celery assíncrona
        task = scheduled_citius_scrape.delay()
        
        # Retornar imediatamente com o ID da tarefa
        return JsonResponse({
            'status': 'success',
            'message': 'Refresh notifications task started',
            'task_id': task.id
        })
    except Exception as e:
        logger.error(f"Error starting refresh task: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to start refresh task: {str(e)}'
        }, status=500)
        
@require_GET
def task_status(request, task_id):
    """
    Check the status of a Celery task and return its result if completed
    """
    try:
        task = AsyncResult(id=task_id)
        
        if task.ready():
            if task.successful():
                # Task completed successfully
                result = task.result
                # The result should now directly be the number of records
                new_records = result
                
                # Add logging to help debug
                logger.info(f"Task completed successfully. Result: {result}, Type: {type(result)}")
                
                return JsonResponse({
                    'status': 'completed',
                    'new_records': new_records
                })
            else:
                # Task failed
                logger.error(f"Task failed with error: {task.result}")
                return JsonResponse({
                    'status': 'failed',
                    'error': str(task.result)
                })
        else:
            # Task still in progress
            return JsonResponse({
                'status': 'pending'
            })
            
    except Exception as e:
        logger.error(f"Error checking task status: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to check task status: {str(e)}'
        }, status=500)
        
# API endpoint to test a single account
@api_view(['POST'])
def test_account(request):
    """
    Test a single Citius account to verify credentials
    """
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return Response({
                'status': 'error',
                'message': 'Username and password are required'
            }, status=400)
        
        # Iniciar uma tarefa assíncrona para testar a conta
        task = test_citius_account.delay(username, password)
        
        # Para este caso, vamos aguardar o resultado
        # Isso é aceitável porque o teste de login é rápido
        result = task.get(timeout=30)
        
        if result['success']:
            return Response({
                'status': 'success',
                'message': 'Login successful'
            })
        else:
            return Response({
                'status': 'error',
                'message': result['message']
            }, status=400)
    except Exception as e:
        logger.error(f"Error testing account: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to test account: {str(e)}'
        }, status=500)
            
class ProcessoListCreate(generics.ListCreateAPIView):
    serializer_class = ProcessoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Only return objects that belong to the current user
        return Processo.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Automatically set the user field to the current user
        serializer.save(user=self.request.user)
            
    
                    
class ProcessoDelete(generics.DestroyAPIView):
    serializer_class = ProcessoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Processo.objects.all()
    
# Create your views here.
class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
# Updated CitiusAccountViewSet - Fix for the router registration error
class CitiusAccountViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Citius accounts
    """
    serializer_class = CitiusAccountSerializer
    permission_classes = [IsAuthenticated]
    # Define a queryset attribute to fix the router registration error
    queryset = CitiusAccount.objects.all()
    
    def get_queryset(self):
        # Override to filter by current user
        return CitiusAccount.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Automatically set the user field to the current user
        serializer.save(user=self.request.user)