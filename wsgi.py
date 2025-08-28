# wsgi.py
from app import create_app

# Gunicorn application
application = create_app()