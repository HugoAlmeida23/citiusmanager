from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Definir o módulo de configurações padrão do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Criar o aplicativo Celery
app = Celery('backend')

# Configurar com base nas configurações do Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carregar tarefas automaticamente dos aplicativos registrados
app.autodiscover_tasks()

# Configurar execuções agendadas - a cada hora
app.conf.beat_schedule = {
    'scrape-citius-every-hour': {
        'task': 'api.tasks.scheduled_citius_scrape',
        'schedule': crontab(minute=0),  # Runs every hour at the top of the hour
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
