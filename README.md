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
- Competition-specific statistical leaderboards
- Professional league leaderboards for goals, assists, goal contributions, appearances, starts, shots, shots on target, conversion, fouls, cards, offsides, and saves
- Favorite team support for every competition
- Team workflow: click any team logo or name to view team form, results, roster, and detailed player data
- World Cup player profiles include their club, with direct links into supported European league club cards
- Compact-first layout designed to fit within roughly one quarter of a desktop screen width
- Chinese team and player names by default, with an English-name toggle in settings
- Player details open as a secondary panel instead of a side-by-side layout
- Local JSON and image cache for faster refreshes and offline fallback after first successful sync
- Windows Per-Monitor V2 high-DPI rendering for sharper text and flags
- Independent normal UI font and score font selectors
- Theme presets and editable colors with locally persisted settings
- One-click GitHub update that preserves the current local configuration
- ESPN play-by-play commentary shown directly below each live score card
- Chinese AI commentary with raw-data and translation modes
- Microsoft Edge online neural voices for more natural live Chinese commentary
- Sports-focused Yunjian is the default voice, with Xiaoxiao, Yunyang, Yunxi, and Xiaoyi available in settings
- Windows OneCore and legacy SAPI voices remain automatic offline fallbacks
- Live commentary is polled independently every two seconds and shows new source events immediately while translation is pending
- League news tab with one-to-twelve-week filtering, favorite-team priority, translated summaries, and original-source links
- AI-first Chinese news rewriting with full ESPN article retrieval and free translation fallback
- News cards and details never fall back to displaying untranslated English copy
- Free machine translation fallback for commentary and news when AI is disabled or unavailable
- Player rosters refresh every 24 hours by default, with a configurable interval
- Official rights-holder links for live matches and fixtures starting within five minutes
- Optional compact live-source labels beneath the centered score; completed match details omit live links
- Live speech reads commentary content only, without announcing the match minute
- More expressive professional live commentary prompts with strict source-fact safeguards
- Match stage and status headers share space and scale together without clipping at compact widths
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
