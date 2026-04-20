FROM python:3.12-slim

WORKDIR /backend

# Для asyncpg
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install -r requirements.txt


# Принудительно скачиваем модель при сборке (best-effort).
# Любые ошибки (например, CPU/NumPy несовместимость на хосте сборки)
# не должны останавливать build.
RUN python - <<'PY'
import os

try:
    from fastembed import TextEmbedding

    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    primary = "BAAI/bge-m3"
    fallback = "BAAI/bge-base-en-v1.5"
    supported = {m.get("model") for m in TextEmbedding.list_supported_models()}
    model_name = primary if primary in supported else fallback
    print(f"Preloading embedding model: {model_name}")
    TextEmbedding(model_name=model_name)
except Exception as exc:
    print(f"WARNING: model preload skipped: {exc}")
PY
COPY . .