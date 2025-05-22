from celery import shared_task, group
import logging
from .webscrapping import test_citius_login, get_chrome_driver, process_account, send_email
from .models import CitiusAccount, Processo
from django.conf import settings
from django.utils import timezone
from supabase import create_client
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def scheduled_citius_scrape(self):
    """
    Tarefa principal que divide o processamento por conta
    """
    try:
        logger.info("Iniciando tarefa agendada de scraping do Citius")
        
        # Buscar contas ativas
        active_accounts = CitiusAccount.objects.filter(is_active=True)
        
        if not active_accounts.exists():
            logger.warning("Nenhuma conta ativa encontrada.")
            return 0
            
        # Iniciar tarefas individuais para cada conta
        for account in active_accounts:
            process_single_account.delay(account.id)
        
        return f"Iniciadas {active_accounts.count()} subtarefas de processamento"
        
    except Exception as e:
        logger.error(f"Erro ao iniciar tarefas de scraping: {str(e)}")
        return None

@shared_task(bind=True, soft_time_limit=300, time_limit=360, max_retries=2)
def process_single_account(self, account_id):
    """
    Processa uma única conta Citius com limites de tempo menores
    """
    driver = None
    start_time = time.time()
    
    try:
        # Obter a conta
        account = CitiusAccount.objects.get(id=account_id)
        logger.info(f"Processando conta: {account.username}")
        
        # Criar o driver com configurações otimizadas
        options = get_chrome_options()
        driver = get_chrome_driver(options)
        driver.set_page_load_timeout(45)  # 45 segundos máximo por página
        
        # Criar cliente Supabase
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
        
        # Processar a conta para obter notificações
        insert_count, new_not, email_data = process_account(driver, supabase, account)
        
        # Processar os documentos após recuperar notificações
        document_errors = 0
        try:
            from .documentmanager import document_manager
            document_manager(driver, supabase, account.user_id)
        except Exception as doc_error:
            logger.error(f"Erro ao processar documentos para conta {account_id}: {str(doc_error)}")
            document_errors += 1
        
        # Atualizar timestamp de uso
        account.last_used = timezone.now()
        account.save()
        
        # Enviar email se houver novas notificações
        if new_not and len(new_not) > 0:
            send_notification_email.delay(new_not, email_data)
        
        # Verificar e atualizar o status do sistema após processamento da conta
        update_system_status_after_account.delay(account_id)
        
        execution_time = time.time() - start_time
        logger.info(f"Conta {account.username} processada em {execution_time:.2f} segundos. {insert_count} novos registros.")
        return insert_count
        
    except SoftTimeLimitExceeded:
        logger.error(f"Tempo limite excedido ao processar conta {account_id}")
        if driver:
            try:
                driver.save_screenshot(f"/tmp/timeout_error_{account_id}_{int(time.time())}.png")
            except Exception as ss_error:
                logger.error(f"Erro ao salvar screenshot: {str(ss_error)}")
        
        # Atualizar status do sistema para reportar o erro de timeout
        update_system_status_after_account.delay(account_id, error="timeout")
        
        raise self.retry(countdown=300, max_retries=1)
        
    except Exception as e:
        logger.error(f"Erro ao processar conta {account_id}: {str(e)}")
        if driver:
            try:
                driver.save_screenshot(f"/tmp/error_{account_id}_{int(time.time())}.png")
            except:
                pass
        
        # Atualizar status do sistema para reportar o erro
        update_system_status_after_account.delay(account_id, error=str(e))
        
        return 0
        
    finally:
        # Garantir que o driver seja fechado
        if driver:
            try:
                driver.quit()
                logger.info(f"Driver fechado para conta {account_id}")
            except Exception as quit_error:
                logger.error(f"Erro ao fechar driver: {str(quit_error)}")

