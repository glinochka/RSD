FROM python:3.12-slim

WORKDIR /backend

# Для asyncpg
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Large wheels (torch, etc.) often exceed pip's default 15s read timeout on slow links.
ENV PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import telethon; print('telethon', telethon.__version__)" \
    && (python -c "import opentele; print('opentele ok')" || echo "WARNING: opentele not installed (tdata import unavailable; QR/SMS use Telethon fallback)")


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