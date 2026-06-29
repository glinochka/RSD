"""ИИ МОП — кастомный рантайм sales_manager для продажи платформы."""

__all__ = ["AiMopWorker", "get_ai_mop_worker"]


def __getattr__(name: str):
    if name == "AiMopWorker":
        from .worker import AiMopWorker

        return AiMopWorker
    if name == "get_ai_mop_worker":
        from .worker import get_ai_mop_worker

        return get_ai_mop_worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
