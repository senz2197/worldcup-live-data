from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from data_provider import DataProvider


class DataCacheFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)
        self.provider = DataProvider(
            cache_dir=self.cache_dir,
            competition_key="worldcup",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_stale_cache_fallback_records_age_and_label(self) -> None:
        cache_name = "espn_worldcup_stats.json"
        fetched_at = time.time() - 7200
        (self.cache_dir / cache_name).write_text(
            json.dumps(
                {
                    "fetched_at": fetched_at,
                    "url": "https://example.invalid/stats",
                    "data": {"stats": [{"name": "goalsLeaders"}]},
                }
            ),
            encoding="utf-8",
        )
        self.provider._request_json = lambda _url: (_ for _ in ()).throw(
            OSError("offline")
        )

        data = self.provider.fetch_json(
            "https://example.invalid/stats",
            cache_name,
            ttl_seconds=120,
            force=True,
        )

        self.assertIn("stats", data)
        self.assertGreaterEqual(
            self.provider.stale_cache_fallbacks[cache_name],
            7100,
        )
        self.assertIn(
            "stale cache 2h",
            self.provider._source_label(
                "ESPN statistics",
                cache_name,
            ),
        )

    def test_scoreboard_group_label_reports_stale_cache(self) -> None:
        self.provider.stale_cache_fallbacks[
            "espn_worldcup_scoreboard_2026.json"
        ] = 3 * 3600

        self.assertEqual(
            "ESPN scoreboard (stale cache 3h)",
            self.provider._source_group_label(
                "ESPN scoreboard",
                "espn_worldcup_scoreboard_",
            ),
        )


if __name__ == "__main__":
    unittest.main()
