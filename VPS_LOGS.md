rsd_telephony_worker         | INFO:     172.18.0.10:59974 - "POST /api/internal/telephony/webhook-auth HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:59974 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:59986 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:59974 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.149.19 - - [01/Jun/2026:13:09:46 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:38926 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:38936 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:38926 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.149.19 - - [01/Jun/2026:13:09:55 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_media_gateway  | [media-gateway] VAD: Silero ONNX + energy assist /app/models/silero_vad.onnx
rsd_telephony_media_gateway  | [media-gateway] reply session registered {"call_id":"F9DA499D42A23B62.1780319385.5551909","total_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] session.start {"call_id":"F9DA499D42A23B62.1780319385.5551909","connection_id":47,"codec":"pcmu","pipeline":true,"stt_provider":"yandex"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":50,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":0.768}
rsd_telephony_orchestrator   | 2026-06-01 13:09:56,852 - app.telephony.orchestrator_worker - INFO - 489: orchestrator session.start call_id=F9DA499D42A23B62.1780319385.5551909 connection_id=47 redis_session=True awaiting_ext=True
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"F9DA499D42A23B62.1780319385.5551909","digit":"1"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"F9DA499D42A23B62.1780319385.5551909","digit":"2"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":100,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":0.961}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"F9DA499D42A23B62.1780319385.5551909","digit":"3"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"F9DA499D42A23B62.1780319385.5551909","digit":"4"}
rsd_telephony_orchestrator   | 2026-06-01 13:09:58,374 - app.telephony.orchestrator_worker - INFO - 369: orchestrator _play_agent_welcome call_id=F9DA499D42A23B62.1780319385.5551909 welcome_raw='Здравствуйте! Чем могу помочь?' welcome_text='Здравствуйте! Чем могу помочь?'
rsd_telephony_orchestrator   | 2026-06-01 13:09:58,376 - app.telephony.orchestrator_worker - INFO - 236: orchestrator _stream_routing_phrase call_id=F9DA499D42A23B62.1780319385.5551909 log_label=welcome text='Здравствуйте! Чем могу помочь?' plain='Здравствуйте! Чем могу помочь?' empty=False
rsd_telephony_orchestrator   | 2026-06-01 13:09:58,379 - app.telephony.orchestrator_worker - INFO - 254: orchestrator welcome starting TTS call_id=F9DA499D42A23B62.1780319385.5551909 voice=default lang=ru-RU text_len=30
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":150,"bytes":160,"expected_frame_bytes":160,"rtf":1.3,"avg_rtf":1.039}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-01 13:09:59,578 - app.telephony.orchestrator_worker - INFO - 322: orchestrator welcome TTS completed call_id=F9DA499D42A23B62.1780319385.5551909
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-01 13:09:59,579 - app.telephony.orchestrator_worker - INFO - 328: [orchestrator] welcome guaranteed path=stream call_id=F9DA499D42A23B62.1780319385.5551909
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-01 13:09:59,616 - app.telephony.orchestrator_worker - INFO - 432: orchestrator dtmf routed call_id=F9DA499D42A23B62.1780319385.5551909 extension=1234 agent_id=37
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":200,"bytes":160,"expected_frame_bytes":160,"rtf":2,"avg_rtf":1.046}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":250,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.033}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":300,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.027}
rsd_db                       | 2026-06-01 13:10:02.620 UTC [27] LOG:  checkpoint starting: time
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":350,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.023}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":400,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.019}
rsd_db                       | 2026-06-01 13:10:04.819 UTC [27] LOG:  checkpoint complete: wrote 22 buffers (0.1%); 0 WAL file(s) added, 0 removed, 0 recycled; write=2.122 s, sync=0.022 s, total=2.200 s; sync files=20, longest=0.015 s, average=0.002 s; distance=67 kB, estimate=116 kB
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":450,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.021}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":500,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.016}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"F9DA499D42A23B62.1780319385.5551909","text":"алло","stt_partial_ms":1099}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":550,"bytes":160,"expected_frame_bytes":160,"rtf":1.15,"avg_rtf":1.018}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"алло","stt_final_ms":2792,"partial_count":4}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":600,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.016}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":650,"bytes":160,"expected_frame_bytes":160,"rtf":1.1,"avg_rtf":1.012}
rsd_telephony_orchestrator   | 2026-06-01 13:10:10,034 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":700,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":750,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.015}
rsd_telephony_orchestrator   | 2026-06-01 13:10:11,655 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":800,"bytes":160,"expected_frame_bytes":160,"rtf":3.2,"avg_rtf":1.013}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":850,"bytes":160,"expected_frame_bytes":160,"rtf":1.45,"avg_rtf":1.009}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":900,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.009}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-01 13:10:14,401 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=F9DA499D42A23B62.1780319385.5551909 db_id=56 latency_ms=6278 redis_history_len=1
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":950,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1000,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.01}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1050,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"F9DA499D42A23B62.1780319385.5551909","text":"нет","stt_partial_ms":762}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1100,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":1.007}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"меня слышно","stt_final_ms":1380,"partial_count":1}
rsd_telephony_orchestrator   | 2026-06-01 13:10:19,029 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1150,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.009}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1200,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.011}
rsd_telephony_orchestrator   | 2026-06-01 13:10:20,725 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1250,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.007}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1300,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.011}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"F9DA499D42A23B62.1780319385.5551909","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-01 13:10:22,345 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=F9DA499D42A23B62.1780319385.5551909 db_id=56 latency_ms=3722 redis_history_len=3
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1350,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.006}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1400,"bytes":160,"expected_frame_bytes":160,"rtf":7.3,"avg_rtf":1.01}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1450,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1500,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1550,"bytes":160,"expected_frame_bytes":160,"rtf":1.7,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1600,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.006}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"F9DA499D42A23B62.1780319385.5551909","frames":1650,"bytes":160,"expected_frame_bytes":160,"rtf":0.35,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] pipeline metrics {"stt_partial_ms":[1099,1668,1865,2147,762],"stt_final_ms":[454,1855,891,2792,1380,1101],"vad_speech_ratio":0.086,"vad_frames":1683,"vad_speech_frames":144}
rsd_frontend                 | 185.164.149.19 - - [01/Jun/2026:13:10:29 +0000] "GET /ws HTTP/1.1" 101 281741 "-" "-" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:58280 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.149.19 - - [01/Jun/2026:13:10:29 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_backend                  | ✅ Коллекция agent_documents проверяется
rsd_backend                  | INFO:     89.37.172.132:6222 - "GET / HTTP/1.1" 404 Not Found
rsd_backend                  | INFO:     185.216.145.164:7490 - "GET /favicon.ico HTTP/1.1" 404 Not Found