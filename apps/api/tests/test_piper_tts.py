"""Piper text-to-speech (D47), tested with a fake voice so CI needs no model file or the `piper` extra."""

import asyncio
import wave

import pytest

from app.speech.piper_tts import PiperTTS
from app.speech.tts import TTSError


class FakeVoice:
    def __init__(self, frames: int = 2205):
        self.frames, self.active, self.peak = frames, 0, 0

    def synthesize_wav(self, text, wav: wave.Wave_write):
        self.active += 1
        self.peak = max(self.peak, self.active)
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\x01\x00" * self.frames)
        self.active -= 1


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "voice.onnx"
    path.write_bytes(b"model")
    return str(path)


async def test_returns_a_real_wav_the_browser_can_decode(model):
    audio = await PiperTTS(model, loader=lambda _: FakeVoice()).synthesize("Hello there.")
    assert audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"


async def test_the_voice_is_loaded_once(model):
    loads = []
    tts = PiperTTS(model, loader=lambda p: loads.append(p) or FakeVoice())
    await tts.synthesize("one")
    await tts.synthesize("two")
    assert len(loads) == 1


async def test_a_missing_voice_file_is_a_clear_error_and_not_healthy(tmp_path):
    tts = PiperTTS(str(tmp_path / "nope.onnx"), loader=lambda _: FakeVoice())
    with pytest.raises(TTSError, match="get-piper-voice"):
        await tts.synthesize("hi")
    assert await tts.healthy() is False


async def test_engine_failures_become_tts_errors_so_the_browser_voice_takes_over(model):
    class Broken:
        def synthesize_wav(self, *_):
            raise RuntimeError("onnx exploded")

    with pytest.raises(TTSError, match="onnx exploded"):
        await PiperTTS(model, loader=lambda _: Broken()).synthesize("hi")


async def test_silence_is_an_error_not_an_empty_clip(model):
    with pytest.raises(TTSError, match="no audio"):
        await PiperTTS(model, loader=lambda _: FakeVoice(frames=0)).synthesize("hi")


async def test_sentences_are_synthesized_one_at_a_time(model):
    voice = FakeVoice()
    tts = PiperTTS(model, loader=lambda _: voice)
    await asyncio.gather(*(tts.synthesize(f"sentence {i}") for i in range(5)))
    assert voice.peak == 1  # on one CPU, parallel synthesis would only slow every sentence


async def test_healthy_when_the_voice_loads(model):
    assert await PiperTTS(model, loader=lambda _: FakeVoice()).healthy() is True
