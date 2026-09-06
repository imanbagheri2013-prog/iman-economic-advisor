FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY iea ./iea

RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

ENV IEA_API_HOST=0.0.0.0
ENV IEA_API_PORT=8000
ENV IEA_REPORT_PATH=/app/health_report.json

EXPOSE 8000

CMD ["iea-api"]
