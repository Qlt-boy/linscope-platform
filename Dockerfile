ARG BASE_IMAGE=docker.1ms.run/library/python:3.12-slim-bookworm
FROM ${BASE_IMAGE}

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NIP_HOST=0.0.0.0 \
    NIP_PORT=1314 \
    NIP_TLS_ENABLED=1 \
    NIP_TLS_CERT=/app/backend/data/tls/server.crt \
    NIP_TLS_KEY=/app/backend/data/tls/server.key \
    NIP_TLS_HOSTS=localhost,127.0.0.1,server,192.168.3.131 \
    NIP_AUTO_BACKUP_HOURS=24 \
    NIP_BACKUP_KEEP=7 \
    NIP_DATA_DIR=/app/backend/data \
    TZ=Asia/Shanghai

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       curl fonts-noto-cjk fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r /app/backend/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/backend/data \
    && chown -R app:app /app

USER app
EXPOSE 1314

HEALTHCHECK --interval=30s --timeout=8s --start-period=30s --retries=3 \
  CMD curl -kfsS https://127.0.0.1:1314/api/system/health || exit 1

CMD ["python", "backend/run.py", "--host", "0.0.0.0", "--port", "1314"]
