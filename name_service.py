from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import re
from pathlib import Path

from opencc import OpenCC


class WikidataNameService:
    ENDPOINT = "https://query.wikidata.org/sparql"

    def __init__(self, cache_dir: Path) -> None:
        self.cache_path = cache_dir / "wikidata_runtime_names.json"
        self.converter = OpenCC("t2s")
        try:
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            self.cache = {}

    def localize_players(self, names: list[str]) -> dict[str, str]:
        unique = list(dict.fromkeys(name.strip() for name in names if name.strip()))
        result = {name: self.cache[name] for name in unique if name in self.cache}
        missing = [name for name in unique if name not in result]
        for start in range(0, len(missing), 250):
            batch = missing[start:start + 250]
            result.update(self._query(batch))
            if start + 250 < len(missing):
                time.sleep(61)
        unresolved = [name for name in missing if name not in result]
        for start in range(0, len(unresolved), 40):
            result.update(self._transliterate(unresolved[start:start + 40]))
        if result:
            self.cache.update(result)
            self.cache_path.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return result

    def _transliterate(self, names: list[str]) -> dict[str, str]:
        query = "\n".join(names)
        url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
            {
                "client": "gtx",
                "sl": "en",
                "tl": "zh-CN",
                "dt": "t",
                "q": query,
            }
        )
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = json.loads(response.read().decode("utf-8-sig"))
            translated = "".join(str(row[0]) for row in data[0] if row and row[0])
            rows = translated.splitlines()
        except Exception:
            return {}
        if len(rows) != len(names):
            return {}
        return {
            source: self.converter.convert(target.strip())
            for source, target in zip(names, rows)
            if target.strip()
            and target.strip() != source
            and re.search(r"[\u4e00-\u9fff]", target)
        }

    def _query(self, names: list[str]) -> dict[str, str]:
        values = " ".join(f"{json.dumps(name)}@en" for name in names)
        query = f"""
        SELECT ?en ?zh ?desc WHERE {{
          VALUES ?en {{ {values} }}
          ?item rdfs:label ?en.
          ?item schema:description ?desc.
          FILTER(LANG(?desc) = "en")
          FILTER(
            CONTAINS(LCASE(STR(?desc)), "association football")
            || CONTAINS(LCASE(STR(?desc)), "soccer")
            || (
              CONTAINS(LCASE(STR(?desc)), "footballer")
              && !CONTAINS(LCASE(STR(?desc)), "rugby")
            )
          )
          OPTIONAL {{ ?item rdfs:label ?zh FILTER(LANG(?zh) = "zh") }}
        }}
        """
        body = urllib.parse.urlencode({"query": query, "format": "json"}).encode("utf-8")
        request = urllib.request.Request(
            self.ENDPOINT,
            data=body,
            headers={
                "User-Agent": "WorldCupFloat/1.5 github.com/senz2197/worldcup-live-data",
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    data = json.loads(response.read().decode("utf-8-sig"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt == 0:
                    time.sleep(65)
                    continue
                return {}
            except Exception:
                return {}
        else:
            return {}
        result: dict[str, str] = {}
        for row in (data.get("results") or {}).get("bindings") or []:
            source = str((row.get("en") or {}).get("value") or "")
            translated = str((row.get("zh") or {}).get("value") or "")
            if source and translated and source not in result:
                result[source] = self.converter.convert(translated)
        return result
