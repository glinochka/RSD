"""stream_fixed_phrase — routing prompts without LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from app.telephony.stream_pipeline import stream_fixed_phrase


@pytest.mark.asyncio
async def test_stream_fixed_phrase_publishes_audio():
    async def fake_pcm16(_text, *, voice_id, language):
        yield b"\x00\x00" * 160

    with (
        patch("app.telephony.stream_pipeline.publish_agent_audio_start", AsyncMock()) as start,
        patch("app.telephony.stream_pipeline.publish_agent_audio_chunk", AsyncMock()) as pub_chunk,
        patch("app.telephony.stream_pipeline.publish_agent_audio_end", AsyncMock()) as end,
        patch("app.telephony.stream_pipeline.set_agent_spoken_text", AsyncMock()),
        patch("app.telephony.stream_pipeline.clear_agent_spoken_text", AsyncMock()),
        patch("app.telephony.stream_pipeline.stream_syntagma_pcm16", fake_pcm16),
        patch("app.telephony.stream_pipeline.is_cancelled", return_value=False),
        patch("app.telephony.stream_pipeline.is_cancelled_call_id", return_value=False),
    ):
        metrics = await stream_fixed_phrase(
            call_id="call-fix-1",
            connection_id=1,
            call_db_id=10,
            text="Добро пожаловать.",
            voice_id="default",
            language="ru-RU",
        )

    start.assert_awaited_once()
    assert pub_chunk.await_count >= 1
    end.assert_awaited_once()
    assert metrics.tts_first_byte_ms is not None
    assert metrics.syntagma_count >= 1
