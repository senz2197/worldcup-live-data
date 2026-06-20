from __future__ import annotations

import queue
import threading
from dataclasses import dataclass


try:
    import pyttsx3
except Exception:
    pyttsx3 = None


@dataclass(frozen=True)
class SpeechVoice:
    id: str
    name: str


class SpeechService:
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, str, int] | None] = queue.Queue(maxsize=6)
        self._thread: threading.Thread | None = None

    def voices(self) -> list[SpeechVoice]:
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
