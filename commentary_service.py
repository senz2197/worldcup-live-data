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

    def event_texts(self, match_id: str, mode: str = "narration_v2") -> dict[int, str]:
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
        return self._transform_events(match, entries, api_key, mode="narration_v2")

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
        parsed = self._request_event_batch(match, missing[:20], api_key, mode)
        if not parsed:
            raise RuntimeError("Agnes 未返回可识别的事件文本")
        self._store_event_texts(match.id, mode, parsed)
        return self.event_texts(match.id, mode=mode)

    def translate_complete_timeline(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
    ) -> dict[int, str]:
        mode = "detail_narration_v2"
        cached = self.event_texts(match.id, mode=mode)
        missing = [entry for entry in entries if entry.sequence not in cached]
        attempts = 0
        while missing and attempts < 3:
            attempts += 1
            for start in range(0, len(missing), 24):
                batch = missing[start : start + 24]
                parsed = self._request_event_batch(match, batch, api_key, mode)
                if parsed:
                    self._store_event_texts(match.id, mode, parsed)
            cached = self.event_texts(match.id, mode=mode)
            missing = [entry for entry in entries if entry.sequence not in cached]
        if missing:
            raise RuntimeError(f"仍有 {len(missing)} 条事件未能完成中文化")
        return {entry.sequence: cached[entry.sequence] for entry in entries}

    def _request_event_batch(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
        mode: str,
    ) -> dict[int, str]:
        prompt_rows = [
            {
                "sequence": entry.sequence,
                "minute": entry.minute,
                "event": entry.text,
            }
            for entry in entries
        ]
        if mode.startswith("narration"):
            instruction = (
                "将每条英文事件改写成短促、准确、有临场感的中文足球实时解说。"
                "进球、关键扑救、击中门框、VAR判定、点球和红牌可以明显增强语气与节奏；"
                "射门、角球、危险任意球可保持适度紧张感；普通犯规、界外球、换人和伤停必须克制。"
                "使用中国大陆常见的专业足球解说术语，句式自然有力，不能机械直译。"
            )
        elif mode.startswith("detail_narration"):
            instruction = (
                "将每条英文事件改写成准确、连贯、富有现场感的中文足球文字直播。"
                "完整保留每条信息；进球、关键扑救、门框、VAR、点球和红牌可采用更有张力的"
                "专业表达，射门和定位球适度渲染，普通犯规、界外球、换人及伤停保持克制。"
                "使用中国大陆常见的足球术语，让读者感到比赛节奏，但不能机械直译或夸大事件。"
            )
        else:
            instruction = (
                "将每条英文事件忠实翻译成简洁中文。保留原始事实与语气，"
                "不添加评论、判断或现场描写。"
            )
        prompt = (
            f"你是专业足球文字直播编辑。{instruction}"
            "可以润色语言和节奏，但不得虚构观众反应、现场画面、球员心理、战术意图、"
            "比赛重要性、动作细节或任何原文没有的事实。不得改变事件结果、主体、地点或比分。"
            "不要在正文重复分钟或时间。单条尽量控制在42个汉字以内，确有必要时可稍长。"
            "仅返回 JSON 数组，每项格式为 {\"sequence\":数字,\"text\":\"中文文本\"}。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"事件：{json.dumps(prompt_rows, ensure_ascii=False)}"
        )
        response = self._chat(prompt, api_key, max_tokens=max(900, len(entries) * 75))
        parsed = self._parse_event_response(response)
        return parsed

    def _store_event_texts(self, match_id: str, mode: str, rows: dict[int, str]) -> None:
        with self.lock:
            events = self.cache.setdefault(mode, {}).setdefault(match_id, {})
            for sequence, text in rows.items():
                events[str(sequence)] = text
            self._save_cache()

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
        full_timeline = [
            f"{entry.minute} {entry.text}".strip()
            for entry in entries
        ]
        highlights = [
            row for row, entry in zip(full_timeline, entries)
            if self._important_event(entry.text)
        ]
        trusted_stats = {
            "totalShots": "射门",
            "shotsOnTarget": "射正",
            "possessionPct": "控球率",
            "wonCorners": "角球",
            "foulsCommitted": "犯规",
            "offsides": "越位",
            "saves": "扑救",
        }
        stats: dict[str, dict[str, str]] = {}
        for team in (match.home, match.away):
            source = match.statistics.get(team.id) or {}
            stats[team.name] = {
                label: str(source[key])
                for key, label in trusted_stats.items()
                if source.get(key) not in (None, "")
            }
            yellow = sum(
                1 for event in match.events
                if event.get("team_id") == team.id and event.get("kind") == "yellow"
            )
            red = sum(
                1 for event in match.events
                if event.get("team_id") == team.id and event.get("kind") == "red"
            )
            if yellow or red:
                stats[team.name]["牌"] = f"黄牌{yellow} 红牌{red}"
        prompt = (
            "你是严谨且有洞察力的足球赛后编辑。请仅依据给定的完整比赛时间线、比分和统计，"
            "写一篇350至550字的中文深度复盘。使用3至4个短段落，不使用标题或Markdown。"
            "内容应包括：比赛主线与赛果；决定比赛的关键时刻、进球、VAR、牌或换人影响；"
            "由统计和事件能够支持的攻防走势；以及一两个真正值得一提的细节，例如连续机会、"
            "门将扑救、门框、伤停、密集犯规或有意思的事件链。所谓有趣点必须直接来自所给资料，"
            "不得编造现场气氛、战术意图、历史纪录、人物背景或未提供的数据。避免逐分钟流水账，"
            "要解释事件之间如何构成比赛走势。不得把控球、射门等数据自动解释成阵型、战术部署或"
            "教练意图；不得声称任何未在时间线或可信统计中明确出现的助攻、纪录或人物表现。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"关键事件：{json.dumps(highlights, ensure_ascii=False)}\n"
            f"完整时间线：{json.dumps(full_timeline, ensure_ascii=False)}\n"
            f"统计：{json.dumps(stats, ensure_ascii=False)}"
        )
        draft = self._trim_summary(self._chat(prompt, api_key, max_tokens=1500).strip(), limit=650)
        if not draft:
            raise RuntimeError("Agnes 未返回比赛总结")
        audit_prompt = (
            "你是足球稿件事实审校员。请逐句核对草稿与所给完整时间线、比分和可信统计，"
            "重写为350至550字的最终中文复盘。只保留资料能够直接证明的内容。"
            "必须删除或改写任何关于阵型、战术部署、教练意图、心理、气氛、历史纪录以及未经明确"
            "提供的因果推断。尤其不要使用“防守反击”“迫使压上”“掌控中场”“战术奏效”"
            "“预示比赛走势”等推断性表述。可以指出连续扑救、同一分钟连续机会、门框、VAR、"
            "伤停、牌、换人和射门差异等有趣细节，但必须能在资料中逐项找到。"
            "保留3至4个短段落，不使用标题或Markdown。不要逐条复述时间线；全文最多明确写出"
            "8个分钟节点，只选择真正改变比分、形成连续威胁或构成比赛看点的时刻。其余事件按"
            "上半场、转折阶段和收官阶段归纳，重点解释可观察到的比赛走势与看点。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"可信统计：{json.dumps(stats, ensure_ascii=False)}\n"
            f"完整时间线：{json.dumps(full_timeline, ensure_ascii=False)}\n"
            f"待审草稿：{draft}"
        )
        text = self._trim_summary(
            self._chat(audit_prompt, api_key, max_tokens=1500).strip(),
            limit=560,
        )
        if not text:
            raise RuntimeError("Agnes 未返回事实审校后的比赛总结")
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
        return f"deep-v5:{match.home.score}-{match.away.score}:{latest}:{len(entries)}"

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
