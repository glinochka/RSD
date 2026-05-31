/**
 * Media WebSocket client: session.start + Voximplant ULAW stream ↔ gateway.
 * Gateway sends Vox native JSON: start → media → stop (see media-streams/websocket).
 */

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

  function bindDuplexMedia() {
    if (mediaBound) return;
    mediaBound = true;
    opts.call.sendMediaTo(webSocket, {
      encoding: WebSocketAudioEncoding.ULAW,
    });
    webSocket.sendMediaTo(opts.call, {
      encoding: WebSocketAudioEncoding.ULAW,
    });
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
      if (msg.type === 'barge_in' && msg.payload && msg.payload.clear_playback) {
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
        Logger.write('[rsd] gateway downlink start call_id=' + opts.callId);
        return;
      }
      if (msg.event === 'stop') {
        Logger.write('[rsd] gateway downlink stop call_id=' + opts.callId);
        return;
      }
      if (msg.event === 'media' && msg.media && msg.media.payload) {
        if (!firstDownlinkMediaLogged) {
          firstDownlinkMediaLogged = true;
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

module.exports = {
  connectMediaGateway: connectMediaGateway,
  sendDtmfToGateway: sendDtmfToGateway,
  sendSessionEnd: sendSessionEnd,
};
