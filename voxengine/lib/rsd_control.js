/**
 * RFC-001 signed webhook posts from VoxEngine → telephony_bridge.
 * Uses built-in Crypto.hmac_sha256 (no Modules.Crypto — not available on current VoxEngine).
 * @see docs/telephony/RFC-001-webhook-contract.md
 */

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

module.exports = {
  postControlEvent: postControlEvent,
};
