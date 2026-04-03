"""
Shared ONNX/fastembed models + a single-thread CPU pool.

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
os.environ.setdefault("ORT_NUM_THREADS", str(settings.EMBEDDING_THREADS))

from fastembed import TextEmbedding

_cpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rsd_cpu")
_embed_lock = threading.Lock()
PRIMARY_DENSE_MODEL = "BAAI/bge-m3"
FALLBACK_DENSE_MODEL = "BAAI/bge-base-en-v1.5"


def _resolve_dense_model_name() -> str:
    supported_models = {m.get("model") for m in TextEmbedding.list_supported_models()}
    if PRIMARY_DENSE_MODEL in supported_models:
        return PRIMARY_DENSE_MODEL
    print(
        f"WARNING: fastembed does not support {PRIMARY_DENSE_MODEL}; "
        f"using {FALLBACK_DENSE_MODEL}."
    )
    return FALLBACK_DENSE_MODEL


ACTIVE_DENSE_MODEL = _resolve_dense_model_name()

dense_model = TextEmbedding(
    model_name=ACTIVE_DENSE_MODEL,
    threads=settings.EMBEDDING_THREADS,
)


async def run_in_cpu_pool(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    if kwargs:
        call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(_cpu_executor, call)
    return await loop.run_in_executor(_cpu_executor, func, *args)


def embed_dense_for_chunks(chunks: list[str]) -> list:
    with _embed_lock:
        dense_vectors = list(
            dense_model.embed(
                chunks,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
                parallel=settings.EMBEDDING_PARALLEL,
            )
        )
    return dense_vectors


def embed_dense_for_query(text: str) -> list[float]:
    with _embed_lock:
        vec = list(
            dense_model.embed(
                [text],
                batch_size=1,
                parallel=1,
            )
        )[0]
    return vec.tolist()


def get_dense_vector_size() -> int:
    with _embed_lock:
        vec = list(
            dense_model.embed(
                ["dimension_probe"],
                batch_size=1,
                parallel=1,
            )
        )[0]
    return len(vec)


def get_active_dense_model_name() -> str:
    return ACTIVE_DENSE_MODEL
