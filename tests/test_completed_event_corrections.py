from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from data_provider import DataProvider, LeaderRow, Leaderboard, Match, MatchTeam, Team


def make_match(
    match_id: str,
    completed: bool,
    events: list[dict[str, object]],
) -> Match:
    return Match(
        id=match_id,
        name="Alpha vs Beta",
        short_name="ALP @ BET",
        date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        round_slug="group-stage",
        round_name="Group",
        group="A",
        status_state="post" if completed else "in",
        status_text="FT" if completed else "45'",
        completed=completed,
        home=MatchTeam(id="1", name="Alpha", abbreviation="ALP"),
        away=MatchTeam(id="2", name="Beta", abbreviation="BET"),
        events=events,
    )


class CompletedEventCorrectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.provider = DataProvider(
            cache_dir=Path(self.temp_dir.name),
            competition_key="worldcup",
        )
        self.provider.teams = {
            "1": Team(id="1", name="Alpha", abbreviation="ALP"),
            "2": Team(id="2", name="Beta", abbreviation="BET"),
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_completed_goals_correct_stale_official_board_but_ignore_live(self) -> None:
        self.provider.matches = [
            make_match(
                "m1",
                True,
                [{"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"}],
            ),
            make_match(
                "m2",
                True,
                [{"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"}],
            ),
            make_match(
                "m3",
                False,
                [{"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"}],
            ),
        ]
        self.provider.leaderboards = [
            Leaderboard(
                "goalsLeaders",
                "Goals",
                [
                    LeaderRow(
                        1,
                        "p1",
                        "Player One",
                        "1",
                        "Alpha",
                        "ALP",
                        "",
                        "Matches: 1, Goals: 1",
                        {"APP": "1", "G": "1", "A": "0"},
                    )
                ],
            )
        ]

        self.provider._apply_completed_event_corrections()

        row = self.provider.leaderboards[0].rows[0]
        self.assertEqual(row.stats["G"], "2")
        self.assertEqual(row.stats["APP"], "2")
        self.assertEqual(row.display_value, "Matches: 2, Goals: 2")

    def test_official_board_is_not_double_counted_after_it_catches_up(self) -> None:
        self.provider.matches = [
            make_match(
                "m1",
                True,
                [{"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"}],
            ),
            make_match(
                "m2",
                True,
                [{"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"}],
            ),
        ]
        self.provider.leaderboards = [
            Leaderboard(
                "goalsLeaders",
                "Goals",
                [
                    LeaderRow(
                        1,
                        "p1",
                        "Player One",
                        "1",
                        "Alpha",
                        "ALP",
                        "",
                        "Matches: 2, Goals: 2",
                        {"APP": "2", "G": "2", "A": "0"},
                    )
                ],
            )
        ]

        self.provider._apply_completed_event_corrections()

        row = self.provider.leaderboards[0].rows[0]
        self.assertEqual(row.stats["G"], "2")
        self.assertNotIn("eventCorrected", row.stats)

    def test_completed_correction_advances_appearances_for_new_finished_match(self) -> None:
        self.provider.matches = [
            make_match(
                "m1",
                True,
                [
                    {"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"},
                    {"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"},
                    {"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"},
                ],
            ),
            make_match(
                "m2",
                True,
                [
                    {"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"},
                    {"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"},
                ],
            ),
            make_match(
                "m3",
                True,
                [{"kind": "goal", "player_id": "p1", "player_name": "Player One", "team_id": "1"}],
            ),
        ]
        self.provider.leaderboards = [
            Leaderboard(
                "goalsLeaders",
                "Goals",
                [
                    LeaderRow(
                        1,
                        "p1",
                        "Player One",
                        "1",
                        "Alpha",
                        "ALP",
                        "",
                        "Matches: 2, Goals: 5",
                        {"APP": "2", "G": "5", "A": "0"},
                    )
                ],
            )
        ]

        self.provider._apply_completed_event_corrections()

        row = self.provider.leaderboards[0].rows[0]
        self.assertEqual(row.stats["APP"], "3")
        self.assertEqual(row.stats["G"], "6")
        self.assertEqual(row.display_value, "Matches: 3, Goals: 6")

    def test_card_boards_are_created_from_completed_events(self) -> None:
        self.provider.matches = [
            make_match(
                "m1",
                True,
                [
                    {"kind": "yellow", "player_id": "p2", "player_name": "Player Two", "team_id": "2"},
                    {"kind": "red", "player_id": "p3", "player_name": "Player Three", "team_id": "2"},
                ],
            )
        ]
        self.provider.leaderboards = []

        self.provider._apply_completed_event_corrections()

        yellow = next(board for board in self.provider.leaderboards if board.key == "yellowCardsLeaders")
        red = next(board for board in self.provider.leaderboards if board.key == "redCardsLeaders")
        self.assertEqual(yellow.rows[0].stats["YC"], "1")
        self.assertEqual(yellow.rows[0].display_value, "Matches: 1, Yellow Cards: 1")
        self.assertEqual(red.rows[0].stats["RC"], "1")
        self.assertEqual(red.rows[0].display_value, "Matches: 1, Red Cards: 1")


if __name__ == "__main__":
    unittest.main()
