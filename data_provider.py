from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = app_dir()
CACHE_DIR = APP_DIR / "cache"

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_WEB_BASE = "https://site.web.api.espn.com/apis/v2/sports/soccer"

COMPETITIONS = {
    "worldcup": {
        "name": "世界杯",
        "title": "世界杯实时数据",
        "espn": "fifa.world",
        "kind": "tournament",
        "year": 2026,
    },
    "premier_league": {
        "name": "英超",
        "title": "英超实时数据",
        "espn": "eng.1",
        "kind": "league",
    },
    "laliga": {
        "name": "西甲",
        "title": "西甲实时数据",
        "espn": "esp.1",
        "kind": "league",
    },
    "bundesliga": {
        "name": "德甲",
        "title": "德甲实时数据",
        "espn": "ger.1",
        "kind": "league",
    },
    "serie_a": {
        "name": "意甲",
        "title": "意甲实时数据",
        "espn": "ita.1",
        "kind": "league",
    },
    "ligue_1": {
        "name": "法甲",
        "title": "法甲实时数据",
        "espn": "fra.1",
        "kind": "league",
    },
}

ESPN_LEAGUE_TO_COMPETITION = {
    str(data["espn"]): key
    for key, data in COMPETITIONS.items()
}

WORLDCUP26_GAMES_URL = "https://worldcup26.ir/get/games"
WORLDCUP26_TEAMS_URL = "https://worldcup26.ir/get/teams"
WORLDCUP26_GROUPS_URL = "https://worldcup26.ir/get/groups"

SCOREBOARD_TTL_SECONDS = 12
STANDINGS_TTL_SECONDS = 60
STATS_TTL_SECONDS = 120


ROUND_LABELS = {
    "group-stage": "小组赛",
    "round-of-32": "32 强",
    "round-of-16": "16 强",
    "quarterfinals": "1/4 决赛",
    "semifinals": "半决赛",
    "third-place": "季军赛",
    "final": "决赛",
}

ROUND_SLUG_ALIASES = {
    "third-place-match": "third-place",
}

STAT_NAMES = {
    "gamesPlayed": "赛",
    "wins": "胜",
    "ties": "平",
    "losses": "负",
    "pointsFor": "进",
    "pointsAgainst": "失",
    "pointDifferential": "净",
    "points": "分",
}


@dataclass
class Team:
    id: str
    name: str
    abbreviation: str = ""
    logo: str = ""
    color: str = ""
    group: str = ""
    standing: dict[str, Any] = field(default_factory=dict)
    links: list[dict[str, Any]] = field(default_factory=list)
    source: str = "espn"


@dataclass
class MatchTeam:
    id: str
    name: str
    abbreviation: str = ""
    logo: str = ""
    score: str = ""
    winner: bool | None = None
    clickable: bool = False


@dataclass
class Match:
    id: str
    name: str
    short_name: str
    date: datetime | None
    round_slug: str
    round_name: str
    group: str
    status_state: str
    status_text: str
    completed: bool
    home: MatchTeam
    away: MatchTeam
    venue: str = ""
    detail: str = ""
    statistics: dict[str, dict[str, str]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    commentary: list["CommentaryEntry"] = field(default_factory=list)
    source: str = "espn"
    round_number: int = 0
    competition_key: str = "worldcup"

    @property
    def is_live(self) -> bool:
        return self.status_state == "in"

    @property
    def is_upcoming(self) -> bool:
        return self.status_state == "pre"


@dataclass
class Player:
    id: str
    name: str
    short_name: str = ""
    jersey: str = ""
    position: str = ""
    age: str = ""
    height: str = ""
    weight: str = ""
    birthplace: str = ""
    citizenship: str = ""
    headshot: str = ""
    stats: dict[str, str] = field(default_factory=dict)
    club_team_id: str = ""
    club_team_name: str = ""
    club_competition_key: str = ""


@dataclass
class CommentaryEntry:
    sequence: int
    minute: str
    text: str


@dataclass
class LeaderRow:
    rank: int
    player_id: str
    player_name: str
    team_id: str
    team_name: str
    team_abbreviation: str
    team_logo: str
    display_value: str
    stats: dict[str, str] = field(default_factory=dict)


@dataclass
class Leaderboard:
    key: str
    name: str
    rows: list[LeaderRow] = field(default_factory=list)


@dataclass
class Snapshot:
    generated_at: datetime
    teams: dict[str, Team]
    matches: list[Match]
    standings: list[dict[str, Any]]
    leaderboards: list[Leaderboard]
    errors: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    competition_key: str = "worldcup"
    competition_name: str = "世界杯"
    competition_kind: str = "tournament"
    season_year: int = 2026
    season_name: str = ""


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).astimezone()
        except ValueError:
            continue
    return None


