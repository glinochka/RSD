import React, { useCallback, useEffect, useRef, useState } from 'react';
import { agentService } from '../services/agentService';
import {
  blobToBase64,
  createContinuousSpeechListener,
  createVoiceActivityListener,
  speakAgentLine,
  speechRecognitionSupported,
  stopSpeaking,
  stripSsml,
} from '../utils/telephonySpeech';
import '../styles/telephonyVoicePreview.css';

const PREVIEW_TIMEOUT_MS = 120_000;

const STATUS_LABEL = {
  idle: 'Готов к тесту',
  starting: 'Подключение…',
  listening: 'Слушаю вас — говорите',
  processing: 'Оператор думает…',
  speaking: 'Оператор отвечает…',
  ended: 'Разговор завершён',
  error: 'Ошибка',
};

function TelephonyVoicePreview({ agentId, hasTelephonyChannel, showError, showSuccess }) {
  const [phase, setPhase] = useState('idle');
  const [callDbId, setCallDbId] = useState(null);
  const [previewSessionId, setPreviewSessionId] = useState(null);
  const [previewMode, setPreviewMode] = useState(null);
  const [dialogState, setDialogState] = useState(null);
  const [turnHistory, setTurnHistory] = useState([]);
  const [transcriptInput, setTranscriptInput] = useState('');
  const [lastUserText, setLastUserText] = useState('');
  const [lastAgentText, setLastAgentText] = useState('');
  const [useBrowserStt, setUseBrowserStt] = useState(() => {
    if (!speechRecognitionSupported()) return false;
    if (typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent || '')) {
      return false;
    }
    return true;
  });
  const [micActive, setMicActive] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [externalTts, setExternalTts] = useState({ available: false, provider: null, voiceId: null });

  const autoListenerRef = useRef(null);
  const phaseRef = useRef(phase);
  const busyRef = useRef(false);
  const autoListenEnabledRef = useRef(false);

  const setBusy = (value) => {
    busyRef.current = value;
    setIsBusy(Boolean(value));
  };

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  const sessionActive = Boolean(callDbId || previewSessionId);

  const resetSession = useCallback(() => {
    setCallDbId(null);
    setPreviewSessionId(null);
    setPreviewMode(null);
    setDialogState(null);
    setTurnHistory([]);
    autoListenEnabledRef.current = false;
  }, []);

  const stopAutoListener = useCallback(() => {
    if (autoListenerRef.current) {
      autoListenerRef.current.stop();
      autoListenerRef.current = null;
    }
    setMicActive(false);
  }, []);

  useEffect(() => () => {
    stopSpeaking();
    stopAutoListener();
  }, [stopAutoListener]);

  const endSession = useCallback(async () => {
    const body = { agent_id: agentId };
    if (callDbId) body.call_db_id = callDbId;
    else if (previewSessionId) body.preview_session_id = previewSessionId;
    if (callDbId || previewSessionId) {
      try {
        await agentService.endTelephonyPreview(body);
      } catch {
        /* best effort */
      }
    }
    resetSession();
    setPhase('idle');
    stopAutoListener();
    stopSpeaking();
    setBusy(false);
  }, [agentId, callDbId, previewSessionId, resetSession, stopAutoListener]);

  const speakLine = useCallback(
    async (text) => {
      await speakAgentLine(text, {
        agentId,
        useExternalTts: externalTts.available,
        speakApi: agentService.telephonyPreviewSpeak,
      });
    },
    [agentId, externalTts.available]
  );

  const applyTurnMeta = useCallback((data) => {
    if (data?.dialog_state) setDialogState(data.dialog_state);
    if (Array.isArray(data?.turn_history)) setTurnHistory(data.turn_history);
    if (data?.preview_session_id) setPreviewSessionId(data.preview_session_id);
    if (data?.mode) setPreviewMode(data.mode);
    if (data?.call_db_id) setCallDbId(data.call_db_id);
    else if (data?.ended && data?.mode === 'voice_logic') {
      setPreviewSessionId(null);
    }
  }, []);

  const playAgentReply = useCallback(
    async (data) => {
      const fillerLines = (Array.isArray(data?.actions) ? data.actions : [])
        .filter((a) => a?.type === 'play_filler' && a?.text)
        .map((a) => stripSsml(String(a.text)));
      const chunks = Array.isArray(data?.reply_chunks_plain) ? data.reply_chunks_plain : [];
      const lines = chunks.length ? chunks : [data?.reply_plain || data?.reply_text || ''];
      setPhase('speaking');
      for (const line of fillerLines) {
        if (!line) continue;
        setLastAgentText(line);
        // eslint-disable-next-line no-await-in-loop
        await speakLine(line);
      }
      for (const line of lines) {
        const plain = stripSsml(line);
        if (!plain) continue;
        setLastAgentText(plain);
        // eslint-disable-next-line no-await-in-loop
        await speakLine(plain);
      }
      applyTurnMeta(data);
      if (data?.ended) {
        autoListenEnabledRef.current = false;
        setPhase('ended');
        stopAutoListener();
        resetSession();
      } else {
        setPhase('listening');
      }
    },
    [applyTurnMeta, resetSession, speakLine, stopAutoListener]
  );

  const sendTurn = useCallback(
    async ({ userTranscript, audioBase64, audioMimeType }) => {
      if (!sessionActive || busyRef.current) return;
      stopAutoListener();
      setBusy(true);
      setPhase('processing');
      try {
        const payload = {
          agent_id: agentId,
          user_transcript: userTranscript || undefined,
          audio_base64: audioBase64 || undefined,
          audio_mime_type: audioMimeType || undefined,
        };
        if (callDbId) payload.call_db_id = callDbId;
        else {
          payload.preview_session_id = previewSessionId;
          if (dialogState) payload.dialog_state = dialogState;
          if (turnHistory.length) payload.turn_history = turnHistory;
        }
        const data = await agentService.telephonyPreviewTurn(payload, { timeout: PREVIEW_TIMEOUT_MS });
        if (userTranscript) setLastUserText(userTranscript);
        await playAgentReply(data);
        if (data?.ended) {
          showSuccess?.('Тестовый разговор завершён');
        }
      } catch (error) {
        setPhase('error');
        showError?.(error?.message || 'Не удалось получить ответ оператора');
      } finally {
        setBusy(false);
      }
    },
    [
      agentId,
      callDbId,
      dialogState,
      playAgentReply,
      previewSessionId,
      sessionActive,
      showError,
      showSuccess,
      stopAutoListener,
      turnHistory,
    ]
  );

  const handleMicError = useCallback(
    (err) => {
      const code = typeof err === 'string' ? err : '';
      if (code === 'aborted') return;
      showError?.(
        code === 'unsupported'
          ? 'Распознавание речи в браузере недоступно. Снимите галочку «Распознавание в браузере».'
          : 'Нет доступа к микрофону. Разрешите микрофон в браузере или введите фразу текстом.'
      );
      if (phaseRef.current === 'listening') {
        stopAutoListener();
      }
    },
    [showError, stopAutoListener]
  );

  const startAutoListener = useCallback(() => {
    if (!autoListenEnabledRef.current || !sessionActive || busyRef.current) return;
    if (phaseRef.current !== 'listening') return;
    if (autoListenerRef.current?.isActive?.()) return;

    stopAutoListener();

    const onUtteranceAudio = async (blob, mime) => {
      stopAutoListener();
      if (!blob?.size) return;
      const audioBase64 = await blobToBase64(blob);
      await sendTurn({ audioBase64, audioMimeType: mime });
    };

    const onUtteranceText = async (text) => {
      stopAutoListener();
      if (!text) return;
      await sendTurn({ userTranscript: text });
    };

    if (useBrowserStt && speechRecognitionSupported()) {
      autoListenerRef.current = createContinuousSpeechListener({
        onUtterance: onUtteranceText,
        onError: handleMicError,
      });
    } else {
      autoListenerRef.current = createVoiceActivityListener({
        onUtterance: onUtteranceAudio,
        onError: handleMicError,
      });
    }

    autoListenerRef.current.start();
    setMicActive(true);
  }, [handleMicError, sendTurn, sessionActive, stopAutoListener, useBrowserStt]);

  useEffect(() => {
    if (!sessionActive || !autoListenEnabledRef.current || isBusy) {
      if (isBusy) stopAutoListener();
      return undefined;
    }
    if (phase === 'listening') {
      startAutoListener();
    } else {
      stopAutoListener();
    }
    return () => stopAutoListener();
  }, [phase, sessionActive, isBusy, startAutoListener, stopAutoListener, useBrowserStt]);

  const startSession = async () => {
    if (busyRef.current) return;
    setBusy(true);
    setPhase('starting');
    stopSpeaking();
    stopAutoListener();
    resetSession();
    setLastUserText('');
    setLastAgentText('');
    try {
      const data = await agentService.startTelephonyPreview(
        { agent_id: agentId },
        { timeout: PREVIEW_TIMEOUT_MS }
      );
      if (data.call_db_id) setCallDbId(data.call_db_id);
      if (data.preview_session_id) setPreviewSessionId(data.preview_session_id);
      setPreviewMode(data.mode || (data.call_db_id ? 'telephony_pipeline' : 'voice_logic'));
      const ttsMeta = data.tts
        ? {
            available: Boolean(data.tts.available),
            provider: data.tts.provider || null,
            voiceId: data.tts.voice_id || null,
          }
        : { available: false, provider: null, voiceId: null };
      setExternalTts(ttsMeta);
      if (data.dialog_state) setDialogState(data.dialog_state);
      if (Array.isArray(data.turn_history)) setTurnHistory(data.turn_history);
      const welcome = data.welcome_plain || data.welcome_text || '';
      const welcomePlain = stripSsml(welcome);
      setLastAgentText(welcomePlain);
      setPhase('speaking');
      autoListenEnabledRef.current = false;
      if (welcomePlain) {
        await speakAgentLine(welcomePlain, {
          agentId,
          useExternalTts: ttsMeta.available,
          speakApi: agentService.telephonyPreviewSpeak,
        });
      }
      autoListenEnabledRef.current = true;
      setPhase('listening');
      const hint = hasTelephonyChannel
        ? 'Тестовый звонок начат (полный телефонный контур).'
        : 'Тест без телефонии: та же логика ответов, озвучка в браузере.';
      showSuccess?.(hint);
    } catch (error) {
      setPhase('error');
      showError?.(error?.message || 'Не удалось начать тестовый звонок');
      resetSession();
    } finally {
      setBusy(false);
    }
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    const text = transcriptInput.trim();
    if (!text || !sessionActive) return;
    setTranscriptInput('');
    await sendTurn({ userTranscript: text });
  };

  const statusKey = phase;
  const ttsNote = externalTts.available
    ? `Озвучка: ${externalTts.provider === 'yandex' ? 'Yandex SpeechKit' : externalTts.provider === 'openai' ? 'OpenAI TTS' : 'внешний TTS'}${externalTts.voiceId ? ` (${externalTts.voiceId})` : ''}.`
    : 'Озвучка: браузер (для SpeechKit добавьте YANDEX_SPEECHKIT_API_KEY на сервере).';
  const modeNote = hasTelephonyChannel
    ? 'Подключена телефония — тест ближе к боевому звонку (история в аналитике).'
    : 'Телефония не подключена — тестируется логика голосового оператора без Voximplant.';

  return (
    <div className="telephony-voice-preview">
      <p className="telephony-voice-preview-hint">
        Голосовой тест как при звонке: микрофон включается сам, говорите как обычно — после паузы фраза уйдёт
        оператору. {ttsNote} {modeNote}
      </p>
      {previewMode === 'voice_logic' && sessionActive ? (
        <p className="telephony-voice-preview-mode-badge">Режим: без телефонии</p>
      ) : null}
      <div
        className={`telephony-voice-preview-status ${micActive && phase === 'listening' ? 'telephony-voice-preview-status--live' : ''}`}
        aria-live="polite"
      >
        {STATUS_LABEL[statusKey] || phase}
      </div>

      {(lastUserText || lastAgentText) && (
        <div className="telephony-voice-preview-transcript">
          {lastUserText ? (
            <p>
              <span>Вы:</span> {lastUserText}
            </p>
          ) : null}
          {lastAgentText ? (
            <p>
              <span>Оператор:</span> {lastAgentText}
            </p>
          ) : null}
        </div>
      )}

      <div className="telephony-voice-preview-actions">
        {!sessionActive ? (
          <button type="button" className="btn btn-black" onClick={startSession} disabled={isBusy}>
            Начать тестовый звонок
          </button>
        ) : (
          <button type="button" className="btn btn-outline" onClick={endSession} disabled={isBusy}>
            Завершить разговор
          </button>
        )}
      </div>

      {sessionActive && speechRecognitionSupported() && (
        <label className="telephony-voice-preview-stt-toggle">
          <input
            type="checkbox"
            checked={useBrowserStt}
            onChange={(e) => setUseBrowserStt(e.target.checked)}
            disabled={isBusy || phase === 'processing'}
          />
          Распознавание в браузере (на телефоне часто надёжнее отправки аудио на сервер)
        </label>
      )}

      {sessionActive && (
        <form className="telephony-voice-preview-text-fallback" onSubmit={handleTextSubmit}>
          <input
            type="text"
            className="input-main"
            placeholder="Или введите фразу текстом…"
            value={transcriptInput}
            onChange={(e) => setTranscriptInput(e.target.value)}
            disabled={phase === 'processing' || isBusy}
          />
          <button
            type="submit"
            className="btn btn-outline"
            disabled={!transcriptInput.trim() || phase === 'processing' || isBusy}
          >
            Сказать текстом
          </button>
        </form>
      )}
    </div>
  );
}

export default TelephonyVoicePreview;
