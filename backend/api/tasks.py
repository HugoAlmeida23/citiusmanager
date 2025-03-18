from celery import shared_task
import logging
from .webscrapping import scrape_citius_data, test_citius_login

logger = logging.getLogger(__name__)

@shared_task
def scheduled_citius_scrape():
    """
    Tarefa Celery para executar o webscraping do Citius de forma agendada
    """
    try:
        logger.info("Iniciando tarefa agendada de scraping do Citius")
        new_records, new_not = scrape_citius_data()
        logger.info(f"Novos registros: {new_records}, Novos encontrados: {new_not}")
        logger.info(f"Tarefa concluída. {new_records} novos registros adicionados.")
        return new_records  # Return just the number for simplicity
    except Exception as e:
        logger.error(f"Erro na tarefa agendada: {str(e)}")
        raise

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