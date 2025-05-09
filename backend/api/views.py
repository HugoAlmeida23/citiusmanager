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
from .serializers import CitiusAccountSerializer, PasswordChangeSerializer
from .tasks import scheduled_citius_scrape, test_citius_account
from django.http import HttpResponse
from .whisper import audio_to_text
from .models import CitiusAccountEmail
from .serializers import CitiusAccountEmailSerializer
from rest_framework import status
from .toggl_notion_utils import (
    extrair_id, 
    get_lastupdate, 
    get_credentials, 
    post_project_summary,
    get_user_details,
    togll_run,
    process_toggl_data,
    getPageID,
    write_from_toggl,
    write_dates_json
)
import os
import json
from pathlib import Path
from django.conf import settings
from .toggl_notion_utils import get_lastupdate


logger = logging.getLogger('citius-app')

SUPABASE_URL = "https://shzvugthjndlagxlcowp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNoenZ1Z3Roam5kbGFneGxjb3dwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MDUyMDk1NywiZXhwIjoyMDU2MDk2OTU3fQ.bmJ7wr2uCPdy1RIqW2A2Xmk0bcx6zjiBYb8NszzadsM"

# Initialize Supabase client (not used for file upload directly but may be used for DB interaction)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        
@api_view(['GET'])
def transcription_status(request, job_id):
    """
    API view to check the status of an ongoing transcription job
    """
    from .whisper import get_job_status
    
    # Obter status do job
    job_status = get_job_status(job_id)
    
    if job_status is None:
        return Response({"error": "Job not found"}, status=404)
    
    return Response(job_status)

