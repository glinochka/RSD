export const RECORDING_DISCLAIMER_RU =
  'Здравствуйте. Ваш разговор может быть записан для контроля качества и обучения сервиса. ' +
  'Продолжая разговор, вы соглашаетесь на обработку персональных данных. ' +
  'Если вы не согласны — положите трубку или нажмите ноль для оператора.';

export function shouldPlayRecordingDisclaimer(params: {
  recordCalls: boolean;
  disclaimerPlayed: boolean;
}): boolean {
  return params.recordCalls && params.disclaimerPlayed;
}
