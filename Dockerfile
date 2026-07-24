FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_DATA_DIR=/data

WORKDIR /app

RUN groupadd --gid 10001 grounded \
    && useradd --uid 10001 --gid grounded --create-home --shell /usr/sbin/nologin grounded

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads /data/backups /app/staticfiles \
    && chown -R grounded:grounded /data /app

USER grounded

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
