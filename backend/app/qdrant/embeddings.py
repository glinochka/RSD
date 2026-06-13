"""
Shared SentenceTransformer model + a single-thread CPU pool.

Heavy embed/text work must not run on the asyncio event loop — it freezes the API.
One worker thread also avoids oversubscribing a small VPS.
"""
from __future__ import annotations

import asyncio
import functools
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from config import settings

os.environ.setdefault("OMP_NUM_THREADS", str(settings.EMBEDDING_THREADS))

from sentence_transformers import SentenceTransformer

_cpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rsd_cpu")
_embed_lock = threading.Lock()
PRIMARY_DENSE_MODEL = "BAAI/bge-m3"
FALLBACK_DENSE_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_SCHEMA_VERSION = settings.EMBEDDING_SCHEMA_VERSION
DEFAULT_EMBEDDING_PROFILE_KEY = settings.EMBEDDING_PROFILE_KEY

ACTIVE_DENSE_MODEL = PRIMARY_DENSE_MODEL


def _init_dense_model() -> SentenceTransformer:
    local = (settings.EMBEDDING_LOCAL_MODEL_PATH or "").strip()
    if local:
        return SentenceTransformer(local, device="cpu", local_files_only=True)
    return SentenceTransformer(ACTIVE_DENSE_MODEL, device="cpu")


dense_model = _init_dense_model()


async def run_in_cpu_pool(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    if kwargs:
        call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(_cpu_executor, call)
    return await loop.run_in_executor(_cpu_executor, func, *args)


def embed_dense_for_chunks(chunks: list[str]) -> list:
    with _embed_lock:
        dense_vectors = dense_model.encode(
            chunks,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    return list(dense_vectors)


def embed_dense_for_query(text: str) -> list[float]:
    with _embed_lock:
        vec = dense_model.encode(
            [text],
            batch_size=1,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
    return vec.tolist()


def get_dense_vector_size() -> int:
    with _embed_lock:
        vec = dense_model.encode(
            ["dimension_probe"],
            batch_size=1,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
    return len(vec)


def get_active_dense_model_name() -> str:
    return ACTIVE_DENSE_MODEL


def get_active_embedding_profile() -> dict:
    return {
        "profile_key": DEFAULT_EMBEDDING_PROFILE_KEY,
        "schema_version": EMBEDDING_SCHEMA_VERSION,
        "model_name": ACTIVE_DENSE_MODEL,
    }
