// Copies the voice-activity-detection runtime into public/vad/ so the browser
// loads it from our own origin (no third-party CDN at interview time).
// Runs before `dev` and `build`; the output is git-ignored.
//
// Only what @ricky0123/vad-web's "onnxruntime-web/wasm" build actually loads:
// onnxruntime ships ~90 MB of other variants (WebGPU/JSEP, JSPI, asyncify) we don't use.

import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "public", "vad");
const files = {
  "node_modules/@ricky0123/vad-web/dist/silero_vad_v5.onnx": "silero_vad_v5.onnx",
  "node_modules/@ricky0123/vad-web/dist/vad.worklet.bundle.min.js": "vad.worklet.bundle.min.js",
  "node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs": "ort-wasm-simd-threaded.mjs",
  "node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.wasm": "ort-wasm-simd-threaded.wasm",
};

mkdirSync(out, { recursive: true });
for (const [from, to] of Object.entries(files)) copyFileSync(join(root, from), join(out, to));
console.log(`copied ${Object.keys(files).length} VAD assets to public/vad/`);
