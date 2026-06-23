from __future__ import annotations

import json
import hashlib
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_provider import CommentaryEntry, Match


AI_MODEL_PRESETS = {
    "agnes": {
        "label": "Agnes · agnes-2.0-flash",
        "api_url": "https://apihub.agnes-ai.com/v1/chat/completions",
        "model": "agnes-2.0-flash",
        "extra": {},
    },
    "glm": {
        "label": "智谱 GLM · glm-4.7-flash",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4.7-flash",
        "extra": {"thinking": {"type": "disabled"}},
    },
}
DEFAULT_AI_MODEL_PRESET = "agnes"
AI_CACHE_RETENTION_SECONDS = 7 * 24 * 60 * 60
AI_CACHE_META_KEY = "_match_cached_at"
AI_EVENT_SIGNATURES_KEY = "_event_source_signatures"


@dataclass(frozen=True)
class AIRequestCredential:
    api_key: str
    preset_id: str = DEFAULT_AI_MODEL_PRESET


class CommentaryService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_path = cache_dir / "ai_commentary.json"
        self.lock = threading.Lock()
        self.request_lock = threading.Lock()
        self.last_request_at = 0.0
        self.cache_generation = 0
        self.model_preset_id = DEFAULT_AI_MODEL_PRESET
        self.cache = self._load_cache()
        self._prepare_cache_metadata()
        self.prune_expired_cache()

    def configure_model(self, preset_id: str) -> str:
        self.model_preset_id = (
            preset_id
            if preset_id in AI_MODEL_PRESETS
            else DEFAULT_AI_MODEL_PRESET
        )
        return self.model_preset_id

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

    def _prepare_cache_metadata(self) -> None:
        metadata = self.cache.setdefault(AI_CACHE_META_KEY, {})
        if not isinstance(metadata, dict):
            metadata = {}
            self.cache[AI_CACHE_META_KEY] = metadata
        signatures = self.cache.setdefault(
            AI_EVENT_SIGNATURES_KEY,
            {},
        )
        if not isinstance(signatures, dict):
            self.cache[AI_EVENT_SIGNATURES_KEY] = {}
        now = int(time.time())
        changed = False
        for section, matches in self.cache.items():
            if (
                section in {AI_CACHE_META_KEY, AI_EVENT_SIGNATURES_KEY}
                or not isinstance(matches, dict)
            ):
                continue
            for match_id in matches:
                if match_id not in metadata:
                    metadata[match_id] = now
                    changed = True
        if changed:
            self._save_cache()

    def prune_expired_cache(self, retention_seconds: int = AI_CACHE_RETENTION_SECONDS) -> int:
        cutoff = time.time() - max(60, retention_seconds)
        removed: set[str] = set()
        with self.lock:
            metadata = self.cache.setdefault(AI_CACHE_META_KEY, {})
            expired = {
                str(match_id)
                for match_id, cached_at in list(metadata.items())
                if self._timestamp(cached_at) < cutoff
            }
            for section, matches in self.cache.items():
                if (
                    section in {AI_CACHE_META_KEY, AI_EVENT_SIGNATURES_KEY}
                    or not isinstance(matches, dict)
                ):
                    continue
                for match_id in expired:
                    if match_id in matches:
                        matches.pop(match_id, None)
                        removed.add(match_id)
            for match_id in expired:
                metadata.pop(match_id, None)
            signature_modes = self.cache.get(
                AI_EVENT_SIGNATURES_KEY,
                {},
            )
            if isinstance(signature_modes, dict):
                for matches in signature_modes.values():
                    if not isinstance(matches, dict):
                        continue
                    for match_id in expired:
                        matches.pop(match_id, None)
            if expired:
                self._save_cache()
        return len(removed)

    def clear_cache(self) -> None:
        with self.lock:
            self.cache_generation += 1
            self.cache = {
                AI_CACHE_META_KEY: {},
                AI_EVENT_SIGNATURES_KEY: {},
            }
            self._save_cache()

    def cache_info(self) -> dict[str, int]:
        metadata = self.cache.get(AI_CACHE_META_KEY) or {}
        try:
            size = self.cache_path.stat().st_size
        except OSError:
            size = 0
        return {
            "matches": len(metadata) if isinstance(metadata, dict) else 0,
            "bytes": size,
        }

    def has_complete_timeline(
        self,
        match_id: str,
        entries: list[CommentaryEntry],
    ) -> bool:
        cached = self.event_texts(
            match_id,
            mode="detail_narration_v4",
            entries=entries,
        )
        return bool(entries) and all(entry.sequence in cached for entry in entries)

    @staticmethod
    def _timestamp(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _mark_cached(self, match_id: str) -> None:
        self.cache.setdefault(AI_CACHE_META_KEY, {})[match_id] = int(time.time())

    @staticmethod
    def _event_signature(entry: CommentaryEntry) -> str:
        source = "\n".join(
            (
                str(entry.minute or "").strip(),
                " ".join(str(entry.text or "").split()),
            )
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def event_texts(
        self,
        match_id: str,
        mode: str = "narration_v3",
        entries: list[CommentaryEntry] | None = None,
    ) -> dict[int, str]:
        rows = (self.cache.get(mode) or {}).get(match_id) or {}
        signatures = (
            (
                (self.cache.get(AI_EVENT_SIGNATURES_KEY) or {})
                .get(mode, {})
            )
            .get(match_id, {})
        )
        expected = (
            {
                entry.sequence: self._event_signature(entry)
                for entry in entries
            }
            if entries is not None
            else None
        )
        result: dict[int, str] = {}
        for key, value in rows.items():
            try:
                sequence = int(key)
            except (TypeError, ValueError):
                continue
            if expected is not None:
                if sequence not in expected:
                    continue
                if signatures.get(str(sequence)) != expected[sequence]:
                    continue
            result[sequence] = self._strip_minute_prefix(str(value))
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
        return self._transform_events(match, entries, api_key, mode="narration_v3")

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
        generation = self.cache_generation
        cached = self.event_texts(match.id, mode=mode, entries=entries)
        missing_all = [entry for entry in entries if entry.sequence not in cached]
        if match.is_live:
            missing = missing_all[-3:]
        elif cached:
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
        parsed = self._request_event_batch_with_retry(
            match,
            missing[:20],
            api_key,
            mode,
        )
        if not parsed:
            raise RuntimeError("AI 服务未返回可识别的事件文本")
        self._store_event_texts(
            match.id,
            mode,
            parsed,
            generation,
            missing[:20],
        )
        return self.event_texts(match.id, mode=mode, entries=entries)

    def translate_complete_timeline(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
    ) -> dict[int, str]:
        generation = self.cache_generation
        mode = "detail_narration_v4"
        cached = self.event_texts(match.id, mode=mode, entries=entries)
        missing = [entry for entry in entries if entry.sequence not in cached]
        if missing:
            try:
                parsed = self._request_complete_timeline(
                    match,
                    entries,
                    api_key,
                )
            except Exception:
                parsed = {}
            if parsed:
                valid_sequences = {entry.sequence for entry in entries}
                if set(parsed) != valid_sequences:
                    parsed = {}
                else:
                    parsed = (
                        self._validate_event_batch(entries, parsed)
                        or {}
                    )
                self._store_event_texts(
                    match.id,
                    mode,
                    parsed,
                    generation,
                    entries,
                )
                cached = self.event_texts(
                    match.id,
                    mode=mode,
                    entries=entries,
                )
                missing = [
                    entry for entry in entries
                    if entry.sequence not in cached
                ]
        attempts = 0
        while missing and attempts < 3:
            attempts += 1
            for start in range(0, len(missing), 18):
                batch = missing[start : start + 18]
                parsed = self._request_event_batch_with_retry(
                    match,
                    batch,
                    api_key,
                    mode,
                )
                if parsed:
                    self._store_event_texts(
                        match.id,
                        mode,
                        parsed,
                        generation,
                        batch,
                    )
            cached = self.event_texts(
                match.id,
                mode=mode,
                entries=entries,
            )
            missing = [entry for entry in entries if entry.sequence not in cached]
        if missing:
            raise RuntimeError(f"仍有 {len(missing)} 条事件未能完成中文化")
        return {entry.sequence: cached[entry.sequence] for entry in entries}

    def _request_complete_timeline(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
    ) -> dict[int, str]:
        source_lines = []
        for entry in entries:
            event = " ".join(str(entry.text or "").split()).replace("|", "/")
            minute = str(entry.minute or "").replace("|", "/")
            source_lines.append(f"{entry.sequence}|{minute}|{event}")
        prompt = (
            "你是经验丰富的中文足球现场解说员兼文字直播总编辑。下面提供同一场比赛的完整英文"
            "时间线，请通读整场后逐条写成准确、连贯、富有临场节奏的中文解说。每条都要优先"
            "写清谁在什么区域完成了什么动作以及结果，使用鲜活有力的动词和长短句变化，避免"
            "“某某获得某某”“某某进行射门”一类翻译腔。进球可以用“球进了！”引出并点明"
            "进球队员与方式；关键扑救、门框、VAR、点球和红牌要有明显张力；连续攻势要体现"
            "节奏推进；普通犯规、界外球、换人和伤停保持专业克制。必须保留全部事件及原编号，"
            "统一球员译名和足球术语，并结合前后文消除代词歧义与机械重复。"
            "只能使用原事件明确给出的动作、部位、区域、方向和结果。原文未写传中或助攻，就"
            "不能补出传中与助攻；只写射门被扑，就不能改成托出横梁、飞出底线或击中门框；"
            "未给球员位置就不能称其为前锋、中场或后卫。不得虚构观众反应、球员心理、战术"
            "意图、动作细节或原文没有的事实。方向必须严格等价：top centre 只能写球门上方"
            "中路，bottom right 只能写右下角，绝不能替换成死角、近角或其他位置。原文未写"
            "旋转、飞身、跃起、传中、速度或出界方式时禁止添加这些词。情绪只能通过“球进了！”"
            "“好险！”等短促开场、标点和句式节奏表达，不能依靠虚构动作来制造画面。输出前"
            "在内部核对每个区域、方向和动作修饰词，任何无法从原文直接找到依据的词都要删除。"
            "可以表达事件本身自然产生的紧张、遗憾、精彩或振奋感，但不能捏造现场信息。"
            "中文正文绝对不要出现分钟、时间或其中文数字写法。普通事件尽量在35至55个汉字，"
            "重大事件可以稍长。"
            "严格每行输出一条，格式只能是“原编号|中文解说”；不得输出标题、说明、Markdown"
            "或遗漏编号。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            "完整时间线：\n"
            + "\n".join(source_lines)
        )
        response = self._chat(
            prompt,
            api_key,
            max_tokens=max(5000, len(entries) * 62),
            timeout_seconds=180,
        )
        return self._parse_line_event_response(response)

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
            "把每条事件写成可以直接由现场解说员播出的中文口播。先准确识别事件强度，再用"
            "有画面感但不虚构的专业表达：明确主体、动作区域、处理方式和结果，多用“突然起脚”"
            "“迎球攻门”“门将飞身化解”“皮球擦柱而出”等与原始事实相符的动态句式，避免"
            "逐词翻译和“获得任意球”“进行射门”等生硬表达。进球可用“球进了！”开场并点明"
            "进球队员；关键扑救、门框、VAR、点球和红牌应明显增强张力；射门、角球、危险"
            "任意球保持适度紧张；普通犯规、界外球、换人和伤停保持简洁克制。句式要有变化，"
            "让连续几条解说听起来像真实比赛进程，而不是数据列表。只能润色原文明确给出的"
            "事实：原文未写传中、助攻、跑位、球员位置、门将动作或皮球出界方式时，绝不能"
            "自行补充；“射门被扑”不能擅自改写成“托出横梁”或“扑出底线”。"
            "区域与方向是锁定字段，必须严格等价翻译，不能把上方中路写成死角或右上角。"
            "原文未出现旋转、飞身、跃起、精准传中、速度或球员位置时禁止添加。感染力只能"
            "来自短促开场、标点与句式节奏；输出前在内部进行事实核对并删除所有无来源修饰。"
            "若事件写成“Goal! A 2, B 1”，只能表述为“A将比分改写为2比1”，不能误写成"
            "两球领先、扳平或打破僵局。原文未明确射门方或扑救方时，不得擅自指定球队。"
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
            f"你是专业、敏锐且富有感染力的中文足球现场解说员。{instruction}"
            "可以润色语言和节奏，但不得虚构观众反应、现场画面、球员心理、战术意图、"
            "比赛重要性、动作细节或任何原文没有的事实。不得改变事件结果、主体、地点或比分。"
            "可以表达事件本身带来的精彩、紧张、遗憾或振奋感，但不得凭空描写看台与气氛。"
            "正文绝对不能出现分钟、时间及其中文数字写法。普通事件控制在30至50个汉字，"
            "重大事件可稍长。参考写法：英文若是“shot from outside the box is saved in the "
            "top centre”，应写“禁区外突然起脚！射门直奔球门上方中路，门将将球扑出”，"
            "不能写旋转、死角或飞身；若是“Goal! A 2, B 1. Header from the centre of the "
            "box to the bottom right corner”，应写“球进了！A在禁区中央完成头球攻门，"
            "皮球钻入右下角，比分改写为2比1！”。"
            "仅返回 JSON 数组，每项格式为 {\"sequence\":数字,\"text\":\"中文文本\"}。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"事件：{json.dumps(prompt_rows, ensure_ascii=False)}"
        )
        response = self._chat(
            prompt,
            api_key,
            max_tokens=max(1100, len(entries) * 95),
            temperature=0.22 if mode.startswith("narration") else 0.25,
        )
        parsed = self._parse_event_response(response)
        return parsed

    def _request_event_batch_with_retry(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
        mode: str,
    ) -> dict[int, str]:
        last_error: Exception | None = None
        expected_sequences = {entry.sequence for entry in entries}
        for attempt in range(3):
            try:
                parsed = self._request_event_batch(match, entries, api_key, mode)
                if set(parsed) != expected_sequences:
                    last_error = RuntimeError(
                        "AI 返回的事件编号与请求批次不一致"
                    )
                else:
                    validated = self._validate_event_batch(entries, parsed)
                    if validated is not None:
                        return validated
                    last_error = RuntimeError(
                        "AI 返回内容与原始足球事件不一致"
                    )
            except urllib.error.HTTPError as exc:
                if exc.code in {400, 401, 403, 404}:
                    raise
                last_error = exc
            except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError("AI 中文润色请求超时，请稍后重试") from last_error

    def _validate_event_batch(
        self,
        entries: list[CommentaryEntry],
        rows: dict[int, str],
    ) -> dict[int, str] | None:
        result: dict[int, str] = {}
        for entry in entries:
            rendered = str(rows.get(entry.sequence) or "").strip()
            source = str(entry.text or "").strip()
            if not rendered or not self._event_semantics_match(source, rendered):
                return None
            result[entry.sequence] = self._canonical_event_text(
                source,
                rendered,
            )
        return result

    @staticmethod
    def _event_semantics_match(source: str, rendered: str) -> bool:
        source_lower = source.casefold()
        chinese = rendered.replace(" ", "")
        source_goal = source_lower.startswith("goal!")
        rendered_goal = any(
            marker in chinese
            for marker in (
                "球进了",
                "进球",
                "破门",
                "比分改写",
                "扳平",
                "打入",
                "建功",
                "洞穿",
            )
        )
        if source_goal != rendered_goal:
            return False
        checks = (
            ("yellow card", ("黄牌",)),
            ("red card", ("红牌", "罚下")),
            ("substitution", ("换人", "替补")),
            ("corner,", ("角球",)),
            ("offside", ("越位",)),
            ("var decision", ("VAR", "视频助理裁判")),
            ("attempt blocked", ("被挡", "封堵", "挡出")),
            ("attempt saved", ("扑出", "扑救", "没收")),
            ("attempt missed", ("偏出", "高出", "打偏", "未能命中")),
        )
        for source_marker, translated_markers in checks:
            if source_marker in source_lower and not any(
                marker in rendered for marker in translated_markers
            ):
                return False
        return True

    @staticmethod
    def _canonical_event_text(source: str, rendered: str) -> str:
        free_kick = re.match(
            r"^(.+?) \((.+?)\) wins a free kick in the "
            r"(defensive half|attacking half|left wing|right wing)\.$",
            source,
            flags=re.IGNORECASE,
        )
        if free_kick:
            player, team, area = free_kick.groups()
            area_text = {
                "defensive half": "防守半场",
                "attacking half": "进攻半场",
                "left wing": "左路",
                "right wing": "右路",
            }[area.casefold()]
            return f"{player}（{team}）在{area_text}赢得任意球。"
        foul = re.match(
            r"^Foul by (.+?) \((.+?)\)\.$",
            source,
            flags=re.IGNORECASE,
        )
        if foul:
            player, team = foul.groups()
            return f"{player}（{team}）出现犯规动作。"
        return rendered

    def _store_event_texts(
        self,
        match_id: str,
        mode: str,
        rows: dict[int, str],
        generation: int,
        entries: list[CommentaryEntry],
    ) -> None:
        with self.lock:
            if generation != self.cache_generation:
                return
            events = self.cache.setdefault(mode, {}).setdefault(match_id, {})
            signatures = (
                self.cache
                .setdefault(AI_EVENT_SIGNATURES_KEY, {})
                .setdefault(mode, {})
                .setdefault(match_id, {})
            )
            entry_map = {entry.sequence: entry for entry in entries}
            for sequence, text in rows.items():
                entry = entry_map.get(sequence)
                if entry is None:
                    continue
                events[str(sequence)] = text
                signatures[str(sequence)] = self._event_signature(entry)
            self._mark_cached(match_id)
            self._save_cache()

    def needs_event_backfill(
        self,
        match_id: str,
        entries: list[CommentaryEntry],
        mode: str,
    ) -> bool:
        cached = self.event_texts(
            match_id,
            mode=mode,
            entries=entries,
        )
        return any(entry.sequence not in cached for entry in entries)

    def summarize_match(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        api_key: str,
    ) -> str:
        generation = self.cache_generation
        signature = self.summary_signature(match, entries)
        cached = self.summary(match.id, signature)
        if cached:
            return cached
        rendered_timeline = self.event_texts(
            match.id,
            mode="detail_narration_v4",
            entries=entries,
        )
        full_timeline = [
            f"{self._summary_minute(entry.minute)} "
            f"{rendered_timeline.get(entry.sequence) or entry.text}".strip()
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
            "你是严谨、专业且有现场感的足球赛后主编。请仅依据给定的完整比赛时间线、比分和统计，"
            "写一篇300至450字的中文深度复盘。严格使用3个短段落，不使用标题或Markdown。"
            "第一段写比赛主线、赛果和最关键转折；第二段用统计与连续事件概括双方机会质量和"
            "比赛走势；第三段提炼一至两个最值得回看的细节与收官过程。内容应包括："
            "决定比赛的关键时刻、进球、VAR、牌或换人影响；"
            "由统计和事件能够支持的攻防走势；以及一两个真正值得一提的细节，例如连续机会、"
            "门将扑救、门框、伤停、密集犯规或有意思的事件链。所谓有趣点必须直接来自所给资料，"
            "不得编造现场气氛、战术意图、历史纪录、人物背景或未提供的数据。避免逐分钟流水账，"
            "要提炼整场节奏、连续威胁与真正的转折，避免把事件逐条压缩成流水账。"
            "语言应有专业足球报道的节奏和现场感，但所有描述必须由资料直接支持。"
            "全文最多明确写出5个时间节点；时间中的“+”表示伤停补时，绝不能写成秒数。"
            "不得把控球、射门等数据自动解释成阵型、战术部署或"
            "教练意图；不得声称任何未在时间线或可信统计中明确出现的助攻、纪录或人物表现。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"关键事件：{json.dumps(highlights, ensure_ascii=False)}\n"
            f"完整时间线：{json.dumps(full_timeline, ensure_ascii=False)}\n"
            f"统计：{json.dumps(stats, ensure_ascii=False)}"
        )
        draft = self._trim_summary(self._chat(prompt, api_key, max_tokens=1500).strip(), limit=650)
        if not draft:
            raise RuntimeError("AI 服务未返回比赛总结")
        audit_prompt = (
            "你是足球稿件事实审校员。请逐句核对草稿与所给完整时间线、比分和可信统计，"
            "重写为300至450字的最终中文复盘。只保留资料能够直接证明的内容。"
            "必须删除或改写任何关于阵型、战术部署、教练意图、心理、气氛、历史纪录以及未经明确"
            "提供的因果推断。尤其不要使用“防守反击”“迫使压上”“掌控中场”“战术奏效”"
            "“预示比赛走势”等推断性表述。可以指出连续扑救、同一分钟连续机会、门框、VAR、"
            "伤停、牌、换人和射门差异等有趣细节，但必须能在资料中逐项找到。"
            "不要逐条复述时间线。必须只返回一个 JSON 对象，不得返回Markdown或额外说明："
            "{\"overview\":\"第一段\",\"trend\":\"第二段\",\"highlight\":\"第三段\"}。"
            "overview 用100至140字写赛果、比赛主线和最关键转折，最多出现2个时间节点；"
            "trend 用100至140字结合统计与连续机会概括双方走势，最多出现1个时间节点；"
            "highlight 用100至140字写最值得回看的细节和收官，最多出现2个时间节点。"
            "输入中的“45+2分钟”表示上半场伤停补时，不得改写成秒数或“45分02秒”。\n"
            f"比赛：{match.home.name} {match.home.score or '0'}-"
            f"{match.away.score or '0'} {match.away.name}\n"
            f"可信统计：{json.dumps(stats, ensure_ascii=False)}\n"
            f"完整时间线：{json.dumps(full_timeline, ensure_ascii=False)}\n"
            f"待审草稿：{draft}"
        )
        audited = self._chat(audit_prompt, api_key, max_tokens=1200).strip()
        structured = self._parse_summary_response(audited)
        text = self._limit_summary_time_references(structured or audited, limit=5)
        text = self._trim_summary(text, limit=460)
        if not text:
            raise RuntimeError("AI 服务未返回事实审校后的比赛总结")
        with self.lock:
            if generation != self.cache_generation:
                return text
            self.cache.setdefault("summaries", {})[match.id] = {
                "signature": signature,
                "text": text,
                "generated_at": int(time.time()),
            }
            self._mark_cached(match.id)
            self._save_cache()
        return text

    def test(self, api_key: str) -> str:
        text = self._chat("只回复：连接成功", api_key, max_tokens=20)
        return text.strip()

    def localize_football_names(
        self,
        names: list[str],
        kind: str,
        api_key: str,
    ) -> dict[str, str]:
        unique = list(dict.fromkeys(
            str(name).strip()
            for name in names
            if str(name).strip()
        ))
        if not unique:
            return {}
        label = "职业足球运动员" if kind == "player" else "足球俱乐部"
        prompt = (
            f"请将下列{label}名称转换为中国大陆足球媒体最常用、严谨统一的简体中文名称。"
            "优先采用新华社、主流体育媒体及长期通行译名；无公认译名时进行自然音译。"
            "不得翻译成含义解释，不得遗漏。仅返回 JSON 对象，键必须保持原英文名称完全一致，"
            "值为中文名称。\n"
            f"名称：{json.dumps(unique, ensure_ascii=False)}"
        )
        response = self._chat(
            prompt,
            api_key,
            max_tokens=max(900, len(unique) * 35),
            timeout_seconds=90,
        )
        candidate = response.strip()
        fenced = re.search(
            r"```(?:json)?\s*(.*?)```",
            candidate,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced:
            candidate = fenced.group(1).strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
        try:
            rows = json.loads(candidate)
        except json.JSONDecodeError:
            return {}
        if not isinstance(rows, dict):
            return {}
        allowed = set(unique)
        return {
            str(source): str(translated).strip()
            for source, translated in rows.items()
            if source in allowed and str(translated).strip()
        }

    def translate_news(
        self,
        title: str,
        summary: str,
        glossary: dict[str, str],
        api_key: str,
    ) -> tuple[str, str]:
        prompt = (
            "以中文专业足球资讯编辑的方式转述新闻标题与摘要，不要逐词硬译。保持新闻事实、"
            "消息来源和不确定性语气，不要补充原文不存在的信息。人名和球队名必须严格使用"
            "给定术语表；术语表未覆盖的专有名称采用中国大陆常见译名或自然音译，不能保留"
            "整段英文标题或英文姓名。结合摘要消除足球标题省略语歧义：strike 在进球语境中"
            "通常是进球或射门，double 通常是梅开二度，不能译成罢工、打击或双杀。"
            "只返回 JSON 对象，字段为 title 和 summary。\n"
            f"术语表：{json.dumps(glossary, ensure_ascii=False)}\n"
            f"标题：{title}\n摘要：{summary}"
        )
        text = self._chat(prompt, api_key, max_tokens=700, timeout_seconds=45)
        candidate = text.strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]
        data = json.loads(candidate)
        return str(data.get("title") or title).strip(), str(data.get("summary") or summary).strip()

    def rewrite_news_article(
        self,
        title: str,
        summary: str,
        content: str,
        glossary: dict[str, str],
        api_key: str,
    ) -> tuple[str, str]:
        prompt = (
            "你是中文专业足球资讯编辑。请依据给定英文标题、摘要与完整正文，重新组织为适合"
            "中文读者阅读的完整资讯稿，不必逐句硬译，但必须保留原文中的核心事实、金额、日期、"
            "人物关系、消息来源和不确定性表述。删除网页导航、相关推荐、广告语和重复段落。"
            "语言应自然、清晰、有专业体育媒体质感；不得添加原文没有的转会结果、评价、背景、"
            "因果或预测。人名与球队名必须严格使用术语表。输出4至8个短段落，并只返回 JSON："
            "{\"title\":\"中文标题\",\"content\":\"中文全文，段落之间用两个换行\"}。\n"
            f"术语表：{json.dumps(glossary, ensure_ascii=False)}\n"
            f"标题：{title}\n摘要：{summary}\n正文：{content[:12000]}"
        )
        text = self._chat(
            prompt,
            api_key,
            max_tokens=2600,
            timeout_seconds=100,
            temperature=0.42,
        )
        candidate = text.strip()
        fenced = re.search(
            r"```(?:json)?\s*(.*?)```",
            candidate,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced:
            candidate = fenced.group(1).strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        data = json.loads(
            candidate[start:end + 1] if start >= 0 and end > start else candidate
        )
        return (
            str(data.get("title") or "").strip(),
            str(data.get("content") or "").strip(),
        )

    def translate_news_batch(
        self,
        items: list[dict[str, str]],
        glossary: dict[str, str],
        api_key: str,
    ) -> dict[str, tuple[str, str]]:
        prompt = (
            "以中文专业足球资讯编辑的方式批量转述以下新闻标题与摘要，语言自然、简洁，避免"
            "逐词硬译和英文语序。保持事实、消息来源与不确定性，不增加原文没有的信息。"
            "必须结合摘要判断标题中的足球新闻省略语：strike 在进球语境中通常指进球或射门，"
            "double 通常指梅开二度；不得把它们译成罢工、打击、双杀或与原意无关的结果。"
            "标题主语、进球者、对手、比分和纪录必须与摘要交叉核对后再输出。"
            "人名和球队名必须严格使用术语表；术语表未覆盖的专有名称采用中国大陆常见译名"
            "或自然音译，不能保留整段英文标题或英文姓名。只返回 JSON 对象，键为新闻 id，"
            "值为含 title 与 summary 的对象。\n"
            f"术语表：{json.dumps(glossary, ensure_ascii=False)}\n"
            f"新闻：{json.dumps(items, ensure_ascii=False)}"
        )
        text = self._chat(prompt, api_key, max_tokens=max(1200, len(items) * 260), timeout_seconds=70)
        start = text.find("{")
        end = text.rfind("}")
        data = json.loads(text[start:end + 1] if start >= 0 and end > start else text)
        return {
            str(item_id): (
                str(row.get("title") or "").strip(),
                str(row.get("summary") or "").strip(),
            )
            for item_id, row in data.items()
            if isinstance(row, dict)
        }

    def summary_signature(self, match: Match, entries: list[CommentaryEntry]) -> str:
        latest = entries[-1].sequence if entries else -1
        return f"deep-v8:{match.home.score}-{match.away.score}:{latest}:{len(entries)}"

    @staticmethod
    def _summary_minute(value: str) -> str:
        minute = str(value or "").strip()
        match = re.match(r"^(\d+)'(?:\+(\d+)')?$", minute)
        if not match:
            return minute
        base, added = match.groups()
        return f"{base}+{added}分钟" if added else f"{base}分钟"

    def _chat(
        self,
        prompt: str,
        api_key: str,
        max_tokens: int,
        timeout_seconds: int = 45,
        temperature: float = 0.25,
    ) -> str:
        if isinstance(api_key, AIRequestCredential):
            request_key = api_key.api_key
            preset_id = api_key.preset_id
        else:
            request_key = str(api_key or "")
            preset_id = self.model_preset_id
        preset = AI_MODEL_PRESETS.get(
            preset_id,
            AI_MODEL_PRESETS[DEFAULT_AI_MODEL_PRESET],
        )
        environment_key = (
            os.environ.get("AGNES_API_KEY")
            if preset_id == "agnes"
            else ""
        )
        key = (request_key or environment_key or "").strip()
        if not key:
            raise RuntimeError("未设置 AI API Key")
        payload = {
            "model": preset["model"],
            "messages": [
                {
                    "role": "system",
                    "content": "你只处理用户提供的足球比赛事实，禁止补充未经提供的信息。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": max(0.0, min(1.0, float(temperature))),
            "max_tokens": max_tokens,
        }
        payload.update(dict(preset.get("extra") or {}))
        with self.request_lock:
            wait_seconds = max(0.0, 0.8 - (time.monotonic() - self.last_request_at))
            if wait_seconds:
                time.sleep(wait_seconds)
            request = urllib.request.Request(
                str(preset["api_url"]),
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": "WorldCupFloat/1.2",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8-sig"))
            finally:
                self.last_request_at = time.monotonic()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(str(data.get("error") or "AI 服务返回为空"))
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
            rows = []
            for match in re.finditer(r"\{[^{}]*\}", candidate, flags=re.DOTALL):
                try:
                    row = json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        result: dict[int, str] = {}
        if isinstance(rows, dict):
            rows = [rows]
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

    def _parse_line_event_response(self, text: str) -> dict[int, str]:
        candidate = str(text or "").strip()
        fenced = re.search(
            r"```(?:text|txt)?\s*(.*?)```",
            candidate,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced:
            candidate = fenced.group(1).strip()
        result: dict[int, str] = {}
        for line in candidate.splitlines():
            match = re.match(r"^\s*(\d+)\s*[|｜\t]\s*(.+?)\s*$", line)
            if not match:
                continue
            sequence = int(match.group(1))
            value = self._strip_minute_prefix(match.group(2).strip())
            if value:
                result[sequence] = value
        return result

    def _parse_summary_response(self, text: str) -> str:
        candidate = str(text or "").strip()
        fenced = re.search(
            r"```(?:json)?\s*(.*?)```",
            candidate,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced:
            candidate = fenced.group(1).strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            return ""
        if not isinstance(data, dict):
            return ""
        paragraphs = [
            re.sub(r"\s+", " ", str(data.get(key) or "")).strip()
            for key in ("overview", "trend", "highlight")
        ]
        if not all(paragraphs):
            return ""
        return "\n\n".join(paragraphs)

    @staticmethod
    def _limit_summary_time_references(text: str, limit: int = 5) -> str:
        pattern = re.compile(
            r"(?:第)?\d+(?:\+\d+)?"
            r"(?:\s*(?:和|及|、)\s*\d+(?:\+\d+)?)*分钟[，,]?"
        )
        seen: set[str] = set()
        used = 0

        def replace(match: re.Match) -> str:
            nonlocal used
            numbers = re.findall(r"\d+(?:\+\d+)?", match.group(0))
            new_numbers = [number for number in numbers if number not in seen]
            if not new_numbers:
                return ""
            if used + len(new_numbers) > limit:
                return "随后，"
            seen.update(new_numbers)
            used += len(new_numbers)
            return match.group(0)

        cleaned = pattern.sub(replace, str(text or ""))
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"(^|\n)\s*[，,]\s*", r"\1", cleaned)
        return cleaned.strip()

    def _strip_minute_prefix(self, text: str) -> str:
        value = re.sub(
            r"^\s*第?\s*\d+(?:\+\d+)?\s*分钟[，,:：、|｜\s-]*",
            "",
            text,
        )
        value = re.sub(
            r"^\s*\d+(?:\+\d+)?\s*['’′]?\s*[!！，,:：、|｜\s-]+",
            "",
            value,
        )
        value = re.sub(
            r"^\s*[零〇一二三四五六七八九十百两]+(?:个)?分钟"
            r"[，,:：、|｜\s-]*",
            "",
            value,
        )
        return value.strip()

    def _trim_summary(self, text: str, limit: int = 220) -> str:
        paragraphs = [
            re.sub(r"[ \t\r\f\v]+", " ", paragraph).strip()
            for paragraph in re.split(r"\n\s*\n", str(text or ""))
            if paragraph.strip()
        ]
        text = "\n\n".join(paragraphs)
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
