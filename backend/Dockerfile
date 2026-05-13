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
# Uses the default Hugging Face Hub URL (do not point HF_ENDPOINT at hf-mirror.com — recent
# huggingface_hub builds fail metadata checks on many mirrors).
RUN python - <<'PY'
try:
    from sentence_transformers import SentenceTransformer

    model_name = "BAAI/bge-m3"
    print(f"Preloading embedding model: {model_name}")
    SentenceTransformer(model_name, device="cpu")
    print("Model preloaded successfully.")
except Exception as exc:
    print(f"WARNING: model preload skipped: {exc}")
PY
COPY . .