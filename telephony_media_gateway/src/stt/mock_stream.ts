import type { StreamingSttProvider, StreamingSttSession, SttPartial } from './types';

/** Dev/test STT: emits partials while audio is pushed. */
export class MockStreamingStt implements StreamingSttProvider {
  readonly name = 'mock';

  startStream(): StreamingSttSession {
    let partialCb: ((p: SttPartial) => void) | null = null;
    let finalCb: ((p: SttPartial) => void) | null = null;
    let errorCb: ((err: Error) => void) | null = null;
    let bytes = 0;
    let tick = 0;
    let timer: ReturnType<typeof setInterval> | null = null;
    let closed = false;

    const session: StreamingSttSession = {
      pushAudio(buf: Buffer) {
        if (closed) return;
        bytes += buf.length;
        if (!timer && bytes > 1600) {
          timer = setInterval(() => {
            tick += 1;
            partialCb?.({
              text: `тестовая фраза ${tick}`,
              confidence: 0.7,
              stable: false,
            });
          }, 80);
        }
      },
      close() {
        if (closed) return;
        closed = true;
        if (timer) clearInterval(timer);
        finalCb?.({ text: `тестовая фраза ${Math.max(1, tick)}`, confidence: 0.85 });
      },
      onPartial(cb) {
        partialCb = cb;
      },
      onFinal(cb) {
        finalCb = cb;
      },
      onError(cb) {
        errorCb = cb;
      },
    };

    return session;
  }
}
