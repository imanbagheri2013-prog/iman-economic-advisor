FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY iea ./iea

RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e . \
    && useradd --create-home --shell /usr/sbin/nologin iea

ENV IEA_API_HOST=0.0.0.0
ENV IEA_API_PORT=8000
ENV IEA_REPORT_PATH=/data/health_report.json

RUN mkdir -p /data && chown -R iea:iea /app /data

USER iea

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', os.getenv('IEA_API_PORT', '8000')) + '/health', timeout=3)"

CMD ["sh", "-c", "export IEA_API_PORT=\"${PORT:-${IEA_API_PORT:-8000}}\"; exec iea-api"]
