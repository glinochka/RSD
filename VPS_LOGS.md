root@hostrsd:~/project/RSD# docker compose logs -f telephony_media_gateway
rsd_telephony_media_gateway  | telephony_media_gateway listening on 8200 (ws /ws, protocol v1)
rsd_telephony_media_gateway  | [media-gateway] subscribed to orchestrator replies
rsd_telephony_media_gateway  | [media-gateway] VAD: Silero ONNX + energy assist /app/models/silero_vad.onnx
rsd_telephony_media_gateway  | [media-gateway] reply session registered {"call_id":"E0483D808857FF6C.1780261367.11271026","total_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] session.start {"call_id":"E0483D808857FF6C.1780261367.11271026","connection_id":47,"codec":"pcmu","pipeline":true,"stt_provider":"yandex"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":1,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":0}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":50,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":0.784}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"E0483D808857FF6C.1780261367.11271026","digit":"1"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"E0483D808857FF6C.1780261367.11271026","digit":"2"}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":100,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":0.933}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"E0483D808857FF6C.1780261367.11271026","digit":"3"}
rsd_telephony_media_gateway  | [media-gateway] dtmf {"call_id":"E0483D808857FF6C.1780261367.11271026","digit":"4"}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":150,"bytes":160,"expected_frame_bytes":160,"rtf":2.1,"avg_rtf":1.073}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":200,"bytes":160,"expected_frame_bytes":160,"rtf":2.05,"avg_rtf":1.068}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":250,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.053}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":300,"bytes":160,"expected_frame_bytes":160,"rtf":1.8,"avg_rtf":1.045}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":350,"bytes":160,"expected_frame_bytes":160,"rtf":0.95,"avg_rtf":1.038}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":400,"bytes":160,"expected_frame_bytes":160,"rtf":1.1,"avg_rtf":1.034}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":450,"bytes":160,"expected_frame_bytes":160,"rtf":2.15,"avg_rtf":1.031}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":500,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.026}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":550,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.024}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":600,"bytes":160,"expected_frame_bytes":160,"rtf":0.85,"avg_rtf":1.022}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":650,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.026}
rsd_telephony_media_gateway  | [media-gateway] stt.partial {"call_id":"E0483D808857FF6C.1780261367.11271026","text":"але","stt_partial_ms":994}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":700,"bytes":160,"expected_frame_bytes":160,"rtf":0.5,"avg_rtf":1.018}
rsd_telephony_media_gateway  | [media-gateway] stt.final {"text":"але але","stt_final_ms":1780,"partial_count":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":750,"bytes":160,"expected_frame_bytes":160,"rtf":1.9,"avg_rtf":1.018}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":800,"bytes":160,"expected_frame_bytes":160,"rtf":1.5,"avg_rtf":1.017}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":850,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.017}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.start","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":900,"bytes":160,"expected_frame_bytes":160,"rtf":0.95,"avg_rtf":1.015}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":950,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.014}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.chunk","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] orch reply received {"type":"agent.audio.end","call_id":"E0483D808857FF6C.1780261367.11271026","has_session":true,"active_sessions":1}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":1000,"bytes":160,"expected_frame_bytes":160,"rtf":1.05,"avg_rtf":1.013}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":1050,"bytes":160,"expected_frame_bytes":160,"rtf":1.15,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":1100,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":1150,"bytes":160,"expected_frame_bytes":160,"rtf":0.9,"avg_rtf":1.011}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":1200,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.012}
rsd_telephony_media_gateway  | [media-gateway] audio.in {"call_id":"E0483D808857FF6C.1780261367.11271026","frames":1250,"bytes":160,"expected_frame_bytes":160,"rtf":0,"avg_rtf":1.011}
rsd_telephony_media_gateway  | [media-gateway] pipeline metrics {"stt_partial_ms":[994],"stt_final_ms":[1250,1069,1780],"vad_speech_ratio":0.058,"vad_frames":1271,"vad_speech_frames":74}
