from __future__ import annotations

import json
import time
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class NewsItem:
    id: str
    title: str
    summary: str
    published: datetime
    url: str
    source: str = "ESPN"
    image: str = ""
    team_ids: list[str] = field(default_factory=list)
    translated_title: str = ""
    translated_summary: str = ""


class FreeTranslationService:
    API_URL = "https://api.mymemory.translated.net/get"
    FOOTBALL_GLOSSARY = {
        "player": "球员",
        "players": "球员",
        "club": "俱乐部",
        "manager": "主教练",
        "coach": "教练",
        "transfer": "转会",
        "midfielder": "中场球员",
        "forward": "前锋",
        "defender": "后卫",
        "goalkeeper": "门将",
        "fixture": "赛程",
        "fixtures": "赛程",
    }

    def __init__(self, cache_dir: Path) -> None:
        self.cache_path = cache_dir / "free_translation_cache.json"
        try:
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            self.cache = {}
        self.lock = threading.Lock()

    def translate(self, text: str, glossary: dict[str, str]) -> str:
        text = " ".join(str(text or "").split())
        if not text:
            return ""
        glossary = {**self.FOOTBALL_GLOSSARY, **glossary}
        cache_key = json.dumps([text, glossary], ensure_ascii=False, sort_keys=True)
        with self.lock:
            cached = str(self.cache.get(cache_key) or "")
        if cached:
            return cached
        protected = text
        placeholders: dict[str, str] = {}
        for index, (source, target) in enumerate(
            sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True)
        ):
            if source and source.casefold() in protected.casefold():
                token = f"ZXQ{index}QXZ"
                start = protected.casefold().find(source.casefold())
                while start >= 0:
                    protected = protected[:start] + token + protected[start + len(source):]
                    start = protected.casefold().find(source.casefold(), start + len(token))
                placeholders[token] = target
        params = urllib.parse.urlencode({"q": protected[:480], "langpair": "en|zh-CN"})
        request = urllib.request.Request(
            f"{self.API_URL}?{params}",
            headers={"User-Agent": "WorldCupFloat/1.5"},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8-sig"))
        translated = str((data.get("responseData") or {}).get("translatedText") or "").strip()
        for token, target in placeholders.items():
            translated = translated.replace(token, target)
        if translated:
            with self.lock:
                self.cache[cache_key] = translated
                self.cache_path.write_text(
                    json.dumps(self.cache, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        return translated

    def translate_many(self, texts: list[str], glossary: dict[str, str]) -> list[str]:
        result: list[str] = []
        batch: list[str] = []
        size = 0
        for text in texts:
            clean = " ".join(str(text or "").split())
            if batch and size + len(clean) > 380:
                result.extend(self._translate_batch(batch, glossary))
                batch = []
                size = 0
            batch.append(clean)
            size += len(clean) + 10
        if batch:
            result.extend(self._translate_batch(batch, glossary))
        return result

    def _translate_batch(self, texts: list[str], glossary: dict[str, str]) -> list[str]:
        delimiter = " ZXSEPZX "
        translated = self.translate(delimiter.join(texts), glossary)
        rows = [row.strip() for row in translated.split("ZXSEPZX")]
        if len(rows) == len(texts):
            return rows
        return [self.translate(text, glossary) for text in texts]


class NewsService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.translation_path = cache_dir / "news_translation_cache.json"
        try:
            self.translations = json.loads(self.translation_path.read_text(encoding="utf-8"))
        except Exception:
            self.translations = {}
        self.translation_lock = threading.Lock()

    def cached_translation(self, item_id: str) -> tuple[str, str]:
        with self.translation_lock:
            row = self.translations.get(str(item_id)) or {}
        return str(row.get("title") or ""), str(row.get("summary") or "")

    def store_translation(self, item_id: str, title: str, summary: str) -> None:
        if not title:
            return
        with self.translation_lock:
            self.translations[str(item_id)] = {
                "title": title,
                "summary": summary,
                "updated_at": int(time.time()),
            }
            self.translation_path.write_text(
                json.dumps(self.translations, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def fetch(
        self,
        espn_league: str,
        weeks: int = 1,
        favorite_team_id: str = "",
        force: bool = False,
    ) -> list[NewsItem]:
        cache_path = self.cache_dir / f"news_{espn_league.replace('.', '_')}.json"
        payload: dict[str, Any] | None = None
        if not force:
            payload = self._read_cache(cache_path, 15 * 60)
        if payload is None:
            url = (
                "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                f"{espn_league}/news?limit=80"
            )
            request = urllib.request.Request(url, headers={"User-Agent": "WorldCupFloat/1.5"})
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8-sig"))
                cache_path.write_text(
                    json.dumps({"fetched_at": time.time(), "data": payload}, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                payload = self._read_cache(cache_path, None) or {}
        cutoff = datetime.now(timezone.utc) - timedelta(weeks=max(1, min(12, weeks)))
        items: list[NewsItem] = []
        for article in payload.get("articles") or []:
            published = self._date(article.get("published") or article.get("lastModified"))
            if published is None or published < cutoff:
                continue
            team_ids = [
                str(category.get("teamId") or (category.get("team") or {}).get("id") or "")
                for category in article.get("categories") or []
                if category.get("type") == "team"
            ]
            links = article.get("links") or {}
            url = str(((links.get("web") or {}).get("href")) or "")
            images = article.get("images") or []
            items.append(
                NewsItem(
                    id=str(article.get("id") or article.get("nowId") or url),
                    title=str(article.get("headline") or "").strip(),
                    summary=str(article.get("description") or "").strip(),
                    published=published.astimezone(),
                    url=url,
                    image=str((images[0] if images else {}).get("url") or ""),
                    team_ids=[team_id for team_id in team_ids if team_id],
                )
            )
        items.sort(
            key=lambda item: (
                0 if favorite_team_id and favorite_team_id in item.team_ids else 1,
                -item.published.timestamp(),
            )
        )
        return items

    @staticmethod
    def _date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _read_cache(path: Path, ttl: int | None) -> dict[str, Any] | None:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if ttl is not None and time.time() - float(envelope.get("fetched_at", 0)) > ttl:
                return None
            return envelope.get("data") or {}
        except Exception:
            return None
