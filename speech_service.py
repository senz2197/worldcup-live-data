from __future__ import annotations

import queue
import threading
import asyncio
import ctypes
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import edge_tts
except Exception:
    edge_tts = None

try:
    from winrt.windows.media.playback import MediaPlayer
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
except Exception:
    MediaPlayer = None
    SpeechSynthesizer = None


EDGE_VOICES = (
    ("zh-CN-YunjianNeural", "云健 · 体育激情（在线神经语音）"),
    ("zh-CN-XiaoxiaoNeural", "晓晓 · 温暖自然（在线神经语音）"),
    ("zh-CN-YunyangNeural", "云扬 · 专业新闻（在线神经语音）"),
    ("zh-CN-YunxiNeural", "云希 · 阳光活力（在线神经语音）"),
    ("zh-CN-XiaoyiNeural", "晓伊 · 活泼明快（在线神经语音）"),
)
DEFAULT_EDGE_VOICE_ID = f"edge:{EDGE_VOICES[0][0]}"


@dataclass(frozen=True)
class SpeechVoice:
    id: str
    name: str


class SpeechService:
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, str, int] | None] = queue.Queue(maxsize=6)
        self._thread: threading.Thread | None = None

    def voices(self) -> list[SpeechVoice]:
        voices = [
            SpeechVoice(f"edge:{voice_id}", name)
            for voice_id, name in EDGE_VOICES
        ] if edge_tts is not None else []
        if SpeechSynthesizer is not None:
            try:
                voices.extend(
                    SpeechVoice(str(voice.id), f"{voice.display_name} · 本地自然语音")
                    for voice in SpeechSynthesizer.all_voices
                    if str(voice.language).lower().startswith("zh")
                )
                return voices
            except Exception:
                pass
        if pyttsx3 is None:
            return voices
        engine = None
        try:
            engine = pyttsx3.init()
            voices.extend(
                SpeechVoice(str(voice.id), str(voice.name))
                for voice in engine.getProperty("voices")
            )
            return voices
        except Exception:
            return voices
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

    def speak(self, text: str, voice_id: str = "", rate: int = 185) -> None:
        text = " ".join(str(text or "").split())
        if not text or (
            edge_tts is None
            and SpeechSynthesizer is None
            and pyttsx3 is None
        ):
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
        while True:
            try:
                item = self._queue.get(timeout=15)
            except queue.Empty:
                break
            if item is None:
                break
            text, voice_id, rate = item
            if voice_id.startswith("edge:") and edge_tts is not None:
                try:
                    asyncio.run(self._speak_edge(text, voice_id, rate))
                    continue
                except Exception:
                    pass
            if SpeechSynthesizer is not None:
                local_voice_id = "" if voice_id.startswith("edge:") else voice_id
                try:
                    asyncio.run(self._speak_onecore(text, local_voice_id, rate))
                    continue
                except Exception:
                    pass
            if pyttsx3 is not None:
                self._speak_sapi(
                    text,
                    "" if voice_id.startswith("edge:") else voice_id,
                    rate,
                )

    async def _speak_edge(self, text: str, voice_id: str, rate: int) -> None:
        voice = voice_id.removeprefix("edge:") or EDGE_VOICES[0][0]
        rate_percent = max(-35, min(40, round((rate / 185 - 1) * 100)))
        rate_value = f"{rate_percent:+d}%"
        handle = tempfile.NamedTemporaryFile(
            prefix="worldcup_tts_",
            suffix=".mp3",
            delete=False,
        )
        audio_path = Path(handle.name)
        handle.close()
        try:
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=rate_value,
                connect_timeout=6,
                receive_timeout=20,
            )
            await communicate.save(str(audio_path))
            self._play_mp3(audio_path)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _play_mp3(audio_path: Path) -> None:
        alias = f"worldcup_{uuid.uuid4().hex}"
        winmm = ctypes.windll.winmm

        def command(value: str) -> None:
            result = ctypes.create_unicode_buffer(256)
            code = winmm.mciSendStringW(value, result, len(result), 0)
            if code:
                message = ctypes.create_unicode_buffer(256)
                winmm.mciGetErrorStringW(code, message, len(message))
                raise RuntimeError(message.value or f"MCI error {code}")

        try:
            command(f'open "{audio_path}" type mpegvideo alias {alias}')
            command(f"play {alias} wait")
        finally:
            try:
                command(f"close {alias}")
            except Exception:
                pass

    @staticmethod
    def _speak_sapi(text: str, voice_id: str, rate: int) -> None:
        engine = None
        try:
            engine = pyttsx3.init()
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
