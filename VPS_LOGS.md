rsd_telephony_worker         | INFO:     157.5.32.85:48142 - "GET / HTTP/1.0" 404 Not Found
rsd_telephony_worker         | INFO:     172.18.0.10:58826 - "POST /api/internal/telephony/webhook-auth HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:58826 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:58842 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:58826 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:16:41:59 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:51498 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:51508 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:51498 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_redis                    | 1:M 01 Jun 2026 16:42:07.912 * 100 changes in 300 seconds. Saving...
rsd_redis                    | 1:M 01 Jun 2026 16:42:07.913 * Background saving started by pid 339180
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:16:42:07 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_redis                    | 339180:C 01 Jun 2026 16:42:07.948 * DB saved on disk
rsd_redis                    | 339180:C 01 Jun 2026 16:42:07.950 * Fork CoW for RDB: current 0 MB, peak 0 MB, average 0 MB
rsd_redis                    | 1:M 01 Jun 2026 16:42:08.016 * Background saving terminated with success
rsd_telephony_media_gateway  | [media-gateway] VAD: Silero ONNX + energy assist /app/models/silero_vad.onnx
rsd_telephony_media_gateway  | [media-gateway] reply session registered {"call_id":"852457B0164A9876.1780332119.13605141","total_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] session.start {"call_id":"852457B0164A9876.1780332119.13605141","connection_id":47,"codec":"pcmu","pipeline":true,"stt_provider":"yandex"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":1,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0}
rsd_telephony_orchestrator   | 2026-06-01 16:42:08,424 - app.telephony.orchestrator_worker - INFO - 489: orchestrator session.start call_id=852457B0164A9876.1780332119.13605141 connection_id=47 redis_session=True awaiting_ext=True
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":50,"bytes":160,"expected_frame_bytes":160,"rtf":1.3,"avg_rtf":0.727}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"852457B0164A9876.1780332119.13605141","digit":"1"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"852457B0164A9876.1780332119.13605141","digit":"2"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":100,"bytes":160,"expected_frame_bytes":160,"rtf":1.25,"avg_rtf":0.94}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"852457B0164A9876.1780332119.13605141","digit":"3"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"852457B0164A9876.1780332119.13605141","digit":"4"}
rsd_telephony_orchestrator   | 2026-06-01 16:42:10,804 - app.telephony.orchestrator_worker - INFO - 369: orchestrator _play_agent_welcome call_id=852457B0164A9876.1780332119.13605141 welcome_raw='Здравствуйте! Чем могу помочь?' welcome_text='Здравствуйте! Чем могу помочь?'
rsd_telephony_orchestrator   | 2026-06-01 16:42:10,805 - app.telephony.orchestrator_worker - INFO - 236: orchestrator _stream_routing_phrase call_id=852457B0164A9876.1780332119.13605141 log_label=welcome text='Здравствуйте! Чем могу помочь?' plain='Здравствуйте! Чем могу помочь?' empty=False
rsd_telephony_orchestrator   | 2026-06-01 16:42:10,807 - app.telephony.orchestrator_worker - INFO - 254: orchestrator welcome starting TTS call_id=852457B0164A9876.1780332119.13605141 voice=default lang=ru-RU text_len=30
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"start\",\"start\":{\"mediaFormat\":{\"encoding\":\"audio/x-mulaw\",\"sampleRate\":8000}}}"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":22,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":23,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":23,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":45,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":71,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":98,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":116,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":117,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":136,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":156,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":196,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":213,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":240,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] pacer ready {"call_id":"852457B0164A9876.1780332119.13605141","queue_len":15}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"852457B0164A9876.1780332119.13605141","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":309,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":310,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/////f39/f39/f39/f39//39/f39///9/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":338,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":339,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f3///39//////3//f3///39/f39/f39//39/f39/f/////9/f//"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":355,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39//39/f////3///39/f3///39/f39/////////f39//39/f3//////f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f3//f39/f39//39//39/f3//f39/f39/f39/f/9/f39/f/9/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":395,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":395,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"////f3//f////39/f/9/f39/f39/f39/f/9/f39/f/9/f39//39/f3//f3//f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f3//f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f3//f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":428,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":429,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3///3//f39/f3///39///9/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f/9/////f//"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":470,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f////39//3///3////////9/f/9/f39/f39/f39/f39/f39/f39/f39/f39/f35"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////////////7+/v7+/v//////////////f39//3//f3//////f/9/fn5/f39"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":519,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":520,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"pKettru9vcHP4+HSxcDFyMbEyvtAMi0sLCsqKSgpKCMjLUTOt7OvqKSipa22uLe"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"OUjtvq6moZ6enZ6foqessLi9wcC/w8nZbFZGOjArKCUkIiAfHx8gJSovO1DQuq6"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":557,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":150,"bytes":160,"expected_frame_bytes":160,"rtf":0.1,"avg_rtf":1.024}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":559,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LCsqKSgpKSssLjM5QlXfxrqxraqpqKeoqamrra+ztrq+ydvvalRIPDk2Mi8tKys"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ra+zt7rEy9V9XU5DPDg2My8uLi0sLCwtLjAzNztCUurLv7mzrqysq6urrK2ur7K"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":599,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":599,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":599,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NTg9RE5n3Mi+urazsa+vr6+wsbK0t7q9wsfO3XpYTEU/PDk2NDIxMC8vLzAyNTg"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"v8XN2fFfUUlDPjw6ODY1NDMzMzM0Njg7P0pZ8NPHv7y5t7W0tLOzs7S1t7m8v8T"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":711,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":712,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PT9ES1dv38/HwL27ubi3t7i4uru8vsLHzNLd7mtcU01KSEVCQD8+Pj09PD09Pj9"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":725,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yc/b3OpsWmtKTtVOP0FBPzw9QEZA9M1PUGLPw7+7wL2+2PpVTWh5rp2gq7m8uuU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GQ8OCwgIBgYUOMSonZaPkZ+2yt5mNzTDpZqVl5eWmqS4SS4lGxQQDg4PCwscXbG"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":769,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":770,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/trHvriyr62tra+yt7vCy8/Z6WZTSkRAPTs7PkNKVXfZy8S+vry7u7m7s7evobd"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"CwkMG9Cdko+Sm64xHyEtUbKfmZWWnaWvxPY4KCQjIB0XEQsHDy+tlY+Qkp1wIx0"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":807,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"UUM3JxsXDgoSNK2alJebpGMiHi3Dn5iYm6W22kVJ37+90zYqJBsYDwsYb6WamJy"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":828,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ubdaPUEsHhwSDRgzsZqZnql5KyQqRKubm5ucrN1GUL+zuN9KQCgeGRARGzG1nZu"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":851,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"zM5BKyclHBYVHTu3qKSnt0UpJzu1n52en6iws9dW2NHj4k85Kh8bFxgdMbeinqX"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"TjovLCwsKiciICQqNUrmwLm4wHtczq+fnaCmrbe2rquv2jQnIiIjJSgpJyYnL0P"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":889,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":889,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":906,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yMXBwL66ury7vr+5ub/N7nhUS0xFSkxEPz1AP0JMS13rYE9NUObb1sjzW2xo9uT"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"WVZiXV5tWF7ycfn969x66N9md21deH5qYmf9ZlNZXWluXXR6cOnv/vv88ejp5t3"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":934,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":935,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":959,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"4ev86+Z9efX07v597Hptcmduc2xsdHplbf/69/9xanv4e33r92l/e3TxcP59cPn"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"dtmf_suppress","since_dtmf_ms":998,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"7/f37PHx7/Xy7e/3/Pf7fP37+vn8+fl++fl+/v9//P58fXz+fvz4/fv/fv1+fnx"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/f39/fz8/Pv7+/z8+/v7+/v7+/v6+vr6+vr6+/v7+/z8/P39/fz8/Pz8/P39/v7"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/Pz8/f39/f7//39+fn5+fn5+fn5+f/9///7+/v39/v7+/v7+//7+/v79/v7+/v7"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHp3fGv9at3D4/PV5PpaaOx8anZ0a3p3ZVVTU1dXUVRXVmjq5725zN73/E9JS0x"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ZXF1bfb2bml56ezx73zv3uHs9fT17vFq9Nni7e/x4e9p8u90//Z+euvva3Xu5+v"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_orchestrator   | 2026-06-01 16:42:11,898 - app.telephony.orchestrator_worker - INFO - 322: orchestrator welcome TTS completed call_id=852457B0164A9876.1780332119.13605141
rsd_telephony_orchestrator   | 2026-06-01 16:42:11,898 - app.telephony.orchestrator_worker - INFO - 328: [orchestrator] welcome guaranteed path=stream call_id=852457B0164A9876.1780332119.13605141
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3+3u7eDtbndrX2BfW1pcXFtcX2FiZ2xubn3y8+be4uTf293f3t3c5ufm7+Ll/Hl"}
rsd_telephony_orchestrator   | 2026-06-01 16:42:11,910 - app.telephony.orchestrator_worker - INFO - 432: orchestrator dtmf routed call_id=852457B0164A9876.1780332119.13605141 extension=1234 agent_id=37
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
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":200,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.026}
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
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":250,"bytes":160,"expected_frame_bytes":160,"rtf":2.05,"avg_rtf":1.026}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LCsrLS4xNjtBS1v32MrCvru4t7a1tLS0s7OysbKztLa4ur7EzNbvXU9HPzs3My8"}
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
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":300,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.015}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"852457B0164A9876.1780332119.13605141","text":"алло","stt_partial_ms":2166}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":350,"bytes":160,"expected_frame_bytes":160,"rtf":3.05,"avg_rtf":1.02}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"852457B0164A9876.1780332119.13605141","text":"алло прием прием меня слышно","stt_partial_ms":3637}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":400,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":450,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.014}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"алло прием прием меня","stt_final_ms":4642,"partial_count":5}
rsd_telephony_orchestrator   | 2026-06-01 16:42:17,854 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":500,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.009}
rsd_telephony_orchestrator   | 2026-06-01 16:42:19,118 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":550,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.009}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"start\",\"start\":{\"mediaFormat\":{\"encoding\":\"audio/x-mulaw\",\"sampleRate\":8000}}}"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":35,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":37,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":37,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":38,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":63,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":66,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":67,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":91,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":111,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":112,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":190,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":191,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":191,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":232,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":233,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":233,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":254,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] pacer ready {"call_id":"852457B0164A9876.1780332119.13605141","queue_len":4}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"852457B0164A9876.1780332119.13605141","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":287,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":335,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":336,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//9//39/f39/f39/f3//f39/f3//////f39/f39/f39/f/9//39/f39///9/f/9"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":397,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":600,"bytes":160,"expected_frame_bytes":160,"rtf":0.1,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":400,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":401,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39//39/f/////9/f/9///9//3////9/f/9/f/9/f///f39/f/9"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":470,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":470,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":470,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":471,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//9//////3//f///f///f39/f3///39/f39/f39/f39/f39/f39//39//3//f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":496,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":496,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////9/f39/f39/f///f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":517,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////////9///9//39/f39/f39/f39/f39/f39/f3//f39//3//f3//f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////////////////////////////////////////////////////9/f/9/f39"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":547,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn9/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/fn5+fn9/fn5/f35"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fX59fH19fHx9fHx9fX5+///+/fz8+/r59/b39/b4+vr7/f59e3l2c3Fvb25ub29"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":597,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":597,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"852457B0164A9876.1780332119.13605141","reason":"playback_grace","since_start_ms":597,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"RkVLUVl63tDHxMK/vr++wMPEydDX3+vwdWRiXFNOSkNBQD4+Pz9CSExQWWV+5df"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Mz5P2cC6s66sq6qrq6usra+xtLe6v8nYaEs+NjAtKygmJSMkJyktNkFdzL+5sa6"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"RW3KvbawrauqqampqqusrrCytrq+x9R+UUM7NjEuLCopKCcmJigrLjU/VdjDurO"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Li4vMTQ5P0to2ce9uLWzsrGxsbKztLa4ur3CydLja1ZMRT88Ojc2NDMzMzQ1Njk"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Uk1KR0RBQD8/QEJFSU5YZPnn29TRzNLMxsW2r7Kzt73M3N5kVktHP0NMPbWn1D8"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"HcqomJKOjZvA+EApHhwyrqWhnJqcqnFGPTQrHxwWDQgPPqiclY6Mlbg7LyoiHzK"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"qpubmJapOh4aJUa8oZiVmqzfPDE1OT9UPCkcDAwjyJ2Ym5ae3ycXHDjHopmWl6P"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"r6qgm56rwUo1MDAvNzYnGhgztKagra61MyQnObmrq6Gcn6t7ODErLTY3LyEXJbu"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"q707IB8rxaWinp6isUcyMzhBMCUcERq9n5mcrbQ7HR4ruJ+kn52ls0MuOkA3LCA"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"6y8sN+Gwp6Ceoq5ALCofIB4WHj60oJ+iqcBHLC9ux7OnoJ+owTwsJx8dGhkocq6"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"4j8tKCMYGSM5u62mnZyhsdXJy9Hfa8zNWT0tKiMaHSg8vrSpn56grb25vcXoUGx"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"852457B0164A9876.1780332119.13605141","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Njc6PD9DSU9f6tHGv7u5t7a3ubzAydd5VUlBPjs5ODY2ODxDTV3x1srDvry5trW"}
rsd_telephony_orchestrator   | 2026-06-01 16:42:20,978 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=852457B0164A9876.1780332119.13605141 db_id=66 latency_ms=3523 redis_history_len=1
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PUNMXO7TyL+7t7SysbKztrq+ydptT0M8NzMwLy8wMzc7QUxh4MzCvLi0srCwsLK"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KiorLTE4P0xo2sm/u7e0sa+vrq6ur7G2u8TVbE0/OTQwLiwsLC0vMjc9R1ju0ca"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"t7e5u7/Gz+NmUUhBPTs6Ojo9QkfHv+Pf4NPV6Nv7XHxPUMnEz+Vrd2V82dvb3fF"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"DgoRXqWVkJGPnHopHCUyM6+ZlJKft9guJiElRD8uJRoSDhlKp5mVkpWlTyclN0T"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"JRwXDQ4orJeSlpmhSh0ZJc+roJqXmq1EKy8+SWbhzM46KB0VDwsat5mOkJmfax8"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"JDu+q67TPy8pKCcnIBkQDjuVjY6cvNgvHh8trZiYm6W52zYoNsCrrNIzKigrLi8"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"OCsfHBUWwZOPlrIyNC8nNMqimJ2zbkJIXFPPrKOowjYtNjs4NTZBQzMpHhwVFMe"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"RUl43VE9MzQ1Kh0aGhzhlY+Vqi0hJyk7uKSamqjPPzc/UFHOtKypst9MPzg8P0d"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"7zc+PDvSr6ekrsn6WU5bd93Mx8C7xM7O9l5OP0JUT0hGQEA7MzM3Mi0mISEzp5m"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"tsPM221cXnXXzcrM7tzRVkFATO7oVU5YXFBGQT88My4zPDo2MDFHuqmnrbrN3vP"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"eezh0svOz9RtXGdTQTo7QUhLSElKQDw/REQ/PD5KXf7v28vDvr7Av7/Awb+9u7u"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"QUVHRkVBPj5ARktSZe7c1tTOysrIxL+6uLm7v8TM3ezj2tnldGZcUUpGRUZHSEt"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3t7f3+Dh39/l7vf7f3p5e3x7dW1paGNfX2JmaGdmaGtsaWpwfPz79/Hv8PPw7Ov"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHx9fn5+fn5+fn9/f35////+/v3+/f7+/fz7+/z9/v7+f35+fn59fHx8fHx7e3t"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f35///9/fn5+fX19fX1+fn5+fn5/f//+/v7+///+/v7+/v7///9/f///f39+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn59fn5+fn5+fX19fn5+fn5+fn9/fn5+fn5+fn5+f/////9/f35+fn5+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/////39//39/f39+fn5+fn9/f35/fn5+fn5+fn5+fn5+f39/f39/f/////7+/v7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn9/f35/f39+fn5+fv////////9/fn5+fn5/////////f39/fn5+fn5+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f3/+/3/////+//7+///+/v7+/v7+/v/////+//7+//9/f35+fn5+fn5+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f/9/////f3/////////+/////39+fn9//39/fn5/f35+fn5+fn5+fn5+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fX1+fv//f/////9/f///////f3/////+/f39/v39/f39/Pz9/v/////+/v9/fn1"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":650,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"8nz9+XtwdPj29PX08fvx7Ov3dXr99fj1+/Dk7vj2+/T0fXFtcG9sefn8/33/f3p"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3Z5dm1xdnd6cX33en75+Xt9+3x0cnR4fXzv9n39cfz2fvX7cnF2eX52cvx9d3t"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+P3+dXn7eHn99P54eXz9e/1+bn79cHlvbvXx8/fz8f/89/t5/fZ+8fD8/3f0833"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fvfu+Gpv/3h5en73eX36dnN3e3dveP1xcfz7b2x8fHR8+fl5/PR8+Ht8+nj39X5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ae/vd3J29vn67Pj5ff7+eH1vfHl1+nZydHn3eXr+/Hhu8vV0fP9/dHJ2df35fX1"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"837qb2TneVtdVmFcVnF7dPfc3ud0beNdUXPrX1ZkaWNu7/P+am57a21z83dx/mJ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"b3rv5Pf983376d7r5ODi4OHd4d/f4+Lo7Oru+W1rbl5gXlpkXl1jX2JjbP/76ub"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Hx8eHyYuQc+2q6SfnZubnKCos8hoSj8+PDc0Ly0rJiEfHyEoMUjTu66noZ2bm52"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Kzlay7Won5uXmJqepq++31M+OTc1NjQvLSceHBscISo1Wsy2p5+al5eanqeuu89"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"nqKjqLC9dUpKQkQ9ODIqIhkWGh4sQV24qKCbnZ+fo6OouMlYQ0g/PTw2MisfGBc"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"JTBHZbCinpqanJufp6/YVUQyMTEtLigiHxkbIyg2UNWrn5yZmpuboKm26Fo9Li4"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"JSYiISQnLThLxrGqo56dm5yfpa263EM1LiooKCcmJiQkJiozPWK9r6iin52cnqG"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ZGPQzM+/w8i7w8K/0svLfdzsRmHLdkBDWHZBR05Ydj5SVFLxUnHc7+PTzenV2NH"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"edx+0Fb45mfOaOxq38TvXtH0/cZOVdxd1fxN81XU8z/XTlHjQWZoRczoUsZK4Mx"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"40zl0UxtbmjVelBez/di7FVt109Pz19rzU110lXc1lXbc1rWaFzm1V9ndm/73Ox"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Wc9dVsNeaNJga9zkTWbOX8xVSsr+6eBO4c1a0Vlcz17NYU/PbOXfTubjY99ybGZ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"aVxl5G/z7E3tZXPNX3JRf9xX6k3S11jXYN3rfeJV2+rv3kXd0uvZb+NX2NxV3FF"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fGdaamdbV1BYYGpqXl5dYGpeXFpXafLn5ura1c3KzMvLysfJzM/c5PVkYFpOST8"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GihcppqXlpeZm52lteJAOkdn287MyLquq6uy0D8uJiIfHBoZGRgXHClTqZuXlZa"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Ih8fJC1LuKefnZyen6KnrLbNUz44OUNmyrmyr66wt8RvQjQuKykoKCcoKCcnJSc"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ztPa3+5qWUxEPzw7OjgyLy4tLCwrLjRB4r2yra2ur7CxsrS5wMzc6N7UzcnIyMj"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"KCcsOe+1qaWlqa2xtbe6v9BvUFT4zL64uLm6u7y/x9tbRz48Ozo5NjIvLSwrKCc"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"oZqYnavGRjk7PUVe17+2uMLsQzYxLikkHhsaGhwZHUGmkouNmKtCKSgnKDBHu6C"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"MSsnLDZDTz0rJB0ZGRMWNqmTjZKesj0pIx4iQayZkZScrF8wKyYpRLqjnJ6ou0g"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"W6udm52jrb/0RT9aw66mpKaprrjE91Zf48a8vL/NZEg8NzMuKyglIiEiJCYmJys"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"vL/Dyc/Y4vxlW1VPS0Q/PTw8Ojs8PDw9PD5DR0xUW2/u3dPPzMjHxcTJx8TIx8X"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"dPxxbn747vL3+nl1//hycHP8+HTv9HtwZ/34bn19b3lzcnhtdv5weHRmdn16enH"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"c3f58XpvbXJzdfJ8ZGxya3Frc+7w9Pvy8vnv7vL98vP+6+ry/v7t9nn68u3s/Pb"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"5PlpbPPzb/T7amtsfHpqd/1sd+92XmTp7WZn8e5r7ud0cG7z8ezxbfDo8uxfVPt"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"33Nr7/FrX2deX3d9YFNd6+DyXU9Qbd3uXl394/tgWmF27+fr+Xf98enl83dw/PN"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"aGls/evw8u71/3h97O39cV5h7ODscnDs39zmaGN66e9qY2z98/pwaHP293JmZW7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ZVpn5dzwYmP45vZwc3Z2fPHv+ebf729lcuXrcWx27er5d/Xn6PhlX2JnfHZoaHP"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"9Pduam396Onv93n67PDx8H53//5uZm5/eGtmbvz1+fDr93RrbH3z+f707u73eX5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"sauoqauut76+vr25trWys7vCz2NMR0BAQDkvKyclJiUkIyQiITevoZ6fpKeryER"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PTgzLisqKSkrKioqKSlLqqCgoaevuds/PEnhvbOuq6yvt8TfbX3s3NrPyMrV9k8"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"XFxdX2BfXl9hZGltc3327+nf2dXT0M7NzMzMy8vMzc/R0tXZ3ODf5fL9dGlnaWt"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"q7jNNycuaL+0rKehnqe/XExGRUxzv7GyvszbZ0s/Oz1BOzMxMjAtKSQgHx4qr5u"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"p6ywyD45Rm3Ht7OwrrTMa1pMSkxHS1tNOzQvLS0rJyIfHh0sqJian6i+TjgrK0y"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"t7a4tre+1VxWbG9TRkA9OC8qKisrKigkJCMnbqafoaWtvNtDN0fIta6srrG3wtz"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NDEuKigoKCksLSssLzhYwbawrq+zt7y/vLm2srK0tbS2u7y7u7q6v8bPbUxEQT4"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"aeLn49jZzcrPy8vKw8TExsbLycbPz9nR0+LrYGZXZH1LW2tFW1JAZ0xTW0puUml"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"2GBi12ZZ6+74cOTvUeb1T99Wc9FSzFNczUPMXVPbUM5P7tVp+Vb2YN1Y/85G2tl"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"YOvVX1jPWGfKVO/oUM9dW9zp7Gl6Z1/l11t3+m/6eWxm0nfo3Vjd/XHOX1/OY23"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"XHzbaOb97V3p5WjeYW/YZfvnbeZladFWa95S3VZl1Erp00/kamvmTdVlWcpN78l"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"0exc2lTNWlbERtHSQsVuSsBMcsRM3N1V89tpVM9eWMlK7dpN0O1WXuBmXM5dX9F"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"2Vzk31bWXPLaVNv/T8hySMZhVctnY+zvd2XjeV7Vcm3OT+LfT8lXXNNV63t75Vz"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"SsdV7tJNzmZW0FPV1UrK/lHP+mnv3WX151rmc+rtauFZ1GFRyUltxURvyUff0U7"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":700,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"3/fmfGXdWW3fXOTzdPFp6mbr6F/dcWx2XuB4Zep5+Ofqb2zl7vxscP925PD4+nj"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"1tDMysnFxMXFyc3S4Ox9Z11STkxIRT88Ojg2NDEvLSsuTrion56gpKmwxFs9Nz9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PEBFQjgxLzA1OTcyLispJSvWq6Ccn6u8y99aVktEfbyvq66+ZkdGT+rQzsm/vLu"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"R0VDQD08OjcyLiwsLC0uLj26pJybn6/ZTERO9dTLv7evrrPEVz05QGPOw8DCxMb"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Ojw/RUhISEVBPTgxLSsrLTE4P+KwpaCiqr5pSk3xx7y4tbOztbzPUT48RGfNwL/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"VEc+PDs8Pj8+PTs6OTc1MzExNDg+R269raelqK++0OHXycC8ube2trrD3ldKTmf"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"RD47OTk6Ojk4ODg4Ojs9PkFGTFZq18K5sq+vsrW4uru8vL29vb7CyM/c7nZpYFx"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"PDw9PkBER0pNUVhheObXzMS/vLu8vL2+vr2+v8HDxsrP2ettXVVQTUpIRUNBQD8"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"5OHf3dzb29vb3N3e3+Dh4uXo7fZ+c2xoZmViYF9fXl5eX2FjZ2tvc3d6ff359fL"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"b3J1dnd2dHJzdHR0dXZ5fX5///9/f/77+fb19fX19fb4+fr7+/z8/f5/fX19fX1"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/v///3////7+/v7+/v7+//9/fn5+fn1+fn59fX1+fn5+fn9/f39/f3////7+/v7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f/////7+///+/v7+/v7+/v7+/////////39/f39+fn5+fn5/f39/fn5+fn5+f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f3//f39/f39/f/9/f39+fn5+fn5+fn5+fn5+fn5+fn5+fn5+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"////////f39/f35/f35+f39/f39/f39/fn9/f39/fn5/fn9/fn5+fn5+fn9/f//"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/////39/f39/f35/f39/f39/f39/f39//////////39/f3//f3//f//////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"//////9/f////////39/fn5/fn5+fn5+fn5+fn5+f35+fn5/f39/f39/f3//f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39//39/f3////9/f39/f39/f3//f39/f39+f39+f3///3/////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39///////9///9/f//////////////////////////////////////////////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f////////////////////////////////////39/f3//f39/f39+fn5+fn5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn5+fn5+f39/f39/f39/f3////////////////////////9/f/////9//////3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fn5+fn5+f39/f39/f39/f39/f39/f39/f39/f39/f39/f39///9///9/f//////"}
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
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f3//f39/f3//f/////9/f/9/f3///3//f///f3//f///f////39/////f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39/f39/f39/f3//f/9/f39/f39///9/f39/f/9/f39/f3///3//f39///9/f3/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f/9///9///9/f/9/f/////9///9/f3///3//f3//f3///39//39//39/////f//"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/39//39//39/f/////9///9///9//////3//////////f3//////f////3/////"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/////////////////3//f39/f39/f39/f39/f/9/f///f39//3///3//////f/9"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/v79/f3+/fv7+vn18PP49vPz9PX7/v19dm9sbGtzfnNpYWFoa2xt/t7V1Nff8X5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"zc7R1t3q7t7b6f1UPzo5NjMyMTAvLi86UNO7s7Oxr6+ur7a9x9PSy8zNysrMzdf"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yNDmaVdOSUQ/PTs6Ojg2NTQyMzc8R2LXyL+7ube0srK0t7q8vr/CxszY72RVTkl"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"y9Pc72JaUEhGQj07Ojg2NjU1Njk9Q01d79PGvbi0s7S2ubq6u7u+w8rP2Op1YVB"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"xczQ3WFKPjcvLComIiEjKTRM0b2zraikoqSorbO6wM99VVN4zMDEy9HzWEM1LSc"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"O8SsnpiUkpWaoay/WDUqJyo1WMe4r66utMxDKx4XDw8UGydHvqealJGRlpyltOo"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"rb8/KBoRERMXHixIr52WkZCUmJ2ovUYsJSMmLj3mua2pq7ZeLh4VExQXHCU0xqS"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Pkxb/XFNOyogHh4eIiUrO96wo56bm5ydoKiyy009OTo+RUhLSEA8MCkmJSYqLC8"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"VltfZm/55djOyMO/vb29v8LIztjpcF5XUU9OT1BTVFVWVlVVVFVWWV5r+ubc19P"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"eHh4eHh5e31+/fr39fPz9Pb5/X57eXd2dXV1dXV2dnd3dnZ1dnZ4en3++/n49/j"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"e3x9fv79+/n49vTz8fDw8PDw8PDx8fLz9PT19fb29/f3+Pj4+fn5+fn5+fr6+/v"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NzQyLzE3Q+S7r6urra+vrqytrrG3vdZJMyojHx0XFx41rJmXm6W76Eo3MDFHtKG"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"kY+arjkmKSsuP96snJmcqNs7OkfWx91eRzMmHRINFi6ijo6asy0fISUsQMemmZa"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"GxELDBq/j4mNm0kbGB0oSMaunpeXnbY3Ki5frqiqtk8rHhYODBEooo2LkactGxw"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"yc/Y4WxSSD44Njc7RFNmdWVWT01SX37k3dzZ083Gwb++vr6/w8nP2+f5d29pZV5"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"6OTg3t/h6PD+d3N1e/v08PD3fG9qZ2hrbnBxcG9ub3F3//bv7Ozv9n92cXF2fvf"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"enp6e3t8fv78+/r6+/z+/35+fX18fH1+//79/f3+//9///79/Pz8/f7+/v7+/f3"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHt6enp6e31+/v38/Pz9/v7+/v79/f38/P39/f7+/39+fX18e3p6ent7fH1+fn/"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"852457B0164A9876.1780332119.13605141","frames":750,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.01}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fHx8fHx8fHx8fH19fn5+fn/////+//7+/v7///7+/v/+/v9+fXx7e3r+ffz7++t"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Y11XUk5JQz47ODg4OTo8PkZW2r6yrKinp6mssLe9xthcQTUtKSUhHhweJTnCqJ2"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"EBAVJOmilpOUmqSzzmRfV1NORkdQ4b6zr7XXNiEWEA8UIX6ilpGTmaS370dGSEx"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"oLX6P0JPXvNiUE5V27+3s7xcLh0UERIaM7Cak5KXn7HXSEZPW3tkU1FX4sS6t71"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"XFRg48/K30UuHxkXGSE7tqCbmp2nssLUz8vIydh2V09bftvXaD8tIRsaGyQ9uqW"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"MS0rLTNA+cO3sbGzt7m4t7i6wM9yT0hITFZcV01BOTMvLi80PVbQvbaysbK0tre"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LzZF6sK5tre5urm4t7m/zO9gZHrc19vqWUo/NzAtKywvOU/Wv7m5uLi3s7O0ucT"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"b7uvrKmop6aprbfNb0tER0dPXmrrc009LyUfHiItRM2zraqmpaOkqrDC/lBDQUJ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"o6y5219FODQzPW/Jv81ELyMbGhsfLkjErqefnJubn6myynpMODAuMkrRvb57OCk"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"MzM8RVFWST42KyQiISUrLztO0LKppKGkpqerr7zlTkNFUF1qcmxwbVpLQj49PDk"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Oj9IWezPxb67uLa1tbW1tba3ubzAydppTUI7NzMwLy8vMTM3Oz9JWPjXysO+u7i"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ubm6vL7Cx87a8mFTS0ZBPj07Ojo6Ozw9P0RKUWDw2M3GwL27urq6uru9v8PJz9z"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Ny8sKCIkKzA6Ruq4raupqKamrLO5v834TU9fYW5859R8RjkuKiMeIigsNkXQsKu"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"R2VgXV9ENywgHyUhIy057bqxpZ2enp6hpq/Nfk85MzU7SUxKU0w6MCcgJCUkKTN"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"Qzo1Njc2NTQxLyonKiopLThDY8u2q6ikoJ+ipaqvus96VUM8Ozo4NTQzLy0rKy0"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"aWbVzNPIxsG/x8G+xsjJydX64mlcZlJaY0pMWExTTlJlR05nTlFeZn9t4dPb183"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"d3TmferhdunvZX36b2pt/XZo/nlnc258c2Tz/Wv3/nR9ePrt+vns7ezte3rxcHH"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/PV3b/lybvx9cHr5dXJ5/Pb6+3d3+ft+7PNr9/1t73x+f23x+Hx8c252/3t4bnN"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fPNxdXZ1e3Z99fn+9f1vb351fvB+c3z9efT07/V6/XL+9v7z9Xz3733+/Xjze3H"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"9PPv8v/6+nt49Xx162108mb+f2b1emrzdfztdOn5ZfH+aPt9dH156Oh38eh7+ez"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"X+j0Z3vzfG1s6Ptj6ut1/f/l91zl5lppfvJ6bNrwbOXt7P7053l1+P/26Pl853t"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"v9laQDMuKyckJB8eKCsuaLqtpJ+cm56eoKq0v2lBODM2NDQ5NS0sIhwmJyM6y7u"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"w082JB0UDxsiId6hnZmXmZqnzc1VLC03PFjivauttK+7SzEjHBcPFSYqSKKamJa"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"qbfPTjQlGxcVDxQrYLeclJKVnKe0QCUkKSs3266lpaakqbn3QDAjGhYVERUs5bS"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"1a+qqq64usZALScfHRsWHC9Hx62jnJylq6++3Ec8WeHuz8O6tb7V2WM+MCopKSU"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"xcLAwcLGys3P09PRz83P2vxXSj86Nzc4Oj0/Sk550t7Fv7+9v7/Ex83N0uvszc/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"NknMsqyrqqiprba7vs5rX/z1fOzXzN1VS0M1LCgiIyotN1XEsquqqKaorbO5wNZ"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"OjQuLC0vMjhGZ9TBurSvr7Cys7i/ydPg7/j25uL6bF5UTEQ+OTEvMDI1OUBR9s7"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ubq8vsHGyMrNzs7R2N/3YFVPRz88NjE0NTY5PkhV+tTHvru6ubm7vsDFycvNz8/"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+2BUTUQ7Ni8tLzAzOUVb3sq+uLSzs7W3u7/GzNTf39nb3NvgfltNRz42MCwqLjA"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"qK62yWZJRUpMXs7AvLq8xOFCNCkhHRocJCg007CmoJ+enqauuM1UPz1ETFzOvbm"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"LT/Pr6ekoqGjp663vcz1XV/r2NLLyc79STsyKycjISMnLThTxrStq6moqqywtLr"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"c2ZUTk1MTEhITEpJTlZnam388fTu397d6O3b2dze2NPZ3d/pdfh+X2ltal1aXlp"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"fO79fe7v7/r9/338cW/y+nX4+3h1c29saml3/Xr5/nz37u53e/nyfnLp9nFya/T"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"/3Ry/H139/798fh+fnv99PP4dvr4dnn27v17e3l5fu/3bXf/cHdtePJ6+vnx8nz"}
rsd_telephony_media_gateway  | [media-gateway] pipeline metrics {"stt_partial_ms":[2166,2287,2665,3212,3637],"stt_final_ms":[2475,4642,1837],"vad_speech_ratio":0.191,"vad_frames":786,"vad_speech_frames":150}
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:16:42:24 +0000] "GET /ws HTTP/1.1" 101 111799 "-" "-" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:59246 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.128 - - [01/Jun/2026:16:42:24 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_media_gateway  | [media-gateway] vox send skipped {"readyState":3}