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
  const [transcriptInput, setTranscriptInput] = useState('');
  const [lastUserText, setLastUserText] = useState('');
  const [lastAgentText, setLastAgentText] = useState('');
  const [useBrowserStt, setUseBrowserStt] = useState(speechRecognitionSupported());
  const [isRecording, setIsRecording] = useState(false);

  const mediaRecorderRef = useRef(null);
  const recordChunksRef = useRef([]);
  const recognitionRef = useRef(null);
  const streamRef = useRef(null);
  const busyRef = useRef(false);

  const setBusy = (value) => {
    busyRef.current = value;
  };

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
    if (callDbId) {
      try {
        await agentService.endTelephonyPreview({ agent_id: agentId, call_db_id: callDbId });
      } catch {
        /* best effort */
      }
    }
    setCallDbId(null);
    setPhase('idle');
    cleanupMic();
    stopSpeaking();
    setBusy(false);
  }, [agentId, callDbId, cleanupMic]);

  const playAgentReply = useCallback(async (data) => {
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
    if (data?.ended) {
      setPhase('ended');
      setCallDbId(null);
    } else {
      setPhase('listening');
    }
  }, []);

  const sendTurn = useCallback(
    async ({ userTranscript, audioBase64, audioMimeType }) => {
      if (!callDbId || busyRef.current) return;
      setBusy(true);
      setPhase('processing');
      try {
        const data = await agentService.telephonyPreviewTurn(
          {
            agent_id: agentId,
            call_db_id: callDbId,
            user_transcript: userTranscript || undefined,
            audio_base64: audioBase64 || undefined,
            audio_mime_type: audioMimeType || undefined,
          },
          { timeout: PREVIEW_TIMEOUT_MS }
        );
        if (userTranscript) setLastUserText(userTranscript);
        await playAgentReply(data);
        if (data?.ended) {
          showSuccess?.('Тестовый звонок завершён (как при реальном разговоре)');
        }
      } catch (error) {
        setPhase('error');
        showError?.(error?.message || 'Не удалось получить ответ оператора');
      } finally {
        setBusy(false);
      }
    },
    [agentId, callDbId, playAgentReply, showError, showSuccess]
  );

  const startSession = async () => {
    if (busyRef.current) return;
    setBusy(true);
    setPhase('starting');
    stopSpeaking();
    setLastUserText('');
    setLastAgentText('');
    try {
      const data = await agentService.startTelephonyPreview(
        { agent_id: agentId },
        { timeout: PREVIEW_TIMEOUT_MS }
      );
      setCallDbId(data.call_db_id);
      setPhase('speaking');
      const welcome = data.welcome_plain || data.welcome_text || '';
      setLastAgentText(stripSsml(welcome));
      await speakPlainText(welcome);
      setPhase('listening');
      showSuccess?.('Тестовый звонок начат. Говорите в микрофон или введите фразу текстом.');
    } catch (error) {
      setPhase('error');
      showError?.(error?.message || 'Не удалось начать тестовый звонок');
      setCallDbId(null);
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
      setPhase(callDbId ? 'listening' : 'idle');
      return;
    }
    const audioBase64 = await blobToBase64(blob);
    await sendTurn({ audioBase64, audioMimeType: mime });
  };

  const startMicRecording = async () => {
    if (!callDbId || busyRef.current || isRecording) return;
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

  const handlePushToTalkDown = () => {
    if (phase === 'listening' && !busyRef.current) startMicRecording();
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
    if (!text || !callDbId) return;
    setTranscriptInput('');
    await sendTurn({ userTranscript: text });
  };

  const active = Boolean(callDbId);
  const statusKey = phase === 'listening' && isRecording ? 'listening' : phase;

  if (!hasTelephonyChannel) {
    return (
      <div className="telephony-voice-preview telephony-voice-preview--muted">
        <p className="telephony-voice-preview-hint">
          Подключите канал «Телефония», чтобы протестировать голосового ИИ-оператора прямо в браузере (без звонка на
          номер).
        </p>
      </div>
    );
  }

  return (
    <div className="telephony-voice-preview">
      <p className="telephony-voice-preview-hint">
        Имитация телефонного разговора: ваш голос → тот же ИИ и база знаний, что на линии → ответ озвучивается в
        браузере. Это не PSTN-звонок; задержки и голос CPaaS могут отличаться.
      </p>
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
        {!active ? (
          <button type="button" className="btn btn-black" onClick={startSession} disabled={busyRef.current}>
            Начать тестовый звонок
          </button>
        ) : (
          <>
            <button
              type="button"
              className={`btn btn-black telephony-voice-preview-ptt ${isRecording ? 'telephony-voice-preview-ptt--active' : ''}`}
              disabled={phase === 'processing' || phase === 'speaking' || phase === 'starting'}
              onMouseDown={handlePushToTalkDown}
              onMouseUp={handlePushToTalkUp}
              onMouseLeave={handlePushToTalkUp}
              onTouchStart={(e) => {
                e.preventDefault();
                handlePushToTalkDown();
              }}
              onTouchEnd={(e) => {
                e.preventDefault();
                handlePushToTalkUp();
              }}
            >
              {isRecording ? 'Отпустите, чтобы отправить' : 'Удерживайте и говорите'}
            </button>
            <button type="button" className="btn btn-outline" onClick={endSession}>
              Завершить
            </button>
          </>
        )}
      </div>

      {active && speechRecognitionSupported() && (
        <label className="telephony-voice-preview-stt-toggle">
          <input
            type="checkbox"
            checked={useBrowserStt}
            onChange={(e) => setUseBrowserStt(e.target.checked)}
          />
          Распознавание в браузере (быстрее, без отправки аудио на сервер)
        </label>
      )}

      {active && (
        <form className="telephony-voice-preview-text-fallback" onSubmit={handleTextSubmit}>
          <input
            type="text"
            className="input-main"
            placeholder="Или введите фразу текстом…"
            value={transcriptInput}
            onChange={(e) => setTranscriptInput(e.target.value)}
            disabled={phase === 'processing' || phase === 'speaking'}
          />
          <button
            type="submit"
            className="btn btn-outline"
            disabled={!transcriptInput.trim() || phase === 'processing' || phase === 'speaking'}
          >
            Сказать текстом
          </button>
        </form>
      )}
    </div>
  );
}

export default TelephonyVoicePreview;
