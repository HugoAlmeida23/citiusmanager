from celery import shared_task
import logging
from .webscrapping import scrape_citius_data, test_citius_login
from celery.exceptions import SoftTimeLimitExceeded

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, soft_time_limit=600, time_limit=900)
def scheduled_citius_scrape(self):
    """
    Tarefa Celery para executar o webscraping do Citius de forma agendada
    """
    try:
        logger.info("Iniciando tarefa agendada de scraping do Citius")
        new_records, new_not = scrape_citius_data()
        logger.info(f"Novos registros: {new_records}, Novos encontrados: {new_not}")
        logger.info(f"Tarefa concluída. {new_records} novos registros adicionados.")
        return new_records
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded in Citius scraping task")
        raise self.retry(countdown=60*30)  # Retry after 30 minutes
    except Exception as e:
        logger.error(f"Erro na tarefa agendada: {str(e)}")
        

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