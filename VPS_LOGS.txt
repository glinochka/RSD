rsd_telephony_worker         | INFO:     172.18.0.10:36332 - "POST /api/internal/telephony/webhook-auth HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:36332 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:36336 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:36332 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.150.17 - - [04/Jun/2026:08:12:24 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:36352 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:36362 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:36352 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.150.17 - - [04/Jun/2026:08:12:32 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_media_gateway  | [media-gateway] VAD: Silero ONNX + energy assist /app/models/silero_vad.onnx
rsd_telephony_media_gateway  | [media-gateway] reply session registered {"call_id":"4A1BB234AA5A2236.1780560743.6433266","total_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] session.start {"call_id":"4A1BB234AA5A2236.1780560743.6433266","connection_id":47,"codec":"pcmu","pipeline":true,"stt_provider":"yandex"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":1,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0}
rsd_telephony_orchestrator   | 2026-06-04 08:12:33,590 - app.telephony.orchestrator_worker - INFO - 489: orchestrator session.start call_id=4A1BB234AA5A2236.1780560743.6433266 connection_id=47 redis_session=True awaiting_ext=True
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":50,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0.947}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":100,"bytes":160,"expected_frame_bytes":160,"rtf":1.2,"avg_rtf":0.879}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":150,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":0.917}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"4A1BB234AA5A2236.1780560743.6433266","digit":"1"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"4A1BB234AA5A2236.1780560743.6433266","digit":"2"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"4A1BB234AA5A2236.1780560743.6433266","digit":"3"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"4A1BB234AA5A2236.1780560743.6433266","digit":"4"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":200,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.009}
rsd_telephony_orchestrator   | 2026-06-04 08:12:37,020 - app.telephony.orchestrator_worker - INFO - 369: orchestrator _play_agent_welcome call_id=4A1BB234AA5A2236.1780560743.6433266 welcome_raw='Здравствуйте! Чем могу помочь?' welcome_text='Здравствуйте! Чем могу помочь?'
rsd_telephony_orchestrator   | 2026-06-04 08:12:37,022 - app.telephony.orchestrator_worker - INFO - 236: orchestrator _stream_routing_phrase call_id=4A1BB234AA5A2236.1780560743.6433266 log_label=welcome text='Здравствуйте! Чем могу помочь?' plain='Здравствуйте! Чем могу помочь?' empty=False
rsd_telephony_orchestrator   | 2026-06-04 08:12:37,025 - app.telephony.orchestrator_worker - INFO - 254: orchestrator welcome starting TTS call_id=4A1BB234AA5A2236.1780560743.6433266 voice=default lang=ru-RU text_len=30
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_redis                    | 1:M 04 Jun 2026 08:12:37.066 * 100 changes in 300 seconds. Saving...
rsd_redis                    | 1:M 04 Jun 2026 08:12:37.069 * Background saving started by pid 611134
rsd_redis                    | 611134:C 04 Jun 2026 08:12:37.127 * DB saved on disk
rsd_redis                    | 611134:C 04 Jun 2026 08:12:37.128 * Fork CoW for RDB: current 0 MB, peak 0 MB, average 0 MB
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"start\",\"start\":{\"mediaFormat\":{\"encoding\":\"audio/x-mulaw\",\"sampleRate\":8000}}}"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":11,"grace_ms":600}
rsd_redis                    | 1:M 04 Jun 2026 08:12:37.172 * Background saving terminated with success
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":12,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":32,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":32,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":41,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":41,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":45,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":46,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":81,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":84,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":102,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":121,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":238,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":239,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":240,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":241,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":255,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":256,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] pacer ready no pacer {"call_id":"4A1BB234AA5A2236.1780560743.6433266"}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"4A1BB234AA5A2236.1780560743.6433266","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":273,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":291,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":337,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":355,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":373,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":395,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":419,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":443,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":470,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":473,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":491,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":511,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":532,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":554,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":577,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"dtmf_suppress","since_dtmf_ms":876,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"dtmf_suppress","since_dtmf_ms":896,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"dtmf_suppress","since_dtmf_ms":917,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"dtmf_suppress","since_dtmf_ms":936,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"dtmf_suppress","since_dtmf_ms":959,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"dtmf_suppress","since_dtmf_ms":981,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":250,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.023}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:12:38,616 - app.telephony.orchestrator_worker - INFO - 322: orchestrator welcome TTS completed call_id=4A1BB234AA5A2236.1780560743.6433266
rsd_telephony_orchestrator   | 2026-06-04 08:12:38,616 - app.telephony.orchestrator_worker - INFO - 328: [orchestrator] welcome guaranteed path=stream call_id=4A1BB234AA5A2236.1780560743.6433266
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:12:38,650 - app.telephony.orchestrator_worker - INFO - 432: orchestrator dtmf routed call_id=4A1BB234AA5A2236.1780560743.6433266 extension=1234 agent_id=37
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/////f39/f39/f39/f39//39/f39///9/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":300,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.048}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f3///39//////3//f3///39/f39/f39//39/f39/f/////9/f//"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39//39/f////3///39/f3///39/f39/////////f39//39/f3//////f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f3//f39/f39//39//39/f3//f39/f39/f39/f/9/f39/f/9/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"////f3//f////39/f/9/f39/f39/f39/f/9/f39/f/9/f39//39/f3//f3//f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f3//f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f3//f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3///3//f39/f3///39///9/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f/9/////f//"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f////39//3///3////////9/f/9/f39/f39/f39/f39/f39/f39/f39/f39/f35"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////////////7+/v7+/v//////////////f39//3//f3//////f/9/fn5/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"pKettru9vcHP4+HSxcDFyMbEyvtAMi0sLCsqKSgpKCMjLUTOt7OvqKSipa22uLe"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"OUjtvq6moZ6enZ6foqessLi9wcC/w8nZbFZGOjArKCUkIiAfHx8gJSovO1DQuq6"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LCsqKSgpKSssLjM5QlXfxrqxraqpqKeoqamrra+ztrq+ydvvalRIPDk2Mi8tKys"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ra+zt7rEy9V9XU5DPDg2My8uLi0sLCwtLjAzNztCUurLv7mzrqysq6urrK2ur7K"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NTg9RE5n3Mi+urazsa+vr6+wsbK0t7q9wsfO3XpYTEU/PDk2NDIxMC8vLzAyNTg"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"v8XN2fFfUUlDPjw6ODY1NDMzMzM0Njg7P0pZ8NPHv7y5t7W0tLOzs7S1t7m8v8T"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PT9ES1dv38/HwL27ubi3t7i4uru8vsLHzNLd7mtcU01KSEVCQD8+Pj09PD09Pj9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yc/b3OpsWmtKTtVOP0FBPzw9QEZA9M1PUGLPw7+7wL2+2PpVTWh5rp2gq7m8uuU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GQ8OCwgIBgYUOMSonZaPkZ+2yt5mNzTDpZqVl5eWmqS4SS4lGxQQDg4PCwscXbG"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/trHvriyr62tra+yt7vCy8/Z6WZTSkRAPTs7PkNKVXfZy8S+vry7u7m7s7evobd"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"CwkMG9Cdko+Sm64xHyEtUbKfmZWWnaWvxPY4KCQjIB0XEQsHDy+tlY+Qkp1wIx0"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"UUM3JxsXDgoSNK2alJebpGMiHi3Dn5iYm6W22kVJ37+90zYqJBsYDwsYb6WamJy"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ubdaPUEsHhwSDRgzsZqZnql5KyQqRKubm5ucrN1GUL+zuN9KQCgeGRARGzG1nZu"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"zM5BKyclHBYVHTu3qKSnt0UpJzu1n52en6iws9dW2NHj4k85Kh8bFxgdMbeinqX"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"TjovLCwsKiciICQqNUrmwLm4wHtczq+fnaCmrbe2rquv2jQnIiIjJSgpJyYnL0P"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yMXBwL66ury7vr+5ub/N7nhUS0xFSkxEPz1AP0JMS13rYE9NUObb1sjzW2xo9uT"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"WVZiXV5tWF7ycfn969x66N9md21deH5qYmf9ZlNZXWluXXR6cOnv/vv88ejp5t3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"4ev86+Z9efX07v597Hptcmduc2xsdHplbf/69/9xanv4e33r92l/e3TxcP59cPn"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"7/f37PHx7/Xy7e/3/Pf7fP37+vn8+fl++fl+/v9//P58fXz+fvz4/fv/fv1+fnx"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/f39/fz8/Pv7+/z8+/v7+/v7+/v6+vr6+vr6+/v7+/z8/P39/fz8/Pz8/P39/v7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/Pz8/f39/f7//39+fn5+fn5+fn5+f/9///7+/v39/v7+/v7+//7+/v79/v7+/v7"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":350,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.021}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHp3fGv9at3D4/PV5PpaaOx8anZ0a3p3ZVVTU1dXUVRXVmjq5725zN73/E9JS0x"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ZXF1bfb2bml56ezx73zv3uHs9fT17vFq9Nni7e/x4e9p8u90//Z+euvva3Xu5+v"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3+3u7eDtbndrX2BfW1pcXFtcX2FiZ2xubn3y8+be4uTf293f3t3c5ufm7+Ll/Hl"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"RdO4raegnZ2eoKarsb3XYExFRk9t0b+2r62tr7bAzeNPPjcxLSomIyAeHh0dHBw"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"s8ZeQTk3PUt9xLKrqKamqay2x/lHODEuLCopJiMgHh0bGhoYHCc0T7eknZmXl5e"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"vbavq6qsr7W+zntKPzw0MTEuKiglIB4dGxoaGh8rNV6vpJ+bmJiZnKCmrcHsWkU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"sLa8w9tWRjszLywpJyUiIR8eHh4eHyYuN1q5rKafnJqam52fpay0wOZaT0xRbdz"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ODEtKykoJygoKiwtLjE1OT5KWPbMwLq0r6yrqqmqq6yvs7e7wMfLztHe3977aGJ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"9vf39/b08vDu7evq6ejn5ubn5+jp6+3v8/j8fnp4d3Z1dHV1dnh5e31+//7+/f3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+/n49/b29/j6/P3/fnx7enp6ent8fH19fn5+fn19fHt5eHd2dXV0dXV2d3h5ent"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//9+fX18fHx8fHx8fHx8fX7//v39/Pz9/n5+fX18e33///x9+f1/4en793f/eXF"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/H7v+XZ9e3Bob3pvee/v/nvy7fRzdXVteG/x+m36bXb49up4bnx1evd2aW1scG5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"2+n1fmlze2Xo3m3n9Whva+/pYfrrW/lradry39L0ceZ1felx3+9e3Odl9nbu8Gn"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"cfRveXvvcG7h62926N9tb/BaVWZ0bmF94Gx+4/rsae/XbPncdnl9Z+xrY8zacc/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3tng39rg4t/k6O3v8Pf29Hh2emljZF1ZWVhWV1dbXV9td3zv7ufd3djU1tHO0c7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KigoKSonKCorPcq+r6Skp6estbvGzsS/vrWztLO2vL7CzdjY4uPW4trO8FxfSTg"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KiknKiwqLTNCwq6sp6Klq7C1ub3DvrWztbSytrzDyczW4drW3OLva2JOQ0I9NjQ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Li8wNDlBV9e/tq+trKytr7Gys7OxsbKys7W5vcPM1ebq2u9YT0U8ODMxLy0sLC0"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"urWwr6+urKurq6ysrbC1t7u/yM7Z72lYST86My8vLi4tLS0uLi4vMDM2Oj9LY9v"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"vsHGy9Xlc15VTEdEQT48Ojo6Ozs7PT9BRUlMU19r++DUzcrGw8G/v8C/v8DBw8b"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ZGVlaGtub25wef79+/Xw7/Dw7+/x8vP1+Pn8/3x3dHV5e3p7fHl7fv759fLw8PH"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"e3x8e3l4d3Z2d3d3eHl6e3x+fn59//38+/r5+fj5+fn6/P38+/v8/P3+fX19fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/P39/f7+/v//////f////39+fn19fX1+fn5+fn5+f//+/v7+/v39/Pz9/f7+///"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39+f/////////////7///7///9/f39/f35+fn9/fn5+fn5+fn5/////f///f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn5+fn5+fn9/f3//f/////9/f39/f39/f3////9/f39/f39/f39+fn9/f/9/f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f////39//////////3//////////////////////////f39/f/9/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3////9/f39/f39+fn9/f39/f35+fn5+f39/fn//f39/f39/fn9/f3///////39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3//f3////9/f3//f39//39/f39/f39/f39/f3//f39/f39/f39/f35+f35+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/fn5+fn5+fn5+fn5+fn9/f35/f39/f35/f35+fn5/fn9/f35/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/fn5+fn5+f35+f39/fn5+fn9/fn9+fn5+f39/f39/f39+f39/f39/f39/f/9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/////////////39/f39/f39/f39/f39/f39/f39/f39/fn5/f3/////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f3//f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f39/f39/f39/f39/f39/f39//39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f3///39/f3//f39//39/////////f////39//////39/////f/9/f///f39/f/9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f/9/f3//f39/f39/f39/f39/f39//39/f3//f39/f39/f39/f3//f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f39/f/9//39//39//39//3//f3//f39/f3////////////////////9////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/fn5/f39/f39+f39+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//9/f////////////////////////////39/f39/f39/f39/f39/f39/f35+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn5+fn5+fn5+fn5+fn5+fn5+fn5+fn5+fn5+fX19fX19fX19fX5+fn5+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/v7//f79/P70/+fe/Ph3bG5laWtscHV4//z59vr9fHd5d29xbm1zcXJ0dXx9fPr"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/2n/e3V8Z/JubXV6aGvubv3ka2vsXf9taHNi62Jl72p1c/F5ct9v8uX7+nvv/PP"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":400,"bytes":160,"expected_frame_bytes":160,"rtf":1.1,"avg_rtf":1.017}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"WvBjXulZ+ndX4GdveXlVcnFM419W6/xq62Xf/ejbYNX76O3v2Ffc5U7LWmnLTM3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"VFjEP9HLO71ZSr06zO47uz9ny0LK/lLEYU3DS23KSOjaYF3PW+zPVM5Z2OVOvkn"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"buFgWdviVt3wVMztZ8hi2ddQ0OlMyu9LzGRv41/TVfrIRMvHO77cPLlLRro41cU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"2WVZ8Erh+Et8+F94aWne/mfc5135dl5tXfr5V+fWYe/PX2/XbHxo5nxSznldy//"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GxYWFRsgJm2tpZuWlpaXmp+or9k9MiQdHBsYFBUcICbfqKCZlJSWmJ2kr7rtNC4"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"j46OlJuoyFtPRElNSTssJR0YEA0XJTSvlY+Oj5adqthKUExNVVlFLiUdFxEOFih"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"z8t3NSkhHBgPER9BtaCZlJOapbzHvczQy8zD5jQnIB0aEhMePbShm5eWmqW7yr+"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KCIfICYxWsCxrKyrq6yrqqqsr7jKX0E3NDAsJx8eICcxUce2rqysrKqnpqepr7r"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LyghHR0fJCo0RlvPu7Wtp6ShoaWprbG6x+1GNSwlHx0eICUsOUnhv7evqaWjoaG"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"o6aprbXGXDovKSIeHBoaHSAnNUZexbexqaCenZydoKOorrS++T8vKSMfHBoZGx0"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"n6WssLa8yV46LSUfHRsaGRcXGR0jLUvJr6ejn52cm5qbnJ2fpquvtr3NVjgrJB4"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GhkYGBwfJS9E17itp6GenJqam5ydn6Omqayxu81ePjEqJSIgHx4cGxkZHB4jKzh"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GRocHiQsOFDOvLCppKCenZ6eoKSnqauusLe7vsbO31tEOjIuKyklIB0bGxwdISc"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Xz0vKSUhHhoWEhQbK9Grp6u3z/Pcw7ixrquno6GkqrTCzMa8tbCwsrW7yGE8Lyo"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"qamrrrfBxr63sK+0vc5xT0M5LyklIiAfHRoXFxwp/6yjoqm0wMK7sa2tra6tq6m"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ISAhJSw6ZMGzrKmnpqWmp6qus7m9v8LDxMTDwsHDx8/qWUg/Ozg1Mi8tLCsrKis"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"u7y9v8HEyMzQ2N/td2VcVlFOS0lGQ0E/Pj09PT4/QURHTFJdcubWzcjDwL6+vr6"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"WVdWVVVUVFNSUE9OTk1NTk9SVlxo/OPYz8vIxsXFxsjKzM/T2N3l731uZ2FfXl1"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"X2JlaW1yeH39/Pf18+/q1sjBv8TP+FRLSk1Wae7f3OL+XlNNTVVs28rCv8PPcEx"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"zcrJy9LpWkU6MSwpJyYlJSUmKCsxP/G9rqmmpaaprLC2vMPP7F5TVWvTv7WurK2"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KjA+a7+vqaShoaOmqq61vcbR4O3t3Mu+tq+sqqqtsbrJ9k0/OTMuKiYiHx8fISM"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"zczJx8XCwL+/v7+/v7+/v7/BxMjL0Njj+2dZUEtHREFAP0BBQ0VISkxPUlZZXF5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"bWxramlpaGhoaWlqamtsbW9vcXN1dnh6e3x+//79/f39/f39/f39/f39/f38+/v"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/f39/f3+/v9+fXx7enp5eXl5enp7e3t7e3t7e3x8fHx8fHx9fX19fn5+f/////7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+vr5+fj49/f39/b19fT09PT09PT09PT09PTz8/Pz8/Pz8/P09PT09PT09fX19fX"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3tvPz91uTkZERktNTlFVWl1dXltXWFRQTUhJSkxNSkU/PTw7Ojk4OTxCSUxMTEx"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Wk9KQjw3MS0rKScmJis3Yb2xr7K6v7+9ubSuqqWioaSpsLq+wcHAwcTNbz8vJyI"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"rKmop6mwxVhHbLyrpaWpr7rE0XZOR0dKS0A0KyQhIycrKycpMmmzqau6Vzc2Rs+"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"qquvucl7T0lHSEc/Ny8qJyYoKisqKi03Wb+xr7bHXUZIa8Szrausr7W6v8XIxb2"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"OjQvLi0tLi8vLzAxMzg+SVvr2M7JxsTAvry7ubi4uLi3tbOzs7S2uLq8v8XN2fN"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LCsrLS4xNjtBS1v32MrCvru4t7a1tLS0s7OysbKztLa4ur7EzNbvXU9HPzs3My8"}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"4A1BB234AA5A2236.1780560743.6433266","text":"алло","stt_partial_ms":908}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Nzo+Rk9e6tXLwr67uLa0s7Ozs7OztLS1t7i6vL7AxczZe1dKQT06ODU0MjEvLy8"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PD9GTlp139LKwr66uLa1tLS0tLS0tbW2uLu9v8PGyMvQ3PFlVEtEPzw5NjU0MzM"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Ly8uLi4xOUf0x725ur3Bw8G9uLOxsLCytLa3ubu9wMTFyMrKysvN0eVkT0I7NzQ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Li4tLS0tLS80QH7Ct7O1ur7Av7y5t7WysbCytbvAyc7PzcvJx8TAv8LL7lFFPjw"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"MS8vMDAvLi4vMDdI4sK6trSztLe7vr68uri2tra3ubzDys3LycvMysrMz99qVUg"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LS0uLy8wMzY6Q1buy723tLKxsrO2t7e4ubi3tre3t7m8v8TK0OFwX1JJQz87ODY"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"VFhdYmlxfPjv7Onm5OLh4ODf39/g4eHi5Obo6uzv8/n+e3ZxbmtqaGZlZGRlZmd"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+vv8/f9/fn5///79/f38/Pz8/Pz9/f3+//9/fn9/////f35+fn5+fn7//v38+/r"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/fz8/f3+/v3//v3+/v7+/v////9//v3+/v7+/v7/fn5/ev15/v562e354mzy/W7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+f9b22Jo11rfdl7ZWut9XOBcaN5Y3vpZ1ljy41LZYVnYUe/oTdllXt9b6G5b1mB"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"YHLmaWHabGb452Vq31zmZ3X0W9pda81Tc8tM5dNMz/ZOyWtXzWBjzVdkzVf23mb"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"6G3y/WDcaGTaXenoXO1yfF9q42Fk4Xlg6+1uduR7beXsbOPqX+LmX/D3buxe4XF"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"7+ZZ3e5o6/ZwafRiZnR1eF9z21pz11vaeWvaXOfuXejzYu/5buh6+uN+/vn4733"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/txwfuNodX5m8Hxn5fpjf/5sbGZvclh46VP+3Fvj6GTeb2DfZ1rqdGd4a/R2Zel"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/ft6+3r/6n/36+7t9fjy9vvw7f715vz+7/t+dXhzam5vbndufet0eOl3cf5tdHJ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fXr28/z57+/3+vT0f3z8/nz+9fDz9fLx+np7fHVydnh4d3l9e3h6fXp1dXh2dXt"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHx7fH5+fn1+/f7++/v8/v/+///+/f38+/v7+/v8/n5+fn5+//7+////fnx9fn1"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/v7+/v7//v9/fn59fHx8fHx8fHx9fn7////////////+/v39/f39/v39/f39/f7"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":450,"bytes":160,"expected_frame_bytes":160,"rtf":1.15,"avg_rtf":1.017}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/////////////////////////////////////////39//39/f35/f35+f35+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn5+fn5+fn5+fn5+fn5+fn9/f39//39//////39/f3//f//////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39+fn5+fn9/f3///////////////////////////////////////////39/f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"////////////f///f///f39/f39/f39/f39/f39/f39/f39//39//39/f39//39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39///9/f39/f3//f39/////f3//f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////////9/f/////////////////////////9/f///f/9/f/9/f//////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/////////39//39//3//////////f39/f/9/f39/f39/f39/f39/f39+f39/fn9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//9//3//f39/f39/f39/f39/f39/f3//f39/f39//39/f39/f39/f39/f35/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f///f39/f39/f3///3/////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f/9/f39////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"stop\"}"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":500,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.014}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"алло","stt_final_ms":2442,"partial_count":3}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":550,"bytes":160,"expected_frame_bytes":160,"rtf":1.2,"avg_rtf":1.014}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":600,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.013}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"нет","stt_final_ms":1359,"partial_count":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":650,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.026}
rsd_telephony_orchestrator   | 2026-06-04 08:12:46,349 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":700,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":1.017}
rsd_telephony_orchestrator   | 2026-06-04 08:12:47,592 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":750,"bytes":160,"expected_frame_bytes":160,"rtf":1.15,"avg_rtf":1.01}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"start\",\"start\":{\"mediaFormat\":{\"encoding\":\"audio/x-mulaw\",\"sampleRate\":8000}}}"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":49,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":49,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":50,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":52,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":52,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":74,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":75,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":77,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":96,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":120,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":151,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":169,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":172,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":192,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":217,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":241,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] pacer ready no pacer {"call_id":"4A1BB234AA5A2236.1780560743.6433266"}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"4A1BB234AA5A2236.1780560743.6433266","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"4A1BB234AA5A2236.1780560743.6433266","reason":"playback_grace","since_start_ms":265,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"4A1BB234AA5A2236.1780560743.6433266","text":"меня","stt_partial_ms":1339}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/////f39/f39/f39/f39//39/f39///9/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f3///39//////3//f3///39/f39/f39//39/f39/f/////9/f//"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39//39/f////3///39/f3///39/f39/////////f39//39/f3//////f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f3//f39/f39//39//39/f3//f39/f39/f39/f/9/f39/f/9/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":800,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.016}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"////f3//f////39/f/9/f39/f39/f39/f/9/f39/f/9/f39//39/f3//f3//f3/"}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"меня слышно","stt_final_ms":1746,"partial_count":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:12:49,395 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=4A1BB234AA5A2236.1780560743.6433266 db_id=75 latency_ms=6119 redis_history_len=1
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f3//f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f3//f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":850,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.01}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3///3//f39/f3///39///9/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f/9/////f//"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f////39//3///3////////9/f/9/f39/f39/f39/f39/f39/f39/f39/f39/f35"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////////////7+/v7+/v//////////////f39//3//f3//////f/9/fn5/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"pKettru9vcHP4+HSxcDFyMbEyvtAMi0sLCsqKSgpKCMjLUTOt7OvqKSipa22uLe"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"OUjtvq6moZ6enZ6foqessLi9wcC/w8nZbFZGOjArKCUkIiAfHx8gJSovO1DQuq6"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LCsqKSgpKSssLjM5QlXfxrqxraqpqKeoqamrra+ztrq+ydvvalRIPDk2Mi8tKys"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ra+zt7rEy9V9XU5DPDg2My8uLi0sLCwtLjAzNztCUurLv7mzrqysq6urrK2ur7K"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NTg9RE5n3Mi+urazsa+vr6+wsbK0t7q9wsfO3XpYTEU/PDk2NDIxMC8vLzAyNTg"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"v8XN2fFfUUlDPjw6ODY1NDMzMzM0Njg7P0pZ8NPHv7y5t7W0tLOzs7S1t7m8v8T"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PT9ES1dv38/HwL27ubi3t7i4uru8vsLHzNLd7mtcU01KSEVCQD8+Pj09PD09Pj9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yc/b3OpsWmtKTtVOP0FBPzw9QEZA9M1PUGLPw7+7wL2+2PpVTWh5rp2gq7m8uuU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GQ8OCwgIBgYUOMSonZaPkZ+2yt5mNzTDpZqVl5eWmqS4SS4lGxQQDg4PCwscXbG"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/trHvriyr62tra+yt7vCy8/Z6WZTSkRAPTs7PkNKVXfZy8S+vry7u7m7s7evobd"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"CwkMG9Cdko+Sm64xHyEtUbKfmZWWnaWvxPY4KCQjIB0XEQsHDy+tlY+Qkp1wIx0"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"UUM3JxsXDgoSNK2alJebpGMiHi3Dn5iYm6W22kVJ37+90zYqJBsYDwsYb6WamJy"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ubdaPUEsHhwSDRgzsZqZnql5KyQqRKubm5ucrN1GUL+zuN9KQCgeGRARGzG1nZu"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"zM5BKyclHBYVHTu3qKSnt0UpJzu1n52en6iws9dW2NHj4k85Kh8bFxgdMbeinqX"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"TjovLCwsKiciICQqNUrmwLm4wHtczq+fnaCmrbe2rquv2jQnIiIjJSgpJyYnL0P"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yMXBwL66ury7vr+5ub/N7nhUS0xFSkxEPz1AP0JMS13rYE9NUObb1sjzW2xo9uT"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"WVZiXV5tWF7ycfn969x66N9md21deH5qYmf9ZlNZXWluXXR6cOnv/vv88ejp5t3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"4ev86+Z9efX07v597Hptcmduc2xsdHplbf/69/9xanv4e33r92l/e3TxcP59cPn"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"7/f37PHx7/Xy7e/3/Pf7fP37+vn8+fl++fl+/v9//P58fXz+fvz4/fv/fv1+fnx"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/f39/fz8/Pv7+/z8+/v7+/v7+/v6+vr6+vr6+/v7+/z8/P39/fz8/Pz8/P39/v7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/Pz8/f39/f7//39+fn5+fn5+fn5+f/9///7+/v39/v7+/v7+//7+/v79/v7+/v7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHp3fGv9at3D4/PV5PpaaOx8anZ0a3p3ZVVTU1dXUVRXVmjq5725zN73/E9JS0x"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ZXF1bfb2bml56ezx73zv3uHs9fT17vFq9Nni7e/x4e9p8u90//Z+euvva3Xu5+v"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3+3u7eDtbndrX2BfW1pcXFtcX2FiZ2xubn3y8+be4uTf293f3t3c5ufm7+Ll/Hl"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"RdO4raegnZ2eoKarsb3XYExFRk9t0b+2r62tr7bAzeNPPjcxLSomIyAeHh0dHBw"}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"меня слышно","stt_final_ms":692,"partial_count":0}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"s8ZeQTk3PUt9xLKrqKamqay2x/lHODEuLCopJiMgHh0bGhoYHCc0T7eknZmXl5e"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"vbavq6qsr7W+zntKPzw0MTEuKiglIB4dGxoaGh8rNV6vpJ+bmJiZnKCmrcHsWkU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"sLa8w9tWRjszLywpJyUiIR8eHh4eHyYuN1q5rKafnJqam52fpay0wOZaT0xRbdz"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ODEtKykoJygoKiwtLjE1OT5KWPbMwLq0r6yrqqmqq6yvs7e7wMfLztHe3977aGJ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"9vf39/b08vDu7evq6ejn5ubn5+jp6+3v8/j8fnp4d3Z1dHV1dnh5e31+//7+/f3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+/n49/b29/j6/P3/fnx7enp6ent8fH19fn5+fn19fHt5eHd2dXV0dXV2d3h5ent"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//9+fX18fHx8fHx8fHx8fX7//v39/Pz9/n5+fX18e33///x9+f1/4en793f/eXF"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/H7v+XZ9e3Bob3pvee/v/nvy7fRzdXVteG/x+m36bXb49up4bnx1evd2aW1scG5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"2+n1fmlze2Xo3m3n9Whva+/pYfrrW/lradry39L0ceZ1felx3+9e3Odl9nbu8Gn"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":900,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"cfRveXvvcG7h62926N9tb/BaVWZ0bmF94Gx+4/rsae/XbPncdnl9Z+xrY8zacc/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3tng39rg4t/k6O3v8Pf29Hh2emljZF1ZWVhWV1dbXV9td3zv7ufd3djU1tHO0c7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KigoKSonKCorPcq+r6Skp6estbvGzsS/vrWztLO2vL7CzdjY4uPW4trO8FxfSTg"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KiknKiwqLTNCwq6sp6Klq7C1ub3DvrWztbSytrzDyczW4drW3OLva2JOQ0I9NjQ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Li8wNDlBV9e/tq+trKytr7Gys7OxsbKys7W5vcPM1ebq2u9YT0U8ODMxLy0sLC0"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"urWwr6+urKurq6ysrbC1t7u/yM7Z72lYST86My8vLi4tLS0uLi4vMDM2Oj9LY9v"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"vsHGy9Xlc15VTEdEQT48Ojo6Ozs7PT9BRUlMU19r++DUzcrGw8G/v8C/v8DBw8b"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ZGVlaGtub25wef79+/Xw7/Dw7+/x8vP1+Pn8/3x3dHV5e3p7fHl7fv759fLw8PH"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"e3x8e3l4d3Z2d3d3eHl6e3x+fn59//38+/r5+fj5+fn6/P38+/v8/P3+fX19fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/P39/f7+/v//////f////39+fn19fX1+fn5+fn5+f//+/v7+/v39/Pz9/f7+///"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39+f/////////////7///7///9/f39/f35+fn9/fn5+fn5+fn5/////f///f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn5+fn5+fn9/f3//f/////9/f39/f39/f3////9/f39/f39/f39+fn9/f/9/f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f////39//////////3//////////////////////////f39/f/9/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3////9/f39/f39+fn9/f39/f35+fn5+f39/fn//f39/f39/fn9/f3///////39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3//f3////9/f3//f39//39/f39/f39/f39/f3//f39/f39/f39/f35+f35+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/fn5+fn5+fn5+fn5+fn9/f35/f39/f35/f35+fn5/fn9/f35/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/fn5+fn5+f35+f39/fn5+fn9/fn9+fn5+f39/f39/f39+f39/f39/f39/f/9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/////////////39/f39/f39/f39/f39/f39/f39/f39/fn5/f3/////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"///////////////////////////////////////////////////////////////"}
rsd_telephony_orchestrator   | 2026-06-04 08:12:51,511 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f3//f3//f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//9//39/f39/f39/f39/f39/f39/f39/f39/f39/f/9/f39/f39/f39/f39/f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3///3//f3////////9///////////////9///////9/f/////9/////f/9/f/9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f3//f3//f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f///f39//39/f39/f39/f39///9/f39/f39/f39/f3///39///9/f3//f3//f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f///f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f/9/f/9/////f/////9/////////////////////f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"////////////////////////////////////f///f39/f39/f39/f35+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fvn4+fv79358+fn1//32fvr6f/38/P3+ev76/n76+Hx+fnp1c/38/v359Pz4+H7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//p+dnV2fH10fP3++394fPxyd/z++vt+e/359/n7enr3/f/89PR+d3n7+vf0d3v"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"7vXv8fr2/nd59/127Onz/nF87+zx8/n9/X55fP32+G9tevv+dXX6e3l9enhwfP9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"93j/ent5bv5+ePR1+/lvfnX8f2/7/n359fN3dvH2+/59/v18+ff09XT5fX/yfvf"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"enn/fXp6/P92fPTt6+3z++7zefzv7fv3f//v+/b6/fR/ev15fPD6/fn6+vz9/nt"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"dl/w8mlhX2p3dnVv8u/qf3Df9+zh9+jo3919+/pnbfHsd/f3/+jye+l9YvPzeXl"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/HX27vr1d2x5fHVtc/56+vLs3d7o6ubpenl8amVqbmVdXFdTW1lXZmRlfObe2dj"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Rj45My8rKCcnKzA9Yc68tK6rqKamqa22xOdPRD04My4pJyYoLDRH6sS4sKyppqW"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LiwqKCgrLjpax7evraysq6qqrLLA9EQ3My8uLCkoKSw0RNm9tK+uraupqKquvPp"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"pq6+TjMnIB0cGxseJTfIrJ+cmpqcnaKsvUouJB4bGhkZHCQ6vKacmZiYm52irck"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"FxwlUKubk5KTl52irL9LKh4YFBQVGB0p7aiZkpCSl56lsc49JxwXFBQUGB4twqK"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"HhkUEhIVGyjcpJePjpCWnqm9WjMjHBYTEhMZID2unJKPj5Sbo6/MRiseGBQTEhc"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"pa6/6Ug4LikkIyQoLzpZy7quqaSjp6u0xdpSPC8pJygqLjZCX863rquqrK60vst"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"WtVaeshY48Vyz+tsxfZr31j07/pdSm1393l+71nf3HnXV3TSXGJr/1JSVlxZTd9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"2NfaWeH8W9pvW2pb6+ByX1b5c/TbV/rWXuj83VlVyEfa1T/HTUm8T+XNTdv70F9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"WfbKRvXMPL92Srw/c9RMzHRQ40vczkTWaV3PZWRvUdRkRsFJ+tdDwk7N3kW9ROL"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"4A1BB234AA5A2236.1780560743.6433266","frames":950,"bytes":160,"expected_frame_bytes":160,"rtf":1.3,"avg_rtf":1.007}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3u3naVLK61HLUenKSdH1TslV5uhL0HNSzm5Nzk72xEpzZO7uXO1Q+O3eX0/NWmL"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fvRr21bt0lLdTm7GTt7fU9jq835acdja/Gf941/fT17nVtBXWe1h5dhb3VVYx0b"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"W9h0ctJX6vnb5GTUXtj1XtV7dfdsZtn8Z/N6Z/bqVddjYN9P2dxYZd/uYvVPd9d"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"x8nJyszN1edfTUQ+NzIxMTMyNDhF5LuwqaOhoKassrvFaT0vKCUhHx4cHio+w7K"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"q6+590g8PEVCPUdVSkY7LCUeGiMtQLmto52cn6Kps7viSURBSltZVXJoRz4zKiI"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Zd7SycfIz1g5LycgGxYbJjbMrqWdmZufp7K90VA+Oz1Nd9W/ubm9z002LCUeGRU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yEk5LystOFrEtaynpaiz5jsrIR0ZFhUVHTbCqZ6al5WZoK/ZQTcvKy03XL+xq6i"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NCkjHx4dHR0dKE+4p5+fnp2fp7LZQTo3OD5L6L+zrausrrfLTjUrJSAfHh4eHSY"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KzzSsamopqWkpKiwwn5MR0hISlL4yLmzsbW9zl9BNCwoJicoKiknKzZTv7Ctq6q"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NDM0OD5MZujXzMS9uLW2ur7EyMnLz9LS0M3Ky8zS33leVlFNR0NCPjw8OTc2Njk"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"2uLofmJdUk5MR0RAPz49PTs6Oz1DS1dy3tLLxsK/vr/Aw8TGx8jKyszNzM7O0Nv"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"u7u8wMnR19bOyMTCwL68urq/zeJoVExIQz89Ojc0MC4tKigsNVi9r6yssLa6vsb"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NiwmISAfHx8dKP6ompieq8ZMPjcxNUfFq6KgpK2930s6OULouKyprLfNXEA2Ly0"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"My8yWLSmoKWxxXlLQTo5T8Ctpqixx18/ODg+UfB+TDowLCspJSQfHzaynpmdrMd"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PUZXy7avr7a/z3FPTE1f1c3YXD82MS0qKSYkIyEvt6Ccn67OVzw0NkPIrKWmrcB"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Y0RAR2TW2W1LPDQvLCopJiUiJkuxpKCnsr52Pjg5Ur6uqquvucdqS0ZJbcu+trG"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"MC8uLS43TNS+uba1t7u+wb+8u7q7u7y+wMPGx8nLzM/U3nVeU0xJREE/PTs5NzY"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3Nvb3uHi3tva2tjU1dbZ3+Ll7fl+aWduZ2RiY2dfYGJdZWZfaG5+d29+bXR3aXP"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fvh9f29x/Xz++Xx9fXn9fnr/e3Z9dHJ//396f/f/+/V//v97fH7+e3v+/H96eH/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/fz7/PT8/vX5///5/vz09vt8/fh+fHx++/19+/59fXV8fXd6ff56en1+/P54eP7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f/1+ev19eH9+ff//ffr+fPx9/Pz/+n379Hv/+nz+eXp/eX33+n35/HV7fn30/Hn"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHt7fn7/d3z8e31+fn//fXn/f/z6fH18ff36/Pv8//n8/v78/v/6fP35/vt8fP3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"eHp7fHh4fXv9/P76fn58fX14/n9+/Xt9fX/8fP79+/58/Pj4/vz4/v19e/z7+Pn"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+/3+fHR6fn5+e3x6d3l1fPj9fnl8+Hx4+3x5/315d334+39/fH58fHx8/vz8fn3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+/1+/v38/X/9/v/9fXh8/3x5eXp//f97e///fHx9//3/f35//31+/n5+fHl7fH5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHp8e3t5en7+/f59fX58fHx+/v79+/r7/n18fH1+fv79/n17ff7+/v38/P99f/7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn5+fn5+f39+fX19fXx8fH19fX1+fn5+fn5+fn19fn5+fn///v//fn5+fX1+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn9/f39+fn5+fn5+fn9/fn5+fn5+fn5+fn5+fn5+fn5+f39/f35+f39////////"}
rsd_telephony_media_gateway  | [media-gateway] pipeline metrics {"stt_partial_ms":[908,1635,1636,1057,1339,1639,1647],"stt_final_ms":[1896,2071,763,2442,1359,1746,692],"vad_speech_ratio":0.232,"vad_frames":980,"vad_speech_frames":227}
rsd_frontend                 | 185.164.150.17 - - [04/Jun/2026:08:12:52 +0000] "GET /ws HTTP/1.1" 101 93651 "-" "-" "-"
rsd_telephony_orchestrator   | 2026-06-04 08:12:53,053 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox send skipped {"readyState":3}
rsd_telephony_media_gateway  | [media-gateway] pacer ready no pacer {"call_id":"4A1BB234AA5A2236.1780560743.6433266"}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"4A1BB234AA5A2236.1780560743.6433266","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_worker         | INFO:     172.18.0.10:44368 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:12:54,941 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=4A1BB234AA5A2236.1780560743.6433266 db_id=75 latency_ms=5544 redis_history_len=3
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_frontend                 | 185.164.150.17 - - [04/Jun/2026:08:12:54 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:12:55,309 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_orchestrator   | 2026-06-04 08:12:57,029 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] vox send skipped {"readyState":3}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] pacer ready no pacer {"call_id":"4A1BB234AA5A2236.1780560743.6433266"}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"4A1BB234AA5A2236.1780560743.6433266","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:12:58,961 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=4A1BB234AA5A2236.1780560743.6433266 db_id=75 latency_ms=4018 redis_history_len=5
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:12:59,349 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_orchestrator   | 2026-06-04 08:13:01,031 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox send skipped {"readyState":3}
rsd_telephony_media_gateway  | [media-gateway] pacer ready no pacer {"call_id":"4A1BB234AA5A2236.1780560743.6433266"}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"4A1BB234AA5A2236.1780560743.6433266","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-04 08:13:05,311 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=4A1BB234AA5A2236.1780560743.6433266 db_id=75 latency_ms=6346 redis_history_len=7
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"4A1BB234AA5A2236.1780560743.6433266","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox send skipped {"readyState":3}
