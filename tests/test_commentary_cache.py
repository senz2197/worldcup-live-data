from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from commentary_service import (
    AI_EVENT_SIGNATURES_KEY,
    CommentaryService,
)
from data_provider import CommentaryEntry


class CommentaryCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = CommentaryService(Path(self.temp_dir.name))
        self.entries = [
            CommentaryEntry(
                12,
                "14'",
                "Goal! France 1, Iraq 0. Kylian Mbappé scores.",
            ),
            CommentaryEntry(
                13,
                "18'",
                "Merchas Doski (Iraq) wins a free kick in the defensive half.",
            ),
        ]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_old_cache_without_source_signature_is_rejected(self) -> None:
        self.service.cache["narration_v3"] = {
            "match": {
                "12": "射门被挡。",
                "13": "球进了！姆巴佩破门。",
            }
        }

        self.assertEqual(
            {},
            self.service.event_texts(
                "match",
                mode="narration_v3",
                entries=self.entries,
            ),
        )

    def test_changed_source_invalidates_only_changed_event(self) -> None:
        signatures = {
            str(entry.sequence): self.service._event_signature(entry)
            for entry in self.entries
        }
        self.service.cache["narration_v3"] = {
            "match": {
                "12": "球进了！姆巴佩破门。",
                "13": "多斯基在防守半场赢得任意球。",
            }
        }
        self.service.cache[AI_EVENT_SIGNATURES_KEY] = {
            "narration_v3": {"match": signatures}
        }
        changed = [
            self.entries[0],
            CommentaryEntry(
                13,
                "18'",
                "Foul by Adrien Rabiot (France).",
            ),
        ]

        cached = self.service.event_texts(
            "match",
            mode="narration_v3",
            entries=changed,
        )

        self.assertIn(12, cached)
        self.assertNotIn(13, cached)

    def test_semantic_validation_rejects_shifted_goal(self) -> None:
        shifted = {
            12: "奥利塞射门被挡。",
            13: "球进了！姆巴佩为法国队破门。",
        }

        self.assertIsNone(
            self.service._validate_event_batch(
                self.entries,
                shifted,
            )
        )

    def test_free_kick_subject_is_canonicalized(self) -> None:
        entry = self.entries[1]
        validated = self.service._validate_event_batch(
            [entry],
            {13: "多斯基犯规，法国队获得任意球。"},
        )

        self.assertEqual(
            "Merchas Doski（Iraq）在防守半场赢得任意球。",
            validated[13],
        )

    def test_foul_subject_is_canonicalized(self) -> None:
        entry = CommentaryEntry(
            14,
            "18'",
            "Foul by Adrien Rabiot (France).",
        )
        validated = self.service._validate_event_batch(
            [entry],
            {14: "法国队获得任意球。"},
        )

        self.assertEqual(
            "Adrien Rabiot（France）出现犯规动作。",
            validated[14],
        )


if __name__ == "__main__":
    unittest.main()
