from __future__ import annotations

import tkinter as tk
import unittest
from types import MethodType

from app import WorldCupFloatApp
from data_provider import CommentaryEntry, Match, MatchTeam


class CommentaryScrollTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.geometry("360x420+20+20")
        self.app = WorldCupFloatApp.__new__(WorldCupFloatApp)
        self.app.root = self.root
        self.app.ui_font_var = tk.StringVar(
            self.root,
            value="Microsoft YaHei UI",
        )
        self.app.match_popup_mode = "commentary"
        self.app.detail_commentary_panels = {}
        self.app.commentary_scroll_states = {}
        self.app.detail_commentary_snapshots = {}
        self.app.commentary_entries = {}
        self.app.commentary_texts = {}
        self.app.detail_commentary_loading = set()
        self.app.detail_commentary_errors = {}
        self.app.match_detail_scroll = None
        self.app._commentary_text = MethodType(
            lambda app, match_id, entry: app.commentary_texts[
                match_id
            ].get(entry.sequence, ""),
            self.app,
        )
        self.app._commentary_emphasis = MethodType(
            lambda _app, _entry: ("", False),
            self.app,
        )
        self.app._localize_commentary_names = MethodType(
            lambda _app, text: text,
            self.app,
        )
        self.panel = tk.Frame(self.root)
        self.panel.pack(fill="both", expand=True)
        self.app.detail_commentary_panels["match"] = self.panel
        self.match = Match(
            "match",
            "match",
            "match",
            None,
            "round",
            "Round",
            "",
            "in",
            "LIVE",
            False,
            MatchTeam("home", "Home"),
            MatchTeam("away", "Away"),
        )

    def tearDown(self) -> None:
        self.root.destroy()

    def _set_entries(self, count: int) -> None:
        entries = [
            CommentaryEntry(
                sequence,
                f"{sequence}'",
                f"第{sequence}条比赛解说，内容足够长以验证实时更新后的稳定位置。",
            )
            for sequence in range(count)
        ]
        self.app.commentary_entries["match"] = entries
        self.app.commentary_texts["match"] = {
            entry.sequence: entry.text
            for entry in entries
        }

    def _timeline(self) -> tk.Text:
        return next(
            child
            for child in self.panel.winfo_children()
            if isinstance(child, tk.Text)
        )

    def _top_sequence(self) -> int | None:
        timeline = self._timeline()
        index = timeline.index("@8,7")
        return next(
            (
                int(tag.removeprefix("event_"))
                for tag in timeline.tag_names(index)
                if tag.startswith("event_")
            ),
            None,
        )

    def test_manual_anchor_survives_partial_timeline_growth(self) -> None:
        self._set_entries(8)
        self.app._render_detail_commentary(self.match)
        self.root.update()
        timeline = self._timeline()
        timeline.event_generate("<ButtonPress-1>", x=120, y=150)
        timeline.event_generate("<B1-Motion>", x=120, y=90)
        timeline.event_generate("<ButtonRelease-1>", x=120, y=90)
        self.root.update()
        expected = self.app.commentary_scroll_states["match"][
            "anchor_sequence"
        ]

        self._set_entries(40)
        self.app._render_detail_commentary(self.match)
        self.root.update()

        self.assertEqual(expected, self._top_sequence())
        self.assertTrue(
            self.app.commentary_scroll_states["match"]["manual_position"]
        )

    def test_wheel_anchor_survives_repeated_redraws(self) -> None:
        self._set_entries(40)
        self.app._render_detail_commentary(self.match)
        self.root.update()
        timeline = self._timeline()
        for _ in range(8):
            timeline.event_generate("<MouseWheel>", delta=120)
            self.root.update()
        expected = self.app.commentary_scroll_states["match"][
            "anchor_sequence"
        ]

        for count in (41, 42, 43):
            self._set_entries(count)
            self.app._render_detail_commentary(self.match)
            self.root.update()
            self.assertEqual(expected, self._top_sequence())


if __name__ == "__main__":
    unittest.main()
