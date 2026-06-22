from __future__ import annotations

import json
import hashlib
import hmac
import re
import time
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


NEWS_TRANSLATION_VERSION = 3


class _ArticleTextParser(HTMLParser):
    BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.ignored_depth = max(0, self.ignored_depth - 1)
        elif not self.ignored_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)

    def text(self) -> str:
        value = unescape("".join(self.parts)).replace("\xa0", " ")
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in value.splitlines()
        ]
        return "\n\n".join(
            line
            for line in lines
            if line and not line.startswith(("- ", "• "))
        )


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
    api_url: str = ""
    full_text: str = ""
    translated_content: str = ""


class FreeTranslationService:
    API_URL = "https://api.mymemory.translated.net/get"
    TENCENT_ENDPOINT = "https://tmt.tencentcloudapi.com"
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
        self.tencent_secret_id = ""
        self.tencent_secret_key = ""

    def configure_tencent(
        self,
        secret_id: str,
        secret_key: str,
    ) -> None:
        self.tencent_secret_id = str(secret_id or "").strip()
        self.tencent_secret_key = str(secret_key or "").strip()

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
        try:
            translated = self._translate_mymemory(protected[:480])
        except Exception:
            translated = ""
        if (
            not translated
            and self.tencent_secret_id
            and self.tencent_secret_key
        ):
            try:
                translated = self._translate_tencent(protected[:1800])
            except Exception:
                translated = ""
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

    def _translate_mymemory(self, text: str) -> str:
        params = urllib.parse.urlencode(
            {"q": text, "langpair": "en|zh-CN"}
        )
        request = urllib.request.Request(
            f"{self.API_URL}?{params}",
            headers={"User-Agent": "WorldCupFloat/1.5"},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8-sig"))
        return str(
            (data.get("responseData") or {}).get("translatedText")
            or ""
        ).strip()

    def _translate_tencent(self, text: str) -> str:
        service = "tmt"
        host = "tmt.tencentcloudapi.com"
        action = "TextTranslate"
        version = "2018-03-21"
        region = "ap-guangzhou"
        timestamp = int(time.time())
        date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
        payload = json.dumps(
            {
                "SourceText": text,
                "Source": "en",
                "Target": "zh",
                "ProjectId": 0,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        canonical_headers = (
            "content-type:application/json; charset=utf-8\n"
            f"host:{host}\n"
        )
        signed_headers = "content-type;host"
        hashed_payload = hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()
        canonical_request = "\n".join(
            [
                "POST",
                "/",
                "",
                canonical_headers,
                signed_headers,
                hashed_payload,
            ]
        )
        credential_scope = f"{date}/{service}/tc3_request"
        string_to_sign = "\n".join(
            [
                "TC3-HMAC-SHA256",
                str(timestamp),
                credential_scope,
                hashlib.sha256(
                    canonical_request.encode("utf-8")
                ).hexdigest(),
            ]
        )

        def sign(key: bytes, message: str) -> bytes:
            return hmac.new(
                key,
                message.encode("utf-8"),
                hashlib.sha256,
            ).digest()

        secret_date = sign(
            ("TC3" + self.tencent_secret_key).encode("utf-8"),
            date,
        )
        secret_service = sign(secret_date, service)
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "TC3-HMAC-SHA256 "
            f"Credential={self.tencent_secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        request = urllib.request.Request(
            self.TENCENT_ENDPOINT,
            data=payload.encode("utf-8"),
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json; charset=utf-8",
                "Host": host,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": version,
                "X-TC-Region": region,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8-sig"))
        result = data.get("Response") or {}
        if result.get("Error"):
            raise RuntimeError(
                str((result.get("Error") or {}).get("Message") or "")
            )
        return str(result.get("TargetText") or "").strip()

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
        self.translation_path = cache_dir / "news_translation_cache_v2.json"
        self.article_cache_dir = cache_dir / "news_articles"
        self.article_cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.translations = json.loads(self.translation_path.read_text(encoding="utf-8"))
        except Exception:
            self.translations = {}
        self.translation_lock = threading.Lock()

    def cached_translation(
        self,
        item_id: str,
        require_ai: bool = False,
        source_title: str = "",
        source_summary: str = "",
    ) -> tuple[str, str]:
        with self.translation_lock:
            row = self.translations.get(str(item_id)) or {}
        if int(row.get("version") or 0) != NEWS_TRANSLATION_VERSION:
            return "", ""
        if (
            source_title
            and row.get("source_signature")
            != self._source_signature(source_title, source_summary)
        ):
            return "", ""
        if require_ai and row.get("list_provider") != "ai":
            return "", ""
        return str(row.get("title") or ""), str(row.get("summary") or "")

    def cached_content(self, item_id: str, require_ai: bool = False) -> str:
        with self.translation_lock:
            row = self.translations.get(str(item_id)) or {}
        if int(row.get("version") or 0) != NEWS_TRANSLATION_VERSION:
            return ""
        if require_ai and row.get("content_provider") != "ai":
            return ""
        return str(row.get("content") or "")

    def store_translation(
        self,
        item_id: str,
        title: str,
        summary: str,
        provider: str,
        source_title: str = "",
        source_summary: str = "",
    ) -> None:
        if not title:
            return
        with self.translation_lock:
            row = dict(self.translations.get(str(item_id)) or {})
            row.update({
                "version": NEWS_TRANSLATION_VERSION,
                "title": title,
                "summary": summary,
                "list_provider": provider,
                "source_signature": self._source_signature(
                    source_title,
                    source_summary,
                ),
                "updated_at": int(time.time()),
            })
            self.translations[str(item_id)] = row
            self._save_translations()

    @staticmethod
    def _source_signature(title: str, summary: str = "") -> str:
        source = json.dumps(
            [
                " ".join(str(title or "").split()),
                " ".join(str(summary or "").split()),
            ],
            ensure_ascii=False,
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def store_content(self, item_id: str, content: str, provider: str) -> None:
        if not content:
            return
        with self.translation_lock:
            row = dict(self.translations.get(str(item_id)) or {})
            row.update({
                "version": NEWS_TRANSLATION_VERSION,
                "content": content,
                "content_provider": provider,
                "updated_at": int(time.time()),
            })
            self.translations[str(item_id)] = row
            self._save_translations()

    def _save_translations(self) -> None:
        self.translation_path.write_text(
            json.dumps(self.translations, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def fetch_full_text(self, item: NewsItem, force: bool = False) -> str:
        if item.full_text and not force:
            return item.full_text
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(item.id))
        cache_path = self.article_cache_dir / f"{safe_id}.json"
        payload: dict[str, Any] | None = None
        if not force:
            payload = self._read_cache(cache_path, 7 * 24 * 60 * 60)
        if payload is None and item.api_url:
            request = urllib.request.Request(
                item.api_url,
                headers={"User-Agent": "WorldCupFloat/1.5"},
            )
            try:
                with urllib.request.urlopen(request, timeout=18) as response:
                    data = json.loads(response.read().decode("utf-8-sig"))
                rows = data.get("headlines") or []
                payload = rows[0] if rows else data
                cache_path.write_text(
                    json.dumps(
                        {"fetched_at": time.time(), "data": payload},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                payload = self._read_cache(cache_path, None) or {}
        story = str((payload or {}).get("story") or "")
        if story:
            parser = _ArticleTextParser()
            parser.feed(story)
            text = parser.text()
        else:
            text = str((payload or {}).get("description") or item.summary or "")
        item.full_text = text.strip()
        return item.full_text

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
            api_url = str(
                (((links.get("api") or {}).get("self") or {}).get("href"))
                or ""
            )
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
                    api_url=api_url,
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
