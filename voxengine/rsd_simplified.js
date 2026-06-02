/**
 * RSD Simplified Telephony - Voximplant native TTS + ASR
 *
 * Architecture:
 * 1. Uses Voximplant's built-in TTS (call.say) for agent speech
 * 2. Uses Voximplant's built-in ASR (call.startASR) for user speech
 * 3. Communicates with backend via HTTP webhooks (no media gateway needed)
 *
 * Backend integration:
 * - POST /telephony/webhook/call.inbound - incoming call
 * - POST /telephony/webhook/call.answer - call answered
 * - POST /telephony/webhook/asr.result - send ASR result to backend
 * - GET /telephony/response/next?call_id=xxx - get next agent action (say/transfer/hangup)
 */

// Load configuration from customData or secrets
function loadConfig() {
  var customData = {};
  try {
    var raw = VoxEngine.customData();
    if (raw) customData = JSON.parse(raw);
  } catch (e) {
    Logger.write('[rsd] Failed to parse customData: ' + e);
  }

  function secret(name) {
    try {
      var v = VoxEngine.getSecretValue(name);
      return v !== undefined && v !== null ? String(v).trim() : '';
    } catch (e) {
      return '';
    }
  }

  return {
    connectionId: Number(customData.connection_id || customData.connectionId || secret('RSD_CONNECTION_ID') || 0),
    webhookBase: String(customData.webhook_base_url || customData.webhookBaseUrl || secret('RSD_WEBHOOK_BASE_URL') || '').replace(/\/$/, ''),
    webhookSecret: String(secret('RSD_WEBHOOK_SECRET') || customData.webhook_secret || ''),
    mediaWsUrl: String(customData.media_ws_url || customData.mediaWsUrl || secret('TELEPHONY_MEDIA_WS_URL') || '').trim(),
    requireExtension: Boolean(customData.require_extension || customData.requireExtension || secret('RSD_REQUIRE_EXTENSION') === 'true'),
    // Voximplant ASR configuration
    asrLang: String(customData.asr_language || secret('VOX_ASR_LANGUAGE') || 'ru-RU').trim(),
    asrModel: String(customData.asr_model || secret('VOX_ASR_MODEL') || 'general').trim(), // general,numbers,dialpad
    // TTS voice configuration  
    ttsVoice: String(customData.tts_voice || secret('VOX_TTS_VOICE') || 'Tatyana').trim(),
  };
}

var DEFAULT_GREETING = 'Здравствуйте! Чем могу помочь?';
var POOL_GREETING = 'Здравствуйте! Введите добавочный номер из четырёх цифр на клавиатуре телефона.';
var NO_AGENT_MESSAGE = 'Агент не найден. Попробуйте позже.';
var RECORDING_DISCLAIMER = 'Разговор может быть записан в целях контроля качества обслуживания.';

var DTMF_DIGIT_COUNT = 4;
var DTMF_PREFILL_TIMEOUT_MS = 2500;

// Call state
var call = null;
var config = null;
var callId = null;
var callerE164 = '';
var calledE164 = '';
var answered = false;
var extensionBuffer = '';
var dtmfPrefillTimer = null;
var isRecordingDisclaimerPlayed = false;
var isAsrActive = false;

// Webhook helpers
function makeAuthHeaders() {
  return {
    'X-RSD-Secret': config.webhookSecret,
    'Content-Type': 'application/json'
  };
}

function postWebhook(event, payload, onResponse) {
  var url = config.webhookBase + '/telephony/webhook/' + event;
  var data = {
    call_id: callId,
    connection_id: config.connectionId,
    caller_e164: callerE164,
    called_e164: calledE164,
    event: event,
    payload: payload || {}
  };

  Net.httpRequest(url, {
    method: 'POST',
    headers: makeAuthHeaders(),
    postData: JSON.stringify(data),
    timeout: 30000
  }, function(result) {
    var body = null;
    try {
      if (result.code === 200 && result.text) {
        body = JSON.parse(result.text);
      }
    } catch (e) {
      Logger.write('[rsd] Webhook parse error: ' + e);
    }
    if (onResponse) onResponse(result.code, body);
  });
}

function pollForResponse(onResponse) {
  var url = config.webhookBase + '/telephony/response/next?call_id=' + encodeURIComponent(callId) +
    '&connection_id=' + config.connectionId;

  Net.httpRequest(url, {
    method: 'GET',
    headers: makeAuthHeaders(),
    timeout: 30000
  }, function(result) {
    var body = null;
    try {
      if (result.code === 200 && result.text) {
        body = JSON.parse(result.text);
      }
    } catch (e) {
      Logger.write('[rsd] Poll parse error: ' + e);
    }
    onResponse(result.code, body);
  });
}

