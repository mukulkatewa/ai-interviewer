/**
 * Records one spoken answer using in-browser voice activity detection
 * (projectprep.md 5.10, D27, D28).
 *
 * Silero VAD splits the mic stream into speech segments. Thinking pauses are
 * normal in interviews, so segments are joined until the candidate has been
 * silent for SEGMENT_END_MS + TURN_GRACE_MS, presses "Done", or hits the cap.
 */
import { MicVAD, utils } from "@ricky0123/vad-web";

const SAMPLE_RATE = 16_000; // VAD output, and what the server expects
const SEGMENT_END_MS = 1000; // silence that closes a speech segment
const TURN_GRACE_MS = 1000; // further silence before the whole answer is submitted
const MAX_ANSWER_MS = 120_000; // 2-minute cap (D12)
const WAV_PCM = 1; // encodeWAV defaults to 32-bit float; the server accepts 16-bit PCM only

type Handlers = {
  onSpeaking: (speaking: boolean) => void;
  onAnswer: (wav: ArrayBuffer) => void;
  onNothingHeard: () => void;
};

export class AnswerRecorder {
  private segments: Float32Array[] = [];
  private graceTimer: ReturnType<typeof setTimeout> | undefined;
  private capTimer: ReturnType<typeof setTimeout> | undefined;
  private active = false;

  private constructor(
    private readonly vad: MicVAD,
    private readonly handlers: Handlers,
  ) {}

  /** Asks for the microphone, so call it from a click handler. Throws if permission is denied. */
  static async create(handlers: Handlers): Promise<AnswerRecorder> {
    // VAD callbacks are wired before the recorder exists; they reach it through this ref.
    const ref: { recorder?: AnswerRecorder } = {};
    const vad = await MicVAD.new({
      model: "v5",
      // Self-hosted by scripts/copy-vad-assets.mjs.
      baseAssetPath: "/vad/",
      onnxWASMBasePath: "/vad/",
      startOnLoad: false,
      redemptionMs: SEGMENT_END_MS,
      minSpeechMs: 300, // ignore coughs and clicks
      submitUserSpeechOnPause: true, // "Done" mid-sentence keeps what was said
      getStream: () =>
        navigator.mediaDevices.getUserMedia({
          // Echo cancellation keeps the interviewer's voice out of the answer (D28).
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }),
      onSpeechStart: () => ref.recorder?.speechStarted(),
      onSpeechEnd: (audio) => ref.recorder?.speechEnded(audio),
    });
    ref.recorder = new AnswerRecorder(vad, handlers);
    return ref.recorder;
  }

  /** Start listening for one answer. Only during the candidate's turn (D28). */
  async listen(): Promise<void> {
    this.segments = [];
    this.active = true;
    await this.vad.start();
    this.capTimer = setTimeout(() => void this.done(), MAX_ANSWER_MS);
  }

  /** The "Done answering" button, the 2-minute cap, or the turn grace ending. */
  async done(): Promise<void> {
    if (!this.active) return;
    await this.vad.pause(); // may deliver the in-progress segment via onSpeechEnd
    this.finish();
  }

  async destroy(): Promise<void> {
    this.active = false;
    this.clearTimers();
    await this.vad.destroy();
  }

  private speechStarted(): void {
    clearTimeout(this.graceTimer); // they kept talking: same answer
    this.handlers.onSpeaking(true);
  }

  private speechEnded(audio: Float32Array): void {
    if (!this.active) return;
    this.segments.push(audio);
    this.handlers.onSpeaking(false);
    clearTimeout(this.graceTimer);
    this.graceTimer = setTimeout(() => void this.done(), TURN_GRACE_MS);
  }

  private finish(): void {
    if (!this.active) return;
    this.active = false;
    this.clearTimers();
    if (this.segments.length === 0) return this.handlers.onNothingHeard();

    const samples = new Float32Array(this.segments.reduce((n, s) => n + s.length, 0));
    let offset = 0;
    for (const s of this.segments) {
      samples.set(s, offset);
      offset += s.length;
    }
    this.handlers.onAnswer(utils.encodeWAV(samples, WAV_PCM, SAMPLE_RATE, 1, 16));
  }

  private clearTimers(): void {
    clearTimeout(this.graceTimer);
    clearTimeout(this.capTimer);
  }
}
