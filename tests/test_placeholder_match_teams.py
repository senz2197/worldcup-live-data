from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from data_provider import DataProvider, Team


class PlaceholderMatchTeamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.provider = DataProvider(
            cache_dir=Path(self.temp_dir.name),
            competition_key="worldcup",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_knockout_placeholder_is_not_clickable_or_registered_as_team(self) -> None:
        team = self.provider._match_team_from_espn(
            {
                "id": "5958",
                "team": {
                    "id": "5958",
                    "displayName": "Semifinal 1 Loser",
                    "abbreviation": "SF L1",
                },
            }
        )

        self.assertEqual(team.name, "Semifinal 1 Loser")
        self.assertFalse(team.clickable)
        self.assertNotIn("5958", self.provider.teams)

    def test_real_match_team_remains_clickable(self) -> None:
        team = self.provider._match_team_from_espn(
            {
                "id": "205",
                "team": {
                    "id": "205",
                    "displayName": "Brazil",
                    "abbreviation": "BRA",
                },
            }
        )

        self.assertEqual(team.name, "Brazil")
        self.assertTrue(team.clickable)
        self.assertIn("205", self.provider.teams)

    def test_existing_placeholder_team_is_still_not_clickable(self) -> None:
        self.provider.teams["131527"] = Team(
            id="131527",
            name="Round of 32 3 Winner",
            abbreviation="RD32",
        )

        team = self.provider._match_team_from_espn(
            {
                "id": "131527",
                "team": {
                    "id": "131527",
                    "displayName": "Round of 32 3 Winner",
                    "abbreviation": "RD32",
                },
            }
        )

        self.assertFalse(team.clickable)

    def test_espn_third_place_slug_maps_to_chinese_round(self) -> None:
        matches = self.provider._parse_espn_matches(
            {
                "events": [
                    {
                        "id": "760516",
                        "name": "Semifinal 2 Loser at Semifinal 1 Loser",
                        "date": "2026-07-18T21:00Z",
                        "season": {"slug": "3rd-place-match"},
                        "status": {"type": {"state": "pre", "shortDetail": "Scheduled"}},
                        "competitions": [
                            {
                                "competitors": [
                                    {
                                        "homeAway": "home",
                                        "team": {
                                            "id": "5958",
                                            "displayName": "Semifinal 1 Loser",
                                            "abbreviation": "SF L1",
                                        },
                                    },
                                    {
                                        "homeAway": "away",
                                        "team": {
                                            "id": "5959",
                                            "displayName": "Semifinal 2 Loser",
                                            "abbreviation": "SF L2",
                                        },
                                    },
                                ]
                            }
                        ],
                    }
                ]
            }
        )

        self.assertEqual(matches[0].round_slug, "third-place")
        self.assertEqual(matches[0].round_name, "季军赛")


if __name__ == "__main__":
    unittest.main()
