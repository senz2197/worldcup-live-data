# Mobile Porting Notes

The data, localization, commentary, and competition configuration layers are
kept separate from the Tkinter view so they can be moved behind a mobile
ViewModel or repository layer.

Windows-specific parts that require Android replacements:

- Tkinter windows, tray menus, borderless dragging, and desktop topmost flags.
- Windows SAPI voices used by `speech_service.py`; Android should use
  `TextToSpeech`.
- Browser launch currently uses Python `webbrowser`; Android should use an
  `ACTION_VIEW` intent.
- JSON files stored beside the executable should move to app-private storage.
- Background refresh should move to lifecycle-aware coroutines and WorkManager.

Shared concepts suitable for reuse:

- Competition IDs and ESPN endpoint mapping.
- Round grouping and current-round selection.
- Snapshot, match, team, player, leaderboard, and commentary models.
- Official broadcaster-link policy.
- Cached Chinese name mappings and AI commentary cache format.
- League news models, translation cache, and favorite-team prioritization.
