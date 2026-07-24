#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py bootstrap_user
python manage.py seed_canonical
python manage.py collectstatic --noinput

exec gunicorn grounded_growth.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --timeout 60 \
    --graceful-timeout 30
