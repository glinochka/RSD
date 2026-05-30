/**
 * PSTN blind transfer: VoxEngine has no call.transfer — dial out and bridge media.
 * @see https://voximplant.com/docs/references/voxengine/voxengine/sendmediabetween
 */

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

module.exports = {
  transferToPstn: transferToPstn,
  normalizePstnE164: normalizePstnE164,
};
