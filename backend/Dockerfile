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
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    from sentence_transformers import SentenceTransformer

    model_name = "BAAI/bge-m3"
    print(f"Preloading embedding model: {model_name}")
    SentenceTransformer(model_name, device="cpu")
    print("Model preloaded successfully.")
except Exception as exc:
    print(f"WARNING: model preload skipped: {exc}")
PY
COPY . .