rsd_telephony_worker         | INFO:     172.18.0.10:39134 - "POST /api/internal/telephony/webhook-auth HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:39146 - "POST /api/internal/telephony/webhook-auth HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:39146 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:39134 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.133 - - [01/Jun/2026:11:51:40 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 107 "-" "VoxEngine/1.0" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:39152 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:39134 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.133 - - [01/Jun/2026:11:51:41 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"


rsd_telephony_worker         | INFO:     172.18.0.10:39134 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:39146 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:39134 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK

rsd_frontend                 | 185.164.148.136 - - [01/Jun/2026:11:51:42 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"


rsd_telephony_worker         | INFO:     172.18.0.10:39134 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.136 - - [01/Jun/2026:11:51:45 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
















rsd_telephony_worker         | INFO:     172.18.0.10:54230 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:54232 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:54230 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:11:51:51 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:52556 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:52564 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:52556 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:11:52:00 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_media_gateway  | [media-gateway] VAD: Silero ONNX + energy assist /app/models/silero_vad.onnx
rsd_telephony_media_gateway  | [media-gateway] reply session registered {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","total_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] session.start {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","connection_id":47,"codec":"pcmu","pipeline":true,"stt_provider":"yandex"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0}
rsd_telephony_orchestrator   | 2026-06-01 11:52:00,892 - app.telephony.orchestrator_worker - INFO - 486: orchestrator session.start call_id=0363B2FDA7BFD9D3.1780314711.12338890 connection_id=47 redis_session=True awaiting_ext=True
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":50,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0.685}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":100,"bytes":160,"expected_frame_bytes":160,"rtf":3,"avg_rtf":0.873}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":150,"bytes":160,"expected_frame_bytes":160,"rtf":1.2,"avg_rtf":0.899}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","digit":"1"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","digit":"2"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","digit":"3"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":200,"bytes":160,"expected_frame_bytes":160,"rtf":1.25,"avg_rtf":0.974}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","digit":"4"}
rsd_telephony_orchestrator   | 2026-06-01 11:52:04,902 - app.telephony.orchestrator_worker - INFO - 366: orchestrator _play_agent_welcome call_id=0363B2FDA7BFD9D3.1780314711.12338890 welcome_raw='Здравствуйте! Чем могу помочь?' welcome_text='Здравствуйте! Чем могу помочь?'
rsd_telephony_orchestrator   | 2026-06-01 11:52:04,903 - app.telephony.orchestrator_worker - INFO - 236: orchestrator _stream_routing_phrase call_id=0363B2FDA7BFD9D3.1780314711.12338890 log_label=welcome text='Здравствуйте! Чем могу помочь?' plain='Здравствуйте! Чем могу помочь?' empty=False
rsd_telephony_orchestrator   | 2026-06-01 11:52:04,904 - app.telephony.orchestrator_worker - INFO - 254: orchestrator welcome starting TTS call_id=0363B2FDA7BFD9D3.1780314711.12338890 voice=default lang=ru-RU text_len=30
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:05,192 - httpx - INFO - 1740: HTTP Request: POST https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":250,"bytes":160,"expected_frame_bytes":160,"rtf":1.9,"avg_rtf":1.024}
rsd_telephony_orchestrator   | 2026-06-01 11:52:05,601 - httpx - INFO - 1740: HTTP Request: POST https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:05,739 - app.telephony.orchestrator_worker - INFO - 319: orchestrator welcome TTS completed call_id=0363B2FDA7BFD9D3.1780314711.12338890
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:05,745 - app.telephony.orchestrator_worker - INFO - 325: [orchestrator] welcome guaranteed path=stream call_id=0363B2FDA7BFD9D3.1780314711.12338890
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:05,771 - app.telephony.orchestrator_worker - INFO - 429: orchestrator dtmf routed call_id=0363B2FDA7BFD9D3.1780314711.12338890 extension=1234 agent_id=37
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_redis                    | 1:M 01 Jun 2026 11:52:05.779 * 100 changes in 300 seconds. Saving...
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_redis                    | 1:M 01 Jun 2026 11:52:05.781 * Background saving started by pid 318136
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_redis                    | 318136:C 01 Jun 2026 11:52:05.806 * DB saved on disk
rsd_redis                    | 318136:C 01 Jun 2026 11:52:05.808 * Fork CoW for RDB: current 0 MB, peak 0 MB, average 0 MB
rsd_redis                    | 1:M 01 Jun 2026 11:52:05.882 * Background saving terminated with success
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":300,"bytes":160,"expected_frame_bytes":160,"rtf":1.9,"avg_rtf":1.031}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":350,"bytes":160,"expected_frame_bytes":160,"rtf":1.7,"avg_rtf":1.023}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":400,"bytes":160,"expected_frame_bytes":160,"rtf":1.1,"avg_rtf":1.019}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":450,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.017}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":500,"bytes":160,"expected_frame_bytes":160,"rtf":0.95,"avg_rtf":1.016}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":550,"bytes":160,"expected_frame_bytes":160,"rtf":1,"avg_rtf":1.014}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","text":"алло","stt_partial_ms":837}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"алло","stt_final_ms":1357,"partial_count":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":600,"bytes":160,"expected_frame_bytes":160,"rtf":3.75,"avg_rtf":1.018}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":650,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":700,"bytes":160,"expected_frame_bytes":160,"rtf":0.95,"avg_rtf":1.012}
rsd_telephony_orchestrator   | 2026-06-01 11:52:14,881 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":750,"bytes":160,"expected_frame_bytes":160,"rtf":1,"avg_rtf":1.01}
rsd_telephony_orchestrator   | 2026-06-01 11:52:16,245 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":800,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.01}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:17,156 - httpx - INFO - 1740: HTTP Request: POST https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:17,492 - httpx - INFO - 1740: HTTP Request: POST https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":850,"bytes":160,"expected_frame_bytes":160,"rtf":2.1,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:17,925 - httpx - INFO - 1740: HTTP Request: POST https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:18,110 - app.telephony.orchestrator_worker - INFO - 646: orchestrator stt.final ok call_id=0363B2FDA7BFD9D3.1780314711.12338890 db_id=54 latency_ms=5516 redis_history_len=1
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":900,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.009}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":950,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1000,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"прием меня слышно нет","stt_final_ms":1767,"partial_count":2}
rsd_telephony_orchestrator   | 2026-06-01 11:52:21,156 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1050,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.007}
rsd_telephony_orchestrator   | 2026-06-01 11:52:22,311 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1100,"bytes":160,"expected_frame_bytes":160,"rtf":0.95,"avg_rtf":1.007}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1150,"bytes":160,"expected_frame_bytes":160,"rtf":1.15,"avg_rtf":1.007}
rsd_telephony_orchestrator   | 2026-06-01 11:52:23,991 - httpx - INFO - 1740: HTTP Request: POST https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_orchestrator   | 2026-06-01 11:52:24,390 - httpx - INFO - 1740: HTTP Request: POST https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"0363B2FDA7BFD9D3.1780314711.12338890","has_session":true,"active_sessions":7}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1200,"bytes":160,"expected_frame_bytes":160,"rtf":0.5,"avg_rtf":1.006}
rsd_telephony_orchestrator   | 2026-06-01 11:52:24,576 - app.telephony.orchestrator_worker - INFO - 646: orchestrator stt.final ok call_id=0363B2FDA7BFD9D3.1780314711.12338890 db_id=54 latency_ms=3834 redis_history_len=3
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1250,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.006}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1300,"bytes":160,"expected_frame_bytes":160,"rtf":1,"avg_rtf":1.006}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1350,"bytes":160,"expected_frame_bytes":160,"rtf":0.95,"avg_rtf":1.006}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1400,"bytes":160,"expected_frame_bytes":160,"rtf":0.95,"avg_rtf":1.006}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1450,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1500,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1550,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1600,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1650,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1700,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.005}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1750,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.004}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1800,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.004}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"0363B2FDA7BFD9D3.1780314711.12338890","frames":1850,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.004}
rsd_telephony_media_gateway  | [media-gateway] pipeline metrics {"stt_partial_ms":[837,1048,1204],"stt_final_ms":[2294,1357,1767],"vad_speech_ratio":0.05,"vad_frames":1875,"vad_speech_frames":94}
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:11:52:38 +0000] "GET /ws HTTP/1.1" 101 182292 "-" "-" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:44580 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:11:52:38 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
