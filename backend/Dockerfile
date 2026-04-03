FROM python:3.13-slim

WORKDIR /backend

# Для asyncpg
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install -r requirements.txt


# Принудительно скачиваем модель при сборке
RUN python -c "\
from fastembed import TextEmbedding; \
import os; \
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'; \
TextEmbedding(model_name='BAAI/bge-m3')"
COPY . .