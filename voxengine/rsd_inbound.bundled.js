/**
 * RSD inbound — единый сценарий для Voximplant Cloud IDE.
 * Скопируйте всё содержимое в сценарий rsd_inbound (один файл, без require).
 * На routing rule привяжите только rsd_inbound.
 *
 * Источник: rsd_inbound.js + lib/rsd_control.js + lib/rsd_media_gateway.js + lib/rsd_transfer.js
 * Обновляйте через: node voxengine/scripts/bundle.mjs
 *
 * Secrets приложения (обязательно для входящего PSTN — customData rule не передаётся):
 *   RSD_CONNECTION_ID, RSD_WEBHOOK_SECRET, RSD_WEBHOOK_BASE_URL, TELEPHONY_MEDIA_WS_URL
 *   RSD_REQUIRE_EXTENSION=true — приветствие «введите 4 цифры»
 * script_custom_data rule — только при ручном StartScenarios, не при звонке на номер
 */

Logger.write('[rsd] scenario loaded (bundled rsd_inbound)');

VoxEngine.addEventListener(AppEvents.Started, function () {
  Logger.write('[rsd] Application.Started customData=' + String(VoxEngine.customData() || ''));
});


// --- lib/rsd_control.js ---
function _uuid() {
  var d = new Date().getTime();
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    d += performance.now();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    var r = (d + Math.random() * 16) % 16 | 0;
    d = Math.floor(d / 16);
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function _isoNow() {
  return new Date().toISOString();
}

/**
 * @param {object} opts
 * @param {string} opts.webhookBaseUrl - e.g. https://host (no trailing slash)
 * @param {number} opts.connectionId
 * @param {string} opts.webhookSecret
 * @param {string} opts.event
 * @param {string} opts.callId
 * @param {object} opts.payload
 * @param {function} done - (err, responseBody)
 */
function postControlEvent(opts, done) {
  var connectionId = Number(opts.connectionId);
  var base = String(opts.webhookBaseUrl || '').replace(/\/$/, '');
  if (!base || !connectionId || !opts.webhookSecret) {
    done('rsd_control: missing webhook config');
    return;
  }

  var bodyObj = {
    schema_version: 1,
    event_id: _uuid(),
    event: String(opts.event),
    emitted_at: _isoNow(),
    call_id: String(opts.callId),
    connection_id: connectionId,
    payload: opts.payload || {},
  };
  var rawBody = JSON.stringify(bodyObj);
  var timestamp = String(Math.floor(Date.now() / 1000));

  // HMAC v1 — same as backend test_webhook_signature / bridge verify
  var signPayload = 'v1\n' + timestamp + '\n' + connectionId + '\n' + rawBody;
  var signature = hmacSha256Hex(String(opts.webhookSecret), signPayload);

  var url = base + '/webhook/voximplant/' + connectionId;
  var httpOpts = {
    method: 'POST',
    headers: [
      'Content-Type: application/json; charset=utf-8',
      'X-RSD-Telephony-Timestamp: ' + timestamp,
      'X-RSD-Telephony-Signature: ' + signature,
    ],
    postData: rawBody,
  };

  Net.httpRequest(url, function (res) {
    if (!res || res.code < 200 || res.code >= 300) {
      done('rsd_control http ' + (res ? res.code : 'no_response') + ' ' + (res ? res.text : ''));
      return;
    }
    try {
      done(null, JSON.parse(res.text || '{}'));
    } catch (e) {
      done(null, { ok: true, raw: res.text });
    }
  }, httpOpts);
}

/**
 * HMAC-SHA256 hex (RFC-001), lowercase — matches telephony_bridge verify.
 * @see https://voximplant.com/docs/references/voxengine/crypto/hmac_sha256
 */
function hmacSha256Hex(secret, message) {
  if (typeof Crypto === 'undefined') {
    throw new Error('rsd_control: Crypto is not available in VoxEngine');
  }
  if (typeof Crypto.hmac_sha256 === 'function') {
    // VoxEngine API: hmac_sha256(key, data) — secret first
    var hex = Crypto.hmac_sha256(secret, message);
    if (!hex) {
      hex = Crypto.hmac_sha256(message, secret);
    }
    return String(hex || '').toLowerCase();
  }
  if (typeof Crypto.hmac === 'function') {
    return String(Crypto.hmac('sha256', secret, message, true) || '').toLowerCase();
  }
  throw new Error('rsd_control: Crypto.hmac_sha256 not available in VoxEngine');
}



// --- lib/rsd_transfer.js ---
function normalizePstnE164(raw) {
  var s = String(raw || '').trim();
  if (!s || s === 'operator') return '';
  var digits = s.replace(/[^\d+]/g, '');
  if (!digits) return '';
  if (digits.charAt(0) === '+') return digits;
  if (digits.length === 11 && digits.charAt(0) === '7') return '+' + digits;
  if (digits.length === 10) return '+7' + digits;
  return '+' + digits;
}

/**
 * @param {object} opts
 * @param {Call} opts.inboundCall
 * @param {string} opts.destinationE164
 * @param {string} [opts.callerId] - outbound CLI (pool DID)
 * @param {string} [opts.callId]
 * @param {function} [opts.onConnected]
 * @param {function} [opts.onFailed]
 * @returns {boolean}
 */
function transferToPstn(opts) {
  var dest = normalizePstnE164(opts.destinationE164);
  if (!dest) {
    return false;
  }

  var callerId = String(opts.callerId || opts.inboundCall.callerid() || '').trim();
  var callId = String(opts.callId || '');

  try {
    var outbound = VoxEngine.callPSTN(dest, callerId);

    outbound.addEventListener(CallEvents.Failed, function (ev) {
      Logger.write(
        '[rsd] transfer PSTN failed dest=' + dest + ' call_id=' + callId + ' ' + JSON.stringify(ev || {}),
      );
      if (opts.onFailed) opts.onFailed(ev);
    });

    outbound.addEventListener(CallEvents.Connected, function () {
      VoxEngine.sendMediaBetween(opts.inboundCall, outbound);
      Logger.write('[rsd] transfer bridged to ' + dest + ' call_id=' + callId);
      if (opts.onConnected) opts.onConnected(outbound);
    });

    outbound.addEventListener(CallEvents.Disconnected, function () {
      try {
        opts.inboundCall.hangup();
      } catch (hangupErr) {
        Logger.write('[rsd] transfer inbound hangup: ' + hangupErr);
      }
    });

    opts.inboundCall.addEventListener(CallEvents.Disconnected, function () {
      try {
        outbound.hangup();
      } catch (hangupErr) {
        Logger.write('[rsd] transfer outbound hangup: ' + hangupErr);
      }
    });

    return true;
  } catch (err) {
    Logger.write('[rsd] transferToPstn error: ' + err);
    return false;
  }
}



// --- lib/rsd_media_gateway.js ---
/**

 * @param {object} opts

 * @param {string} opts.mediaWsUrl - wss://host/ws

 * @param {string} opts.callId

 * @param {number} opts.connectionId

 * @param {string} opts.callerE164

 * @param {string} [opts.calledNumber]

 * @param {Call} opts.call - VoxEngine call for playback

 * @param {function} opts.onReady

 * @param {function} opts.onError

 */

function connectMediaGateway(opts) {

  var wsUrl = String(opts.mediaWsUrl || '').trim();

  if (!wsUrl) {

    opts.onError('media_ws_url missing');

    return null;

  }



  var webSocket = VoxEngine.createWebSocket(wsUrl);

  var mediaBound = false;

  var firstDownlinkMediaLogged = false;
  var firstDownlinkMediaAtMs = 0;
  var lastSttPartialAtMs = 0;



  function bindDownlinkMedia() {

    // Re-bind websocket -> call explicitly when playback starts.
    // In some Vox runtimes the downlink leg can be dropped after early media/answer transition.
    try {

      webSocket.sendMediaTo(opts.call, {

        encoding: WebSocketAudioEncoding.ULAW,

      });

      return;

    } catch (downErr) {

      Logger.write('[rsd] downlink bind with ULAW failed, retry without encoding: ' + downErr);

    }

    try {

      webSocket.sendMediaTo(opts.call);

    } catch (fallbackErr) {

      Logger.write('[rsd] downlink bind fallback failed: ' + fallbackErr);

    }

  }



  function bindDuplexMedia() {

    if (mediaBound) return;

    mediaBound = true;

    opts.call.sendMediaTo(webSocket, {

      encoding: WebSocketAudioEncoding.ULAW,

    });

    bindDownlinkMedia();

    Logger.write('[rsd] gateway duplex ULAW ready call_id=' + opts.callId);

  }



  if (typeof WebSocketEvents !== 'undefined' && WebSocketEvents.MEDIA_STARTED !== undefined) {

    webSocket.addEventListener(WebSocketEvents.MEDIA_STARTED, function (ev) {

      Logger.write(

        '[rsd] gateway WS MEDIA_STARTED encoding=' +

          String(ev.encoding || '') +

          ' tag=' +

          String(ev.tag || '') +

          ' call_id=' +

          opts.callId,

      );

    });

  }



  if (typeof WebSocketEvents !== 'undefined' && WebSocketEvents.MEDIA_ENDED !== undefined) {

    webSocket.addEventListener(WebSocketEvents.MEDIA_ENDED, function () {

      Logger.write('[rsd] gateway WS MEDIA_ENDED call_id=' + opts.callId);

    });

  }



  webSocket.addEventListener(WebSocketEvents.OPEN, function () {

    var startMsg = {

      type: 'session.start',

      payload: {

        call_id: String(opts.callId),

        connection_id: Number(opts.connectionId),

        caller_e164: String(opts.callerE164),

        codec: 'pcmu',

        called_number: opts.calledNumber ? String(opts.calledNumber) : undefined,

        protocol_version: '1',

      },

    };

    webSocket.send(JSON.stringify(startMsg));

    bindDuplexMedia();

    if (opts.onReady) opts.onReady(webSocket);

  });



  webSocket.addEventListener(WebSocketEvents.MESSAGE, function (e) {

    var text = (e && e.text) ? String(e.text) : '';

    if (!text) return;



    try {

      var msg = JSON.parse(text);

      if (msg.type === 'session.start' && msg.payload && msg.payload.ok) {

        Logger.write('[rsd] gateway session.start ok call_id=' + opts.callId);

        return;

      }

      if (msg.type === 'error') {

        Logger.write('[rsd] gateway error: ' + JSON.stringify(msg.payload));

        return;

      }

      if (msg.type === 'call.transfer' && msg.payload) {

        var target = String(msg.payload.e164 || msg.payload.operator_transfer_e164 || '').trim();

        if (opts.onTransferRequest) {

          opts.onTransferRequest(target || 'operator');

        } else {

          Logger.write('[rsd] call.transfer ignored: no onTransferRequest handler call_id=' + opts.callId);

        }

        return;

      }

      if (msg.type === 'stt.partial') {

        lastSttPartialAtMs = Date.now();

        return;

      }

      if (msg.type === 'barge_in' && msg.payload && msg.payload.clear_playback) {

        var nowMs = Date.now();
        var sinceFirstMediaMs = firstDownlinkMediaAtMs ? nowMs - firstDownlinkMediaAtMs : -1;
        var sinceSttPartialMs = lastSttPartialAtMs ? nowMs - lastSttPartialAtMs : -1;
        var recentPlaybackStart = sinceFirstMediaMs >= 0 && sinceFirstMediaMs < 1200;
        var noRecentUserSpeech = sinceSttPartialMs < 0 || sinceSttPartialMs > 1200;
        if (recentPlaybackStart && noRecentUserSpeech) {

          Logger.write(

            '[rsd] gateway barge_in ignored (likely playback echo) call_id=' +

              opts.callId +

              ' since_first_media_ms=' +

              sinceFirstMediaMs +

              ' since_stt_partial_ms=' +

              sinceSttPartialMs,

          );

          return;

        }

        try {

          if (typeof webSocket.clearMediaBuffer === 'function') {

            webSocket.clearMediaBuffer();

            Logger.write('[rsd] gateway barge_in clearMediaBuffer call_id=' + opts.callId);

          } else {

            Logger.write('[rsd] gateway barge_in: clearMediaBuffer not available on WebSocket');

          }

        } catch (clearErr) {

          Logger.write('[rsd] gateway barge_in clear failed: ' + clearErr);

        }

        return;

      }

      if (msg.event === 'start' && msg.start) {

        // Guard against lost websocket->call media routing before first chunk.
        bindDownlinkMedia();
        firstDownlinkMediaLogged = false;
        firstDownlinkMediaAtMs = 0;

        Logger.write('[rsd] gateway downlink start call_id=' + opts.callId);

        return;

      }

      if (msg.event === 'stop') {

        Logger.write('[rsd] gateway downlink stop call_id=' + opts.callId);

        return;

      }

      if (msg.event === 'media' && msg.media && msg.media.payload) {

        if (!firstDownlinkMediaLogged) {

          // One more safety rebind at the first real payload.
          bindDownlinkMedia();

          firstDownlinkMediaLogged = true;
          firstDownlinkMediaAtMs = Date.now();

          Logger.write(

            '[rsd] gateway first downlink media call_id=' +

              opts.callId +

              ' payloadLen=' +

              String(msg.media.payload.length || 0),

          );

        }

        return;

      }

      if (msg.type && String(msg.type).indexOf('agent.audio') === 0) {

        if (msg.type === 'agent.audio.start') {

          firstDownlinkMediaLogged = false;
          firstDownlinkMediaAtMs = 0;

        }

        return;

      }

    } catch (err) {

      Logger.write('[rsd] gateway ws text: ' + text.substring(0, 200));

    }

  });



  webSocket.addEventListener(WebSocketEvents.ERROR, function (e) {

    Logger.write('[rsd] gateway ws error: ' + JSON.stringify(e || {}));

    if (opts.onError) opts.onError('websocket_error');

  });



  webSocket.addEventListener(WebSocketEvents.CLOSE, function (e) {

    Logger.write('[rsd] gateway ws close: ' + (e && e.reason ? e.reason : ''));

  });



  return webSocket;

}



function sendDtmfToGateway(webSocket, digit) {

  if (!webSocket || !digit) return;

  webSocket.send(

    JSON.stringify({

      type: 'dtmf',

      payload: { digit: String(digit) },

    }),

  );

}



function sendSessionEnd(webSocket, reason) {

  if (!webSocket) return;

  try {

    webSocket.send(JSON.stringify({ type: 'session.end', payload: { reason: reason || 'hangup' } }));

    webSocket.close();

  } catch (e) {

    Logger.write('[rsd] session.end failed: ' + e);

  }

}





// --- rsd_inbound (main) ---
var rsdControl = { postControlEvent: postControlEvent };
var rsdMedia = {
  connectMediaGateway: connectMediaGateway,
  sendDtmfToGateway: sendDtmfToGateway,
  sendSessionEnd: sendSessionEnd,
};
var rsdTransfer = { transferToPstn: transferToPstn };
var DEFAULT_GREETING_TEXT = 'Здравствуйте! Ожидайте, пожалуйста.';
var POOL_GREETING_TEXT =
  'Здравствуйте! Введите добавочный номер из четырёх цифр на клавиатуре телефона.';
var RECORDING_DISCLAIMER_RU =
  'Разговор может быть записан в целях контроля качества обслуживания.';
/** Wait for DTMF from dial string (+7...,1234) before pool prompt. */
var EXTENSION_DIGIT_COUNT = 4;
var DTMF_PREFILL_MS = 2500;

function parseCustomData() {
  try {
    var raw = VoxEngine.customData();
    if (!raw) return {};
    return JSON.parse(raw);
  } catch (e) {
    Logger.write('[rsd] invalid customData: ' + e);
    return {};
  }
}

function secretValue(name) {
  try {
    var v = VoxEngine.getSecretValue(name);
    if (v === undefined || v === null) return '';
    return String(v).trim();
  } catch (e) {
    return '';
  }
}

function resolveConfig() {
  var cfg = parseCustomData();
  var connectionId = Number(
    cfg.connection_id ||
      cfg.connectionId ||
      secretValue('RSD_CONNECTION_ID') ||
      0,
  );
  var webhookBase = String(
    cfg.webhook_base_url || cfg.webhookBaseUrl || secretValue('RSD_WEBHOOK_BASE_URL') || '',
  ).replace(/\/$/, '');
  var mediaWsUrl = String(
    cfg.media_ws_url || cfg.mediaWsUrl || secretValue('TELEPHONY_MEDIA_WS_URL') || '',
  ).trim();
  var webhookSecret = String(
    secretValue('RSD_WEBHOOK_SECRET') || cfg.webhook_secret || cfg.webhookSecret || '',
  ).trim();
  var requireExtSecret = secretValue('RSD_REQUIRE_EXTENSION').toLowerCase();
  var requireExtension = Boolean(
    cfg.require_extension ||
      cfg.requireExtension ||
      requireExtSecret === '1' ||
      requireExtSecret === 'true' ||
      requireExtSecret === 'yes',
  );
  return {
    connectionId: connectionId,
    webhookBaseUrl: webhookBase,
    mediaWsUrl: mediaWsUrl,
    greetingUrl: String(cfg.greeting_url || cfg.greetingUrl || '').trim(),
    greetingText: String(cfg.greeting_text || cfg.greetingText || DEFAULT_GREETING_TEXT).trim(),
    webhookSecret: webhookSecret,
    requireExtension: requireExtension,
  };
}

function callerE164(e, call) {
  if (e && e.callerid) {
    return String(e.callerid).trim();
  }
  return String(call.callerid() || call.displayName() || '+00000000000').trim();
}

function calledNumber(e, call) {
  if (e && e.destination) {
    return String(e.destination).trim();
  }
  if (e && e.toURI) {
    var sipMatch = String(e.toURI).match(/^sip:([^@;]+)/i);
    if (sipMatch && sipMatch[1]) {
      return String(sipMatch[1]).trim();
    }
  }
  try {
    if (call && typeof call.number === 'function') {
      var num = call.number();
      if (num) return String(num).trim();
    }
  } catch (numErr) {
    Logger.write('[rsd] call.number failed: ' + numErr);
  }
  return '';
}

VoxEngine.addEventListener(AppEvents.CallAlerting, function (e) {
  var call = e.call;
  var cfg = resolveConfig();
  var callId = String(call.id());
  var caller = callerE164(e, call);
  var called = calledNumber(e, call);
  var mediaWs = null;
  var operatorTransferE164 = '';
  var playRecordingDisclaimer = false;
  var degradedTransferE164 = '';
  var dtmfBuffer = '';
  var pendingDtmfDigits = [];
  var extensionDialComplete = false;
  var dtmfPrefillTimer = null;
  var answered = false;

  if (!cfg.connectionId || !cfg.webhookBaseUrl || !cfg.webhookSecret) {
    Logger.write(
      '[rsd] missing config connection_id=' +
        cfg.connectionId +
        ' webhook_base=' +
        (cfg.webhookBaseUrl ? 'ok' : 'no') +
        ' webhook_secret=' +
        (cfg.webhookSecret ? 'ok' : 'no') +
        ' (PSTN: use Application Secrets, not rule StartScenarios customData)',
    );
    call.reject(603, 'misconfigured');
    call.addEventListener(CallEvents.Disconnected, function () {
      VoxEngine.terminate();
    });
    return;
  }

  function enableToneCapture() {
    try {
      call.handleTones(true);
    } catch (toneErr) {
      Logger.write('[rsd] handleTones: ' + toneErr);
    }
  }

  function flushPendingDtmf() {
    if (!mediaWs || !pendingDtmfDigits.length) {
      return;
    }
    for (var i = 0; i < pendingDtmfDigits.length; i++) {
      rsdMedia.sendDtmfToGateway(mediaWs, pendingDtmfDigits[i]);
    }
    pendingDtmfDigits = [];
  }

  function pushDtmfDigit(digit) {
    var d = String(digit || '').trim();
    if (!/^[0-9]$/.test(d)) {
      return;
    }
    if (cfg.requireExtension) {
      dtmfBuffer = (dtmfBuffer + d).slice(-EXTENSION_DIGIT_COUNT);
      if (dtmfBuffer.length >= EXTENSION_DIGIT_COUNT && !extensionDialComplete) {
        extensionDialComplete = true;
        Logger.write(
          '[rsd] extension pre-dial complete ext=' + dtmfBuffer + ' call_id=' + callId,
        );
        onExtensionPreDialReady();
      }
    }
    if (mediaWs) {
      rsdMedia.sendDtmfToGateway(mediaWs, d);
    } else {
      pendingDtmfDigits.push(d);
    }
  }

  function clearDtmfPrefillTimer() {
    if (dtmfPrefillTimer) {
      clearTimeout(dtmfPrefillTimer);
      dtmfPrefillTimer = null;
    }
  }

  function proceedToAnswer() {
    if (answered) {
      return;
    }
    answered = true;
    clearDtmfPrefillTimer();
    call.answer();
    onAnswered();
  }

  function completeExtensionFastPath() {
    if (!cfg.requireExtension || !extensionDialComplete || answered) {
      return;
    }
    clearDtmfPrefillTimer();
    Logger.write('[rsd] skip pool greeting — extension from dial string call_id=' + callId);
    if (playRecordingDisclaimer) {
      call.say(RECORDING_DISCLAIMER_RU, Language.RU_RUSSIAN_FEMALE);
      call.addEventListener(CallEvents.PlaybackFinished, function onDisclaimerDone() {
        call.removeEventListener(CallEvents.PlaybackFinished, onDisclaimerDone);
        proceedToAnswer();
      });
      return;
    }
    proceedToAnswer();
  }

  function onExtensionPreDialReady() {
    if (!cfg.requireExtension || !extensionDialComplete || answered) {
      return;
    }
    if (dtmfPrefillTimer) {
      completeExtensionFastPath();
    }
  }

  enableToneCapture();

  call.addEventListener(CallEvents.Disconnected, function () {
    clearDtmfPrefillTimer();
    rsdMedia.sendSessionEnd(mediaWs, 'hangup');
    rsdControl.postControlEvent(
      {
        webhookBaseUrl: cfg.webhookBaseUrl,
        connectionId: cfg.connectionId,
        webhookSecret: cfg.webhookSecret,
        event: 'call.hangup',
        callId: callId,
        payload: { caller_e164: caller, reason: 'completed' },
      },
      function () {
        VoxEngine.terminate();
      },
    );
  });

  call.addEventListener(CallEvents.Failed, function () {
    rsdMedia.sendSessionEnd(mediaWs, 'failed');
    VoxEngine.terminate();
  });

  call.addEventListener(CallEvents.ToneReceived, function (ev) {
    var digit = ev && ev.tone ? String(ev.tone) : '';
    if (digit) {
      pushDtmfDigit(digit);
    }
  });

  function tryDegradedTransfer() {
    var dest = String(degradedTransferE164 || operatorTransferE164 || '').trim();
    if (!dest) {
      return false;
    }
    return rsdTransfer.transferToPstn({
      inboundCall: call,
      destinationE164: dest,
      callerId: called || caller,
      callId: callId,
    });
  }

  function onAnswered() {
    if (degradedTransferE164) {
      if (tryDegradedTransfer()) {
        return;
      }
      Logger.write('[rsd] degraded transfer failed, continuing with media gateway call_id=' + callId);
      degradedTransferE164 = '';
    }

    enableToneCapture();

    rsdControl.postControlEvent(
      {
        webhookBaseUrl: cfg.webhookBaseUrl,
        connectionId: cfg.connectionId,
        webhookSecret: cfg.webhookSecret,
        event: 'call.answered',
        callId: callId,
        payload: { caller_e164: caller, called_e164: called },
      },
      function (err) {
        if (err) Logger.write('[rsd] call.answered webhook failed: ' + err);
      },
    );

    if (!cfg.mediaWsUrl) {
      Logger.write('[rsd] media_ws_url missing — audio not streamed');
      return;
    }

    mediaWs = rsdMedia.connectMediaGateway({
      mediaWsUrl: cfg.mediaWsUrl,
      callId: callId,
      connectionId: cfg.connectionId,
      callerE164: caller,
      calledNumber: called,
      call: call,
      onReady: function () {
        Logger.write('[rsd] media gateway ready call_id=' + callId);
        flushPendingDtmf();
      },
      onError: function (msg) {
        Logger.write('[rsd] media gateway error: ' + msg);
      },
      onTransferRequest: function (target) {
        var dest = operatorTransferE164 || target || 'operator';
        if (dest && dest !== 'operator') {
          rsdTransfer.transferToPstn({
            inboundCall: call,
            destinationE164: dest,
            callerId: called || caller,
            callId: callId,
          });
        }
      },
    });
  }

  function sipHeader(name) {
    try {
      if (typeof call.sipHeader === 'function') {
        return String(call.sipHeader(name) || '').trim();
      }
      if (typeof call.headers === 'function') {
        return String(call.headers(name) || '').trim();
      }
    } catch (e) {
      Logger.write('[rsd] sipHeader read failed: ' + e);
    }
    return '';
  }

  function playEarlyGreetingThenAnswer() {
    call.startEarlyMedia();

    function runGreetingSteps() {
      var greetText = cfg.requireExtension ? POOL_GREETING_TEXT : cfg.greetingText;
      var steps = [];

      if (playRecordingDisclaimer) {
        steps.push(function (next) {
          call.say(RECORDING_DISCLAIMER_RU, Language.RU_RUSSIAN_FEMALE);
          call.addEventListener(CallEvents.PlaybackFinished, function onDisclaimer() {
            call.removeEventListener(CallEvents.PlaybackFinished, onDisclaimer);
            next();
          });
        });
      }

      steps.push(function (next) {
        if (cfg.requireExtension && extensionDialComplete) {
          next();
          return;
        }
        if (cfg.greetingUrl && !cfg.requireExtension) {
          call.startPlayback(cfg.greetingUrl, false);
          call.addEventListener(CallEvents.PlaybackFinished, function finishPlayback() {
            call.removeEventListener(CallEvents.PlaybackFinished, finishPlayback);
            next();
          });
          call.addEventListener(CallEvents.PlaybackError, function () {
            Logger.write('[rsd] greeting playback error, answering anyway');
            next();
          });
          return;
        }
        call.say(greetText, Language.RU_RUSSIAN_FEMALE);
        call.addEventListener(CallEvents.PlaybackFinished, function finishSay() {
          call.removeEventListener(CallEvents.PlaybackFinished, finishSay);
          next();
        });
      });

      function runStep(i) {
        if (i >= steps.length) {
          proceedToAnswer();
          return;
        }
        steps[i](function () {
          runStep(i + 1);
        });
      }
      runStep(0);
    }

    if (cfg.requireExtension) {
      if (extensionDialComplete) {
        completeExtensionFastPath();
        return;
      }
      dtmfPrefillTimer = setTimeout(function () {
        dtmfPrefillTimer = null;
        if (!extensionDialComplete && !answered) {
          Logger.write('[rsd] dtmf prefill timeout, play pool greeting call_id=' + callId);
          runGreetingSteps();
        }
      }, DTMF_PREFILL_MS);
      return;
    }

    runGreetingSteps();
  }

  rsdControl.postControlEvent(
    {
      webhookBaseUrl: cfg.webhookBaseUrl,
      connectionId: cfg.connectionId,
      webhookSecret: cfg.webhookSecret,
      event: 'call.inbound',
      callId: callId,
      payload: {
        caller_e164: caller,
        called_e164: called,
        provider_session_id: callId,
        sip_from: sipHeader('From') || sipHeader('from'),
        sip_to: sipHeader('To') || sipHeader('to'),
      },
    },
    function (err, body) {
      if (err) Logger.write('[rsd] call.inbound webhook failed: ' + err);
      if (body && body.operator_transfer_e164) {
        operatorTransferE164 = String(body.operator_transfer_e164).trim();
      }
      if (body && body.degraded && body.transfer_e164) {
        degradedTransferE164 = String(body.transfer_e164).trim();
      }
      if (body && body.record_calls && !body.disclaimer_played) {
        playRecordingDisclaimer = true;
      }
      if (degradedTransferE164) {
        proceedToAnswer();
        return;
      }
      playEarlyGreetingThenAnswer();
    },
  );
});
