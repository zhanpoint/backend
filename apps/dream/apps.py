from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class DreamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dream'