def pick_logo(team: dict[str, Any]) -> str:
    logos = team.get("logos") or []
    for logo in logos:
        rel = logo.get("rel") or []
        if "default" in rel and "dark" not in rel:
            return logo.get("href") or ""
    return (logos[0].get("href") if logos else "") or team.get("flag", "")


def stat_value(stats: list[dict[str, Any]], name: str, fallback: str = "") -> str:
    for item in stats:
        if item.get("name") == name or item.get("abbreviation") == name:
            return str(item.get("displayValue") or item.get("value") or fallback)
    return fallback


def extract_player_stats(payload: Any) -> dict[str, str]:
    stats: dict[str, str] = {}

    def add_items(items: Any) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            key = item.get("abbreviation") or item.get("displayName") or item.get("name")
            if not key:
                continue
            stats[str(key)] = str(item.get("displayValue") or item.get("value") or "")

    if isinstance(payload, list):
        add_items(payload)
    elif isinstance(payload, dict):
        splits = payload.get("splits") or {}
        for category in splits.get("categories") or []:
            add_items(category.get("stats") if isinstance(category, dict) else None)
    return stats


def safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "cache"


class DataProvider:
    def __init__(
        self,
        cache_dir: Path | None = None,
        competition_key: str = "worldcup",
    ) -> None:
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "images").mkdir(parents=True, exist_ok=True)
        self.teams: dict[str, Team] = {}
        self.matches: list[Match] = []
        self.standings: list[dict[str, Any]] = []
        self.leaderboards: list[Leaderboard] = []
        self.last_snapshot: Snapshot | None = None
        self.competition_key = "worldcup"
        self.competition = COMPETITIONS["worldcup"]
        self.season_year = int(self.competition.get("year") or datetime.now().year)
        self.season_name = ""
        self.set_competition(competition_key)

    def set_competition(self, competition_key: str) -> None:
        key = competition_key if competition_key in COMPETITIONS else "worldcup"
        self.competition_key = key
        self.competition = COMPETITIONS[key]
        self.season_year = int(
            self.competition.get("year") or datetime.now().year
        )
        self.season_name = ""

    @property
    def espn_league(self) -> str:
        return str(self.competition["espn"])

    @property
    def is_league(self) -> bool:
        return self.competition.get("kind") == "league"

    def _cache_name(self, suffix: str) -> str:
        return f"espn_{safe_filename(self.competition_key)}_{suffix}.json"

    def _site_url(self, endpoint: str) -> str:
        return f"{ESPN_SITE_BASE}/{self.espn_league}/{endpoint}"

    def _web_url(self, endpoint: str) -> str:
        return f"{ESPN_WEB_BASE}/{self.espn_league}/{endpoint}"

    def load_all(self, force: bool = False) -> Snapshot:
        errors: list[str] = []
        sources: list[str] = []
        self.teams = {}
        self.matches = []
        self.standings = []
        self.leaderboards = []

        try:
            teams_data = self.fetch_json(
                self._site_url("teams"),
                self._cache_name("teams"),
                ttl_seconds=12 * 3600,
                force=force,
            )
            self._parse_espn_teams(teams_data)
            sources.append("ESPN teams")
        except Exception as exc:
            errors.append(f"ESPN 球队数据不可用: {exc}")

        try:
            standings_data = self.fetch_json(
                self._web_url("standings"),
                self._cache_name("standings"),
                ttl_seconds=STANDINGS_TTL_SECONDS,
                force=force,
            )
            season = standings_data.get("season") or {}
            self.season_year = int(
                season.get("year") or self.season_year
            )
            self.season_name = str(
                season.get("displayName") or ""
            )
            self.standings = self._parse_espn_standings(standings_data)
            sources.append("ESPN standings")
        except Exception as exc:
            errors.append(f"ESPN 积分榜不可用: {exc}")

        try:
            scoreboard_data = self._load_scoreboard(force=force)
            self.matches = self._parse_espn_matches(scoreboard_data)
            self._assign_round_numbers()
            sources.append("ESPN scoreboard")
        except Exception as exc:
            errors.append(f"ESPN 赛程比分不可用: {exc}")

        try:
            stats_data = self.fetch_json(
                self._site_url("statistics"),
                self._cache_name("stats"),
                ttl_seconds=STATS_TTL_SECONDS,
                force=force,
            )
            self.leaderboards = self._parse_espn_leaderboards(stats_data)
            sources.append("ESPN statistics")
        except Exception as exc:
            errors.append(f"ESPN 球员榜单不可用: {exc}")

        if (
            self.competition_key == "worldcup"
            and (not self.matches or not self.teams)
        ):
            try:
                self._load_worldcup26_fallback(force=force)
                sources.append("worldcup26.ir fallback")
            except Exception as exc:
                errors.append(f"备用源不可用: {exc}")

        self.matches.sort(key=lambda match: match.date or datetime.max.replace(tzinfo=timezone.utc))
        snapshot = Snapshot(
            generated_at=datetime.now().astimezone(),
            teams=self.teams,
            matches=self.matches,
            standings=self.standings,
            leaderboards=self.leaderboards,
            errors=errors,
            sources=sources,
            competition_key=self.competition_key,
            competition_name=str(self.competition["name"]),
            competition_kind=str(self.competition["kind"]),
            season_year=self.season_year,
            season_name=self.season_name,
        )
        self.last_snapshot = snapshot
        return snapshot

    def get_roster(self, team_id: str, force: bool = False) -> tuple[list[Player], str | None]:
        if not team_id or team_id not in self.teams:
            return [], "没有找到可用的球队 ID。"
        team = self.teams[team_id]
        if team.source != "espn":
            return [], "当前备用数据源没有球员名单接口。"
        try:
            data = self.fetch_json(
                self._site_url(f"teams/{team_id}/roster"),
                self._cache_name(f"roster_{safe_filename(team_id)}"),
                ttl_seconds=6 * 3600,
                force=force,
            )
            return self._parse_roster(data), None
        except Exception as exc:
            return [], f"球员名单暂时不可用: {exc}"

    def get_match_commentary(
        self,
        match_id: str,
        live: bool = False,
        force: bool = False,
    ) -> tuple[list[CommentaryEntry], dict[str, Any], str | None]:
        if not match_id:
            return [], {}, "缺少比赛 ID"
        # Completed play-by-play is immutable; retain it for fast detail opening.
        ttl = 8 if live else 365 * 24 * 3600
        try:
            data = self.fetch_json(
                self._site_url(f"summary?event={match_id}"),
                self._cache_name(f"summary_{safe_filename(match_id)}"),
                ttl_seconds=ttl,
                force=force,
            )
            commentary = self._parse_espn_commentary(data.get("commentary") or [])
            return commentary, data, None
        except Exception as exc:
            return [], {}, f"文字直播暂时不可用: {exc}"

    def get_player_profile(
        self,
        player: Player,
        force: bool = False,
    ) -> Player:
        if not player.id:
            return player
        try:
            data = self.fetch_json(
                (
                    "https://site.web.api.espn.com/apis/common/v3/"
                    f"sports/soccer/athletes/{player.id}"
                ),
                f"espn_player_{safe_filename(player.id)}.json",
                ttl_seconds=12 * 3600,
                force=force,
            )
        except Exception:
            return player
        athlete = data.get("athlete") or {}
        team = athlete.get("team") or {}
        league = data.get("league") or {}
        league_slug = str(league.get("slug") or "")
        profile_stats = extract_player_stats(
            athlete.get("statistics")
        )
        summary = athlete.get("statsSummary") or {}
        if isinstance(summary, dict):
            profile_stats.update(
                extract_player_stats(summary.get("statistics"))
            )
        return Player(
            id=player.id,
            name=athlete.get("displayName") or player.name,
            short_name=athlete.get("shortName") or player.short_name,
            jersey=str(athlete.get("jersey") or player.jersey),
            position=(
                (athlete.get("position") or {}).get("displayName")
                if isinstance(athlete.get("position"), dict)
                else player.position
            ) or player.position,
            age=str(athlete.get("age") or player.age),
            height=athlete.get("displayHeight") or player.height,
            weight=athlete.get("displayWeight") or player.weight,
            birthplace=player.birthplace,
            citizenship=(
                (athlete.get("citizenshipCountry") or {}).get("displayName")
                if isinstance(athlete.get("citizenshipCountry"), dict)
                else athlete.get("citizenship")
            ) or player.citizenship,
            headshot=player.headshot,
            stats={**player.stats, **profile_stats},
            club_team_id=str(team.get("id") or ""),
            club_team_name=team.get("displayName") or team.get("name") or "",
            club_competition_key=ESPN_LEAGUE_TO_COMPETITION.get(
                league_slug,
                "",
            ),
        )

    def _load_scoreboard(self, force: bool = False) -> dict[str, Any]:
        years = [self.season_year]
        if self.is_league:
            years.append(self.season_year + 1)
        events: dict[str, dict[str, Any]] = {}
        payload: dict[str, Any] = {}
        for year in years:
            data = self.fetch_json(
                self._site_url(f"scoreboard?limit=1000&dates={year}"),
                self._cache_name(f"scoreboard_{year}"),
                ttl_seconds=SCOREBOARD_TTL_SECONDS,
                force=force,
            )
            if not payload:
                payload = dict(data)
            for event in data.get("events") or []:
                event_season = event.get("season") or {}
                if int(event_season.get("year") or self.season_year) != self.season_year:
                    continue
                event_id = str(event.get("id") or "")
                if event_id:
                    events[event_id] = event
        payload["events"] = list(events.values())
        return payload

    def fetch_json(self, url: str, cache_name: str, ttl_seconds: int, force: bool = False) -> dict[str, Any]:
        cache_path = self.cache_dir / cache_name
        if not force:
            cached = self._read_cache(cache_path, ttl_seconds)
            if cached is not None:
                return cached

        try:
            data = self._request_json(url)
            envelope = {"fetched_at": time.time(), "url": url, "data": data}
            cache_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception:
            stale = self._read_cache(cache_path, ttl_seconds=None)
            if stale is not None:
                return stale
            raise

    def _read_cache(self, cache_path: Path, ttl_seconds: int | None) -> dict[str, Any] | None:
        if not cache_path.exists():
            return None
        try:
            envelope = json.loads(cache_path.read_text(encoding="utf-8"))
            fetched_at = float(envelope.get("fetched_at", 0))
            if ttl_seconds is not None and time.time() - fetched_at > ttl_seconds:
                return None
            return envelope.get("data")
        except Exception:
            return None

    def _request_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "WorldCupFloat/0.1 (+desktop score widget)",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8-sig")
        return json.loads(raw)

    def _parse_espn_teams(self, data: dict[str, Any]) -> None:
        for sport in data.get("sports", []):
            for league in sport.get("leagues", []):
                for item in league.get("teams", []):
                    team_data = item.get("team") or item
                    team = self._team_from_espn(team_data)
                    if team.id:
                        self.teams[team.id] = team

    def _team_from_espn(self, data: dict[str, Any]) -> Team:
        return Team(
            id=str(data.get("id") or ""),
            name=data.get("displayName") or data.get("name") or data.get("location") or "TBD",
            abbreviation=data.get("abbreviation") or "",
            logo=pick_logo(data),
            color=(data.get("color") or "").strip("#"),
            links=data.get("links") or [],
            source="espn",
        )

    def _match_team_from_espn(self, competitor: dict[str, Any]) -> MatchTeam:
        team_data = competitor.get("team") or {}
        team_id = str(team_data.get("id") or competitor.get("id") or "")
        team = self.teams.get(team_id)
        name = team_data.get("displayName") or team_data.get("name") or competitor.get("displayName") or "待定"
        if team is None and team_id:
            team = self._team_from_espn(team_data)
            if team.id and name and "Winner" not in name and "Place" not in name:
                self.teams[team.id] = team
        return MatchTeam(
            id=team_id,
            name=team.name if team else name,
            abbreviation=(team.abbreviation if team else team_data.get("abbreviation", "")) or "",
            logo=(team.logo if team else pick_logo(team_data)) or "",
            score=str(competitor.get("score") or ""),
            winner=competitor.get("winner"),
            clickable=bool(team_id and team_id in self.teams),
        )

    def _parse_espn_matches(self, data: dict[str, Any]) -> list[Match]:
        matches: list[Match] = []
        for event in data.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors") or []
            home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
            away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})
            home = self._match_team_from_espn(home_comp)
            away = self._match_team_from_espn(away_comp)
            status_type = (event.get("status") or {}).get("type") or (comp.get("status") or {}).get("type") or {}
            season = event.get("season") or {}
            round_slug = str(season.get("slug") or "")
            round_slug = ROUND_SLUG_ALIASES.get(round_slug, round_slug)
            round_name = ROUND_LABELS.get(round_slug, season.get("name") or round_slug or "赛事")
            if self.is_league:
                round_slug = ""
                round_name = ""
            group = ""
            if round_slug == "group-stage" and home.id in self.teams and away.id in self.teams:
                home_group = self.teams[home.id].group
                away_group = self.teams[away.id].group
                group = home_group if home_group == away_group else home_group or away_group
            venue_data = event.get("venue") or comp.get("venue") or {}
            venue = venue_data.get("fullName") or venue_data.get("displayName") or venue_data.get("name") or ""
            statistics = self._match_statistics_from_espn(competitors)
            events = self._match_events_from_espn(comp.get("details") or [])
            matches.append(
                Match(
                    id=str(event.get("id") or comp.get("id") or ""),
                    name=event.get("name") or "",
                    short_name=event.get("shortName") or event.get("name") or "",
                    date=parse_datetime(event.get("date") or comp.get("date")),
                    round_slug=round_slug,
                    round_name=round_name,
                    group=group,
                    status_state=status_type.get("state") or "pre",
                    status_text=status_type.get("shortDetail") or status_type.get("detail") or status_type.get("description") or "",
                    completed=bool(status_type.get("completed") or status_type.get("state") == "post"),
                    home=home,
                    away=away,
                    venue=venue,
                    detail=status_type.get("detail") or "",
                    statistics=statistics,
                    events=events,
                    source="espn",
                    competition_key=self.competition_key,
                )
            )
        return matches

    def _assign_round_numbers(self) -> None:
        if not self.matches:
            return
        future_schedule = (
            self.is_league
            and sum(1 for match in self.matches if match.is_upcoming)
            >= len(self.matches) * 0.8
        )
        if self.is_league and not future_schedule:
            ordered = sorted(
                self.matches,
                key=lambda item: (
                    int(item.id) if item.id.isdigit() else 10**18,
                    item.id,
                ),
            )
        else:
            ordered = sorted(
                self.matches,
                key=lambda item: (
                    item.date or datetime.max.replace(tzinfo=timezone.utc),
                    item.id,
                ),
            )
        appearances: dict[str, int] = {}
        for match in ordered:
            if not self.is_league and match.round_slug != "group-stage":
                continue
            home_count = appearances.get(match.home.id, 0)
            away_count = appearances.get(match.away.id, 0)
            number = max(home_count, away_count) + 1
            match.round_number = number
            if self.is_league:
                match.round_slug = f"matchday-{number}"
                match.round_name = f"第 {number} 轮"
            else:
                match.round_name = f"小组赛第 {number} 轮"
            if match.home.id:
                appearances[match.home.id] = max(home_count + 1, number)
            if match.away.id:
                appearances[match.away.id] = max(away_count + 1, number)

    def _match_statistics_from_espn(self, competitors: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for competitor in competitors:
            team_data = competitor.get("team") or {}
            team_id = str(team_data.get("id") or competitor.get("id") or "")
            if not team_id:
                continue
            stats: dict[str, str] = {}
            for item in competitor.get("statistics") or []:
                if not isinstance(item, dict):
                    continue
                key = item.get("name") or item.get("abbreviation")
                if not key:
                    continue
                stats[str(key)] = str(item.get("displayValue") or item.get("value") or "")
            result[team_id] = stats
        return result

    def _match_events_from_espn(self, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for item in details:
            if not isinstance(item, dict):
                continue
            event_type = item.get("type") or {}
            text = event_type.get("text") or ""
            is_goal = bool(item.get("scoringPlay") or item.get("scoreValue"))
            is_yellow = bool(item.get("yellowCard"))
            is_red = bool(item.get("redCard"))
            if not (is_goal or is_yellow or is_red):
                continue
            athletes = item.get("athletesInvolved") or []
            athlete = athletes[0] if athletes and isinstance(athletes[0], dict) else {}
            team = item.get("team") or {}
            clock = item.get("clock") or {}
            if is_goal:
                kind = "goal"
            elif is_red:
                kind = "red"
            else:
                kind = "yellow"
            events.append(
                {
                    "kind": kind,
                    "team_id": str(team.get("id") or ""),
                    "minute": clock.get("displayValue") or "",
                    "player_id": str(athlete.get("id") or ""),
                    "player_name": athlete.get("displayName") or athlete.get("fullName") or athlete.get("shortName") or "",
                    "type": text,
                    "own_goal": bool(item.get("ownGoal")),
                    "penalty": bool(item.get("penaltyKick")),
                }
            )
        return events

    def _parse_espn_commentary(self, rows: list[dict[str, Any]]) -> list[CommentaryEntry]:
        commentary: list[CommentaryEntry] = []
        seen: set[int] = set()
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            try:
                sequence = int(item.get("sequence", index))
            except (TypeError, ValueError):
                sequence = index
            if sequence in seen:
                continue
            seen.add(sequence)
            time_data = item.get("time") or {}
            minute = str(time_data.get("displayValue") or "").strip()
            commentary.append(CommentaryEntry(sequence=sequence, minute=minute, text=text))
        commentary.sort(key=lambda row: row.sequence)
        return commentary

    def _parse_espn_standings(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for child in data.get("children", []):
            group_name = child.get("name") or child.get("abbreviation") or ""
            group_letter = (
                "积分榜"
                if self.is_league
                else group_name.replace("Group", "").strip()
            )
            entries = []
            for entry in (child.get("standings") or {}).get("entries", []):
                team_data = entry.get("team") or {}
                team = self._team_from_espn(team_data)
                if team.id:
                    existing = self.teams.get(team.id)
                    if existing:
                        existing.group = group_letter
                        if not existing.logo:
                            existing.logo = team.logo
                    else:
                        team.group = group_letter
                        self.teams[team.id] = team
                stats_list = entry.get("stats") or []
                stats = {
                    label: stat_value(stats_list, source_name)
                    for source_name, label in STAT_NAMES.items()
                }
                rank_text = stat_value(stats_list, "rank", "")
                try:
                    rank = int(float(rank_text))
                except ValueError:
                    rank = len(entries) + 1
                if team.id in self.teams:
                    self.teams[team.id].standing = {**stats, "rank": rank, "group": group_letter}
                entries.append({"team": self.teams.get(team.id, team), "stats": stats, "rank": rank})
            entries.sort(key=lambda row: row["rank"])
            groups.append({"name": group_letter, "entries": entries})
        return groups

    def _parse_espn_leaderboards(self, data: dict[str, Any]) -> list[Leaderboard]:
        boards: list[Leaderboard] = []
        for stat_group in data.get("stats") or []:
            board = Leaderboard(
                key=stat_group.get("name") or stat_group.get("abbreviation") or "",
                name=stat_group.get("displayName") or stat_group.get("shortDisplayName") or "榜单",
            )
            for index, leader in enumerate(stat_group.get("leaders") or [], start=1):
                athlete = leader.get("athlete") or {}
                team_data = athlete.get("team") or {}
                team_id = str(team_data.get("id") or "")
                if team_id and team_id not in self.teams:
                    self.teams[team_id] = self._team_from_espn(team_data)
                stats = extract_player_stats(athlete.get("statistics"))
                board.rows.append(
                    LeaderRow(
                        rank=index,
                        player_id=str(athlete.get("id") or ""),
                        player_name=str(
                            athlete.get("displayName")
                            or athlete.get("shortName")
                            or ""
                        ).strip(),
                        team_id=team_id,
                        team_name=team_data.get("displayName") or team_data.get("name") or "",
                        team_abbreviation=team_data.get("abbreviation") or "",
                        team_logo=pick_logo(team_data),
                        display_value=leader.get("displayValue") or leader.get("shortDisplayValue") or str(leader.get("value") or ""),
                        stats=stats,
                    )
                )
            boards.append(board)
        return boards

    def _parse_roster(self, data: dict[str, Any]) -> list[Player]:
        players: list[Player] = []
        for athlete in data.get("athletes") or []:
            birth_place = athlete.get("birthPlace") or {}
            if isinstance(birth_place, dict):
                birth_text = ", ".join(str(part) for part in [birth_place.get("city"), birth_place.get("country")] if part)
            else:
                birth_text = str(birth_place or "")
            stats = extract_player_stats(athlete.get("statistics"))
            headshot = ""
            for link in athlete.get("headshots") or []:
                headshot = link.get("href") or headshot
            position = athlete.get("position") or {}
            if isinstance(position, dict):
                position_text = position.get("displayName") or position.get("name") or ""
            else:
                position_text = str(position or "")
            players.append(
                Player(
                    id=str(athlete.get("id") or ""),
                    name=str(
                        athlete.get("displayName")
                        or athlete.get("fullName")
                        or ""
                    ).strip(),
                    short_name=str(athlete.get("shortName") or "").strip(),
                    jersey=str(athlete.get("jersey") or ""),
                    position=position_text,
                    age=str(athlete.get("age") or ""),
                    height=athlete.get("displayHeight") or "",
                    weight=athlete.get("displayWeight") or "",
                    birthplace=birth_text,
                    citizenship=athlete.get("citizenship") or "",
                    headshot=headshot,
                    stats=stats,
                )
            )
        players.sort(key=lambda p: (p.position, int(p.jersey) if p.jersey.isdigit() else 99, p.name))
        return players

    def _load_worldcup26_fallback(self, force: bool = False) -> None:
        teams_data = self.fetch_json(WORLDCUP26_TEAMS_URL, "worldcup26_teams.json", ttl_seconds=12 * 3600, force=force)
        groups_data = self.fetch_json(WORLDCUP26_GROUPS_URL, "worldcup26_groups.json", ttl_seconds=STANDINGS_TTL_SECONDS, force=force)
        games_data = self.fetch_json(WORLDCUP26_GAMES_URL, "worldcup26_games.json", ttl_seconds=SCOREBOARD_TTL_SECONDS, force=force)

        for item in teams_data.get("teams") or []:
            team = Team(
                id=str(item.get("id") or ""),
                name=item.get("name_en") or "",
                abbreviation=item.get("fifa_code") or "",
                logo=item.get("flag") or "",
                group=item.get("groups") or "",
                source="worldcup26.ir",
            )
            self.teams[team.id] = team

        self.standings = []
        for group in groups_data.get("groups") or []:
            group_entries = []
            for idx, entry in enumerate(group.get("teams") or [], start=1):
                team_id = str(entry.get("team_id") or "")
                team = self.teams.get(team_id)
                if not team:
                    continue
                stats = {
                    "赛": str(entry.get("mp", "")),
                    "胜": str(entry.get("w", "")),
                    "平": str(entry.get("d", "")),
                    "负": str(entry.get("l", "")),
                    "进": str(entry.get("gf", "")),
                    "失": str(entry.get("ga", "")),
                    "净": str(entry.get("gd", "")),
                    "分": str(entry.get("pts", "")),
                }
                rank = idx
                try:
                    rank = int(entry.get("rank", idx))
                except (TypeError, ValueError):
                    pass
                team.standing = {**stats, "rank": rank, "group": group.get("name", "")}
                group_entries.append({"team": team, "stats": stats, "rank": rank})
            group_entries.sort(key=lambda row: (-int(row["stats"].get("分") or 0), -int(row["stats"].get("净") or 0)))
            for idx, row in enumerate(group_entries, start=1):
                row["rank"] = idx
                row["team"].standing["rank"] = idx
            self.standings.append({"name": group.get("name", ""), "entries": group_entries})

        self.matches = []
        for game in games_data.get("games") or []:
            home = self.teams.get(str(game.get("home_team_id") or ""))
            away = self.teams.get(str(game.get("away_team_id") or ""))
            if not home or not away:
                continue
            elapsed = str(game.get("time_elapsed") or "")
            completed = str(game.get("finished") or "").upper() == "TRUE" or elapsed == "finished"
            status_state = "post" if completed else ("in" if elapsed not in ("notstarted", "") else "pre")
            self.matches.append(
                Match(
                    id=str(game.get("id") or ""),
                    name=f"{away.name} at {home.name}",
                    short_name=f"{away.abbreviation} @ {home.abbreviation}",
                    date=parse_datetime(game.get("local_date")),
                    round_slug="group-stage" if game.get("type") == "group" else str(game.get("type") or ""),
                    round_name="小组赛" if game.get("type") == "group" else str(game.get("type") or "赛事"),
                    group=str(game.get("group") or ""),
                    status_state=status_state,
                    status_text="完赛" if completed else ("进行中" if status_state == "in" else "未开始"),
                    completed=completed,
                    home=MatchTeam(home.id, home.name, home.abbreviation, home.logo, str(game.get("home_score") or ""), clickable=True),
                    away=MatchTeam(away.id, away.name, away.abbreviation, away.logo, str(game.get("away_score") or ""), clickable=True),
                    source="worldcup26.ir",
                )
            )
