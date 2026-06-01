rsd_telephony_worker         | INFO:     172.18.0.10:44790 - "POST /api/internal/telephony/webhook-auth HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:44790 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:44798 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:44790 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.149.17 - - [01/Jun/2026:16:33:20 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:34690 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:34694 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:34690 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.149.17 - - [01/Jun/2026:16:33:29 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_media_gateway  | [media-gateway] VAD: Silero ONNX + energy assist /app/models/silero_vad.onnx
rsd_telephony_media_gateway  | [media-gateway] reply session registered {"call_id":"D6F09AAEF8626F22.1780331599.10397808","total_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] session.start {"call_id":"D6F09AAEF8626F22.1780331599.10397808","connection_id":47,"codec":"pcmu","pipeline":true,"stt_provider":"yandex"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":1,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"D6F09AAEF8626F22.1780331599.10397808","digit":"1"}
rsd_telephony_orchestrator   | 2026-06-01 16:33:30,155 - app.telephony.orchestrator_worker - INFO - 489: orchestrator session.start call_id=D6F09AAEF8626F22.1780331599.10397808 connection_id=47 redis_session=True awaiting_ext=True
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"D6F09AAEF8626F22.1780331599.10397808","digit":"2"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"D6F09AAEF8626F22.1780331599.10397808","digit":"3"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"D6F09AAEF8626F22.1780331599.10397808","digit":"4"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":50,"bytes":160,"expected_frame_bytes":160,"rtf":0.75,"avg_rtf":1.117}
rsd_telephony_orchestrator   | 2026-06-01 16:33:31,112 - app.telephony.orchestrator_worker - INFO - 369: orchestrator _play_agent_welcome call_id=D6F09AAEF8626F22.1780331599.10397808 welcome_raw='Здравствуйте! Чем могу помочь?' welcome_text='Здравствуйте! Чем могу помочь?'
rsd_telephony_orchestrator   | 2026-06-01 16:33:31,113 - app.telephony.orchestrator_worker - INFO - 236: orchestrator _stream_routing_phrase call_id=D6F09AAEF8626F22.1780331599.10397808 log_label=welcome text='Здравствуйте! Чем могу помочь?' plain='Здравствуйте! Чем могу помочь?' empty=False
rsd_telephony_orchestrator   | 2026-06-01 16:33:31,116 - app.telephony.orchestrator_worker - INFO - 254: orchestrator welcome starting TTS call_id=D6F09AAEF8626F22.1780331599.10397808 voice=default lang=ru-RU text_len=30
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":48,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":67,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":109,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":213,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":214,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":214,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"D6F09AAEF8626F22.1780331599.10397808","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":269,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":269,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":269,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":291,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":311,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":311,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":373,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":389,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":411,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":432,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":434,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":453,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":473,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":495,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":546,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":564,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":582,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":795,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":795,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":795,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":796,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":812,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":814,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":837,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":875,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":892,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":910,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":928,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":945,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":963,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"dtmf_suppress","since_dtmf_ms":984,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":100,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.137}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_orchestrator   | 2026-06-01 16:33:32,989 - app.telephony.orchestrator_worker - INFO - 322: orchestrator welcome TTS completed call_id=D6F09AAEF8626F22.1780331599.10397808
rsd_telephony_orchestrator   | 2026-06-01 16:33:32,991 - app.telephony.orchestrator_worker - INFO - 328: [orchestrator] welcome guaranteed path=stream call_id=D6F09AAEF8626F22.1780331599.10397808
rsd_telephony_orchestrator   | 2026-06-01 16:33:33,020 - app.telephony.orchestrator_worker - INFO - 432: orchestrator dtmf routed call_id=D6F09AAEF8626F22.1780331599.10397808 extension=1234 agent_id=37
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":150,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.107}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":200,"bytes":160,"expected_frame_bytes":160,"rtf":2.25,"avg_rtf":1.09}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":250,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":1.085}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":300,"bytes":160,"expected_frame_bytes":160,"rtf":1.7,"avg_rtf":1.058}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":350,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.046}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"D6F09AAEF8626F22.1780331599.10397808","text":"алло прием","stt_partial_ms":1608}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":400,"bytes":160,"expected_frame_bytes":160,"rtf":2.2,"avg_rtf":1.045}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"алло прием","stt_final_ms":2226,"partial_count":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":450,"bytes":160,"expected_frame_bytes":160,"rtf":1.2,"avg_rtf":1.036}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":500,"bytes":160,"expected_frame_bytes":160,"rtf":1.15,"avg_rtf":1.033}
rsd_telephony_orchestrator   | 2026-06-01 16:33:40,300 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":550,"bytes":160,"expected_frame_bytes":160,"rtf":1.15,"avg_rtf":1.029}
rsd_telephony_orchestrator   | 2026-06-01 16:33:41,682 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":600,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.026}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":20,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":20,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":38,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":58,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":164,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":164,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":164,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":165,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":181,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":190,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":198,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":217,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":263,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":265,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"D6F09AAEF8626F22.1780331599.10397808","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":304,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":305,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":341,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":343,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":417,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":418,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":420,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":468,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":468,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":468,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":469,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":516,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":516,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":554,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":555,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":650,"bytes":160,"expected_frame_bytes":160,"rtf":2.15,"avg_rtf":1.027}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"D6F09AAEF8626F22.1780331599.10397808","reason":"playback_grace","since_start_ms":599,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"D6F09AAEF8626F22.1780331599.10397808","has_session":true,"active_sessions":3}
rsd_telephony_orchestrator   | 2026-06-01 16:33:43,584 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=D6F09AAEF8626F22.1780331599.10397808 db_id=65 latency_ms=5091 redis_history_len=1
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":700,"bytes":160,"expected_frame_bytes":160,"rtf":1.5,"avg_rtf":1.024}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":750,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":1.031}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":800,"bytes":160,"expected_frame_bytes":160,"rtf":1.1,"avg_rtf":1.02}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":850,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.02}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":900,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.018}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":950,"bytes":160,"expected_frame_bytes":160,"rtf":1,"avg_rtf":1.017}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":1000,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.02}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"D6F09AAEF8626F22.1780331599.10397808","frames":1050,"bytes":160,"expected_frame_bytes":160,"rtf":5.75,"avg_rtf":1.02}
rsd_telephony_media_gateway  | [media-gateway] pipeline metrics {"stt_partial_ms":[1608],"stt_final_ms":[1760,2226,786,1180,1934],"vad_speech_ratio":0.081,"vad_frames":1071,"vad_speech_frames":87}
rsd_frontend                 | 185.164.149.17 - - [01/Jun/2026:16:33:51 +0000] "GET /ws HTTP/1.1" 101 116270 "-" "-" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:39932 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.149.17 - - [01/Jun/2026:16:33:52 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
