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
  /** How much like speech the microphone sounds right now, 0 to 1 (drives the voice orb). */
  onLevel?: (level: number) => void;
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
    private readonly releaseMicrophone: () => void,
  ) {}

  /** Asks for the microphone now, so call it from the Start click. Throws if permission is denied. */
  static async create(handlers: Handlers): Promise<AnswerRecorder> {
    // VAD callbacks are wired before the recorder exists; they reach it through this ref.
    const ref: { recorder?: AnswerRecorder; stream?: MediaStream } = {};
    const vad = await MicVAD.new({
      model: "v5",
      // Self-hosted by scripts/copy-vad-assets.mjs.
      baseAssetPath: "/vad/",
      onnxWASMBasePath: "/vad/",
      startOnLoad: false,
      redemptionMs: SEGMENT_END_MS,
      minSpeechMs: 300, // ignore coughs and clicks
      submitUserSpeechOnPause: true, // "Done" mid-sentence keeps what was said
      getStream: async () => {
        // Echo cancellation keeps the interviewer's voice out of the answer (D28).
        ref.stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        return ref.stream;
      },
      // One microphone stream for the whole interview. The library's default stops the stream on every
      // pause and asks the browser for the microphone again each turn (a new prompt on some browsers).
      pauseStream: async (stream) => {
        stream.getAudioTracks().forEach((track) => (track.enabled = false));
      },
      resumeStream: async (stream) => {
        stream.getAudioTracks().forEach((track) => (track.enabled = true));
        return stream;
      },
      onFrameProcessed: (probabilities) => handlers.onLevel?.(probabilities.isSpeech),
      onSpeechStart: () => ref.recorder?.speechStarted(),
      onSpeechEnd: (audio) => ref.recorder?.speechEnded(audio),
    });
    const releaseMicrophone = () => ref.stream?.getTracks().forEach((track) => track.stop());
    try {
      // The library only opens the microphone on the first start(). Do that here, on the click, so the
      // browser's permission prompt appears now and not 15 seconds in, when it is your turn to answer.
      await vad.start();
      await vad.pause();
    } catch (error) {
      releaseMicrophone();
      await vad.destroy().catch(() => {}); // can throw when startup failed half-way; nothing more to release
      throw error;
    }
    ref.recorder = new AnswerRecorder(vad, handlers, releaseMicrophone);
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

  /** Stop listening and throw away a half-finished answer, e.g. when the connection dropped. Never submits. */
  async abandon(): Promise<void> {
    this.active = false;
    this.clearTimers();
    this.segments = [];
    await this.vad.pause().catch(() => {});
  }

  /** Safe to call at any time and more than once: it releases the microphone and never throws. */
  async destroy(): Promise<void> {
    this.active = false;
    this.clearTimers();
    this.releaseMicrophone(); // the stream outlives every pause now, so it must be stopped explicitly
    await this.vad.destroy().catch(() => {});
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
