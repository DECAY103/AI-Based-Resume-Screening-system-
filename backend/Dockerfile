FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip --default-timeout=900 --retries 10 --no-cache-dir \
    install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip --default-timeout=900 --retries 10 --no-cache-dir \
    install -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY . .

CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT}"