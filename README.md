# 世界杯实时数据 / WorldCup Float

面向 Windows 的 2026 世界杯桌面浮动比分工具。

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
- Live matches with score and national team logos
- Upcoming fixtures
- Completed results
- Group standings with GP/W/D/L/GF/GA/GD/PTS
- Knockout bracket placeholders, such as group winner or second place, before results are known
- Data panel with player leaderboards
- Team workflow: select a national team, or click any team logo, to view team data, match chain, roster, and player stats
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
- Full match commentary timelines and cached AI post-match summaries

## Data Sources

Default source:

- ESPN public FIFA World Cup endpoints for scoreboard, teams, standings, rosters, and player statistics.

Fallback source:

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

## Smoke Test

Fetch and parse data without opening the UI:

```powershell
python .\worldcup_float.py --smoke-test
```

## Notes

- The app refreshes the main data automatically.
- Roster data is loaded only when a team page is opened.
- If no internet is available, the app uses the latest successful local cache.
