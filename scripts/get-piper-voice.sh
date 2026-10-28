#!/usr/bin/env bash
# Download the Piper voice used by TTS_ENGINE=piper (D47) into apps/api/voices/ (about 63 MB, git-ignored).
#   ./scripts/get-piper-voice.sh
# Other voices: https://huggingface.co/rhasspy/piper-voices (set PIPER_VOICE_PATH to the .onnx file).
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
dir=voices
base=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium
name=en_US-lessac-medium
mkdir -p "$dir"
for file in "$name.onnx" "$name.onnx.json"; do
  [ -s "$dir/$file" ] || curl -fL --retry 3 -o "$dir/$file" "$base/$file"
done
ls -la "$dir"