@csrf_exempt
def upload_audio(request):
    """
    API view to handle audio file upload and transcription with diarization
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
            
            # Verificar se o formato JSON foi solicitado
            output_format = request.POST.get('format', 'text')  # 'text' ou 'json'
            
            # Verificar tamanho do arquivo para determinar processamento síncrono ou assíncrono
            file_size = os.path.getsize(temp_file_path) / (1024 * 1024)  # tamanho em MB
            
            # Para arquivos grandes (acima de 5MB), usamos processamento assíncrono
            if file_size > 5:
                from .whisper import audio_to_text_async
                
                # Start async processing and get job ID
                job_id = audio_to_text_async(temp_file_path)
                
                # Return job ID for polling
                return JsonResponse({
                    'status': 'processing',
                    'job_id': job_id,
                    'file_size': f"{file_size:.2f}MB"
                })
            else:
                # Para arquivos pequenos, processamento síncrono 
                try:
                        from .whisper import audio_to_text
                        transcription = audio_to_text(temp_file_path, format_type=output_format)
                        
                        # Delete the temporary file
                        if temp_file_path and os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)
                            temp_file_path = None
                        
                        # Return the transcription
                        return JsonResponse({
                            'transcription': transcription,
                            'format': output_format
                        })
                        
                except Exception as e:
                        # Log the detailed error
                        import traceback
                        error_msg = str(e)
                        print(f"Error in upload_audio: {error_msg}")
                        print(traceback.format_exc())
                        
                        # Clean user-facing error message
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


# Função last_update atualizada para buscar os dados específicos do usuário

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def last_update(request):
    """
    Endpoint para obter informações sobre a última atualização
    """
    try:
        user_id = request.user.id
        user_update_file = f'user_{user_id}_lastupdate.json'
        start_date = None
        end_date = None
        
        if not start_date or not end_date:
            try:
                # Baixar do Supabase
                response = supabase.storage.from_('updates').download(user_update_file)
                logger.info(f"result of updating in the supabase: {response}")
                # Decodificar e carregar como JSON
                update_data = json.loads(response.decode('utf-8'))
                start_date = update_data.get('start')
                end_date = update_data.get('end')
            except Exception as e:
                # Se não encontrar no Supabase, tentar o arquivo padrão
                fallback_start, fallback_end = get_lastupdate()
                start_date = fallback_start
                end_date = fallback_end
        
        if start_date and end_date:
            return Response({
                "success": True,
                "start_date": start_date,
                "end_date": end_date
            })
        else:
            return Response({
                "success": False,
                "message": "Nenhuma atualização registrada"
            })
    except Exception as e:
        return Response({
            "success": False,
            "message": f"Erro ao buscar última atualização: {str(e)}"
        }, status=500)
# Função import_toggl_data atualizada para usar as credenciais específicas do usuário

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_toggl_data(request):
    """
    Endpoint para importar dados do Toggl para o Notion
    """
    try:
        # Obter os dados do corpo da requisição
        notion_database_id = request.data.get('notion_database_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        logger.info(f"Dados recebidos: {notion_database_id}, {start_date}, {end_date}")
        # Validar os dados de entrada
        if not notion_database_id or not start_date or not end_date:
            return Response({
                "success": False,
                "message": "Parâmetros obrigatórios ausentes: notion_database_id, start_date, end_date"
            }, status=400)
        
        # Extrair ID limpo do Notion se vier como URL
        notion_database_id = extrair_id(notion_database_id)
        
        # Obter credenciais específicas do usuário
        user_id = request.user.id
        credentials = get_credentials(user_id)
        
        # Se as credenciais específicas do usuário não forem encontradas, tentar credenciais padrão
        if not credentials:
            credentials = get_credentials()
            
        if not credentials:
            return Response({
                "success": False,
                "message": "Falha ao obter credenciais. Configure suas credenciais primeiro."
            }, status=500)
        
        valid_email = credentials['email']
        valid_password = credentials['password']
        notion_token = credentials['token']
        workspace_id = credentials['workspace']
        logger.info(f"Credenciais obtidas: {valid_email}, {notion_token}, {workspace_id}, {start_date}, {end_date}, {notion_database_id}")

        from notion_client import Client
        client = Client(auth=notion_token)
        
        # Obter dados do Toggl
        summary_data = post_project_summary(valid_email, valid_password, workspace_id, start_date, end_date)
        data = get_user_details(valid_email, valid_password, workspace_id)
        toggl_original_data = togll_run(start_date, end_date, valid_email, valid_password, workspace_id)
        
        # Processar dados do Toggl
        data_processed = process_toggl_data(summary_data, data, toggl_original_data, valid_email, valid_password, workspace_id)
        
        # Obter informações das páginas do Notion
        notion_info, notion_info_file = getPageID(client, notion_database_id)
        
        # Escrever os dados do Toggl no Notion
        write_from_toggl(data_processed, client, notion_database_id, notion_info)
        
        # Salvar as datas da última atualização para este usuário
        user_update_file = f'user_{user_id}_lastupdate.json'
        
        
        # Em produção, salvar no Supabase
    
        
        # Converter para string JSON e depois para bytes
        update_json = json.dumps({
            "start": start_date,
            "end": end_date,
        })
        update_bytes = update_json.encode('utf-8')
        
        # Enviar para o Supabase
        try:
            # Try to delete the file first (ignore errors if it doesn't exist)
            try:
                supabase.storage.from_('updates').remove([user_update_file])
                logger.info(f"Arquivo de atualização anterior removido: {user_update_file}")
            except Exception as e:
                logger.info(f"Arquivo não existia ou erro ao remover: {str(e)}")
            
            # Then upload the new file
            supabase.storage.from_('updates').upload(
                user_update_file,
                update_bytes,
                {'content-type': 'application/json'}
            )
            logger.info(f"Novo arquivo de atualização criado: {user_update_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar dados de atualização: {str(e)}")
            # Continue execution, as this isn't critical
                
        # Retornar sucesso
        return Response({
            "success": True,
            "message": "Dados importados com sucesso",
            "projects": data_processed
        })
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({
            "success": False,
            "message": f"Erro durante a importação: {str(e)}"
        }, status=500)     

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_credentials(request):
    """
    Verifica se as credenciais Toggl/Notion já estão configuradas para o usuário
    """
    # Definir o caminho do arquivo de credenciais
    # Usamos o ID do usuário para garantir que cada usuário tenha suas próprias credenciais
    user_id = request.user.id
    credentials_file = f'user_{user_id}_info.json'
    
    # Verificar se o arquivo existe no bucket do Supabase
    file_exists = False
    
    try:
        # Add this logic to ensure the bucket exists
        try:
            supabase.storage.create_bucket('credentials') 
            logger.info("Bucket 'credentials' created successfully.")
        except Exception as e:
            # Handle case where bucket already exists
            pass
            logger.info(f"Bucket 'credentials' already exists or could not be created: {e}")
        
        # Verificar se o arquivo existe no bucket
        response = supabase.storage.from_('credentials').list()
        logger.info(f"result of creating credentials in the supabase: {response}")

        file_list = [item['name'] for item in response]
        file_exists = credentials_file in file_list
    
    except Exception as e:
        print(f"Erro ao verificar credenciais: {str(e)}")
        file_exists = False
    
    return Response({
        "exists": file_exists
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_credentials(request):
    """
    Salva as credenciais Toggl/Notion do usuário
    """
    # Obter dados da requisição
    email = request.data.get('email')
    password = request.data.get('password')
    token = request.data.get('token')
    workspace = request.data.get('workspace')
    
    # Validar os campos obrigatórios
    if not email or not password or not token or not workspace:
        return Response({
            "success": False,
            "message": "Todos os campos são obrigatórios"
        }, status=400)
    
    # Criar objeto de credenciais
    credentials = {
        "email": email,
        "password": password,
        "token": token,
        "workspace": workspace
    }
    
    # Salvar as credenciais
    user_id = request.user.id
    credentials_file = f'user_{user_id}_info.json'
    
    try:
        
      
        
        # Converter para string JSON e depois para bytes
        json_str = json.dumps(credentials)
        json_bytes = json_str.encode('utf-8')
        
        # Enviar para o Supabase
        supabase.storage.from_('credentials').upload(
            credentials_file,
            json_bytes,
            {'content-type': 'application/json'}
        )
        
        return Response({
            "success": True,
            "message": "Credenciais salvas com sucesso"
        })
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({
            "success": False,
            "message": f"Erro ao salvar credenciais: {str(e)}"
        }, status=500)

# Modificar a função get_credentials em toggl_notion_utils.py para ler o arquivo do usuário

def get_credentials(user_id=None):
    """
    Obter credenciais do arquivo info.json ou do arquivo específico do usuário
    """
    try:
        # Se o user_id for fornecido, tentar ler o arquivo específico do usuário
        if user_id:
            credentials_file = f'user_{user_id}_info.json'
            
            # Se não encontrar localmente, tentar no Supabase
            try:
                
                
                # Baixar do Supabase
                response = supabase.storage.from_('credentials').download(credentials_file)
                
                # Decodificar e carregar como JSON
                credentials_json = json.loads(response.decode('utf-8'))
                return credentials_json
            except Exception as e:
                print(f"Erro ao obter credenciais do Supabase: {e}")
                # Se falhar no Supabase, tentar o arquivo padrão
                pass
        
        # Fallback para o arquivo info.json padrão
        with open('info.json', 'r') as handler:
            info = json.load(handler)
        
        return {
            'email': info.get('email', ''),
            'password': info.get('password', ''),
            'token': info.get('token', ''),
            'workspace': info.get('workspace', '')
        }
    except Exception as e:
        print(f"Erro ao obter credenciais: {e}")
        return None
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    API view to handle changing user's password
    """
    serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Senha alterada com sucesso."}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)