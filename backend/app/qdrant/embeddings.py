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

from fastembed import SparseTextEmbedding, TextEmbedding

_cpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rsd_cpu")
_embed_lock = threading.Lock()

dense_model = TextEmbedding(
    model_name="BAAI/bge-small-en-v1.5",
    threads=settings.EMBEDDING_THREADS,
)
sparse_model = SparseTextEmbedding(
    model_name="prithivida/Splade_PP_en_v1",
    threads=settings.EMBEDDING_THREADS,
)


async def run_in_cpu_pool(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    if kwargs:
        call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(_cpu_executor, call)
    return await loop.run_in_executor(_cpu_executor, func, *args)


def embed_dense_and_sparse_for_chunks(chunks: list[str]) -> tuple[list, list]:
    with _embed_lock:
        dense_vectors = list(
            dense_model.embed(
                chunks,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
                parallel=settings.EMBEDDING_PARALLEL,
            )
        )
        sparse_vectors = list(
            sparse_model.embed(
                chunks,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
                parallel=settings.EMBEDDING_PARALLEL,
            )
        )
    return dense_vectors, sparse_vectors


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
