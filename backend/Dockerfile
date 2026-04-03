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


# Принудительно скачиваем модель при сборке (best-effort)
RUN python - <<'PY'
from fastembed import TextEmbedding
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
primary = "BAAI/bge-m3"
fallback = "BAAI/bge-base-en-v1.5"
supported = {m.get("model") for m in TextEmbedding.list_supported_models()}
model_name = primary if primary in supported else fallback
print(f"Preloading embedding model: {model_name}")

try:
    TextEmbedding(model_name=model_name)
except Exception as exc:
    print(f"WARNING: model preload skipped: {exc}")
PY
COPY . .