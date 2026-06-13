import http from 'http';

import express from 'express';
import { WebSocketServer } from 'ws';

import { config } from './config';
import { PROTOCOL_VERSION } from './protocol/events';
import { isSttConfigured } from './stt/factory';
import { startReplySubscriber } from './orch/reply_hub';
import { attachMediaSessionHandler } from './ws/session_handler';

const app = express();

app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    service: 'telephony_media_gateway',
    protocol_version: PROTOCOL_VERSION,
    ws_path: config.wsPath,
    pipeline_enabled: config.pipelineEnabled,
    stt_provider: config.sttProvider,
    stt_configured: isSttConfigured(),
    turn_silence_ms: config.turnSilenceMs,
    vad_model_path: config.vadModelPath,
  });
});

app.get('/', (_req, res) => {
  res.json({
    service: 'telephony_media_gateway',
    docs: 'docs/telephony/SESSION_PROTOCOL.md',
    health: '/health',
    websocket: config.wsPath,
  });
});

const server = http.createServer(app);
const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url || '/', `http://${request.headers.host || 'localhost'}`);
  if (url.pathname !== config.wsPath) {
    socket.destroy();
    return;
  }
  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit('connection', ws, request);
  });
});

wss.on('connection', (ws) => {
  attachMediaSessionHandler(ws);
});

void startReplySubscriber();

server.listen(config.port, () => {
  console.log(
    `telephony_media_gateway listening on ${config.port} (ws ${config.wsPath}, protocol v${PROTOCOL_VERSION})`,
  );
});