// Call flow functions
function playRecordingDisclaimer(next) {
  if (isRecordingDisclaimerPlayed) {
    next();
    return;
  }
  isRecordingDisclaimerPlayed = true;
  call.say(RECORDING_DISCLAIMER, { tts: true, voice: config.ttsVoice });
  call.addEventListener(CallEvents.PlaybackFinished, function onDisclaimer() {
    call.removeEventListener(CallEvents.PlaybackFinished, onDisclaimer);
    next();
  });
}

function playGreetingAndAnswer(greetingText, isPoolGreeting) {
  var text = greetingText || (isPoolGreeting ? POOL_GREETING : DEFAULT_GREETING);

  playRecordingDisclaimer(function() {
    Logger.write('[rsd] Playing greeting: ' + text.substring(0, 50));
    call.say(text, { tts: true, voice: config.ttsVoice });
    call.addEventListener(CallEvents.PlaybackFinished, function onGreeting() {
      call.removeEventListener(CallEvents.PlaybackFinished, onGreeting);
      proceedToAnswer();
    });
  });
}

function proceedToAnswer() {
  if (answered) return;
  answered = true;
  clearTimeout(dtmfPrefillTimer);

  call.answer();

  // Notify backend that call is answered
  postWebhook('call.answered', {
    extension: extensionBuffer || null
  }, function(code, body) {
    Logger.write('[rsd] call.answered webhook response: ' + code);
    if (body && body.welcome_message) {
      // Agent assigned - play welcome and start dialog
      playAgentWelcome(body.welcome_message, body.voice_id);
    }
  });
}

function playAgentWelcome(welcomeText, voiceId) {
  var text = welcomeText || DEFAULT_GREETING;
  var voice = voiceId || config.ttsVoice;

  Logger.write('[rsd] Playing agent welcome: ' + text.substring(0, 50));
  call.say(text, { tts: true, voice: voice });
  call.addEventListener(CallEvents.PlaybackFinished, function onWelcome() {
    call.removeEventListener(CallEvents.PlaybackFinished, onWelcome);
    // Start ASR after welcome
    startAsrDialog();
  });
}

function startAsrDialog() {
  if (isAsrActive) return;
  isAsrActive = true;

  Logger.write('[rsd] Starting ASR dialog');

  // Start ASR
  call.startASR({
    lang: config.asrLang,
    model: config.asrModel,
    interimResults: true,
    singleUtterance: false
  });

  // Handle ASR results
  call.addEventListener(CallEvents.ASREvents.INTERIM, function(e) {
    // Optional: handle interim results for faster response
    Logger.write('[rsd] ASR interim: ' + (e.text || ''));
  });

  call.addEventListener(CallEvents.ASREvents.FINAL, function(e) {
    var transcript = (e.text || '').trim();
    if (!transcript) return;

    Logger.write('[rsd] ASR final: ' + transcript);

    // Send transcript to backend and get response
    postWebhook('asr.result', {
      transcript: transcript,
      confidence: e.confidence || 0
    }, function(code, body) {
      if (code === 200 && body) {
        handleAgentResponse(body);
      } else {
        // Error - try to recover
        call.say('Прошу прощения, не расслышал. Повторите, пожалуйста.', { tts: true, voice: config.ttsVoice });
      }
    });
  });

  call.addEventListener(CallEvents.ASREvents.ERROR, function(e) {
    Logger.write('[rsd] ASR error: ' + JSON.stringify(e));
    // Restart ASR after error
    stopAsr();
    setTimeout(startAsrDialog, 500);
  });

  call.addEventListener(CallEvents.ASREvents.TIMEOUT, function() {
    Logger.write('[rsd] ASR timeout - restarting');
    stopAsr();
    setTimeout(startAsrDialog, 100);
  });
}

function stopAsr() {
  if (!isAsrActive) return;
  isAsrActive = false;
  try {
    call.stopASR();
  } catch (e) {
    Logger.write('[rsd] stopASR error: ' + e);
  }
}

function handleAgentResponse(response) {
  // Stop ASR while playing agent response
  stopAsr();

  var action = response.action || 'say';
  var text = response.text || '';
  var voice = response.voice_id || config.ttsVoice;

  Logger.write('[rsd] Agent action: ' + action + ', text: ' + text.substring(0, 50));

  switch (action) {
    case 'say':
      if (text) {
        call.say(text, { tts: true, voice: voice });
        call.addEventListener(CallEvents.PlaybackFinished, function onAgentSpeech() {
          call.removeEventListener(CallEvents.PlaybackFinished, onAgentSpeech);
          // Resume ASR after agent speaks
          startAsrDialog();
        });
      } else {
        // Empty response - just restart ASR
        startAsrDialog();
      }
      break;

    case 'transfer':
      var dest = response.destination || response.e164 || 'operator';
      Logger.write('[rsd] Transferring to: ' + dest);
      call.say('Соединяю с оператором.', { tts: true, voice: voice });
      call.addEventListener(CallEvents.PlaybackFinished, function onTransferMsg() {
        call.removeEventListener(CallEvents.PlaybackFinished, onTransferMsg);
        transferCall(dest);
      });
      break;

    case 'hangup':
      Logger.write('[rsd] Hanging up');
      if (text) {
        call.say(text, { tts: true, voice: voice });
        call.addEventListener(CallEvents.PlaybackFinished, function onHangupMsg() {
          call.removeEventListener(CallEvents.PlaybackFinished, onHangupMsg);
          call.hangup();
        });
      } else {
        call.hangup();
      }
      break;

    case 'enable_dtmf':
      // DTMF menu requested
      if (text) {
        call.say(text, { tts: true, voice: voice });
        call.addEventListener(CallEvents.PlaybackFinished, function onDtmfMsg() {
          call.removeEventListener(CallEvents.PlaybackFinished, onDtmfMsg);
          startAsrDialog();
        });
      }
      break;

    default:
      startAsrDialog();
  }
}

