/**
 * Local smoke test: session.start + Vox media JSON loopback.
 * Usage: node scripts/test_vox_loopback.mjs [ws://127.0.0.1:8200/ws]
 */
import WebSocket from 'ws';

const url = process.argv[2] || 'ws://127.0.0.1:8200/ws';
const ulaw = Buffer.alloc(160, 0x7f);

const ws = new WebSocket(url);
ws.on('open', () => {
  ws.send(
    JSON.stringify({
      type: 'session.start',
      payload: {
        call_id: 'test-' + Date.now(),
        connection_id: 1,
        caller_e164: '+79001112233',
        codec: 'pcmu',
      },
    }),
  );
  ws.send(
    JSON.stringify({
      event: 'media',
      media: { payload: ulaw.toString('base64') },
    }),
  );
});
ws.on('message', (data) => {
  const text = data.toString();
  console.log('recv:', text.slice(0, 200));
  if (text.includes('"event":"media"')) {
    console.log('ok: vox loopback received');
    ws.close();
    process.exit(0);
  }
});
ws.on('error', (e) => {
  console.error(e);
  process.exit(1);
});
setTimeout(() => {
  console.error('timeout');
  process.exit(1);
}, 5000);
