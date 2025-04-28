import os
from celery import Celery

# Django'nun settings dosyasını belirtelim
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Celery uygulamasını oluştur
app = Celery('appointment_project')

# Django ayarlarından Celery konfigürasyonlarını yükle
app.config_from_object('django.conf:settings', namespace='CELERY')

# Projedeki bütün task'ları otomatik bulsun
app.autodiscover_tasks()
