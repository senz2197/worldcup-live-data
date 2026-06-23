# 世界杯与五大联赛实时数据 / WorldCup Float

面向 Windows 的世界杯与欧洲五大联赛桌面浮动比分工具。

## 下载

打开仓库右侧的 **Releases**，下载最新版本中的：

```text
WorldCupFloat_Portable.zip
```

解压后直接运行 `WorldCupFloat.exe`，无需安装 Python。

## Features

- Always-on-top, resizable, semi-transparent desktop window
- Borderless floating widget mode, similar to a desktop pet
- Bottom-right floating badge for show/hide, settings, refresh, and exit
- System tray menu as a backup control entry
- Drag inside the content area to scroll; no visible side scrollbar
- Competition switcher for the World Cup, Premier League, La Liga, Bundesliga, Serie A, and Ligue 1
- Configurable centered or left-aligned title, with sync status directly below it
- Live matches with scores and team logos
- Upcoming fixtures grouped by the current or next round
- Completed results defaulting to the current round, with previous/next and all-results controls
- Group standings with GP/W/D/L/GF/GA/GD/PTS
- League tables and World Cup knockout bracket placeholders
- Standings, professional data boards, and player statistics identify the exact season that supplied their data, including previous-season fallbacks
- World Cups use edition labels such as `第23届世界杯（2026年）`; leagues use season labels such as `2025-26赛季`
- Stale ESPN fallback data displays its local cache age instead of appearing as a successful current sync
- Competition-specific statistical leaderboards
- Professional league leaderboards for goals, assists, goal contributions, appearances, starts, shots, shots on target, conversion, fouls, cards, offsides, and saves
- Favorite team support for every competition
- Team workflow: click any team logo or name to view team form, results, roster, and detailed player data
- World Cup player profiles include their club, with direct links into supported European league club cards
- League rosters automatically fall back to the latest populated ESPN season when a newly opened season is still empty
- World Cup rosters are enriched with current club relationships in the background and retain player-to-club-to-player navigation
- Compact-first layout designed to fit within roughly one quarter of a desktop screen width
- Chinese team and player names by default, with an English-name toggle in settings
- Player details open as a secondary panel instead of a side-by-side layout
- Local JSON and image cache for faster refreshes and offline fallback after first successful sync
- Windows Per-Monitor V2 high-DPI rendering for sharper text and flags
- Independent normal UI font and score font selectors
- Theme presets and editable colors with locally persisted settings
- One-click GitHub update that preserves the current local configuration
- ESPN play-by-play commentary shown directly below each live score card
- AI commentary cache entries are bound to exact source-event fingerprints, so shifted or edited ESPN events invalidate old translations
- AI event batches require complete sequence coverage and football-event semantic validation before entering the cache
- Clicking live commentary opens a dedicated full timeline that stays synchronized with the main live feed
- Full commentary drag positions survive refreshes; new events auto-follow only when the viewer is already at the bottom
- Chinese AI commentary with raw-data and translation modes
- Selectable AI presets for Agnes `agnes-2.0-flash` and Zhipu `glm-4.7-flash`, with Agnes retained as the default
- Separate locally persisted API keys per AI provider prevent model switches from overwriting credentials
- MyMemory remains the primary free translation service; optional Tencent Cloud Machine Translation takes over only when MyMemory fails or is rate-limited
- Microsoft Edge online neural voices for more natural live Chinese commentary
- Sports-focused Yunjian is the default voice, with Xiaoxiao, Yunyang, Yunxi, and Xiaoyi available in settings
- Windows OneCore and legacy SAPI voices remain automatic offline fallbacks
- Live commentary is polled independently every two seconds and shows new source events immediately while translation is pending
- World Cup and league news tabs with one-to-twelve-week filtering, favorite-team priority, translated summaries, and original-source links
- Startup news prewarming prioritizes the active favorite-team competition, then other favorites, then the last active competition; opening a queued news tab promotes it to the next task
- AI-first Chinese news rewriting with full ESPN article retrieval and free translation fallback
- News translations are invalidated whenever ESPN changes the source headline or summary, preventing stale mistranslations from being reused
- Football headline shorthand such as `strike` and `double` is disambiguated from article context before translation
- News cards and details never fall back to displaying untranslated English copy
- Free machine translation fallback for commentary and news when AI is disabled or unavailable
- Player rosters refresh every 24 hours by default, with a configurable interval
- Official rights-holder links for live matches and fixtures starting within five minutes
- Optional compact live-source labels beneath the centered score; completed match details omit live links
- Live speech reads only finalized Chinese commentary, never the untranslated English source or match minute
- More expressive professional live commentary prompts with strict source-fact safeguards
- Match stage and status headers share space and scale together without clipping at compact widths
- The title stays centered with quick refresh enabled by scaling and wrapping without silently changing the user's alignment setting
- Quick refresh and competition selection use mirrored, equal-width title-bar slots with matched icon sizing and vertical alignment
- Live match notifications automatically close when their tracked matches finish
- Wrapped labels size from their real container width so news, cards, popups, and compact layouts keep complete glyphs visible
- Full match commentary timelines and cached AI post-match summaries

## Data Sources

Default sources:

- ESPN public soccer endpoints for scoreboards, teams, standings, rosters, player profiles, and statistics.

World Cup fallback source:

- `worldcup26.ir`, an open-source no-key REST API, for teams, groups, and matches if ESPN is unavailable and no ESPN cache exists.

The app keeps API data in `cache\*.json` and logos in `cache\images`.

## Run

Install optional image dependency for crisp resized logos:

```powershell
python -m pip install -r requirements.txt
```

Start:

```powershell
python .\worldcup_float.py
```

Or double-click:

```text
run_worldcup.bat
```

## Build EXE

```powershell
.\build_exe.bat
```

Generated file:

```text
dist\WorldCupFloat.exe
```

The portable package includes the EXE, assets, configuration, and current cache.
AI API keys are stored only in the local `secrets.json` file. This file is
excluded from Git and release packages. Without a key, commentary automatically
falls back to the original ESPN play-by-play text.

`package_release.ps1` always creates the single public
`WorldCupFloat_Portable.zip` used by GitHub Releases. The persistent local
runtime is kept in `publish\WorldCupFloat_Local`; packaging and in-app updates
preserve its `config.json`, `secrets.json`, and cache. A separately named local
share copy is created only when explicitly requested:

```powershell
.\package_release.ps1 -CreateSharePackage -ShareOutputDirectory "$HOME\Desktop"
```

Live buttons only open official broadcaster or official broadcaster-lookup
pages. The project does not discover, proxy, embed, or redistribute match
video streams.

## Smoke Test

Fetch and parse data without opening the UI:

```powershell
python .\worldcup_float.py --smoke-test
```

## Notes

- The app refreshes the main data automatically.
- Roster data is loaded only when a team page is opened.
- If no internet is available, the app uses the latest successful local cache.
