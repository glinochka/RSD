/**
 * End-of-utterance when VAD reports silence for >= turnSilenceMs after speech.
 */
export class TurnTaking {
  private silenceMs = 0;
  private inUtterance = false;
  private speechSeen = false;

  constructor(
    private readonly frameMs: number,
    private readonly turnSilenceMs: number,
  ) {}

  onVad(isSpeech: boolean): 'continue' | 'utterance_start' | 'utterance_end' {
    if (isSpeech) {
      this.silenceMs = 0;
      if (!this.inUtterance) {
        this.inUtterance = true;
        this.speechSeen = true;
        return 'utterance_start';
      }
      return 'continue';
    }

    if (!this.inUtterance) {
      return 'continue';
    }

    this.silenceMs += this.frameMs;
    if (this.silenceMs >= this.turnSilenceMs) {
      this.inUtterance = false;
      this.silenceMs = 0;
      const hadSpeech = this.speechSeen;
      this.speechSeen = false;
      return hadSpeech ? 'utterance_end' : 'continue';
    }
    return 'continue';
  }

  reset(): void {
    this.silenceMs = 0;
    this.inUtterance = false;
    this.speechSeen = false;
  }
}
