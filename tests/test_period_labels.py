from __future__ import annotations

import tkinter as tk
import unittest
from types import SimpleNamespace

from app import WorldCupFloatApp


class PeriodLabelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.app = WorldCupFloatApp.__new__(WorldCupFloatApp)
        self.app.root = self.root
        self.app.snapshot = None

    def tearDown(self) -> None:
        self.root.destroy()

    def test_world_cup_uses_edition_label(self) -> None:
        self.assertEqual(
            "第23届世界杯（2026年）",
            self.app._season_label(
                2026,
                competition_key="worldcup",
            ),
        )

    def test_league_uses_season_label(self) -> None:
        self.assertEqual(
            "2025-26赛季",
            self.app._season_label(
                2025,
                competition_key="premier_league",
            ),
        )

    def test_world_cup_data_label_discloses_stale_cache(self) -> None:
        self.app.snapshot = SimpleNamespace(
            season_year=2026,
            competition_key="worldcup",
            competition_kind="tournament",
            stale_sources={
                "espn_worldcup_stats.json": 5 * 3600,
            },
        )

        self.assertEqual(
            "第23届世界杯（2026年） · 数据来自5 小时前缓存",
            self.app._period_with_cache_status("_stats.json"),
        )


if __name__ == "__main__":
    unittest.main()
