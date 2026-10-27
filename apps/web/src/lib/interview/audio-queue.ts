/**
 * Plays interviewer audio back-to-back with no gaps (projectprep.md, 5.9).
 *
 * Each sentence arrives as its own MP3. Instead of chaining `onended` callbacks
 * (which leave small, audible gaps), every clip is scheduled on the AudioContext
 * clock to start exactly when the previous one ends.
 */
export class AudioQueue {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null; // feeds the voice orb with the real loudness
  private levels = new Uint8Array(0);
  private endsAt = 0; // AudioContext time when the last scheduled clip finishes
  private chain: Promise<void> = Promise.resolve(); // keeps decode+schedule in arrival order
  private epoch = 0; // bumped by stop(): work queued before it is dropped

  /** Must run inside a click handler: browsers only allow audio after a user gesture. */
  async unlock(): Promise<void> {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.6;
      this.analyser.connect(this.ctx.destination);
      this.levels = new Uint8Array(this.analyser.fftSize);
    }
    if (this.ctx.state === "suspended") await this.ctx.resume();
  }

  /** Loudness of what is playing right now, 0 to 1. Cheap enough to call every animation frame. */
  level(): number {
    if (!this.analyser) return 0;
    this.analyser.getByteTimeDomainData(this.levels);
    let sum = 0;
    for (const v of this.levels) sum += ((v - 128) / 128) ** 2;
    return Math.min(1, Math.sqrt(sum / this.levels.length) * 3); // RMS, scaled up: speech rarely peaks
  }

  enqueue(mp3: ArrayBuffer): void {
    const epoch = this.epoch;
    // Decoding is async and clips can differ in size; chaining keeps them in order.
    this.chain = this.chain.then(async () => {
      const { ctx, analyser } = this;
      if (!ctx || !analyser || epoch !== this.epoch) return;
      try {
        const buffer = await ctx.decodeAudioData(mp3);
        if (epoch !== this.epoch) return; // stopped while decoding
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(analyser);
        const startAt = Math.max(ctx.currentTime + 0.02, this.endsAt); // 20 ms lead avoids a click
        source.start(startAt);
        this.endsAt = startAt + buffer.duration;
      } catch {
        // An undecodable clip (or a context closed by stop()) must not break the clips after it.
      }
    });
  }

  /** Speak `text` with the browser's voice, in order with the clips around it (D26). */
  enqueueSpeech(text: string): void {
    const epoch = this.epoch;
    this.chain = this.chain.then(async () => {
      if (epoch !== this.epoch) return;
      await this.waitForScheduledAudio();
      if (epoch !== this.epoch) return;
      await speakWithBrowser(text);
      if (this.ctx) this.endsAt = this.ctx.currentTime; // later clips start after the speech
    });
  }

  /** Resolves when everything queued so far has finished playing. */
  async idle(): Promise<void> {
    await this.chain;
    await this.waitForScheduledAudio();
  }

  /** Cut all sound right now and forget what was queued ("End interview" must feel instant). */
  async stop(): Promise<void> {
    this.epoch++;
    this.chain = Promise.resolve();
    this.endsAt = 0;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    const ctx = this.ctx;
    this.ctx = null;
    this.analyser = null;
    await ctx?.close().catch(() => {});
  }

  private async waitForScheduledAudio(): Promise<void> {
    const ctx = this.ctx;
    if (!ctx) return;
    const remainingMs = Math.max(0, (this.endsAt - ctx.currentTime) * 1000);
    await new Promise((resolve) => setTimeout(resolve, remainingMs));
  }

  async close(): Promise<void> {
    await this.stop();
  }
}

/** Browser's built-in voice: the fallback when our TTS is down (D26).
 *  Always resolves: some browsers (no voices installed) never fire onend or
 *  onerror, so a deadline based on text length keeps the interview moving. */
export function speakWithBrowser(text: string): Promise<void> {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) return resolve();
    const deadline = setTimeout(resolve, 2000 + text.split(/\s+/).length * 400); // ~150 wpm + slack
    const done = () => {
      clearTimeout(deadline);
      resolve();
    };
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.onend = done;
    utterance.onerror = done;
    window.speechSynthesis.speak(utterance);
  });
}
