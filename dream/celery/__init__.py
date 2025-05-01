"""Celery应用包"""
from dream.celery.app import app as celery_app

# celery 包的入口点，导出 celery 应用实例
__all__ = ['celery_app'] 