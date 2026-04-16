FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md run_prod.sh ./
COPY app ./app

RUN pip install --upgrade pip \
    && pip install .

RUN chmod +x /app/run_prod.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,sys,urllib.request; port=os.getenv('PORT', os.getenv('API_PORT', '8000')); response=urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/health'); sys.exit(0 if response.status == 200 else 1)"

CMD ["./run_prod.sh"]
