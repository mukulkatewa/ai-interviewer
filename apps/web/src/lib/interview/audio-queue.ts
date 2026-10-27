/**
 * Plays interviewer audio back-to-back with no gaps (projectprep.md, 5.9).
 *
 * Each sentence arrives as its own MP3. Instead of chaining `onended` callbacks
 * (which leave small, audible gaps), every clip is scheduled on the AudioContext
 * clock to start exactly when the previous one ends.
 */
export class AudioQueue {
  private ctx: AudioContext | null = null;
  private endsAt = 0; // AudioContext time when the last scheduled clip finishes
  private chain: Promise<void> = Promise.resolve(); // keeps decode+schedule in arrival order

  /** Must run inside a click handler: browsers only allow audio after a user gesture. */
  async unlock(): Promise<void> {
    this.ctx ??= new AudioContext();
    if (this.ctx.state === "suspended") await this.ctx.resume();
  }

  enqueue(mp3: ArrayBuffer): void {
    // Decoding is async and clips can differ in size; chaining keeps them in order.
    this.chain = this.chain.then(async () => {
      const ctx = this.ctx;
      if (!ctx) return;
      const buffer = await ctx.decodeAudioData(mp3);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      const startAt = Math.max(ctx.currentTime + 0.02, this.endsAt); // 20 ms lead avoids a click
      source.start(startAt);
      this.endsAt = startAt + buffer.duration;
    });
  }

  /** Speak `text` with the browser's voice, in order with the clips around it (D26). */
  enqueueSpeech(text: string): void {
    this.chain = this.chain.then(async () => {
      await this.waitForScheduledAudio();
      await speakWithBrowser(text);
      if (this.ctx) this.endsAt = this.ctx.currentTime; // later clips start after the speech
    });
  }

  /** Resolves when everything queued so far has finished playing. */
  async idle(): Promise<void> {
    await this.chain;
    await this.waitForScheduledAudio();
  }

  private async waitForScheduledAudio(): Promise<void> {
    const ctx = this.ctx;
    if (!ctx) return;
    const remainingMs = Math.max(0, (this.endsAt - ctx.currentTime) * 1000);
    await new Promise((resolve) => setTimeout(resolve, remainingMs));
  }

  async close(): Promise<void> {
    await this.ctx?.close();
    this.ctx = null;
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
