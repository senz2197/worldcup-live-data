from __future__ import annotations

import queue
import threading
import asyncio
from dataclasses import dataclass


try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    from winrt.windows.media.playback import MediaPlayer
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
except Exception:
    MediaPlayer = None
    SpeechSynthesizer = None


@dataclass(frozen=True)
class SpeechVoice:
    id: str
    name: str


class SpeechService:
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, str, int] | None] = queue.Queue(maxsize=6)
        self._thread: threading.Thread | None = None

    def voices(self) -> list[SpeechVoice]:
        if SpeechSynthesizer is not None:
            try:
                return [
                    SpeechVoice(str(voice.id), f"{voice.display_name} · 本地自然语音")
                    for voice in SpeechSynthesizer.all_voices
                    if str(voice.language).lower().startswith("zh")
                ]
            except Exception:
                pass
        if pyttsx3 is None:
            return []
        engine = None
        try:
            engine = pyttsx3.init()
            return [
                SpeechVoice(str(voice.id), str(voice.name))
                for voice in engine.getProperty("voices")
            ]
        except Exception:
            return []
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

    def speak(self, text: str, voice_id: str = "", rate: int = 185) -> None:
        text = " ".join(str(text or "").split())
        if not text or pyttsx3 is None:
            return
        while self._queue.full():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queue.put_nowait((text, voice_id, max(120, min(260, int(rate)))))
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _worker(self) -> None:
        if SpeechSynthesizer is not None:
            try:
                self._worker_onecore()
                return
            except Exception:
                pass
        engine = None
        try:
            engine = pyttsx3.init()
            while True:
                try:
                    item = self._queue.get(timeout=15)
                except queue.Empty:
                    break
                if item is None:
                    break
                text, voice_id, rate = item
                engine.setProperty("rate", rate)
                if voice_id:
                    engine.setProperty("voice", voice_id)
                engine.say(text)
                engine.runAndWait()
        except Exception:
            pass
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

    def _worker_onecore(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=15)
            except queue.Empty:
                break
            if item is None:
                break
            text, voice_id, rate = item
            asyncio.run(self._speak_onecore(text, voice_id, rate))

    async def _speak_onecore(self, text: str, voice_id: str, rate: int) -> None:
        synthesizer = SpeechSynthesizer()
        voices = list(SpeechSynthesizer.all_voices)
        selected = next((voice for voice in voices if str(voice.id) == voice_id), None)
        if selected is None:
            selected = next(
                (voice for voice in voices if str(voice.language).lower().startswith("zh")),
                voices[0] if voices else None,
            )
        if selected is not None:
            synthesizer.voice = selected
        rate_value = max(0.65, min(1.35, rate / 185))
        ssml = (
            "<speak version='1.0' xml:lang='zh-CN'>"
            f"<prosody rate='{rate_value:.2f}'>{self._escape_ssml(text)}</prosody>"
            "</speak>"
        )
        stream = await synthesizer.synthesize_ssml_to_stream_async(ssml)
        player = MediaPlayer()
        finished = threading.Event()
        player.add_media_ended(lambda *_args: finished.set())
        player.add_media_failed(lambda *_args: finished.set())
        player.set_stream_source(stream)
        player.play()
        finished.wait(timeout=max(8, min(90, len(text) // 3)))
        player.close()

    @staticmethod
    def _escape_ssml(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
