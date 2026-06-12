from datetime import datetime

from app.services.agent_memory import (
    build_client_memory_block,
    format_channel_history_memory,
)


def test_format_channel_history_memory_includes_timestamps():
    history = [
        {
            "role": "user",
            "content": "Сколько стоит?",
            "created_at": datetime(2026, 6, 11, 21, 33),
        },
        {
            "role": "assistant",
            "content": "От 5000 руб.",
            "created_at": datetime(2026, 6, 11, 21, 34),
        },
    ]
    text = format_channel_history_memory(history)
    assert "[2026-06-11 21:33] Клиент: Сколько стоит?" in text
    assert "[2026-06-11 21:34] Агент: От 5000 руб." in text


def test_build_client_memory_block_includes_portrait_and_history():
    block = build_client_memory_block(
        portrait="Интересуется записью",
        history=[
            {
                "role": "user",
                "content": "Привет",
                "created_at": datetime(2026, 6, 11, 22, 0),
            }
        ],
    )
    assert block.startswith("ПАМЯТЬ О ДИАЛОГЕ И КЛИЕНТЕ:")
    assert "Портрет клиента:" in block
    assert "Недавние реплики:" in block