function transferCall(destination) {
  var dest = String(destination || '').trim();
  if (!dest || dest === 'operator') {
    // Use default operator transfer from config
    dest = 'operator';
  }

  // Try to make PSTN transfer
  try {
    var outgoing = VoxEngine.callPSTN(dest, calledE164 || callerE164);
    outgoing.addEventListener(CallEvents.Connected, function() {
      VoxEngine.sendMediaBetween(call, outgoing);
    });
    outgoing.addEventListener(CallEvents.Failed, function() {
      call.say('Не удалось соединить с оператором. Попробуйте позже.', { tts: true, voice: config.ttsVoice });
    });
  } catch (e) {
    Logger.write('[rsd] Transfer failed: ' + e);
    call.say('Сервис временно недоступен.', { tts: true, voice: config.ttsVoice });
  }
}

// DTMF handling
function handleDtmfDigit(digit) {
  if (!/^[0-9]$/.test(digit)) return;

  Logger.write('[rsd] DTMF received: ' + digit);

  extensionBuffer = (extensionBuffer + digit).slice(-DTMF_DIGIT_COUNT);

  if (extensionBuffer.length >= DTMF_DIGIT_COUNT && !answered) {
    Logger.write('[rsd] Extension complete: ' + extensionBuffer);
    clearTimeout(dtmfPrefillTimer);
    // Route to agent and answer
    proceedToAnswer();
  }
}

// Main call handler
VoxEngine.addEventListener(AppEvents.CallAlerting, function(e) {
  call = e.call;
  config = loadConfig();
  callId = String(call.id());
  callerE164 = String(e.callerid || call.callerid() || '+00000000000').trim();

  // Try to get called number
  try {
    calledE164 = String(e.destination || call.number() || '').trim();
  } catch (err) {
    calledE164 = '';
  }

  Logger.write('[rsd] Call alerting: ' + callId + ' from ' + callerE164);

  // Validate config
  if (!config.connectionId || !config.webhookBase || !config.webhookSecret) {
    Logger.write('[rsd] Invalid config - rejecting call');
    call.reject(603, 'misconfigured');
    return;
  }

  // Enable DTMF detection
  try {
    call.handleTones(true);
  } catch (toneErr) {
    Logger.write('[rsd] handleTones error: ' + toneErr);
  }

  // Set up event handlers
  call.addEventListener(CallEvents.Disconnected, function() {
    Logger.write('[rsd] Call disconnected');
    stopAsr();
    postWebhook('call.hangup', { reason: 'completed' }, null);
    VoxEngine.terminate();
  });

  call.addEventListener(CallEvents.Failed, function(e) {
    Logger.write('[rsd] Call failed: ' + (e.code || 'unknown'));
    postWebhook('call.failed', { code: e.code }, null);
    VoxEngine.terminate();
  });

  call.addEventListener(CallEvents.ToneReceived, function(e) {
    if (e && e.tone) {
      handleDtmfDigit(String(e.tone));
    }
  });

  // Start early media
  call.startEarlyMedia();

  // Send inbound webhook
  postWebhook('call.inbound', {
    caller_e164: callerE164,
    called_e164: calledE164
  }, function(code, body) {
    Logger.write('[rsd] call.inbound response: ' + code);

    if (code !== 200 || !body) {
      // Default flow
      if (config.requireExtension) {
        playGreetingAndAnswer(null, true);
      } else {
        playGreetingAndAnswer(null, false);
      }
      return;
    }

    // Use backend response
    if (body.greeting_text) {
      playGreetingAndAnswer(body.greeting_text, false);
    } else if (config.requireExtension) {
      playGreetingAndAnswer(null, true);
    } else {
      playGreetingAndAnswer(null, false);
    }
  });

  // DTMF prefill timeout (if extension not entered)
  if (config.requireExtension) {
    dtmfPrefillTimer = setTimeout(function() {
      if (!answered) {
        Logger.write('[rsd] DTMF prefill timeout - playing pool greeting');
        playGreetingAndAnswer(null, true);
      }
    }, DTMF_PREFILL_TIMEOUT_MS);
  } else {
    // No extension required - answer after a short delay or immediately
    playGreetingAndAnswer(null, false);
  }
});