@shared_task
def update_system_status_after_account(account_id, error=None):
    """
    Verifica e atualiza o status do sistema após o processamento de uma conta.
    Também notifica o responsável caso haja problemas com documentos.
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        from .models import SystemStatus, Processo
        
        # Obter a conta que acabou de ser processada
        account = CitiusAccount.objects.get(id=account_id)
        
        # Verificar se há erros em documentos recentes para esta conta
        threshold_time = timezone.now() - timedelta(hours=1)  # Documentos da última hora
        document_errors = Processo.objects.filter(
            user_id=account.user_id,
            document_status='error',
            created_at__gte=threshold_time
        ).count()
        
        # Obter ou criar objeto de status
        status_obj, created = SystemStatus.objects.get_or_create(id=1)
        
        # Registrar status desta conta específica
        if not status_obj.accounts_status:
            status_obj.accounts_status = {}
        
        account_status = {
            'active': account.last_used > (timezone.now() - timedelta(minutes=30)),
            'last_used': account.last_used.isoformat() if account.last_used else None,
            'advogado': account.advogado,
            'document_errors': document_errors,
            'last_error': error
        }
        
        if isinstance(status_obj.accounts_status, dict):
            status_obj.accounts_status[str(account_id)] = account_status
        else:
            status_obj.accounts_status = {str(account_id): account_status}
        
        # Atualizar contagem total de erros de documento no sistema
        all_document_errors = Processo.objects.filter(document_status='error').count()
        status_obj.document_errors = all_document_errors
        
        # Determinar status geral do sistema
        all_accounts = CitiusAccount.objects.filter(is_active=True)
        threshold_time = timezone.now() - timedelta(minutes=30)
        all_accounts_active = all(
            account.last_used and account.last_used > threshold_time 
            for account in all_accounts if account.last_used
        )
        
        if all_accounts_active and all_document_errors == 0:
            status_obj.status = 'active'
            status_obj.message = 'Sistema funcionando normalmente'
        else:
            status_obj.status = 'inactive'
            
            # Compor mensagem de erro
            error_messages = []
            
            # Contas inativas
            inactive_accounts = [acc.username for acc in all_accounts 
                               if not acc.last_used or acc.last_used <= threshold_time]
            if inactive_accounts:
                error_messages.append(f"Contas inativas: {', '.join(inactive_accounts)}")
            
            # Erros em documentos
            if all_document_errors > 0:
                error_messages.append(f"Erros em documentos: {all_document_errors}")
                
            status_obj.message = ". ".join(error_messages)
        
        # Salvar o status atualizado
        status_obj.last_check = timezone.now()
        status_obj.save()
        
        # Se houver erros de documento para esta conta específica, enviar email para o responsável
        if document_errors > 0 and account.email:
            send_document_error_email.delay(account_id, document_errors)
        
        logger.info(f"Status do sistema atualizado após processar conta {account_id}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao atualizar status do sistema após conta {account_id}: {str(e)}")
        return False
    

@shared_task
def send_document_error_email(account_id, error_count):
    """
    Envia email notificando sobre erros em documentos.
    Verifica se os erros já foram notificados (campo alerted) e atualiza esse campo após enviar o email.
    """
    try:
        # Importar os modelos necessários
        from .models import CitiusAccount, Processo, CitiusAccountEmail
        from django.utils import timezone
        from datetime import timedelta
        
        # Obter a conta
        account = CitiusAccount.objects.get(id=account_id)
        
        # Obter processos com erro recentes que não foram notificados (alerted=False)
        threshold_time = timezone.now() - timedelta(hours=1)
        error_processes = Processo.objects.filter(
            user_id=account.user_id,
            document_status='error',
            created_at__gte=threshold_time,
            alerted=False  # Apenas erros que não foram notificados
        )
        
        # Se não houver processos com erro não notificados, não enviar email
        if not error_processes.exists():
            logger.info(f"Nenhum erro novo para notificar para a conta {account.username}")
            return True
        
        # Conta real de erros não notificados
        non_alerted_count = error_processes.count()
        
        # Preparar dados para o email
        subject = f"Alerta: Erros em {non_alerted_count} documentos Citius"
        
        body = f"Olá {account.advogado},\n\n"
        body += f"Detectamos erros em {non_alerted_count} documentos durante o processamento recente da sua conta Citius.\n\n"
        body += "Detalhes dos processos com erro:\n\n"
        
        for processo in error_processes:
            body += f"Referência: {processo.referencia}\n"
            body += f"Processo: {processo.processo}\n"
            body += f"Erro: {processo.document_error_message or 'Erro não especificado'}\n\n"
        
        body += "O administrador já foi contactado. Aguarde pelo feedback que deverá receber nos próximos momentos.\n\n"
        body += "Atenciosamente,\nHugo Almeida - SoftSolutions"
        
        # Preparar dados de email
        primary_email = {"data": [{"email": account.email}]} if account.email else {"data": []}
        
        # Buscar emails adicionais
        additional_email_objects = CitiusAccountEmail.objects.filter(account=account, is_active=True)
        additional_emails = {
            "data": [{"email": email_obj.email} for email_obj in additional_email_objects]
        }
        
        email_data = {'primary': primary_email, 'additional': additional_emails}
        
        # Enviar o email
        result = send_email(subject, body, email_data, error=True)
        
        if result:
            # Se o email foi enviado com sucesso, marcar os processos como notificados (alerted=True)
            error_processes.update(alerted=True)
            logger.info(f"Email de alerta enviado e {non_alerted_count} processos marcados como notificados para {account.username}")
        else:
            logger.error(f"Falha ao enviar email de alerta para {account.username}")
        
        return result
        
    except Exception as e:
        logger.error(f"Erro ao enviar email de alerta de erros em documentos: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
     
def get_chrome_options():
    """
    Configurações otimizadas para Chrome em modo headless
    """
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-browser-side-navigation')
    
    # Limitar uso de memória
    options.add_argument('--js-flags=--max-old-space-size=512')
    
    # Estratégias de carregamento mais rápidas
    options.page_load_strategy = 'eager'  # Não espera recursos secundários
    
    return options

@shared_task
def send_notification_email(new_not, email_data):
    """
    Tarefa separada apenas para envio de emails
    """
    logger.info(f"Vai enviar email no tasks.py")

    try:
        subject = "Novas notificações Citius"
        body = f"Tem {len(new_not)} novas notificações:\n\n"
        
        # Adicionar detalhes das notificações
        for notification in new_not:
            body += f"Responsável - {notification['advogado']} - {notification['especie']} - {notification['acto']} - {notification['tribunal']} - {notification['unidade']} - {notification['origem']} - {notification['data']}\n"
        
        # Enviar email
        result = send_email(subject, body, email_data)
        return result
    except Exception as e:
        logger.error(f"Erro ao enviar email: {str(e)}")
        return False
    
@shared_task
def test_citius_account(username, password):
    """
    Tarefa Celery para testar as credenciais de uma conta do Citius
    """
    try:
        success, message = test_citius_login(username, password)
        return {
            'success': success,
            'message': message
        }
    except Exception as e:
        logger.error(f"Erro ao testar conta: {str(e)}")
        return {
            'success': False,
            'message': f"Erro: {str(e)}"
        }