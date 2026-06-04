rsd_frontend                 | 192.142.24.66 - - [04/Jun/2026:07:51:31 +0000] "GET /SDK/webLanguage HTTP/1.1" 301 169 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36 Edg/90.0.818.46" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:35144 - "POST /api/internal/telephony/webhook-auth HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:35144 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:35152 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:35144 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_redis                    | 1:M 04 Jun 2026 07:53:20.356 * 1 changes in 3600 seconds. Saving...
rsd_redis                    | 1:M 04 Jun 2026 07:53:20.359 * Background saving started by pid 609756
rsd_frontend                 | 185.164.148.130 - - [04/Jun/2026:07:53:20 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_redis                    | 609756:C 04 Jun 2026 07:53:20.389 * DB saved on disk
rsd_redis                    | 609756:C 04 Jun 2026 07:53:20.391 * Fork CoW for RDB: current 0 MB, peak 0 MB, average 0 MB
rsd_redis                    | 1:M 04 Jun 2026 07:53:20.463 * Background saving terminated with success
rsd_telephony_worker         | INFO:     172.18.0.10:49994 - "POST /api/internal/telephony/resolve-inbound HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:49996 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_telephony_worker         | INFO:     172.18.0.10:49994 - "POST /api/internal/telephony/resolve HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.130 - - [04/Jun/2026:07:53:28 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_media_gateway  | [media-gateway] VAD: Silero ONNX + energy assist /app/models/silero_vad.onnx
rsd_telephony_media_gateway  | [media-gateway] reply session registered {"call_id":"FE85B5C89262D753.1780559599.7555395","total_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] session.start {"call_id":"FE85B5C89262D753.1780559599.7555395","connection_id":47,"codec":"pcmu","pipeline":true,"stt_provider":"yandex"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":1,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0}
rsd_telephony_orchestrator   | 2026-06-04 07:53:29,740 - app.telephony.orchestrator_worker - INFO - 489: orchestrator session.start call_id=FE85B5C89262D753.1780559599.7555395 connection_id=47 redis_session=True awaiting_ext=True
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":50,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0.744}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":100,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":0.872}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":150,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0.909}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"FE85B5C89262D753.1780559599.7555395","digit":"1"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"FE85B5C89262D753.1780559599.7555395","digit":"2"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"FE85B5C89262D753.1780559599.7555395","digit":"3"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"FE85B5C89262D753.1780559599.7555395","digit":"4"}
rsd_telephony_orchestrator   | 2026-06-04 07:53:32,695 - app.telephony.orchestrator_worker - INFO - 369: orchestrator _play_agent_welcome call_id=FE85B5C89262D753.1780559599.7555395 welcome_raw='Здравствуйте! Чем могу помочь?' welcome_text='Здравствуйте! Чем могу помочь?'
rsd_telephony_orchestrator   | 2026-06-04 07:53:32,696 - app.telephony.orchestrator_worker - INFO - 236: orchestrator _stream_routing_phrase call_id=FE85B5C89262D753.1780559599.7555395 log_label=welcome text='Здравствуйте! Чем могу помочь?' plain='Здравствуйте! Чем могу помочь?' empty=False
rsd_telephony_orchestrator   | 2026-06-04 07:53:32,698 - app.telephony.orchestrator_worker - INFO - 254: orchestrator welcome starting TTS call_id=FE85B5C89262D753.1780559599.7555395 voice=default lang=ru-RU text_len=30
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"start\",\"start\":{\"mediaFormat\":{\"encoding\":\"audio/x-mulaw\",\"sampleRate\":8000}}}"}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":144,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":144,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":145,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":145,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":168,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":168,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":234,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":234,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] pacer ready no pacer {"call_id":"FE85B5C89262D753.1780559599.7555395"}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"FE85B5C89262D753.1780559599.7555395","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":258,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"playback_grace","since_start_ms":260,"grace_ms":600}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":862,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":863,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":863,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":885,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":887,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":888,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":200,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":1.088}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":890,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":892,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":893,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":894,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":895,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":896,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":897,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":923,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":938,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":939,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":939,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":939,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":939,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":939,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":940,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":983,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":983,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":983,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":983,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] barge_in suppressed {"call_id":"FE85B5C89262D753.1780559599.7555395","reason":"dtmf_suppress","since_dtmf_ms":984,"suppress_ms":1000}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f39/f39/f39/f39/////f39/f39/f39/f39//39/f39///9/f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39/f39/f3///39//////3//f3///39/f39/f39//39/f39/f/////9/f//"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"f39/f39//39/f////3///39/f3///39/f39/////////f39//39/f3//////f39"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
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
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":250,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":1.013}
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
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"s8ZeQTk3PUt9xLKrqKamqay2x/lHODEuLCopJiMgHh0bGhoYHCc0T7eknZmXl5e"}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"vbavq6qsr7W+zntKPzw0MTEuKiglIB4dGxoaGh8rNV6vpJ+bmJiZnKCmrcHsWkU"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"sLa8w9tWRjszLywpJyUiIR8eHh4eHyYuN1q5rKafnJqam52fpay0wOZaT0xRbdz"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"ODEtKykoJygoKiwtLjE1OT5KWPbMwLq0r6yrqqmqq6yvs7e7wMfLztHe3977aGJ"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_orchestrator   | 2026-06-04 07:53:34,522 - app.telephony.orchestrator_worker - INFO - 322: orchestrator welcome TTS completed call_id=FE85B5C89262D753.1780559599.7555395
rsd_telephony_orchestrator   | 2026-06-04 07:53:34,523 - app.telephony.orchestrator_worker - INFO - 328: [orchestrator] welcome guaranteed path=stream call_id=FE85B5C89262D753.1780559599.7555395
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"9vf39/b08vDu7evq6ejn5ubn5+jp6+3v8/j8fnp4d3Z1dHV1dnh5e31+//7+/f3"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox frame {"len":160}
rsd_telephony_media_gateway  | [media-gateway] vox send {"msg":"{\"event\":\"media\",\"media\":{\"payload\":\"+/n49/b29/j6/P3/fnx7enp6ent8fH19fn5+fn19fHt5eHd2dXV0dXV2d3h5ent"}
rsd_telephony_orchestrator   | 2026-06-04 07:53:34,563 - app.telephony.orchestrator_worker - INFO - 432: orchestrator dtmf routed call_id=FE85B5C89262D753.1780559599.7555395 extension=1234 agent_id=37
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
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":300,"bytes":160,"expected_frame_bytes":160,"rtf":2.3,"avg_rtf":1.029}
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
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":350,"bytes":160,"expected_frame_bytes":160,"rtf":6.95,"avg_rtf":1.03}
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
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":400,"bytes":160,"expected_frame_bytes":160,"rtf":0.05,"avg_rtf":1.042}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":450,"bytes":160,"expected_frame_bytes":160,"rtf":1.2,"avg_rtf":1.042}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":500,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.015}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":550,"bytes":160,"expected_frame_bytes":160,"rtf":1.2,"avg_rtf":1.01}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":600,"bytes":160,"expected_frame_bytes":160,"rtf":1.2,"avg_rtf":1.011}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":650,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.007}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":700,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.016}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":750,"bytes":160,"expected_frame_bytes":160,"rtf":1.4,"avg_rtf":1.006}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"FE85B5C89262D753.1780559599.7555395","frames":800,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.008}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"прием прием","stt_final_ms":1461,"partial_count":0}
rsd_telephony_media_gateway  | [media-gateway] pipeline metrics {"stt_partial_ms":[],"stt_final_ms":[4289,1928,897,1495,1458,1461],"vad_speech_ratio":0.229,"vad_frames":835,"vad_speech_frames":191}
rsd_frontend                 | 185.164.148.130 - - [04/Jun/2026:07:53:45 +0000] "GET /ws HTTP/1.1" 101 47639 "-" "-" "-"
rsd_telephony_worker         | INFO:     172.18.0.10:49416 - "POST /api/internal/telephony/call-event HTTP/1.1" 200 OK
rsd_frontend                 | 185.164.148.130 - - [04/Jun/2026:07:53:46 +0000] "POST /webhook/voximplant/47 HTTP/1.1" 200 145 "-" "VoxEngine/1.0" "-"
rsd_telephony_orchestrator   | 2026-06-04 07:53:49,954 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_orchestrator   | 2026-06-04 07:53:55,393 - httpx - INFO - 1740: HTTP Request: POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] vox send skipped {"readyState":3}
rsd_telephony_media_gateway  | [media-gateway] pacer ready no pacer {"call_id":"FE85B5C89262D753.1780559599.7555395"}
rsd_telephony_media_gateway  | [media-gateway] downlink.ready fallback {"call_id":"FE85B5C89262D753.1780559599.7555395","timeout_ms":250}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"FE85B5C89262D753.1780559599.7555395","has_session":true,"active_sessions":6}
rsd_telephony_orchestrator   | 2026-06-04 07:53:58,086 - app.telephony.orchestrator_worker - INFO - 649: orchestrator stt.final ok call_id=FE85B5C89262D753.1780559599.7555395 db_id=74 latency_ms=12163 redis_history_len=1
rsd_telephony_media_gateway  | [media-gateway] vox send skipped {"readyState":3}
rsd_frontend                 | 5.61.209.33 - - [04/Jun/2026:07:54:25 +0000] "GET /cgi-bin/luci/;stok=/locale HTTP/1.1" 200 6588 "-" "-" "-"