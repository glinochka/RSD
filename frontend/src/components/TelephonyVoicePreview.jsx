import React, { useCallback, useEffect, useRef, useState } from 'react';
import { agentService } from '../services/agentService';
import {
  blobToBase64,
  createSpeechRecognition,
  pickRecorderMimeType,
  speakPlainText,
  speechRecognitionSupported,
  stopSpeaking,
  stripSsml,
} from '../utils/telephonySpeech';
import '../styles/telephonyVoicePreview.css';

const PREVIEW_TIMEOUT_MS = 120_000;

const STATUS_LABEL = {
  idle: 'Готов к тесту',
  starting: 'Подключение…',
  listening: 'Слушаю вас…',
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
  const [useBrowserStt, setUseBrowserStt] = useState(speechRecognitionSupported());
  const [isRecording, setIsRecording] = useState(false);
  const [isBusy, setIsBusy] = useState(false);

  const mediaRecorderRef = useRef(null);
  const phaseRef = useRef(phase);
  const recordChunksRef = useRef([]);
  const recognitionRef = useRef(null);
  const streamRef = useRef(null);
  const busyRef = useRef(false);

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
  }, []);

  const cleanupMic = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        /* ignore */
      }
    }
    mediaRecorderRef.current = null;
    recordChunksRef.current = [];
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        /* ignore */
      }
      recognitionRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, []);

  useEffect(() => () => {
    stopSpeaking();
    cleanupMic();
  }, [cleanupMic]);

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
    cleanupMic();
    stopSpeaking();
    setBusy(false);
  }, [agentId, callDbId, cleanupMic, previewSessionId, resetSession]);

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
      const chunks = Array.isArray(data?.reply_chunks_plain) ? data.reply_chunks_plain : [];
      const lines = chunks.length ? chunks : [data?.reply_plain || data?.reply_text || ''];
      setPhase('speaking');
      for (const line of lines) {
        const plain = stripSsml(line);
        if (!plain) continue;
        setLastAgentText(plain);
        // eslint-disable-next-line no-await-in-loop
        await speakPlainText(plain);
      }
      applyTurnMeta(data);
      if (data?.ended) {
        setPhase('ended');
        resetSession();
      } else {
        setPhase('listening');
      }
    },
    [applyTurnMeta, resetSession]
  );

  const sendTurn = useCallback(
    async ({ userTranscript, audioBase64, audioMimeType }) => {
      if (!sessionActive || busyRef.current) return;
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
      turnHistory,
    ]
  );

  const startSession = async () => {
    if (busyRef.current) return;
    setBusy(true);
    setPhase('starting');
    stopSpeaking();
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
      if (data.dialog_state) setDialogState(data.dialog_state);
      if (Array.isArray(data.turn_history)) setTurnHistory(data.turn_history);
      const welcome = data.welcome_plain || data.welcome_text || '';
      setLastAgentText(stripSsml(welcome));
      // Do not block the mic button on welcome TTS (Android often never fires onend).
      setPhase('listening');
      void speakPlainText(welcome);
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

  const stopRecordingAndSend = async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      setIsRecording(false);
      return;
    }
    const mime = recorder.mimeType || pickRecorderMimeType() || 'audio/webm';
    await new Promise((resolve) => {
      recorder.onstop = resolve;
      recorder.stop();
    });
    cleanupMic();
    const blob = new Blob(recordChunksRef.current, { type: mime });
    recordChunksRef.current = [];
    if (!blob.size) {
      showError?.('Запись пустая. Повторите фразу.');
      setPhase(sessionActive ? 'listening' : 'idle');
      return;
    }
    const audioBase64 = await blobToBase64(blob);
    await sendTurn({ audioBase64, audioMimeType: mime });
  };

  const startMicRecording = async () => {
    if (!sessionActive || busyRef.current || isRecording) return;
    stopSpeaking();
    if (useBrowserStt && speechRecognitionSupported()) {
      setPhase('listening');
      setIsRecording(true);
      const rec = createSpeechRecognition({
        onResult: async (text) => {
          cleanupMic();
          if (text) await sendTurn({ userTranscript: text });
        },
        onError: (code) => {
          cleanupMic();
          if (code !== 'aborted') {
            showError?.('Не удалось распознать речь в браузере. Отключите «Микрофон браузера» или разрешите доступ.');
          }
          setPhase('listening');
        },
      });
      if (!rec) {
        showError?.('Распознавание речи в браузере недоступно');
        return;
      }
      recognitionRef.current = rec;
      rec.start();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = pickRecorderMimeType();
      const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      recordChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data?.size) recordChunksRef.current.push(e.data);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      setPhase('listening');
    } catch {
      showError?.('Нет доступа к микрофону. Разрешите микрофон в браузере или введите фразу текстом.');
    }
  };

  const canUsePushToTalk = () => {
    const p = phaseRef.current;
    return sessionActive && !busyRef.current && (p === 'listening' || p === 'speaking');
  };

  const handlePushToTalkDown = () => {
    if (!canUsePushToTalk() || isRecording) return;
    if (phaseRef.current === 'speaking') {
      stopSpeaking();
      setPhase('listening');
    }
    startMicRecording();
  };

  const handlePushToTalkUp = () => {
    if (useBrowserStt && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        cleanupMic();
      }
      return;
    }
    if (isRecording) stopRecordingAndSend();
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    const text = transcriptInput.trim();
    if (!text || !sessionActive) return;
    setTranscriptInput('');
    await sendTurn({ userTranscript: text });
  };

  const statusKey = phase === 'listening' && isRecording ? 'listening' : phase;
  const modeNote = hasTelephonyChannel
    ? 'Подключена телефония — тест ближе к боевому звонку (история в аналитике).'
    : 'Телефония не подключена — тестируется логика голосового оператора без Voximplant.';

  return (
    <div className="telephony-voice-preview">
      <p className="telephony-voice-preview-hint">
        Голосовой тест в браузере: микрофон → ИИ (канал phone) → ответ озвучивается здесь же. Без звонка на номер.{' '}
        {modeNote}
      </p>
      {previewMode === 'voice_logic' && sessionActive ? (
        <p className="telephony-voice-preview-mode-badge">Режим: без телефонии</p>
      ) : null}
      <div className="telephony-voice-preview-status" aria-live="polite">
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
          <>
            <button
              type="button"
              className={`btn btn-black telephony-voice-preview-ptt ${isRecording ? 'telephony-voice-preview-ptt--active' : ''}`}
              disabled={phase === 'processing' || phase === 'starting' || isBusy}
              onPointerDown={(e) => {
                if (e.pointerType === 'mouse' && e.button !== 0) return;
                e.preventDefault();
                handlePushToTalkDown();
              }}
              onPointerUp={(e) => {
                e.preventDefault();
                handlePushToTalkUp();
              }}
              onPointerCancel={handlePushToTalkUp}
              onMouseDown={handlePushToTalkDown}
              onMouseUp={handlePushToTalkUp}
              onMouseLeave={handlePushToTalkUp}
            >
              {isRecording ? 'Отпустите, чтобы отправить' : 'Удерживайте и говорите'}
            </button>
            <button type="button" className="btn btn-outline" onClick={endSession}>
              Завершить
            </button>
          </>
        )}
      </div>

      {sessionActive && speechRecognitionSupported() && (
        <label className="telephony-voice-preview-stt-toggle">
          <input type="checkbox" checked={useBrowserStt} onChange={(e) => setUseBrowserStt(e.target.checked)} />
          Распознавание в браузере (быстрее, без отправки аудио на сервер)
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
