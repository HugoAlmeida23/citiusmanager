from celery import shared_task, group
import logging
from .webscrapping import test_citius_login, get_chrome_driver, process_account, send_email
from .models import CitiusAccount
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
        try:
            from .documentmanager import document_manager
            document_manager(driver, supabase, account.user_id)
        except Exception as doc_error:
            logger.error(f"Erro ao processar documentos para conta {account_id}: {str(doc_error)}")
        
        # Atualizar timestamp de uso
        account.last_used = timezone.now()
        account.save()
        
        # Enviar email se houver novas notificações
        if new_not and len(new_not) > 0:
            send_notification_email.delay(new_not, email_data)
            
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
        raise self.retry(countdown=300, max_retries=1)
        
    except Exception as e:
        logger.error(f"Erro ao processar conta {account_id}: {str(e)}")
        if driver:
            try:
                driver.save_screenshot(f"/tmp/error_{account_id}_{int(time.time())}.png")
            except:
                pass
        return 0
        
    finally:
        # Garantir que o driver seja fechado
        if driver:
            try:
                driver.quit()
                logger.info(f"Driver fechado para conta {account_id}")
            except Exception as quit_error:
                logger.error(f"Erro ao fechar driver: {str(quit_error)}")

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