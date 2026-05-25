/**
 * RSD inbound PSTN — Early Media + Media Gateway WebSocket (streaming refactor stage 2).
 *
 * Routing rule customData (JSON), example:
 * {
 *   "connection_id": 42,
 *   "webhook_base_url": "https://telephony.example.com",
 *   "media_ws_url": "wss://telephony.example.com/ws",
 *   "greeting_url": "https://cdn.example/telephony/greeting.ulaw",
 *   "greeting_text": "Здравствуйте"
 * }
 *
 * Secret: VoxEngine application secret RSD_WEBHOOK_SECRET (webhook HMAC).
 * WebSocket and Crypto are built-in (no require(Modules.*) — Modules.Crypto is absent on current runtime).
 */
function requireRsdModule(name) {
  try {
    return require('./lib/' + name);
  } catch (e1) {
    try {
      return require('./' + name);
    } catch (e2) {
      Logger.write('[rsd] cannot load module ' + name + ': ' + e1 + ' / ' + e2);
      throw e2;
    }
  }
}

var rsdControl = requireRsdModule('rsd_control');
var rsdMedia = requireRsdModule('rsd_media_gateway');

var DEFAULT_GREETING_TEXT = 'Здравствуйте! Ожидайте, пожалуйста.';
var POOL_GREETING_TEXT =
  'Здравствуйте! Введите добавочный номер из четырёх цифр на клавиатуре телефона.';
var RECORDING_DISCLAIMER_RU =
  'Разговор может быть записан в целях контроля качества обслуживания.';

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

function resolveConfig() {
  var cfg = parseCustomData();
  var connectionId = Number(cfg.connection_id || cfg.connectionId || 0);
  var webhookBase = String(
    cfg.webhook_base_url || cfg.webhookBaseUrl || VoxEngine.getSecretValue('RSD_WEBHOOK_BASE_URL') || '',
  ).replace(/\/$/, '');
  var mediaWsUrl = String(
    cfg.media_ws_url || cfg.mediaWsUrl || VoxEngine.getSecretValue('TELEPHONY_MEDIA_WS_URL') || '',
  ).trim();
  var webhookSecret = String(
    VoxEngine.getSecretValue('RSD_WEBHOOK_SECRET') || cfg.webhook_secret || '',
  ).trim();
  return {
    connectionId: connectionId,
    webhookBaseUrl: webhookBase,
    mediaWsUrl: mediaWsUrl,
    greetingUrl: String(cfg.greeting_url || cfg.greetingUrl || '').trim(),
    greetingText: String(cfg.greeting_text || cfg.greetingText || DEFAULT_GREETING_TEXT).trim(),
    webhookSecret: webhookSecret,
    requireExtension: Boolean(cfg.require_extension || cfg.requireExtension),
  };
}

function callerE164(call) {
  return String(call.callerid() || call.displayName() || '+00000000000').trim();
}

function calledNumber(call) {
  return String(call.destination() || call.number() || '').trim();
}

VoxEngine.addEventListener(AppEvents.CallAlerting, function (e) {
  var call = e.call;
  var cfg = resolveConfig();
  var callId = String(call.id());
  var caller = callerE164(call);
  var called = calledNumber(call);
  var mediaWs = null;
  var operatorTransferE164 = '';
  var playRecordingDisclaimer = false;
  var degradedTransferE164 = '';

  if (!cfg.connectionId || !cfg.webhookBaseUrl || !cfg.webhookSecret) {
    Logger.write('[rsd] missing connection_id / webhook_base_url / RSD_WEBHOOK_SECRET');
    call.reject(603, 'misconfigured');
    return;
  }

  call.addEventListener(CallEvents.Disconnected, function () {
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
    if (digit && mediaWs) {
      rsdMedia.sendDtmfToGateway(mediaWs, digit);
    }
  });

  function tryDegradedTransfer() {
    var dest = String(degradedTransferE164 || operatorTransferE164 || '').trim();
    if (!dest) {
      return false;
    }
    try {
      call.transfer(dest);
      Logger.write('[rsd] degraded transfer to ' + dest + ' call_id=' + callId);
      return true;
    } catch (transferErr) {
      Logger.write('[rsd] degraded transfer failed: ' + transferErr);
      return false;
    }
  }

  function onAnswered() {
    if (degradedTransferE164) {
      tryDegradedTransfer();
      return;
    }

    try {
      call.handleTones(true);
    } catch (toneErr) {
      Logger.write('[rsd] handleTones: ' + toneErr);
    }

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
      },
      onError: function (msg) {
        Logger.write('[rsd] media gateway error: ' + msg);
      },
      onTransferRequest: function (target) {
        var dest = operatorTransferE164 || target || 'operator';
        if (dest && dest !== 'operator') {
          try {
            call.transfer(dest);
            Logger.write('[rsd] transfer via operator e164 ' + dest);
          } catch (transferErr) {
            Logger.write('[rsd] transfer failed: ' + transferErr);
          }
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
        call.answer();
        onAnswered();
        return;
      }
      steps[i](function () {
        runStep(i + 1);
      });
    }
    runStep(0);
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
        call.answer();
        onAnswered();
        return;
      }
      playEarlyGreetingThenAnswer();
    },
  );
});
