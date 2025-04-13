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
from rest_framework.decorators import api_view, permission_classes
from .models import CitiusAccount
from .serializers import CitiusAccountSerializer
from .tasks import scheduled_citius_scrape, test_citius_account
from django.http import HttpResponse
from .whisper import audio_to_text
from .models import CitiusAccountEmail
from .serializers import CitiusAccountEmailSerializer
from rest_framework import status


logger = logging.getLogger('citius-app')


# Initialize Supabase client (not used for file upload directly but may be used for DB interaction)
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ACCESS_KEY  # Only two arguments needed for the Supabase client
)

logger = logging.getLogger('citius-app')


# Adicione essa classe ao arquivo views.py
class CitiusAccountEmailViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing additional emails for Citius accounts
    """
    serializer_class = CitiusAccountEmailSerializer
    permission_classes = [IsAuthenticated]
    queryset = CitiusAccountEmail.objects.all()
    
    def get_queryset(self):
        # Filtrar por usuário atual através da conta associada
        return CitiusAccountEmail.objects.filter(account__user=self.request.user)
    
    def perform_create(self, serializer):
        # Garantir que a conta pertence ao usuário atual
        account_id = self.request.data.get('account')
        if account_id:
            try:
                account = CitiusAccount.objects.get(id=account_id, user=self.request.user)
                serializer.save(account=account)
            except CitiusAccount.DoesNotExist:
                raise serializers.ValidationError("Conta Citius não encontrada ou não pertence ao usuário atual")
        else:
            raise serializers.ValidationError("É necessário especificar uma conta Citius")

# Endpoint para gerenciar emails de uma conta específica
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def account_emails(request, account_id):
    """
    GET: Lista todos os emails adicionais de uma conta
    POST: Adiciona um novo email a uma conta
    DELETE: Remove um email de uma conta
    """
    try:
        account = CitiusAccount.objects.get(id=account_id, user=request.user)
    except CitiusAccount.DoesNotExist:
        return Response(
            {"error": "Conta Citius não encontrada ou não pertence ao usuário atual"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        emails = CitiusAccountEmail.objects.filter(account=account)
        serializer = CitiusAccountEmailSerializer(emails, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        # Adicionar email à conta
        email = request.data.get('email')
        
        if not email:
            return Response(
                {"error": "O campo 'email' é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se já existe
        if CitiusAccountEmail.objects.filter(account=account, email=email).exists():
            return Response(
                {"error": "Este email já está registrado para esta conta"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_email = CitiusAccountEmail.objects.create(
            account=account,
            email=email,
            is_active=request.data.get('is_active', True)
        )
        
        serializer = CitiusAccountEmailSerializer(new_email)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    elif request.method == 'DELETE':
        # Remover email da conta
        email_id = request.data.get('email_id')
        
        if not email_id:
            return Response(
                {"error": "O campo 'email_id' é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            email_obj = CitiusAccountEmail.objects.get(id=email_id, account=account)
            email_obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CitiusAccountEmail.DoesNotExist:
            return Response(
                {"error": "Email não encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )
        
@csrf_exempt
def upload_audio(request):
    """
    API view to handle audio file upload and transcription
    """
    if request.method == 'POST':
        temp_file_path = None
        try:
            # Check if a file is in the request
            if 'audio_file' not in request.FILES:
                return JsonResponse({'error': 'No audio file provided'}, status=400)
            
            audio_file = request.FILES['audio_file']
            
            # Validate file size (limit to 100MB to prevent abuse)
            if audio_file.size > 100 * 1024 * 1024:  # 100MB
                return JsonResponse({
                    'error': 'File too large. Maximum file size is 100MB.'
                }, status=400)
            
            # Validate file type
            valid_extensions = ['.mp3', '.m4a', '.wav', '.ogg', '.flac']
            valid_mimetypes = ['audio/mp3', 'audio/mp4', 'audio/mpeg', 'audio/wav', 
                            'audio/ogg', 'audio/flac', 'audio/x-m4a']
                            
            file_ext = os.path.splitext(audio_file.name)[1].lower()
            if file_ext not in valid_extensions and audio_file.content_type not in valid_mimetypes:
                return JsonResponse({
                    'error': 'Invalid file type. Please upload an audio file (mp3, m4a, wav, ogg, flac).'
                }, status=400)
            
            # Create a temporary file with the correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                # Write the uploaded file to the temporary file
                for chunk in audio_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Process the audio file
            try:
                transcription = audio_to_text(temp_file_path)
                
                # Delete the temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    temp_file_path = None
                
                # Return the transcription
                return JsonResponse({'transcription': transcription})
                
            except Exception as e:
                # Log the detailed error
                import traceback
                error_msg = str(e)
                print(f"Error in upload_audio: {error_msg}")
                print(traceback.format_exc())
                
                # Clean user-facing error message
                # If it's just a UUID, provide a more helpful message
                if error_msg and all(c in '0123456789abcdef-' for c in error_msg):
                    error_msg = "Audio processing failed. The file may be too large, corrupted, or in an unsupported format."
                
                return JsonResponse({'error': error_msg}, status=500)
        
        except Exception as e:
            # General exception handler for any other errors
            import traceback
            print(f"Unexpected error in upload_audio: {str(e)}")
            print(traceback.format_exc())
            
            return JsonResponse({
                'error': 'An unexpected error occurred while processing your audio file. Please try again.'
            }, status=500)
            
        finally:
            # Always clean up temp file if it exists
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    print(f"Error deleting temporary file: {str(e)}")
    
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
        # Ordenar por created_at (se existir) ou por id em ordem decrescente
        queryset = Processo.objects.filter(user=self.request.user)
        
        if 'created_at' in [field.name for field in Processo._meta.get_fields()]:
            # Se o campo created_at existe
            return queryset.order_by('-created_at')
        else:
            # Fallback para ordenação por ID
            return queryset.order_by('-id')
    
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
        