from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from data_provider import CommentaryEntry, Match


AGNES_API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
AGNES_MODEL = "agnes-2.0-flash"


class CommentaryService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_path = cache_dir / "ai_commentary.json"
        self.lock = threading.Lock()
        self.request_lock = threading.Lock()
        self.last_request_at = 0.0
        self.cache = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def event_texts(self, match_id: str, mode: str = "narration") -> dict[int, str]:
        rows = (self.cache.get(mode) or {}).get(match_id) or {}
        result: dict[int, str] = {}
        for key, value in rows.items():
            try:
                result[int(key)] = self._strip_minute_prefix(str(value))
            except (TypeError, ValueError):
                continue
        return result

    def summary(self, match_id: str, signature: str) -> str:
        item = ((self.cache.get("summaries") or {}).get(match_id) or {})
        if item.get("signature") == signature:
            return self._trim_summary(str(item.get("text") or ""))
        return ""

    def narrate_events(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
    ) -> dict[int, str]:
        return self._transform_events(match, entries, api_key, mode="narration")

    def translate_events(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
    ) -> dict[int, str]:
        return self._transform_events(match, entries, api_key, mode="translations")

    def _transform_events(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
        mode: str,
    ) -> dict[int, str]:
        cached = self.event_texts(match.id, mode=mode)
        missing_all = [entry for entry in entries if entry.sequence not in cached]
        if cached:
            latest_cached = max(cached)
            new_entries = [entry for entry in missing_all if entry.sequence > latest_cached]
            newest = new_entries[-6:]
            newest_sequences = {entry.sequence for entry in newest}
            oldest = [
                entry for entry in missing_all
                if entry.sequence not in newest_sequences
            ][: max(0, 20 - len(newest))]
            missing = oldest + newest
        else:
            missing = entries[-12:]
        if not missing:
            return cached
        prompt_rows = [
            {
                "sequence": entry.sequence,
                "minute": entry.minute,
                "event": entry.text,
            }
            for entry in missing[-12:]
        ]
        instruction = (
            "将每条英文事件改写成准确、简短、自然的中文实时解说。可以调整语序，但不得增加事实。"
            if mode == "narration"
            else "将每条英文事件忠实翻译成简洁中文。保留原始事实与语气，不添加评论、判断或现场描写。"
        )
        prompt = (
            f"你是足球文字直播编辑。{instruction}"
            "不得虚构现场画面、情绪、球员动作或比分。不要在正文重复分钟或时间。每条最多34个汉字。"
            "仅返回 JSON 数组，每项格式为 {\"sequence\":数字,\"text\":\"中文文本\"}。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"事件：{json.dumps(prompt_rows, ensure_ascii=False)}"
        )
        response = self._chat(prompt, api_key, max_tokens=800)
        parsed = self._parse_event_response(response)
        if not parsed:
            raise RuntimeError("Agnes 未返回可识别的事件文本")
        with self.lock:
            events = self.cache.setdefault(mode, {}).setdefault(match.id, {})
            for sequence, text in parsed.items():
                events[str(sequence)] = text
            self._save_cache()
        return self.event_texts(match.id, mode=mode)

    def needs_event_backfill(
        self,
        match_id: str,
        entries: list[CommentaryEntry],
        mode: str,
    ) -> bool:
        cached = self.event_texts(match_id, mode=mode)
        return any(entry.sequence not in cached for entry in entries)

    def summarize_match(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
    ) -> str:
        signature = self.summary_signature(match, entries)
        cached = self.summary(match.id, signature)
        if cached:
            return cached
        facts = [
            f"{entry.minute} {entry.text}".strip()
            for entry in entries
            if self._important_event(entry.text)
        ][-40:]
        stats = {
            match.home.name: match.statistics.get(match.home.id) or {},
            match.away.name: match.statistics.get(match.away.id) or {},
        }
        prompt = (
            "你是严谨的足球赛后编辑。请仅依据给定比分、关键事件和统计，写一段120至220字中文比赛总结。"
            "先交代赛果，再概括关键转折和数据走势。没有提供的事实不要猜测，不要使用Markdown。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"关键事件：{json.dumps(facts, ensure_ascii=False)}\n"
            f"统计：{json.dumps(stats, ensure_ascii=False)}"
        )
        text = self._trim_summary(self._chat(prompt, api_key, max_tokens=600).strip())
        if not text:
            raise RuntimeError("Agnes 未返回比赛总结")
        with self.lock:
            self.cache.setdefault("summaries", {})[match.id] = {
                "signature": signature,
                "text": text,
                "generated_at": int(time.time()),
            }
            self._save_cache()
        return text

    def test(self, api_key: str) -> str:
        text = self._chat("只回复：连接成功", api_key, max_tokens=20)
        return text.strip()

    def summary_signature(self, match: Match, entries: list[CommentaryEntry]) -> str:
        latest = entries[-1].sequence if entries else -1
        return f"{match.home.score}-{match.away.score}:{latest}:{len(entries)}"

    def _chat(self, prompt: str, api_key: str, max_tokens: int) -> str:
        key = (api_key or os.environ.get("AGNES_API_KEY") or "").strip()
        if not key:
            raise RuntimeError("未设置 Agnes API Key")
        payload = {
            "model": AGNES_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你只处理用户提供的足球比赛事实，禁止补充未经提供的信息。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
            "max_tokens": max_tokens,
        }
        with self.request_lock:
            wait_seconds = max(0.0, 3.2 - (time.monotonic() - self.last_request_at))
            if wait_seconds:
                time.sleep(wait_seconds)
            request = urllib.request.Request(
                AGNES_API_URL,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": "WorldCupFloat/1.2",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = json.loads(response.read().decode("utf-8-sig"))
            finally:
                self.last_request_at = time.monotonic()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(str(data.get("error") or "Agnes 返回为空"))
        message = choices[0].get("message") or {}
        return str(message.get("content") or "")

    def _parse_event_response(self, text: str) -> dict[int, str]:
        candidate = text.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            candidate = fenced.group(1).strip()
        start = candidate.find("[")
        end = candidate.rfind("]")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
        try:
            rows = json.loads(candidate)
        except json.JSONDecodeError:
            return {}
        result: dict[int, str] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            try:
                sequence = int(row.get("sequence"))
            except (TypeError, ValueError):
                continue
            value = str(row.get("text") or "").strip()
            if value:
                result[sequence] = self._strip_minute_prefix(value)
        return result

    def _strip_minute_prefix(self, text: str) -> str:
        return re.sub(
            r"^\s*第?\s*\d+(?:\+\d+)?\s*分钟[，,:：、\s-]*",
            "",
            text,
        ).strip()

    def _trim_summary(self, text: str, limit: int = 220) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        candidate = text[:limit]
        last_stop = max(candidate.rfind("。"), candidate.rfind("！"), candidate.rfind("？"))
        if last_stop >= 100:
            return candidate[: last_stop + 1]
        return candidate.rstrip("，,；; ") + "。"

    def _important_event(self, text: str) -> bool:
        lowered = text.lower()
        words = (
            "goal",
            "penalty",
            "red card",
            "yellow card",
            "substitution",
            "var",
            "shot",
            "save",
            "post",
            "bar",
            "half begins",
            "half ends",
            "match ends",
        )
        return any(word in lowered for word in words)
