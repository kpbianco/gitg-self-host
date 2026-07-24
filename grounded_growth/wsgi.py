import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grounded_growth.settings")

application = get_wsgi_application()
