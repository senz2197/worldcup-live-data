from __future__ import annotations

import hashlib
import ctypes
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import webbrowser
import weakref
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import colorchooser, ttk
import tkinter as tk
import tkinter.font as tkfont

from commentary_service import (
    AI_MODEL_PRESETS,
    AIRequestCredential,
    DEFAULT_AI_MODEL_PRESET,
    CommentaryService,
)
from data_provider import COMPETITIONS, CommentaryEntry, DataProvider, LeaderRow, Leaderboard, Match, MatchTeam, Player, Snapshot, Team
from localization import NameLocalizer
from news_service import FreeTranslationService, NewsItem, NewsService
from name_service import WikidataNameService
from speech_service import DEFAULT_EDGE_VOICE_ID, SpeechService


try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except Exception:  # Pillow is optional, but recommended for crisp small logos.
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageTk = None

try:
    import pystray
except Exception:
    pystray = None


BG = "#091015"
PANEL = "#101a22"
PANEL_2 = "#16232d"
PANEL_3 = "#1d2d38"
LINE = "#273946"
TEXT = "#f3fbfc"
MUTED = "#8da4b3"
ACCENT = "#22e6b8"
ACCENT_2 = "#65a7ff"
WARNING = "#ffd166"
LIVE = "#ff4d6d"
AUTO_REFRESH_MS = 15000
DEFAULT_APP_TITLE = "世界杯实时数据"
DEFAULT_ICON_CHOICE = "icon_1"
DEFAULT_UI_FONT = "Microsoft YaHei UI"
DEFAULT_SCORE_FONT = "Bahnschrift SemiBold"
APP_VERSION = "1.5.11"
GITHUB_REPOSITORY = "senz2197/worldcup-live-data"
GITHUB_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/version.json"
GITHUB_LATEST_DOWNLOAD_URL = (
    f"https://github.com/{GITHUB_REPOSITORY}/releases/latest/download/WorldCupFloat_Portable.zip"
)
PALETTE_PRESETS = {
    "codex": {
        "label": "深海青墨",
        "BG": "#0b0f14",
        "PANEL": "#111820",
        "PANEL_2": "#17212b",
        "PANEL_3": "#202b36",
        "LINE": "#2a3441",
        "TEXT": "#f4f7f8",
        "MUTED": "#8d9aa7",
        "ACCENT": "#10a37f",
        "ACCENT_2": "#7aa2ff",
        "WARNING": "#f2c94c",
        "LIVE": "#ff5370",
    },
    "graphite": {
        "label": "石墨青绿",
        "BG": "#0d1112",
        "PANEL": "#151b1d",
        "PANEL_2": "#1c2527",
        "PANEL_3": "#263235",
        "LINE": "#334145",
        "TEXT": "#f2f6f5",
        "MUTED": "#92a09d",
        "ACCENT": "#35d6a7",
        "ACCENT_2": "#8ab4ff",
        "WARNING": "#ffd36b",
        "LIVE": "#ff5c7a",
    },
    "ink": {
        "label": "墨蓝银光",
        "BG": "#080d16",
        "PANEL": "#101722",
        "PANEL_2": "#172132",
        "PANEL_3": "#202d42",
        "LINE": "#2b3a52",
        "TEXT": "#f5f7fb",
        "MUTED": "#96a3b6",
        "ACCENT": "#6ee7ff",
        "ACCENT_2": "#9b8cff",
        "WARNING": "#f7c66a",
        "LIVE": "#ff4f7b",
    },
    "atelier": {
        "label": "暖白工坊",
        "BG": "#11100d",
        "PANEL": "#1a1814",
        "PANEL_2": "#232018",
        "PANEL_3": "#2e2a20",
        "LINE": "#40392a",
        "TEXT": "#fbf6eb",
        "MUTED": "#b5aa95",
        "ACCENT": "#e8b45c",
        "ACCENT_2": "#80c7bd",
        "WARNING": "#f2cf73",
        "LIVE": "#ff6a6a",
    },
    "studio": {
        "label": "冷灰工作室",
        "BG": "#0f1115",
        "PANEL": "#171a20",
        "PANEL_2": "#20242c",
        "PANEL_3": "#2b303a",
        "LINE": "#3a414d",
        "TEXT": "#f1f3f6",
        "MUTED": "#9aa3ad",
        "ACCENT": "#9fe870",
        "ACCENT_2": "#66b7ff",
        "WARNING": "#ffd166",
        "LIVE": "#ff5a72",
    },
    "porcelain": {
        "label": "瓷白青绿",
        "BG": "#f4f7f6",
        "PANEL": "#ffffff",
        "PANEL_2": "#e9efed",
        "PANEL_3": "#dce6e2",
        "LINE": "#c6d2ce",
        "TEXT": "#17221f",
        "MUTED": "#687873",
        "ACCENT": "#168568",
        "ACCENT_2": "#496f9f",
        "WARNING": "#a76b0b",
        "LIVE": "#c94459",
    },
    "mist": {
        "label": "雾蓝纸张",
        "BG": "#f1f5f8",
        "PANEL": "#fbfdff",
        "PANEL_2": "#e6edf3",
        "PANEL_3": "#d9e3ec",
        "LINE": "#c2cfda",
        "TEXT": "#1c2730",
        "MUTED": "#687986",
        "ACCENT": "#287f77",
        "ACCENT_2": "#5075ad",
        "WARNING": "#a76c17",
        "LIVE": "#ca4b61",
    },
    "sage": {
        "label": "鼠尾草白",
        "BG": "#f3f5f0",
        "PANEL": "#fcfdf9",
        "PANEL_2": "#e8ece3",
        "PANEL_3": "#dce3d7",
        "LINE": "#c7d0c1",
        "TEXT": "#202820",
        "MUTED": "#6d796b",
        "ACCENT": "#477a61",
        "ACCENT_2": "#5f739b",
        "WARNING": "#9d6a1c",
        "LIVE": "#c64f59",
    },
    "pearl": {
        "label": "珍珠柔灰",
        "BG": "#f4f4f5",
        "PANEL": "#fdfdfd",
        "PANEL_2": "#e9e9eb",
        "PANEL_3": "#dedee1",
        "LINE": "#cacbd0",
        "TEXT": "#232429",
        "MUTED": "#70737b",
        "ACCENT": "#377b6c",
        "ACCENT_2": "#6375a5",
        "WARNING": "#a46e1d",
        "LIVE": "#c94d60",
    },
}
PALETTE_KEYS = ("BG", "PANEL", "PANEL_2", "PANEL_3", "LINE", "TEXT", "MUTED", "ACCENT", "ACCENT_2", "WARNING", "LIVE")
PALETTE_FIELD_LABELS = {
    "BG": "背景",
    "PANEL": "主面板",
    "PANEL_2": "卡片",
    "PANEL_3": "按钮",
    "LINE": "边线",
    "TEXT": "文字",
    "MUTED": "次文字",
    "ACCENT": "强调",
    "ACCENT_2": "辅助",
    "WARNING": "预告",
    "LIVE": "直播",
}
MATCH_STAT_ROWS = [
    ("totalShots", "射门"),
    ("shotsOnTarget", "射正"),
    ("wonCorners", "角球"),
    ("foulsCommitted", "犯规"),
    ("cards", "牌"),
    ("possessionPct", "控球"),
    ("goalAssists", "助攻"),
]
MAX_DATE = datetime.max.replace(tzinfo=timezone.utc)
MIN_DATE = datetime.min.replace(tzinfo=timezone.utc)
PLAYER_STAT_LABELS = {
    "APP": "出场",
    "G": "进球",
    "A": "助攻",
    "FC": "犯规",
    "FA": "被犯规",
    "RC": "红牌",
    "YC": "黄牌",
    "OG": "乌龙球",
    "SUB": "替补",
    "OF": "越位",
    "SOG": "射正",
    "SHOT": "射门",
    "SV": "扑救",
    "SHF": "被射正",
    "GA": "失球",
    "value": "数值",
}

PROFESSIONAL_BOARD_DEFS = [
    ("goalsLeaders", "射手榜", "G", True, " 球"),
    ("assistsLeaders", "助攻榜", "A", True, " 助"),
    ("goalContributions", "参与进球", "GA_TOTAL", True, " 次"),
    ("appearancesLeaders", "出场榜", "APP", True, " 场"),
    ("startsLeaders", "首发榜", "STARTS", True, " 场"),
    ("shotsLeaders", "射门榜", "SHOT", True, " 次"),
    ("shotsOnTargetLeaders", "射正榜", "SOG", True, " 次"),
    ("conversionLeaders", "射门转化率", "CONVERSION", True, "%"),
    ("foulsLeaders", "犯规榜", "FC", True, " 次"),
    ("fouledLeaders", "被犯规榜", "FA", True, " 次"),
    ("offsidesLeaders", "越位榜", "OF", True, " 次"),
    ("yellowCardsLeaders", "黄牌榜", "YC", True, " 张"),
    ("redCardsLeaders", "红牌榜", "RC", True, " 张"),
    ("savesLeaders", "扑救榜", "SV", True, " 次"),
]

OFFICIAL_LIVE_TARGETS = {
    "worldcup": [("央视体育", "https://sports.cctv.com/"), ("CCTV-5", "https://tv.cctv.com/live/cctv5/")],
    "premier_league": [("咪咕视频", "https://www.miguvideo.com/p/sports/")],
    "laliga": [("咪咕视频", "https://www.miguvideo.com/p/sports/")],
    "bundesliga": [("德甲官方转播查询", "https://www.bundesliga.com/en/bundesliga/info/broadcasters")],
    "serie_a": [("咪咕视频", "https://www.miguvideo.com/p/sports/")],
    "ligue_1": [("咪咕视频", "https://www.miguvideo.com/p/sports/")],
}


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = runtime_dir() / "config.json"
SECRETS_PATH = runtime_dir() / "secrets.json"


def enable_high_dpi_rendering() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class ImageCache:
    def __init__(self, root: tk.Tk, image_dir: Path, on_loaded=None) -> None:
        self.root = root
        self.image_dir = image_dir
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self._images: dict[tuple[str, int], tk.PhotoImage] = {}
        self._pending: set[str] = set()
        self.on_loaded = on_loaded

    def get(self, url: str, size: int = 28) -> tk.PhotoImage | None:
        if not url:
            return None
        key = (url, size)
        if key in self._images:
            return self._images[key]
        path = self._local_path(url)
        if not path.exists() or path.stat().st_size <= 0:
            self._download_async(url, path)
            return None
        try:
            if Image is not None and ImageTk is not None:
                image = Image.open(path).convert("RGBA")
                image.thumbnail((size, size), Image.Resampling.LANCZOS, reducing_gap=3.0)
                if ImageFilter is not None:
                    image = image.filter(ImageFilter.UnsharpMask(radius=0.45, percent=115, threshold=2))
                photo = ImageTk.PhotoImage(image)
            else:
                source = tk.PhotoImage(file=str(path))
                factor = max(1, min(source.width(), source.height()) // size)
                photo = source.subsample(factor, factor)
            self._images[key] = photo
            return photo
        except Exception:
            return None

    def _local_path(self, url: str) -> Path:
        suffix = Path(url.split("?", 1)[0]).suffix or ".png"
        name = hashlib.sha1(url.encode("utf-8")).hexdigest() + suffix
        return self.image_dir / name

    def _download_async(self, url: str, path: Path) -> None:
        if url in self._pending:
            return
        self._pending.add(url)

        def worker() -> None:
            ok = False
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "WorldCupFloat/0.1"})
                with urllib.request.urlopen(request, timeout=8) as response:
                    path.write_bytes(response.read())
                ok = True
            except Exception:
                pass

            def done() -> None:
                self._pending.discard(url)
                if ok and self.on_loaded is not None:
                    self.on_loaded()

            try:
                self.root.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def prefetch(self, urls: list[str]) -> None:
        for url in sorted(set(url for url in urls if url)):
            path = self._local_path(url)
            if path.exists() and path.stat().st_size > 0:
                continue
            self._download_async(url, path)


class ScrollFrame(tk.Frame):
    _instances: weakref.WeakSet = weakref.WeakSet()
    _bound_roots: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    def __init__(self, parent: tk.Widget, bg: str = BG) -> None:
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.body = tk.Frame(self.canvas, bg=bg)
        self.window_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._drag_active = False
        self._drag_start_y = 0
        self._drag_start_fraction = 0.0
        self._saved_yview = 0.0
        self._saved_yoffset = 0.0
        self._wheel_delta = 0
        self._wheel_after_id: str | None = None
        self._scroll_idle_after_id: str | None = None
        self.scroll_active = False
        ScrollFrame._instances.add(self)
        self.body.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._update_width)
        root = self._root()
        if root not in ScrollFrame._bound_roots:
            root.bind_all("<MouseWheel>", lambda event: ScrollFrame._dispatch("_on_mousewheel", event), add="+")
            root.bind_all("<ButtonPress-1>", lambda event: ScrollFrame._dispatch("_start_content_drag", event), add="+")
            root.bind_all("<B1-Motion>", lambda event: ScrollFrame._dispatch("_drag_content", event), add="+")
            root.bind_all("<ButtonRelease-1>", lambda event: ScrollFrame._dispatch("_stop_content_drag", event), add="+")
            ScrollFrame._bound_roots[root] = True

    @classmethod
    def _dispatch(cls, method_name: str, event: tk.Event):
        for frame in tuple(cls._instances):
            try:
                if frame.winfo_exists() and frame._contains_widget(event.widget):
                    return getattr(frame, method_name)(event)
            except tk.TclError:
                continue
        return None

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def begin_update(self) -> None:
        self._saved_yview = self.canvas.yview()[0]
        self._saved_yoffset = self.canvas.canvasy(0)

    def end_update(self) -> None:
        saved_yoffset = self._saved_yoffset

        def restore_yview() -> None:
            try:
                scroll_region = self.canvas.bbox("all")
                self.canvas.configure(scrollregion=scroll_region)
                if scroll_region:
                    content_height = max(1, scroll_region[3] - scroll_region[1])
                    self.canvas.yview_moveto(max(0.0, saved_yoffset - scroll_region[1]) / content_height)
            except tk.TclError:
                return

        self.after_idle(restore_yview)

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _update_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        try:
            viewable = self.winfo_viewable()
        except tk.TclError:
            return None
        if viewable and self._contains_widget(event.widget):
            self._wheel_delta += event.delta
            if self._wheel_after_id is None:
                self._wheel_after_id = self.after(16, self._flush_mousewheel)
            return "break"
        return None

    def _flush_mousewheel(self) -> None:
        self._wheel_after_id = None
        delta = self._wheel_delta
        self._wheel_delta = 0
        if not delta:
            return
        units = int(round(-delta / 120))
        if units == 0:
            units = -1 if delta > 0 else 1
        try:
            self.canvas.yview_scroll(units, "units")
            self._mark_scrolling()
        except tk.TclError:
            return

    def _contains_widget(self, widget: tk.Widget) -> bool:
        try:
            if widget.winfo_toplevel() is not self.winfo_toplevel():
                return False
            current = widget
            while current is not None:
                if current in (self.canvas, self.body):
                    return True
                current = getattr(current, "master", None)
            return False
        except tk.TclError:
            return False

    def _is_interactive_drag_widget(self, widget: tk.Widget) -> bool:
        interactive_types = (
            tk.Entry,
            tk.Text,
            tk.Listbox,
            tk.Checkbutton,
            tk.Button,
            tk.Scale,
            ttk.Combobox,
            FlatSlider,
        )
        return isinstance(widget, interactive_types)

    def _start_content_drag(self, event: tk.Event) -> None:
        try:
            viewable = self.winfo_viewable()
        except tk.TclError:
            return
        if (
            not viewable
            or not self._contains_widget(event.widget)
            or self._is_interactive_drag_widget(event.widget)
        ):
            return
        self._drag_active = True
        self._drag_start_y = event.y_root
        self._drag_start_fraction = self.canvas.yview()[0]

    def _drag_content(self, event: tk.Event) -> None:
        try:
            viewable = self.winfo_viewable()
        except tk.TclError:
            return
        if not self._drag_active or not viewable:
            return
        scroll_region = self.canvas.bbox("all")
        if not scroll_region:
            return
        content_height = max(1, scroll_region[3] - scroll_region[1])
        viewport_height = self.canvas.winfo_height()
        scrollable_height = max(0, content_height - viewport_height)
        if scrollable_height <= 0:
            return
        pointer_delta = event.y_root - self._drag_start_y
        start_offset = self._drag_start_fraction * content_height
        target_offset = max(0, min(scrollable_height, start_offset - pointer_delta))
        self.canvas.yview_moveto(target_offset / content_height)
        self._mark_scrolling()

    def _stop_content_drag(self, _event: tk.Event) -> None:
        if not self._drag_active:
            return
        self._drag_active = False

    def _mark_scrolling(self) -> None:
        self.scroll_active = True
        if self._scroll_idle_after_id is not None:
            try:
                self.after_cancel(self._scroll_idle_after_id)
            except tk.TclError:
                pass
        self._scroll_idle_after_id = self.after(180, self._finish_scrolling)

    def _finish_scrolling(self) -> None:
        self._scroll_idle_after_id = None
        self.scroll_active = False


class FlatSlider(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        variable: tk.DoubleVar,
        command,
        from_: float = 0.0,
        to: float = 1.0,
        height: int = 22,
        accent_getter=None,
    ) -> None:
        super().__init__(parent, bg=PANEL, highlightthickness=0, bd=0, height=height)
        self.variable = variable
        self.command = command
        self.from_ = from_
        self.to = to
        self.accent_getter = accent_getter or (lambda: ACCENT)
        self._dragging = False
        self._updating = False
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<ButtonPress-1>", self._set_from_event)
        self.bind("<B1-Motion>", self._set_from_event)
        self.bind("<ButtonRelease-1>", lambda _event: setattr(self, "_dragging", False))
        self.variable.trace_add("write", lambda *_args: self._draw())

    def _value_ratio(self) -> float:
        value = float(self.variable.get())
        if self.to == self.from_:
            return 0.0
        return max(0.0, min(1.0, (value - self.from_) / (self.to - self.from_)))

    def _draw(self) -> None:
        try:
            self.delete("all")
            width = max(1, self.winfo_width())
            height = max(1, self.winfo_height())
            pad = 10
            y = height // 2
            x1 = pad
            x2 = max(pad + 1, width - pad)
            handle_x = x1 + (x2 - x1) * self._value_ratio()
            self.create_line(x1, y, x2, y, fill=LINE, width=3, capstyle=tk.ROUND)
            accent = self.accent_getter()
            self.create_line(x1, y, handle_x, y, fill=accent, width=3, capstyle=tk.ROUND)
            half_w = 5
            half_h = 8
            self.create_rectangle(
                handle_x - half_w,
                y - half_h,
                handle_x + half_w,
                y + half_h,
                fill=accent,
                outline=PANEL_2,
                width=2,
            )
        except tk.TclError:
            pass

    def _set_from_event(self, event: tk.Event) -> None:
        width = max(1, self.winfo_width())
        pad = 10
        x1 = pad
        x2 = max(pad + 1, width - pad)
        ratio = max(0.0, min(1.0, (event.x - x1) / (x2 - x1)))
        value = self.from_ + ratio * (self.to - self.from_)
        self.variable.set(round(value, 2))
        self.command(float(self.variable.get()))


class WorldCupFloatApp:
    def __init__(self) -> None:
        enable_high_dpi_rendering()
        self.root = tk.Tk()
        self.ui_tasks: queue.Queue = queue.Queue()
        self.refresh_lock = threading.Lock()
        self.root.after(50, self._drain_ui_tasks)
        self.config = self._load_config()
        self.secrets = self._load_secrets()
        self.available_fonts = sorted(set(tkfont.families(self.root)), key=str.casefold)
        self.ui_font_var = tk.StringVar(value=self._valid_font_name(self.config.get("ui_font"), DEFAULT_UI_FONT))
        self.score_font_var = tk.StringVar(value=self._valid_font_name(self.config.get("score_font"), DEFAULT_SCORE_FONT))
        configured_titles = self.config.get("competition_titles")
        self.competition_titles = {
            key: str(
                (configured_titles or {}).get(key)
                or (
                    self.config.get("title")
                    if key == "worldcup"
                    else ""
                )
                or data["title"]
            )
            for key, data in COMPETITIONS.items()
        }
        self.active_competition_key = (
            self.config.get("active_competition")
            if self.config.get("active_competition") in COMPETITIONS
            else "worldcup"
        )
        self.app_title_var = tk.StringVar(
            value=self.competition_titles[self.active_competition_key]
        )
        self.palette_var = tk.StringVar(value=self._valid_palette_name(self.config.get("palette")))
        self.palette_colors = self._palette_from_config()
        self._apply_palette_values(self.palette_colors, persist=False, restyle=False)
        self.root.title(self.app_title_var.get())
        self.root.minsize(300, 360)
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.93)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.root.bind_all("<ButtonPress-1>", self._global_pointer_press, add="+")
        self.root.bind_all("<B1-Motion>", self._global_pointer_motion, add="+")
        self.root.bind_all("<ButtonRelease-1>", self._global_pointer_release, add="+")

        self.provider = DataProvider(
            competition_key=self.active_competition_key
        )
        self.commentary_service = CommentaryService(self.provider.cache_dir)
        self.news_service = NewsService(self.provider.cache_dir)
        self.free_translation_service = FreeTranslationService(self.provider.cache_dir)
        self.wikidata_name_service = WikidataNameService(self.provider.cache_dir)
        self.speech_service = SpeechService()
        self.ai_prewarm_running = False
        self.ai_prewarm_scheduled = False
        self.ai_prewarm_suppressed = False
        self.root.report_callback_exception = self._log_tk_exception
        self.images = ImageCache(self.root, self.provider.cache_dir / "images", on_loaded=self._schedule_image_refresh)
        self.localizer = NameLocalizer()
        self.name_cache_path = self.provider.cache_dir / "ai_name_localization.json"
        self.name_localization_cache = self._load_name_localization_cache()
        self.localizer.teams_by_name.update(
            self.name_localization_cache.get("teams", {})
        )
        self.localizer.players.update(
            self.name_localization_cache.get("players", {})
        )
        self.name_localization_loading: set[str] = set()
        self.snapshot: Snapshot | None = None
        self.snapshot_cache: dict[str, Snapshot] = {}
        self.active_tab = "live"
        self.round_selection: dict[str, str] = {
            "upcoming": "current",
            "results": "current",
        }
        self.favorite_teams: dict[str, str] = {
            key: str(value)
            for key, value in (
                self.config.get("favorite_teams") or {}
            ).items()
            if key in COMPETITIONS
        }
        self.team_options: dict[str, str] = {"全部球队": ""}
        self.selected_team_id = ""
        self.selected_player_id = ""
        self.active_data_board_key = ""
        self.data_board_buttons: dict[str, tk.Label] = {}
        self.rosters: dict[tuple[str, str], list[Player]] = {}
        self.roster_loaded_at: dict[tuple[str, str], float] = {}
        self.roster_errors: dict[tuple[str, str], str] = {}
        self.roster_error_at: dict[tuple[str, str], float] = {}
        self.loading_rosters: set[tuple[str, str]] = set()
        self.match_labels: dict[str, list[dict[str, object]]] = {}
        self.commentary_entries: dict[str, list[CommentaryEntry]] = {}
        self.commentary_texts: dict[str, dict[int, str]] = {}
        self.commentary_errors: dict[str, str] = {}
        self.commentary_loading: set[str] = set()
        self.commentary_ai_loading: set[str] = set()
        self.summary_texts: dict[str, str] = {}
        self.summary_errors: dict[str, str] = {}
        self.summary_loading: set[str] = set()
        self.summary_requested: set[str] = set()
        self.live_match_ids: set[str] = set()
        self.commentary_labels: dict[str, list[tk.Label]] = {}
        self.detail_commentary_panels: dict[str, tk.Frame] = {}
        self.detail_summary_labels: dict[str, tk.Label] = {}
        self.detail_commentary_snapshots: dict[str, tuple[list[CommentaryEntry], dict[int, str]]] = {}
        self.detail_commentary_loading: set[str] = set()
        self.detail_commentary_errors: dict[str, str] = {}
        self.commentary_scroll_states: dict[str, dict[str, object]] = {}
        self.live_detail_prewarmed: set[str] = set()
        self.roster_name_prewarm_running: set[str] = set()
        self.roster_name_prewarmed_at: dict[str, float] = {}
        self.match_detail_scroll: ScrollFrame | None = None
        self.standing_labels: dict[tuple[str, str], tk.Label] = {}
        self.leader_labels: dict[tuple[str, str], tk.Label] = {}
        self.rendered_signature: tuple | None = None
        self.tab_rendered_signatures: dict[str, tuple] = {}
        self.image_refresh_pending = False
        self.image_refresh_after_id: str | None = None
        self.render_in_progress = False
        self.tab_switching = False
        self.pending_snapshot: tuple[Snapshot, bool] | None = None
        self.pending_snapshot_after_id: str | None = None
        self.window_visible = True
        self.context_menu: tk.Menu | None = None
        self.settings_popup: tk.Toplevel | None = None
        self.competition_popup: tk.Toplevel | None = None
        self.api_help_popup: tk.Toplevel | None = None
        self.player_popup: tk.Toplevel | None = None
        self.player_popup_body: tk.Widget | None = None
        self.player_popup_player_id = ""
        self.club_popup: tk.Toplevel | None = None
        self.club_popup_body: tk.Widget | None = None
        self.club_source_player: Player | None = None
        self.news_popup: tk.Toplevel | None = None
        self.match_popup: tk.Toplevel | None = None
        self.match_popup_match_id = ""
        self.match_popup_mode = ""
        self.match_popup_opening = False
        self.match_notification_popup: tk.Toplevel | None = None
        self.match_notification_ids: set[str] = set()
        self.notified_live_match_ids: set[str] = set()
        self.tray_icon = None
        self.drag_origin = (0, 0)
        self.drag_target: tk.Tk | tk.Toplevel | None = None
        self.pointer_origin = (0, 0)
        self.pointer_dragged = False
        self.popups_at_pointer_press: list[tk.Toplevel] = []
        self.popup_back_stack: list = []
        self.resize_origin = (0, 0, 0, 0)
        self.header_frame: tk.Frame | None = None
        self.title_box: tk.Frame | None = None
        self.title_label: tk.Label | None = None
        self.status_label: tk.Label | None = None
        self.competition_button: tk.Label | None = None
        self.quick_refresh_button: tk.Label | None = None
        self.tab_bar: tk.Frame | None = None
        self.tab_button_order: list[str] = []
        self.data_board_button_order: list[str] = []
        self.theme_color_var = tk.StringVar(value=self._valid_color(self.config.get("theme_color"), ACCENT))
        self.icon_choice_var = tk.StringVar(value=self._valid_icon_choice(self.config.get("icon_choice")))
        self.palette_colors["ACCENT"] = self.theme_color_var.get()
        self._apply_palette_values(self.palette_colors, persist=False, restyle=False)
        self.icon_images: dict[str, tk.PhotoImage] = {}
        self.icon_photo = self._make_tk_icon(64)
        if self.icon_photo is not None:
            try:
                self.root.iconphoto(True, self.icon_photo)
            except tk.TclError:
                pass
        self.root.after(400, self._sync_shell_icon)

        self.status_var = tk.StringVar(value="准备同步赛事数据")
        self.last_status_text = "准备同步赛事数据"
        self.team_var = tk.StringVar(value="全部球队")
        self.alpha_var = tk.DoubleVar(value=float(self.config.get("alpha", 0.93)))
        self.topmost_var = tk.BooleanVar(value=bool(self.config.get("topmost", True)))
        self.use_english_var = tk.BooleanVar(value=bool(self.config.get("use_english", False)))
        self.quick_refresh_var = tk.BooleanVar(value=bool(self.config.get("quick_refresh", False)))
        self.show_status_var = tk.BooleanVar(value=bool(self.config.get("show_status", False)))
        self.show_live_labels_var = tk.BooleanVar(value=bool(self.config.get("show_live_labels", True)))
        self.title_alignment_var = tk.StringVar(
            value="left" if self.config.get("title_alignment") == "left" else "center"
        )
        preferred_alignment = str(
            self.config.get("title_alignment_preference")
            or self.title_alignment_var.get()
        )
        self.title_preferred_alignment = (
            "left"
            if preferred_alignment == "left"
            else "center"
        )
        self.title_alignment_var.set(self.title_preferred_alignment)
        self.match_notifications_var = tk.BooleanVar(value=bool(self.config.get("match_notifications", True)))
        self.ai_commentary_var = tk.BooleanVar(value=bool(self.config.get("ai_commentary", True)))
        self.ai_translate_raw_var = tk.BooleanVar(value=bool(self.config.get("ai_translate_raw", False)))
        if self.ai_commentary_var.get() and self.ai_translate_raw_var.get():
            self.ai_translate_raw_var.set(False)
        self.commentary_lines_var = tk.IntVar(value=self._valid_commentary_lines(self.config.get("commentary_lines"), 3))
        self.tts_enabled_var = tk.BooleanVar(value=bool(self.config.get("tts_enabled", False)))
        self.tts_voice_var = tk.StringVar(value=str(self.config.get("tts_voice") or DEFAULT_EDGE_VOICE_ID))
        self.tts_rate_var = tk.IntVar(value=int(self.config.get("tts_rate") or 185))
        self.speech_voices = self.speech_service.voices()
        self.spoken_commentary_sequences: dict[str, int] = {}
        self.professional_boards_cache: dict[str, list[Leaderboard]] = {}
        self.professional_boards_loaded_at: dict[str, float] = {}
        self.professional_boards_loading: set[str] = set()
        self.professional_board_seasons: dict[str, set[int]] = {}
        self.news_items: dict[str, list[NewsItem]] = {}
        self.news_loading: set[str] = set()
        self.news_queue: deque[
            tuple[str, bool, int, object, str]
        ] = deque()
        self.news_queued: set[str] = set()
        self.news_queue_lock = threading.Lock()
        self.news_worker_running = False
        self.news_active_key = ""
        configured_model = str(
            self.config.get("ai_model_preset")
            or DEFAULT_AI_MODEL_PRESET
        )
        self.active_ai_model_preset = (
            configured_model
            if configured_model in AI_MODEL_PRESETS
            else DEFAULT_AI_MODEL_PRESET
        )
        stored_keys = self.secrets.get("ai_api_keys") or {}
        self.ai_api_keys = {
            key: str(stored_keys.get(key) or "")
            for key in AI_MODEL_PRESETS
        }
        if not self.ai_api_keys["agnes"]:
            self.ai_api_keys["agnes"] = str(
                self.secrets.get("agnes_api_key") or ""
            )
        self.ai_model_var = tk.StringVar(
            value=self.active_ai_model_preset
        )
        self.ai_model_name_var = tk.StringVar(
            value=str(
                AI_MODEL_PRESETS[
                    self.active_ai_model_preset
                ]["label"]
            )
        )
        self.agnes_api_key_var = tk.StringVar(
            value=self.ai_api_keys.get(
                self.active_ai_model_preset,
                "",
            )
        )
        self.commentary_service.configure_model(
            self.active_ai_model_preset
        )
        self.tencent_translate_secret_id_var = tk.StringVar(
            value=str(
                self.secrets.get("tencent_translate_secret_id")
                or ""
            )
        )
        self.tencent_translate_secret_key_var = tk.StringVar(
            value=str(
                self.secrets.get("tencent_translate_secret_key")
                or ""
            )
        )
        self.free_translation_service.configure_tencent(
            self.tencent_translate_secret_id_var.get(),
            self.tencent_translate_secret_key_var.get(),
        )
        self.translation_status_var = tk.StringVar(
            value=(
                "腾讯云翻译已配置，将在 MyMemory 失败时接管"
                if self.tencent_translate_secret_id_var.get().strip()
                and self.tencent_translate_secret_key_var.get().strip()
                else "MyMemory 为首选；未配置腾讯云备用翻译"
            )
        )
        self.ai_status_var = tk.StringVar(value="AI 已启用" if self.agnes_api_key_var.get().strip() else "未设置 API Key，将显示原始数据")
        self.ai_cache_status_var = tk.StringVar(value=self._ai_cache_status_text())
        self.live_refresh_seconds_var = tk.IntVar(value=self._valid_seconds(self.config.get("live_refresh_seconds"), 5))
        self.default_refresh_seconds_var = tk.IntVar(value=self._valid_seconds(self.config.get("default_refresh_seconds"), 300))
        self.roster_refresh_hours_var = tk.IntVar(value=max(1, min(168, int(self.config.get("roster_refresh_hours") or 24))))
        self.news_weeks_var = tk.IntVar(value=max(1, min(12, int(self.config.get("news_weeks") or 1))))
        self.free_translate_var = tk.BooleanVar(value=bool(self.config.get("free_translate", True)))
        self.update_status_var = tk.StringVar(value=f"当前版本 {APP_VERSION}")
        self.root.attributes("-alpha", max(0.72, min(1.0, float(self.alpha_var.get()))))
        self.root.attributes("-topmost", self.topmost_var.get())

        self.tabs: dict[str, ScrollFrame] = {}
        self.tab_buttons: dict[str, tk.Label] = {}
        self._position_initial_window()
        self._build_shell()
        self._apply_fonts_to_tree(self.root)
        self._build_context_menu()
        self._start_tray_icon()
        self.root.after(50, self._mark_as_tool_window)
        self.refresh_data(force=False, quiet=False)
        self.root.after(120, self._queue_startup_news)
        self.auto_refresh_after_id: str | None = None
        self._schedule_next_refresh()
        self.root.after(1600, self._commentary_poll)
        self.root.after(60 * 60 * 1000, self._maintain_ai_cache)

    def run(self) -> None:
        self.root.mainloop()

    def _post_ui(self, callback) -> None:
        self.ui_tasks.put(callback)

    def _drain_ui_tasks(self) -> None:
        for _ in range(32):
            try:
                callback = self.ui_tasks.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception:
                traceback.print_exc()
        try:
            delay = 10 if not self.ui_tasks.empty() else 50
            self.root.after(delay, self._drain_ui_tasks)
        except tk.TclError:
            pass

    def _load_config(self) -> dict[str, str]:
        if not CONFIG_PATH.exists():
            return {}
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_secrets(self) -> dict[str, str]:
        if not SECRETS_PATH.exists():
            return {}
        try:
            data = json.loads(SECRETS_PATH.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_name_localization_cache(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(
                self.name_cache_path.read_text(encoding="utf-8")
            )
            return {
                "teams": dict(data.get("teams") or {}),
                "players": dict(data.get("players") or {}),
            }
        except Exception:
            return {"teams": {}, "players": {}}

    def _save_name_localization_cache(self) -> None:
        try:
            self.name_cache_path.write_text(
                json.dumps(
                    self.name_localization_cache,
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _save_secrets(self) -> None:
        try:
            if hasattr(self, "active_ai_model_preset"):
                self.ai_api_keys[self.active_ai_model_preset] = (
                    self.agnes_api_key_var.get().strip()
                )
            SECRETS_PATH.write_text(
                json.dumps(
                    {
                        "agnes_api_key": self.ai_api_keys.get(
                            "agnes",
                            "",
                        ),
                        "ai_api_keys": self.ai_api_keys,
                        "tencent_translate_secret_id": (
                            self.tencent_translate_secret_id_var.get().strip()
                        ),
                        "tencent_translate_secret_key": (
                            self.tencent_translate_secret_key_var.get().strip()
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _save_config(self) -> None:
        try:
            current_title = (
                self.app_title_var.get().strip()
                or str(COMPETITIONS[self.active_competition_key]["title"])
            )
            self.app_title_var.set(current_title)
            self.competition_titles[self.active_competition_key] = current_title
            palette = {key: self._valid_color(self.palette_colors.get(key), PALETTE_PRESETS["codex"][key]) for key in PALETTE_KEYS}
            CONFIG_PATH.write_text(
                json.dumps(
                    {
                        "title": current_title,
                        "active_competition": self.active_competition_key,
                        "competition_titles": self.competition_titles,
                        "favorite_teams": self.favorite_teams,
                        "theme_color": self._valid_color(self.theme_color_var.get(), ACCENT),
                        "icon_choice": self._valid_icon_choice(self.icon_choice_var.get()),
                        "palette": self._valid_palette_name(self.palette_var.get()),
                        "custom_palette": palette,
                        "quick_refresh": bool(self.quick_refresh_var.get()) if hasattr(self, "quick_refresh_var") else False,
                        "show_status": bool(self.show_status_var.get()) if hasattr(self, "show_status_var") else False,
                        "show_live_labels": bool(self.show_live_labels_var.get()) if hasattr(self, "show_live_labels_var") else True,
                        "title_alignment": self.title_alignment_var.get() if hasattr(self, "title_alignment_var") else "center",
                        "title_alignment_preference": self.title_preferred_alignment if hasattr(self, "title_preferred_alignment") else "center",
                        "match_notifications": bool(self.match_notifications_var.get()) if hasattr(self, "match_notifications_var") else True,
                        "ai_commentary": bool(self.ai_commentary_var.get()) if hasattr(self, "ai_commentary_var") else True,
                        "ai_model_preset": self.active_ai_model_preset if hasattr(self, "active_ai_model_preset") else DEFAULT_AI_MODEL_PRESET,
                        "ai_translate_raw": bool(self.ai_translate_raw_var.get()) if hasattr(self, "ai_translate_raw_var") else False,
                        "free_translate": bool(self.free_translate_var.get()) if hasattr(self, "free_translate_var") else True,
                        "commentary_lines": self._valid_commentary_lines(self.commentary_lines_var.get(), 3) if hasattr(self, "commentary_lines_var") else 3,
                        "tts_enabled": bool(self.tts_enabled_var.get()) if hasattr(self, "tts_enabled_var") else False,
                        "tts_voice": self.tts_voice_var.get() if hasattr(self, "tts_voice_var") else "",
                        "tts_rate": max(120, min(260, int(self.tts_rate_var.get()))) if hasattr(self, "tts_rate_var") else 185,
                        "topmost": bool(self.topmost_var.get()) if hasattr(self, "topmost_var") else True,
                        "use_english": bool(self.use_english_var.get()) if hasattr(self, "use_english_var") else False,
                        "alpha": round(float(self.alpha_var.get()), 2) if hasattr(self, "alpha_var") else 0.93,
                        "window_geometry": self.root.geometry() if hasattr(self, "root") else "",
                        "live_refresh_seconds": self._valid_seconds(self.live_refresh_seconds_var.get(), 5) if hasattr(self, "live_refresh_seconds_var") else 5,
                        "default_refresh_seconds": self._valid_seconds(self.default_refresh_seconds_var.get(), 300) if hasattr(self, "default_refresh_seconds_var") else 300,
                        "roster_refresh_hours": max(1, min(168, int(self.roster_refresh_hours_var.get()))) if hasattr(self, "roster_refresh_hours_var") else 24,
                        "news_weeks": max(1, min(12, int(self.news_weeks_var.get()))) if hasattr(self, "news_weeks_var") else 1,
                        "ui_font": self._valid_font_name(self.ui_font_var.get(), DEFAULT_UI_FONT) if hasattr(self, "ui_font_var") else DEFAULT_UI_FONT,
                        "score_font": self._valid_font_name(self.score_font_var.get(), DEFAULT_SCORE_FONT) if hasattr(self, "score_font_var") else DEFAULT_SCORE_FONT,
                    },
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _close_settings(self) -> None:
        self._save_config()
        self._save_secrets()
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.destroy()
        self.settings_popup = None

    def _close_api_help(self) -> None:
        if self.api_help_popup is not None and self.api_help_popup.winfo_exists():
            self.api_help_popup.destroy()
        self.api_help_popup = None

    def _close_competition_popup(self) -> None:
        if (
            self.competition_popup is not None
            and self.competition_popup.winfo_exists()
        ):
            self.competition_popup.destroy()
        self.competition_popup = None

    def _close_player_popup(self) -> None:
        if self.player_popup is not None and self.player_popup.winfo_exists():
            self.player_popup.destroy()
        self.player_popup = None
        self.player_popup_body = None
        self.player_popup_player_id = ""

    def _close_club_popup(self) -> None:
        if self.club_popup is not None and self.club_popup.winfo_exists():
            self.club_popup.destroy()
        self.club_popup = None
        self.club_popup_body = None

    def _close_news_popup(self) -> None:
        if self.news_popup is not None and self.news_popup.winfo_exists():
            self.news_popup.destroy()
        self.news_popup = None

    def _valid_color(self, value: str | None, fallback: str = ACCENT) -> str:
        value = str(value or "").strip()
        if len(value) == 7 and value.startswith("#"):
            try:
                int(value[1:], 16)
                return value.lower()
            except ValueError:
                pass
        return fallback

    def _contrast_text_color(self, color: str) -> str:
        color = self._valid_color(color, PANEL_2)
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        return "#101418" if luminance >= 155 else "#f7fafb"

    def _valid_seconds(self, value, fallback: int) -> int:
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(3, min(seconds, 3600))

    def _valid_commentary_lines(self, value, fallback: int = 3) -> int:
        try:
            lines = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(1, min(lines, 8))

    def _season_label(
        self,
        season_year: int | None = None,
        snapshot: Snapshot | None = None,
        competition_key: str = "",
    ) -> str:
        snapshot = snapshot or self.snapshot
        year = int(
            season_year
            or (snapshot.season_year if snapshot is not None else 0)
            or 0
        )
        if year <= 0:
            return "赛季待定"
        if competition_key in COMPETITIONS:
            is_league = COMPETITIONS[competition_key].get("kind") == "league"
        else:
            is_league = bool(
                snapshot
                and snapshot.competition_kind == "league"
            )
        if is_league:
            return f"{year}-{str(year + 1)[-2:]} 赛季"
        return f"{year} 赛季"

    def _valid_font_name(self, value: str | None, fallback: str) -> str:
        value = str(value or "").strip()
        if value in self.available_fonts:
            return value
        if fallback in self.available_fonts:
            return fallback
        return self.available_fonts[0] if self.available_fonts else "TkDefaultFont"

    def _font_spec(self, widget: tk.Widget, family: str):
        try:
            actual = tkfont.Font(root=self.root, font=widget.cget("font")).actual()
        except (tk.TclError, TypeError):
            return None
        styles = [actual.get("weight", "normal"), actual.get("slant", "roman")]
        if actual.get("underline"):
            styles.append("underline")
        if actual.get("overstrike"):
            styles.append("overstrike")
        return (family, int(actual.get("size", 9)), *styles)

    def _apply_fonts_to_tree(self, widget: tk.Widget) -> None:
        try:
            widget.cget("font")
        except tk.TclError:
            pass
        else:
            family = self.score_font_var.get() if getattr(widget, "_worldcup_score_font", False) else self.ui_font_var.get()
            spec = self._font_spec(widget, family)
            if spec is not None:
                try:
                    widget.configure(font=spec)
                except tk.TclError:
                    pass
        for child in widget.winfo_children():
            self._apply_fonts_to_tree(child)

    def _apply_font_settings(self, *_args) -> None:
        self.ui_font_var.set(self._valid_font_name(self.ui_font_var.get(), DEFAULT_UI_FONT))
        self.score_font_var.set(self._valid_font_name(self.score_font_var.get(), DEFAULT_SCORE_FONT))
        self._apply_fonts_to_tree(self.root)
        for popup in (
            self.settings_popup,
            self.competition_popup,
            self.api_help_popup,
            self.player_popup,
            self.club_popup,
            self.news_popup,
            self.match_popup,
            self.match_notification_popup,
        ):
            if popup is not None and popup.winfo_exists():
                self._apply_fonts_to_tree(popup)
        for label_sets in self.match_labels.values():
            for labels in label_sets:
                header = labels.get("_header")
                align_header = getattr(
                    header,
                    "_worldcup_align_header",
                    None,
                )
                if callable(align_header):
                    try:
                        header.after_idle(align_header)
                    except tk.TclError:
                        pass
        self.root.after_idle(self._ensure_title_alignment_fits)
        self._save_config()

    def _valid_palette_name(self, value: str | None) -> str:
        value = str(value or "").strip()
        if value in PALETTE_PRESETS or value == "custom":
            return value
        return "atelier"

    def _palette_from_config(self) -> dict[str, str]:
        name = self._valid_palette_name(self.config.get("palette"))
        if name == "custom":
            source = self.config.get("custom_palette")
            if not isinstance(source, dict):
                source = PALETTE_PRESETS["codex"]
        else:
            source = PALETTE_PRESETS.get(name, PALETTE_PRESETS["codex"])
        palette = {key: self._valid_color(source.get(key), PALETTE_PRESETS["codex"][key]) for key in PALETTE_KEYS}
        if self.config.get("theme_color"):
            palette["ACCENT"] = self._valid_color(self.config.get("theme_color"), palette["ACCENT"])
        return palette

    def _apply_palette_values(self, palette: dict[str, str], persist: bool = True, restyle: bool = True) -> None:
        global BG, PANEL, PANEL_2, PANEL_3, LINE, TEXT, MUTED, ACCENT, ACCENT_2, WARNING, LIVE
        old = {key: globals()[key] for key in PALETTE_KEYS if key in globals()}
        clean = {key: self._valid_color(palette.get(key), PALETTE_PRESETS["codex"][key]) for key in PALETTE_KEYS}
        BG = clean["BG"]
        PANEL = clean["PANEL"]
        PANEL_2 = clean["PANEL_2"]
        PANEL_3 = clean["PANEL_3"]
        LINE = clean["LINE"]
        TEXT = clean["TEXT"]
        MUTED = clean["MUTED"]
        ACCENT = clean["ACCENT"]
        ACCENT_2 = clean["ACCENT_2"]
        WARNING = clean["WARNING"]
        LIVE = clean["LIVE"]
        self.palette_colors = clean
        if hasattr(self, "theme_color_var"):
            self.theme_color_var.set(ACCENT)
        if restyle and hasattr(self, "root"):
            self._restyle_widget_tree(self.root, old, clean)
            if self.settings_popup is not None and self.settings_popup.winfo_exists():
                self._restyle_widget_tree(self.settings_popup, old, clean)
            if self.match_notification_popup is not None and self.match_notification_popup.winfo_exists():
                self._restyle_widget_tree(self.match_notification_popup, old, clean)
            if self.api_help_popup is not None and self.api_help_popup.winfo_exists():
                self._restyle_widget_tree(self.api_help_popup, old, clean)
            if (
                self.competition_popup is not None
                and self.competition_popup.winfo_exists()
            ):
                self._restyle_widget_tree(self.competition_popup, old, clean)
            if self.player_popup is not None and self.player_popup.winfo_exists():
                self._restyle_widget_tree(self.player_popup, old, clean)
            if self.club_popup is not None and self.club_popup.winfo_exists():
                self._restyle_widget_tree(self.club_popup, old, clean)
            if self.news_popup is not None and self.news_popup.winfo_exists():
                self._restyle_widget_tree(self.news_popup, old, clean)
            self._configure_fonts()
            self._invalidate_render_cache()
            self.render_active()
        if persist:
            self._save_config()

    def _invalidate_render_cache(self, tab: str | None = None) -> None:
        if tab is None:
            self.tab_rendered_signatures.clear()
        else:
            self.tab_rendered_signatures.pop(tab, None)

    def _restyle_widget_tree(self, widget: tk.Widget, old: dict[str, str], new: dict[str, str]) -> None:
        color_map = {old[key]: new[key] for key in PALETTE_KEYS if key in old and key in new}
        for option in ("bg", "fg", "activebackground", "activeforeground", "selectcolor", "highlightbackground", "insertbackground"):
            try:
                current = str(widget.cget(option))
            except tk.TclError:
                continue
            if current in color_map:
                try:
                    widget.configure(**{option: color_map[current]})
                except tk.TclError:
                    pass
        for child in widget.winfo_children():
            self._restyle_widget_tree(child, old, new)

    def _set_global_accent(self, value: str) -> None:
        self.palette_colors["ACCENT"] = self._valid_color(value, ACCENT)
        self._apply_palette_values(self.palette_colors, persist=False, restyle=False)

    def _valid_icon_choice(self, value: str | None) -> str:
        value = str(value or "").strip()
        if value in {f"icon_{index}" for index in range(1, 6)}:
            return value
        return DEFAULT_ICON_CHOICE

    def _app_icon_dirs(self) -> list[Path]:
        return [
            runtime_dir() / "assets" / "app_icons",
            Path(__file__).resolve().parent / "assets" / "app_icons",
        ]

    def _app_icon_path(self, choice: str | None = None) -> Path | None:
        choice = self._valid_icon_choice(choice or self.icon_choice_var.get())
        for directory in self._app_icon_dirs():
            path = directory / f"{choice}.png"
            if path.exists():
                return path
        return None

    def _apply_title(self) -> None:
        title = self.app_title_var.get().strip() or DEFAULT_APP_TITLE
        self.app_title_var.set(title)
        self.competition_titles[self.active_competition_key] = title
        self.root.title(title)
        if self.tray_icon is not None:
            try:
                self.tray_icon.title = title
            except Exception:
                pass
        self.root.after_idle(self._ensure_title_alignment_fits)
        self._save_config()

    def _apply_theme_color(self) -> None:
        color = self._valid_color(self.theme_color_var.get(), ACCENT)
        self.theme_color_var.set(color)
        self.palette_colors["ACCENT"] = color
        self.palette_var.set("custom")
        self._apply_palette_values(self.palette_colors, persist=True, restyle=True)
        self._refresh_language()
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.destroy()
            self.settings_popup = None
            self.open_settings()

    def _choose_theme_color(self) -> None:
        _rgb, color = colorchooser.askcolor(color=self.theme_color_var.get(), parent=self.settings_popup or self.root)
        if color:
            self.theme_color_var.set(color.lower())
            self._apply_theme_color()

    def _apply_palette_choice(self, _event: tk.Event | None = None) -> None:
        name = self._valid_palette_name(self.palette_var.get())
        if name == "custom":
            source = self.palette_colors
        else:
            source = PALETTE_PRESETS[name]
        self._apply_palette_values(dict(source), persist=True, restyle=True)
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.destroy()
            self.settings_popup = None
            self.open_settings()

    def _choose_palette_color(self, key: str) -> None:
        _rgb, color = colorchooser.askcolor(color=self.palette_colors.get(key, ACCENT), parent=self.settings_popup or self.root)
        if not color:
            return
        self.palette_var.set("custom")
        self.palette_colors[key] = color.lower()
        if key == "ACCENT":
            self.theme_color_var.set(color.lower())
        self._apply_palette_values(self.palette_colors, persist=True, restyle=True)
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.destroy()
            self.settings_popup = None
            self.open_settings()

    def _save_custom_palette(self) -> None:
        self.palette_var.set("custom")
        self._apply_palette_values(self.palette_colors, persist=True, restyle=True)

    def _toggle_quick_refresh(self) -> None:
        self._save_config()
        self._apply_quick_refresh_visibility()

    def _toggle_status_visibility(self) -> None:
        self._save_config()
        if not self.show_status_var.get():
            self.status_var.set("")
        self._apply_status_visibility()

    def _set_title_alignment(self, value: str) -> None:
        selected = "left" if value == "left" else "center"
        self.title_preferred_alignment = selected
        self.title_alignment_var.set(selected)
        self._apply_title_alignment()
        self._save_config()

    def _apply_title_alignment(self) -> None:
        if self.title_label is None or self.status_label is None:
            return
        centered = self.title_alignment_var.get() != "left"
        anchor = "center" if centered else "w"
        justify = "center" if centered else "left"
        self.title_label.configure(anchor=anchor, justify=justify)
        self.status_label.configure(anchor=anchor, justify=justify)
        self._layout_header_controls()
        self._update_title_wrap_reserve()
        if centered:
            self.root.after_idle(self._ensure_title_alignment_fits)

    def _title_control_reserve(self) -> int:
        # Controls occupy dedicated mirrored grid columns and never overlap the
        # title's own layout area.
        return 0

    def _update_title_wrap_reserve(self) -> None:
        if self.title_label is None:
            return
        self.title_label._worldcup_wrap_reserve = 0

    def _ensure_title_alignment_fits(
        self,
        _event: tk.Event | None = None,
    ) -> None:
        if (
            self.title_label is None
            or self.title_box is None
        ):
            return
        if self.title_preferred_alignment != "center":
            if self.title_alignment_var.get() != "left":
                self.title_alignment_var.set("left")
                self._apply_title_alignment()
                self._save_config()
            self._set_title_font_size(17)
            return
        width = self.title_box.winfo_width()
        if width <= 1:
            return
        available = width - self._title_control_reserve() * 2
        selected_size = 17
        for size in range(17, 10, -1):
            try:
                font = tkfont.Font(
                    root=self.root,
                    family=self.ui_font_var.get(),
                    size=size,
                    weight="bold",
                )
                required = font.measure(self.app_title_var.get())
            except tk.TclError:
                return
            if required <= max(24, available):
                selected_size = size
                break
        else:
            selected_size = 11
        self._set_title_font_size(selected_size)
        if self.title_alignment_var.get() != "center":
            self.title_alignment_var.set("center")
            self._apply_title_alignment()
            self._save_config()

    def _set_title_font_size(self, size: int) -> None:
        if self.title_label is None:
            return
        try:
            self.title_label.configure(
                font=(
                    self.ui_font_var.get(),
                    size,
                    "bold",
                )
            )
        except tk.TclError:
            pass

    def _toggle_match_notifications(self) -> None:
        self._save_config()
        if not self.match_notifications_var.get():
            self._close_match_notification()
            return
        if self.snapshot:
            self.root.after(120, lambda: self._maybe_show_match_notification(self.snapshot, include_seen=True) if self.snapshot else None)

    def _toggle_live_labels(self) -> None:
        self._save_config()
        self._invalidate_render_cache("live")
        self._invalidate_render_cache("upcoming")
        if self.active_tab in {"live", "upcoming"}:
            self.render_active()

    def _apply_quick_refresh_visibility(self) -> None:
        if self.quick_refresh_button is None:
            return
        self._layout_header_controls()
        self._update_title_wrap_reserve()
        self.root.after_idle(self._ensure_title_alignment_fits)

    def _layout_header_controls(self) -> None:
        if (
            self.header_frame is None
            or self.quick_refresh_button is None
            or self.competition_button is None
        ):
            return
        centered = self.title_alignment_var.get() != "left"
        quick_visible = self.quick_refresh_var.get()
        # Keep the title's left and right reserves symmetric even when the
        # optional refresh control is hidden.
        left_width = 22 if centered else 0
        right_refresh_width = 22 if not centered and quick_visible else 0
        self.header_frame.columnconfigure(0, minsize=left_width)
        self.header_frame.columnconfigure(1, weight=1)
        self.header_frame.columnconfigure(
            2,
            minsize=right_refresh_width,
        )
        self.header_frame.columnconfigure(3, minsize=22)
        if quick_visible:
            self.quick_refresh_button.grid(
                row=0,
                column=0 if centered else 2,
                padx=(0, 0) if centered else (0, 5),
            )
        else:
            self.quick_refresh_button.grid_remove()
        self.competition_button.grid(
            row=0,
            column=3,
        )

    def _apply_status_visibility(self) -> None:
        if self.status_label is None:
            return
        if self.show_status_var.get():
            self.status_var.set(self.last_status_text)
            if not self.status_label.winfo_manager():
                self.status_label.grid(
                    row=1,
                    column=0,
                    columnspan=4,
                    sticky="ew",
                    pady=(2, 0),
                )
        else:
            self.status_label.grid_remove()

    def _save_refresh_settings(self, *_args) -> None:
        self.live_refresh_seconds_var.set(self._valid_seconds(self.live_refresh_seconds_var.get(), 5))
        self.default_refresh_seconds_var.set(self._valid_seconds(self.default_refresh_seconds_var.get(), 300))
        self.roster_refresh_hours_var.set(max(1, min(168, int(self.roster_refresh_hours_var.get() or 24))))
        self.professional_boards_loaded_at.clear()
        self.professional_board_seasons.clear()
        self.roster_loaded_at.clear()
        self._save_config()
        self._schedule_next_refresh()

    def _save_news_settings(self, *_args) -> None:
        self.news_weeks_var.set(max(1, min(12, int(self.news_weeks_var.get() or 1))))
        self.news_items.clear()
        self._invalidate_render_cache("news")
        self._save_config()
        self._load_news(
            self.active_competition_key,
            priority=True,
        )
        if self.active_tab == "news" and self.snapshot:
            self.render_news()

    def _save_tts_settings(self, *_args) -> None:
        self.tts_rate_var.set(max(120, min(260, int(self.tts_rate_var.get() or 185))))
        if not self.tts_enabled_var.get():
            self.speech_service.stop()
        self._save_config()

    def _preview_tts_voice(self) -> None:
        self.speech_service.speak(
            "禁区前沿突然起脚，皮球直挂死角，漂亮的进球！",
            self.tts_voice_var.get(),
            self.tts_rate_var.get(),
        )

    def _save_commentary_settings(self, *_args) -> None:
        self.commentary_lines_var.set(self._valid_commentary_lines(self.commentary_lines_var.get(), 3))
        self._save_config()
        self._save_secrets()
        if self.active_tab == "live":
            self._invalidate_render_cache("live")
            self.render_active()
        else:
            self._update_all_commentary_labels()
        if self.snapshot:
            self._refresh_live_commentary(self.snapshot, force=True)

    def _toggle_ai_commentary(self) -> None:
        if self.ai_commentary_var.get():
            self.ai_translate_raw_var.set(False)
        self._save_config()
        self.commentary_texts.clear()
        self._update_all_commentary_labels()
        if self.snapshot and (self.ai_commentary_var.get() or self.ai_translate_raw_var.get()):
            self._refresh_live_commentary(self.snapshot, force=True)

    def _toggle_raw_translation(self) -> None:
        if self.ai_translate_raw_var.get():
            self.ai_commentary_var.set(False)
        self._save_config()
        self.commentary_texts.clear()
        self._update_all_commentary_labels()
        if not self.ai_commentary_var.get() and self.ai_translate_raw_var.get() and self.snapshot:
            self._refresh_live_commentary(self.snapshot, force=True)

    def _toggle_free_translation(self) -> None:
        self._save_config()
        self.commentary_texts.clear()
        self._update_all_commentary_labels()
        if self.snapshot:
            self._refresh_live_commentary(self.snapshot, force=True)

    def _test_agnes_connection(self) -> None:
        raw_key = self.agnes_api_key_var.get().strip()
        self._save_config()
        self._save_secrets()
        if not raw_key:
            self.ai_status_var.set("请先填写 AI API Key")
            return
        key = AIRequestCredential(
            raw_key,
            self.active_ai_model_preset,
        )
        self.ai_status_var.set("正在测试 AI 连接...")

        def worker() -> None:
            try:
                result = self.commentary_service.test(key)
                status = "AI 连接成功" if result else "AI 返回为空"
            except Exception as exc:
                status = f"连接失败：{exc}"
            self._post_ui(lambda text=status: self.ai_status_var.set(text))

        threading.Thread(target=worker, daemon=True).start()

    def _current_ai_credential(
        self,
    ) -> AIRequestCredential | str:
        key = self.agnes_api_key_var.get().strip()
        if not key:
            return ""
        return AIRequestCredential(
            key,
            self.active_ai_model_preset,
        )

    def _select_ai_model(
        self,
        _event: tk.Event | None = None,
    ) -> None:
        selected_label = self.ai_model_name_var.get()
        selected = next(
            (
                key
                for key, preset in AI_MODEL_PRESETS.items()
                if preset["label"] == selected_label
            ),
            DEFAULT_AI_MODEL_PRESET,
        )
        self.ai_api_keys[self.active_ai_model_preset] = (
            self.agnes_api_key_var.get().strip()
        )
        self.active_ai_model_preset = selected
        self.ai_model_var.set(selected)
        self.commentary_service.configure_model(selected)
        self.agnes_api_key_var.set(
            self.ai_api_keys.get(selected, "")
        )
        self.ai_status_var.set(
            "AI 已启用"
            if self.agnes_api_key_var.get().strip()
            else "请填写当前模型对应的 API Key"
        )
        self._save_config()
        self._save_secrets()

    def _save_translation_credentials(
        self,
        *_args,
    ) -> None:
        secret_id = (
            self.tencent_translate_secret_id_var.get().strip()
        )
        secret_key = (
            self.tencent_translate_secret_key_var.get().strip()
        )
        self.free_translation_service.configure_tencent(
            secret_id,
            secret_key,
        )
        self.translation_status_var.set(
            "腾讯云翻译已配置，将在 MyMemory 失败时接管"
            if secret_id and secret_key
            else "MyMemory 为首选；未配置腾讯云备用翻译"
        )
        self._save_secrets()

    def _test_translation_connection(self) -> None:
        self._save_translation_credentials()
        if not (
            self.tencent_translate_secret_id_var.get().strip()
            and self.tencent_translate_secret_key_var.get().strip()
        ):
            self.translation_status_var.set(
                "请先填写腾讯云 SecretId 与 SecretKey"
            )
            return
        self.translation_status_var.set("正在测试腾讯云翻译...")

        def worker() -> None:
            try:
                text = (
                    self.free_translation_service._translate_tencent(
                        "football match"
                    )
                )
                status = (
                    "腾讯云翻译连接成功"
                    if text
                    else "腾讯云翻译返回为空"
                )
            except Exception as exc:
                status = f"腾讯云翻译连接失败：{exc}"
            self._post_ui(
                lambda current=status:
                self.translation_status_var.set(current)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _open_api_help(self) -> None:
        if self.api_help_popup is not None and self.api_help_popup.winfo_exists():
            self.api_help_popup.lift()
            return
        self._prepare_single_popup(back_action=self.open_settings)
        popup = tk.Toplevel(self.root)
        self.api_help_popup = popup
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.98)
        width = min(350, max(300, self.root.winfo_width() - 8))
        height = min(
            540,
            max(400, self.root.winfo_screenheight() - 120),
        )
        x = min(
            max(8, self.root.winfo_x() + 14),
            max(8, self.root.winfo_screenwidth() - width - 8),
        )
        y = min(
            max(8, self.root.winfo_y() + 48),
            max(8, self.root.winfo_screenheight() - height - 48),
        )
        popup.geometry(f"{width}x{height}+{x}+{y}")
        popup.bind(
            "<Destroy>",
            lambda event, current=popup:
            setattr(self, "api_help_popup", None)
            if event.widget is current and self.api_help_popup is current else None,
            add="+",
        )

        header = tk.Frame(popup, bg=PANEL, padx=12, pady=9)
        header.pack(fill="x")
        title = tk.Label(
            header,
            text="如何获取免费模型 API Key",
            bg=PANEL,
            fg=TEXT,
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        title.pack(side="left")
        close = tk.Label(
            header,
            text="×",
            bg=PANEL,
            fg=MUTED,
            cursor="hand2",
            font=("Microsoft YaHei UI", 13, "bold"),
        )
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_and_restore(self._close_api_help))
        self._bind_drag(header)
        self._bind_drag(title)

        scroll = ScrollFrame(popup, bg=PANEL)
        scroll.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 10),
        )
        body = scroll.body

        def add_guide(
            heading: str,
            text: str,
            link_text: str,
            url: str,
        ) -> None:
            card = tk.Frame(
                body,
                bg=PANEL_2,
                padx=10,
                pady=9,
                highlightthickness=1,
                highlightbackground=LINE,
            )
            card.pack(fill="x", pady=4)
            heading_label = tk.Label(
                card,
                text=heading,
                bg=PANEL_2,
                fg=ACCENT,
                anchor="nw",
                justify="left",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            heading_label.pack(fill="x")
            self._bind_wrap(
                heading_label,
                reserve=20,
                minimum=220,
                maximum=310,
            )
            guide = tk.Label(
                card,
                text=text,
                bg=PANEL_2,
                fg=TEXT,
                anchor="nw",
                justify="left",
                font=("Microsoft YaHei UI", 8),
            )
            guide.pack(fill="x", pady=(5, 7))
            self._bind_wrap(
                guide,
                reserve=20,
                minimum=220,
                maximum=310,
            )
            link = tk.Label(
                card,
                text=link_text,
                bg=PANEL_3,
                fg=ACCENT,
                cursor="hand2",
                anchor="center",
                padx=8,
                pady=6,
                font=("Microsoft YaHei UI", 8, "bold"),
            )
            link.pack(fill="x")
            self._bind_click(
                link,
                lambda _event, target=url:
                webbrowser.open(target),
            )

        add_guide(
            "Agnes · agnes-2.0-flash（默认首选）",
            "注册或登录 Agnes，进入 API Key 管理页面创建 Key。"
            "在设置中选择 Agnes 模型，粘贴 Key 后点击测试。",
            "打开 Agnes AI 平台",
            "https://platform.agnes-ai.com/",
        )
        add_guide(
            "智谱 GLM · glm-4.7-flash",
            "注册智谱开放平台，进入 API Keys 页面创建 Key。"
            "在设置中选择 GLM-4.7-Flash 并粘贴该 Key。"
            "该预设会自动指定 glm-4.7-flash，并关闭深度思考以降低实时延迟。",
            "打开智谱开放平台",
            "https://open.bigmodel.cn/usercenter/apikeys",
        )
        add_guide(
            "腾讯云机器翻译（MyMemory 失败时备用）",
            "在腾讯云访问管理中创建仅授予机器翻译权限的子用户密钥，"
            "把 SecretId 与 SecretKey 填入设置。软件始终先使用 MyMemory，"
            "只有其失败、限流或返回为空时才调用腾讯云大陆节点。"
            "不要使用主账号全权限密钥。",
            "打开腾讯云 API 密钥管理",
            "https://console.cloud.tencent.com/cam/capi",
        )
        self._apply_fonts_to_tree(popup)

    def _ai_cache_status_text(self, prefix: str = "") -> str:
        info = self.commentary_service.cache_info()
        size = info["bytes"]
        if size >= 1024 * 1024:
            size_text = f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            size_text = f"{size / 1024:.0f} KB"
        else:
            size_text = f"{size} B"
        detail = f"已缓存 {info['matches']} 场 · {size_text} · 自动保留 7 天"
        return f"{prefix}{detail}" if prefix else detail

    def _refresh_ai_cache_status(self, prefix: str = "") -> None:
        self.ai_cache_status_var.set(self._ai_cache_status_text(prefix))

    def _clear_ai_cache(self) -> None:
        self.ai_prewarm_suppressed = True
        self.commentary_service.clear_cache()
        self.commentary_texts.clear()
        self.detail_commentary_snapshots.clear()
        self.detail_commentary_errors.clear()
        self.summary_texts.clear()
        self.summary_errors.clear()
        self._refresh_ai_cache_status("已清除 · ")
        self._update_all_commentary_labels()
        if self.snapshot:
            self._refresh_live_commentary(self.snapshot, force=False)
        if self.match_popup is not None and self.match_popup.winfo_exists():
            self._close_match_popup()

    def _maintain_ai_cache(self) -> None:
        removed = self.commentary_service.prune_expired_cache()
        self._refresh_ai_cache_status(f"已自动清理 {removed} 场 · " if removed else "")
        try:
            self.root.after(60 * 60 * 1000, self._maintain_ai_cache)
        except tk.TclError:
            pass

    def _schedule_recent_ai_prewarm(self, snapshot: Snapshot) -> None:
        if (
            self.ai_prewarm_running
            or self.ai_prewarm_scheduled
            or self.ai_prewarm_suppressed
            or not self.agnes_api_key_var.get().strip()
            or not self.ai_commentary_var.get()
            or any(match.is_live for match in snapshot.matches)
        ):
            return
        completed = [match for match in snapshot.matches if match.completed]
        completed.sort(key=lambda match: match.date or MIN_DATE, reverse=True)
        candidates = completed[:3]
        if not candidates:
            return
        self.ai_prewarm_scheduled = True

        def start() -> None:
            self.ai_prewarm_scheduled = False
            if self.ai_prewarm_suppressed or self.ai_prewarm_running:
                return
            self.ai_prewarm_running = True
            generation = self.commentary_service.cache_generation
            api_key = self._current_ai_credential()

            def worker() -> None:
                rendered = 0
                try:
                    for match in candidates:
                        if (
                            generation != self.commentary_service.cache_generation
                            or self.ai_prewarm_suppressed
                            or self.detail_commentary_loading
                            or self.summary_loading
                        ):
                            break
                        entries, _detail, error = self.provider.get_match_commentary(
                            match.id,
                            live=False,
                            force=False,
                        )
                        if error or not entries:
                            continue
                        timeline_ready = self.commentary_service.has_complete_timeline(
                            match.id,
                            entries,
                        )
                        summary_ready = bool(
                            self.commentary_service.summary(
                                match.id,
                                self.commentary_service.summary_signature(match, entries),
                            )
                        )
                        if timeline_ready and summary_ready:
                            continue
                        if not timeline_ready:
                            self.commentary_service.translate_complete_timeline(
                                match,
                                entries,
                                api_key,
                            )
                        if generation != self.commentary_service.cache_generation:
                            break
                        if not summary_ready:
                            self.commentary_service.summarize_match(
                                match,
                                entries,
                                api_key,
                            )
                        rendered += 1
                        self._post_ui(
                            lambda count=rendered:
                            self._refresh_ai_cache_status(f"后台已预渲染 {count} 场 · ")
                        )
                except Exception as exc:
                    message = self._friendly_commentary_error(exc)
                    self._post_ui(lambda text=message: self.ai_cache_status_var.set(text))
                finally:
                    self._post_ui(self._finish_ai_prewarm)

            threading.Thread(target=worker, daemon=True).start()

        self.root.after(15000, start)

    def _finish_ai_prewarm(self) -> None:
        self.ai_prewarm_running = False
        self._refresh_ai_cache_status()

    def _schedule_roster_name_prewarm(self, snapshot: Snapshot) -> None:
        competition_key = snapshot.competition_key
        last_loaded = self.roster_name_prewarmed_at.get(competition_key, 0.0)
        if (
            competition_key in self.roster_name_prewarm_running
            or time.time() - last_loaded < self.roster_refresh_hours_var.get() * 3600
        ):
            return
        self.roster_name_prewarm_running.add(competition_key)
        provider = DataProvider(
            cache_dir=self.provider.cache_dir,
            competition_key=competition_key,
        )
        provider.teams = snapshot.teams
        provider.season_year = snapshot.season_year
        provider.season_name = snapshot.season_name
        teams = list(snapshot.teams.values())
        roster_ttl_hours = self.roster_refresh_hours_var.get()

        def load_team(team: Team) -> tuple[str, list[Player]]:
            players, _error = provider.get_roster(
                team.id,
                season_year=snapshot.season_year,
                ttl_hours=roster_ttl_hours,
            )
            return team.id, players

        def worker() -> None:
            loaded: dict[tuple[str, str], list[Player]] = {}
            names: list[str] = []
            try:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    for team_id, players in executor.map(load_team, teams):
                        if not players:
                            continue
                        loaded[self._roster_key(team_id, competition_key)] = players
                        names.extend(player.name for player in players if player.name)
            finally:
                self._post_ui(
                    lambda rows=loaded, player_names=names, key=competition_key:
                    self._apply_roster_name_prewarm(key, rows, player_names)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _apply_roster_name_prewarm(
        self,
        competition_key: str,
        rosters: dict[tuple[str, str], list[Player]],
        names: list[str],
    ) -> None:
        self.roster_name_prewarm_running.discard(competition_key)
        self.roster_name_prewarmed_at[competition_key] = time.time()
        now = time.time()
        for roster_key, players in rosters.items():
            self.rosters[roster_key] = players
            self.roster_loaded_at[roster_key] = now
        missing = [
            name
            for name in dict.fromkeys(names)
            if self.localizer.player(name) == name
        ]
        if missing:
            self._request_name_localization("player", missing)

    def _version_tuple(self, value: str) -> tuple[int, ...]:
        parts = []
        for part in str(value).strip().lstrip("vV").split("."):
            digits = "".join(character for character in part if character.isdigit())
            parts.append(int(digits or 0))
        return tuple(parts)

    def _check_for_updates(self) -> None:
        if self.update_status_var.get().startswith("正在"):
            return
        self.update_status_var.set("正在检查 GitHub 最新版本...")

        def worker() -> None:
            try:
                request = urllib.request.Request(
                    GITHUB_VERSION_URL,
                    headers={"User-Agent": f"WorldCupFloat/{APP_VERSION}"},
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    version_info = json.loads(response.read().decode("utf-8"))
                latest = str(version_info.get("version") or "").lstrip("vV")
                if not latest:
                    raise RuntimeError("GitHub 未返回版本号")
                if self._version_tuple(latest) <= self._version_tuple(APP_VERSION):
                    self._post_ui(lambda: self.update_status_var.set(f"已是最新版 {APP_VERSION}"))
                    return
                self._post_ui(lambda current=latest: self.update_status_var.set(f"正在下载版本 {current}..."))
                update_dir = Path(tempfile.mkdtemp(prefix="worldcup_update_"))
                archive_path = update_dir / "WorldCupFloat_Portable.zip"
                download = urllib.request.Request(
                    str(version_info.get("download_url") or GITHUB_LATEST_DOWNLOAD_URL),
                    headers={"User-Agent": f"WorldCupFloat/{APP_VERSION}"},
                )
                with urllib.request.urlopen(download, timeout=60) as response, archive_path.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                if not zipfile.is_zipfile(archive_path):
                    raise RuntimeError("下载的更新包无效")
                self._post_ui(
                    lambda path=archive_path, current=latest: self._install_downloaded_update(path, current)
                )
            except Exception as exc:
                message = str(exc) or "未知错误"
                self._post_ui(lambda detail=message: self.update_status_var.set(f"更新失败：{detail}"))

        threading.Thread(target=worker, daemon=True).start()

    def _install_downloaded_update(self, archive_path: Path, latest: str) -> None:
        if not getattr(sys, "frozen", False):
            self.update_status_var.set(f"已下载 {latest}，开发模式不自动替换")
            return
        target_exe = Path(sys.executable).resolve()
        target_dir = target_exe.parent
        script_path = archive_path.parent / "install_update.ps1"
        script = r"""
param(
    [int]$ProcessId,
    [string]$Archive,
    [string]$TargetDirectory,
    [string]$ExecutableName
)
$ErrorActionPreference = "Stop"
Wait-Process -Id $ProcessId -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 700
$extract = Join-Path ([System.IO.Path]::GetTempPath()) ("worldcup_extract_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $extract | Out-Null
Expand-Archive -LiteralPath $Archive -DestinationPath $extract -Force
$newExe = Get-ChildItem -LiteralPath $extract -Recurse -Filter $ExecutableName | Select-Object -First 1
if (-not $newExe) { throw "Updated executable was not found." }
$source = $newExe.Directory.FullName
Get-ChildItem -LiteralPath $source | ForEach-Object {
    if ($_.Name -notin @("config.json", "secrets.json")) {
        Copy-Item -LiteralPath $_.FullName -Destination $TargetDirectory -Recurse -Force
    }
}

Start-Process -FilePath (Join-Path $TargetDirectory $ExecutableName) -WorkingDirectory $TargetDirectory
Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
"""
        script_path.write_text(script.strip() + "\n", encoding="utf-8-sig")
        self.update_status_var.set(f"正在安装版本 {latest}，软件即将重启...")
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-ProcessId",
                str(os.getpid()),
                "-Archive",
                str(archive_path),
                "-TargetDirectory",
                str(target_dir),
                "-ExecutableName",
                target_exe.name,
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.root.after(300, self.exit_app)

    def _apply_icon_choice(self, choice: str | None = None) -> None:
        if choice is not None:
            self.icon_choice_var.set(self._valid_icon_choice(choice))
        else:
            self.icon_choice_var.set(self._valid_icon_choice(self.icon_choice_var.get()))
        self.icon_photo = self._make_tk_icon(64)
        if self.icon_photo is not None:
            try:
                self.root.iconphoto(True, self.icon_photo)
            except tk.TclError:
                pass
        if self.tray_icon is not None:
            try:
                self.tray_icon.icon = self._tray_image()
            except Exception:
                pass
        self._save_config()
        self._sync_shell_icon()
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            x = self.settings_popup.winfo_x()
            y = self.settings_popup.winfo_y()
            self.settings_popup.destroy()
            self.settings_popup = None
            self.open_settings()
            if self.settings_popup is not None:
                self.settings_popup.geometry(f"+{x}+{y}")

    def _sync_shell_icon(self) -> None:
        if Image is None or not sys.platform.startswith("win"):
            return
        image = self._make_icon_image(256)
        if image is None:
            return
        icon_path = runtime_dir() / "selected_app_icon.ico"
        try:
            image.save(
                icon_path,
                format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
            if not getattr(sys, "frozen", False):
                return
            target = Path(sys.executable).resolve()
            working_dir = target.parent
            title = self.app_title_var.get().strip() or DEFAULT_APP_TITLE
            escaped_target = str(target).replace("'", "''")
            escaped_working = str(working_dir).replace("'", "''")
            escaped_icon = str(icon_path).replace("'", "''")
            escaped_title = title.replace("'", "''")
            script = (
                "$desktop=[Environment]::GetFolderPath('Desktop');"
                f"$link=Join-Path $desktop '{escaped_title}.lnk';"
                "$w=New-Object -ComObject WScript.Shell;"
                "$s=$w.CreateShortcut($link);"
                f"$s.TargetPath='{escaped_target}';"
                f"$s.WorkingDirectory='{escaped_working}';"
                f"$s.IconLocation='{escaped_icon},0';"
                f"$s.Description='{escaped_title}';"
                "$s.Save()"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=8,
                check=False,
            )
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass

    def _make_icon_image(self, size: int = 64):
        if Image is None:
            return None
        icon_path = self._app_icon_path() if hasattr(self, "icon_choice_var") else None
        if icon_path is not None:
            try:
                source = self._normalized_icon_source(icon_path)
                source.thumbnail((size, size), Image.Resampling.LANCZOS)
                image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                image.alpha_composite(source, ((size - source.width) // 2, (size - source.height) // 2))
                return image
            except Exception:
                pass
        if ImageDraw is None:
            return None
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        inset = max(3, size // 14)
        draw.rounded_rectangle((inset, inset, size - inset, size - inset), radius=size // 4, fill=(9, 16, 21, 245))
        ring = max(3, size // 18)
        draw.ellipse((inset + ring, inset + ring, size - inset - ring, size - inset - ring), fill=(243, 251, 252, 255))
        cx = cy = size // 2
        ball_r = size // 2 - inset - ring
        draw.polygon(
            [
                (cx, cy - ball_r // 2),
                (cx + ball_r // 2, cy - ball_r // 7),
                (cx + ball_r // 3, cy + ball_r // 2),
                (cx - ball_r // 3, cy + ball_r // 2),
                (cx - ball_r // 2, cy - ball_r // 7),
            ],
            fill=(16, 26, 34, 255),
        )
        for x1, y1, x2, y2 in [
            (cx, cy - ball_r // 2, cx, cy - ball_r),
            (cx + ball_r // 2, cy - ball_r // 7, cx + ball_r, cy - ball_r // 4),
            (cx + ball_r // 3, cy + ball_r // 2, cx + ball_r // 2, cy + ball_r),
            (cx - ball_r // 3, cy + ball_r // 2, cx - ball_r // 2, cy + ball_r),
            (cx - ball_r // 2, cy - ball_r // 7, cx - ball_r, cy - ball_r // 4),
        ]:
            draw.line((x1, y1, x2, y2), fill=(16, 26, 34, 255), width=max(2, size // 22))
        draw.arc((inset + 5, inset + 5, size - inset - 5, size - inset - 5), 36, 140, fill=(34, 230, 184, 255), width=max(3, size // 18))
        return image

    def _normalized_icon_source(self, path: Path):
        image = Image.open(path).convert("RGBA")
        pixels = image.load()
        width, height = image.size
        bbox = image.getbbox()
        if not bbox:
            return image
        left, top, right, bottom = bbox
        visited: set[tuple[int, int]] = set()
        remove: set[tuple[int, int]] = set()

        def is_side_white(x: int, y: int) -> bool:
            r, g, b, a = pixels[x, y]
            return a > 8 and r > 232 and g > 232 and b > 232

        band = 10
        seeds: list[tuple[int, int]] = []
        for y in range(top, bottom):
            for x in list(range(left, min(left + band, right))) + list(range(max(left, right - band), right)):
                if is_side_white(x, y):
                    seeds.append((x, y))
        for seed in seeds:
            if seed in visited:
                continue
            queue = deque([seed])
            visited.add(seed)
            component: list[tuple[int, int]] = []
            min_x = max_x = seed[0]
            touches_side = False
            while queue:
                x, y = queue.popleft()
                component.append((x, y))
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                if x <= left + band or x >= right - band - 1:
                    touches_side = True
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nx < left or nx >= right or ny < top or ny >= bottom or (nx, ny) in visited:
                        continue
                    if is_side_white(nx, ny):
                        visited.add((nx, ny))
                        queue.append((nx, ny))
            component_width = max_x - min_x + 1
            if touches_side and (component_width <= 14 or len(component) < (right - left) * (bottom - top) * 0.035):
                remove.update(component)
        for x, y in remove:
            pixels[x, y] = (255, 255, 255, 0)
        bbox = image.getbbox()
        if bbox:
            image = image.crop(bbox)
        return image

    def _make_tk_icon(self, size: int = 64):
        image = self._make_icon_image(size)
        if image is None or ImageTk is None:
            return None
        return ImageTk.PhotoImage(image)

    def _bind_wrap(self, label: tk.Label, reserve: int = 0, minimum: int = 80, maximum: int = 900) -> tk.Label:
        parent = label.master
        state = {"wraplength": None, "after_id": None}
        try:
            # A long requested label width can expand a ScrollFrame body beyond
            # the viewport before wrapping is applied. Let the geometry manager
            # allocate the real width first, then wrap inside that allocation.
            label.configure(width=1)
        except tk.TclError:
            pass

        def update(event: tk.Event | None = None) -> None:
            state["after_id"] = None
            try:
                if not label.winfo_exists():
                    return
                label_width = (
                    event.width
                    if event is not None and event.widget == label
                    else label.winfo_width()
                )
                extra_reserve = int(
                    getattr(label, "_worldcup_wrap_reserve", 0)
                )
                if label_width > 1:
                    available = max(
                        24,
                        label_width - 6 - extra_reserve,
                    )
                else:
                    parent_width = (
                        event.width
                        if event is not None and event.widget == parent
                        else parent.winfo_width()
                    )
                    available = max(24, parent_width - reserve - 12)
                if label_width <= 1 and parent.winfo_width() <= 1:
                    if state["after_id"] is None:
                        state["after_id"] = label.after(50, update)
                    return
                wraplength = min(maximum, available)
                if state["wraplength"] == wraplength:
                    return
                state["wraplength"] = wraplength
                label.configure(wraplength=wraplength)
            except tk.TclError:
                return

        parent.bind("<Configure>", update, add="+")
        label.bind("<Configure>", update, add="+")
        label.after_idle(update)
        return label

    def _bind_click_tree(
        self,
        widget: tk.Widget,
        command,
        cursor: str = "hand2",
    ) -> None:
        targets = [widget]
        targets.extend(self._widget_descendants(widget))
        for target in targets:
            try:
                target.configure(cursor=cursor)
                self._bind_click(target, command)
            except tk.TclError:
                continue

    @staticmethod
    def _widget_descendants(widget: tk.Widget) -> list[tk.Widget]:
        result: list[tk.Widget] = []
        pending = list(widget.winfo_children())
        while pending:
            current = pending.pop()
            result.append(current)
            pending.extend(current.winfo_children())
        return result

    def _roster_key(
        self,
        team_id: str,
        competition_key: str | None = None,
    ) -> tuple[str, str]:
        return (competition_key or self.active_competition_key, str(team_id))

    def _log_tk_exception(self, exc_type, exc_value, exc_tb) -> None:
        log_path = self.provider.cache_dir.parent / "worldcup_error.log"
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("\n--- Tk callback exception ---\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
        except Exception:
            pass

    def _schedule_image_refresh(self) -> None:
        if not self.snapshot:
            return
        self.image_refresh_pending = True
        if self.image_refresh_after_id is not None:
            try:
                self.root.after_cancel(self.image_refresh_after_id)
            except tk.TclError:
                pass
        self.image_refresh_after_id = self.root.after(350, self._refresh_images)

    def _refresh_images(self) -> None:
        self.image_refresh_after_id = None
        self.image_refresh_pending = False
        if self.snapshot and self.root.state() != "withdrawn":
            active_frame = self.tabs.get(self.active_tab)
            if active_frame is not None and active_frame.scroll_active:
                self.image_refresh_pending = True
                self.image_refresh_after_id = self.root.after(220, self._refresh_images)
                return
            self._invalidate_render_cache(self.active_tab)
            self.render_active()

    def _team_text(self, team: Team | MatchTeam | LeaderRow) -> str:
        name = getattr(team, "name", "") or getattr(team, "team_name", "")
        abbreviation = getattr(team, "abbreviation", "") or getattr(team, "team_abbreviation", "")
        return self.localizer.team(name, abbreviation, english=False)

    def _player_text(self, name: str, player_id: str = "") -> str:
        return self.localizer.player(name, player_id=player_id, english=self.use_english_var.get())

    def _position_text(self, name: str) -> str:
        return self.localizer.position(name, english=False)

    def _board_text(self, key: str, fallback: str) -> str:
        return self.localizer.board(key, fallback, english=False)

    def _stat_label(self, key: str) -> str:
        return PLAYER_STAT_LABELS.get(key, key)

    def _team_option_text(self, team: Team) -> str:
        return f"{team.abbreviation or team.name} · {self._team_text(team)}"

    def _all_logo_urls(self, snapshot: Snapshot) -> list[str]:
        urls = [team.logo for team in snapshot.teams.values() if team.logo]
        for match in snapshot.matches:
            urls.extend([match.home.logo, match.away.logo])
        for board in snapshot.leaderboards:
            urls.extend([row.team_logo for row in board.rows if row.team_logo])
        return urls

    def _position_initial_window(self) -> None:
        saved_geometry = str(self.config.get("window_geometry") or "")
        if saved_geometry and "x" in saved_geometry:
            try:
                self.root.geometry(saved_geometry)
                return
            except tk.TclError:
                pass
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(360, max(300, screen_w // 4))
        height = min(590, max(420, screen_h - 140))
        x = max(20, self.root.winfo_screenwidth() - width - 82)
        y = max(20, self.root.winfo_screenheight() - height - 104)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _compact_geometry(self) -> str:
        width = min(360, max(300, self.root.winfo_screenwidth() // 4))
        height = min(560, max(430, self.root.winfo_screenheight() - 160))
        return f"{width}x{height}"

    def _apply_window_preset(self, geometry: str) -> None:
        self.root.geometry(geometry)

        def refresh_layout() -> None:
            try:
                self.root.update_idletasks()
                self._relayout_match_headers()
                self.root.update_idletasks()
                self._save_config()
            except tk.TclError:
                return

        self.root.after(40, refresh_layout)
        self.root.after(160, refresh_layout)

    def _relayout_match_headers(self) -> None:
        frame = self.tabs.get(self.active_tab)
        if frame is None:
            return

        def visit(widget: tk.Widget) -> None:
            callback = getattr(widget, "_worldcup_align_header", None)
            if callback is not None:
                try:
                    callback()
                except tk.TclError:
                    pass
            for child in widget.winfo_children():
                visit(child)

        visit(frame)

    def _mark_as_tool_window(self) -> None:
        if not sys.platform.startswith("win"):
            return
        try:
            hwnd = self.root.winfo_id()
            gwl_exstyle = -20
            ws_ex_toolwindow = 0x00000080
            ws_ex_appwindow = 0x00040000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
            style = (style | ws_ex_toolwindow) & ~ws_ex_appwindow
            ctypes.windll.user32.SetWindowLongW(hwnd, gwl_exstyle, style)
        except Exception:
            pass

    def _build_shell(self) -> None:
        self._configure_fonts()
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=14, pady=(12, 6))
        header.columnconfigure(0, minsize=0)
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, minsize=0)
        header.columnconfigure(3, minsize=22)
        self.header_frame = header
        self.root.bind("<Button-3>", self._show_context_menu)

        title_box = tk.Frame(header, bg=BG)
        title_box.grid(row=0, column=1, sticky="ew")
        self.title_box = title_box
        title_box.bind(
            "<Configure>",
            self._ensure_title_alignment_fits,
            add="+",
        )
        quick_refresh = tk.Label(
            header,
            text="↻",
            bg=BG,
            fg=ACCENT,
            padx=0,
            pady=0,
            cursor="hand2",
            font=("Microsoft YaHei UI", 9, "bold"),
            highlightthickness=0,
            bd=0,
        )
        self._bind_click(quick_refresh, lambda _event: self.refresh_data(force=True, quiet=True))
        self.quick_refresh_button = quick_refresh
        title_label = tk.Label(
            title_box,
            textvariable=self.app_title_var,
            bg=BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 17, "bold"),
        )
        title_label.pack(fill="x")
        competition_button = tk.Label(
            header,
            text="▾",
            bg=BG,
            fg=ACCENT,
            cursor="hand2",
            padx=0,
            pady=0,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        competition_button.grid(row=0, column=3)
        self._bind_click(
            competition_button,
            lambda _event: self._open_competition_popup(),
        )
        self.title_label = title_label
        self.competition_button = competition_button
        self._bind_wrap(title_label, reserve=34, minimum=120, maximum=260)
        status_label = tk.Label(
            header,
            textvariable=self.status_var,
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        )
        status_label.grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(2, 0),
        )
        self.status_label = status_label
        self._bind_wrap(status_label, reserve=12, minimum=120, maximum=260)
        self._apply_status_visibility()
        self._apply_title_alignment()
        self._apply_quick_refresh_visibility()
        for widget in (header, title_label, status_label):
            self._bind_drag(widget)

        controls = tk.Frame(self.root, bg=BG)
        self.team_combo = ttk.Combobox(
            controls,
            textvariable=self.team_var,
            state="readonly",
            style="WorldCup.TCombobox",
            width=1,
            values=["全部球队"],
        )
        self.team_combo.bind("<<ComboboxSelected>>", self._on_team_select)

        tab_bar = tk.Frame(self.root, bg=BG)
        tab_bar.pack(fill="x", padx=14, pady=(0, 8))
        self.tab_bar = tab_bar
        tab_defs = [
            ("live", "直播"),
            ("upcoming", "预告"),
            ("results", "赛果"),
            ("standings", "积分"),
            ("bracket", "淘汰"),
            ("data", "榜单"),
            ("news", "资讯"),
            ("team", "球队"),
        ]
        for key, label in tab_defs:
            btn = tk.Label(
                tab_bar,
                text=label,
                bg=PANEL if key == self.active_tab else BG,
                fg=ACCENT if key == self.active_tab else MUTED,
                padx=2,
                pady=6,
                cursor="hand2",
                font=("Microsoft YaHei UI", 8, "bold"),
            )
            self._bind_click(btn, lambda _event, tab=key: self.select_tab(tab))
            self.tab_buttons[key] = btn
            self.tab_button_order.append(key)
        tab_bar.bind("<Configure>", self._layout_tab_buttons, add="+")
        self.root.after_idle(self._layout_tab_buttons)

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        for key, _label in tab_defs:
            frame = ScrollFrame(content, bg=BG)
            self.tabs[key] = frame
            if key == self.active_tab:
                frame.pack(fill="both", expand=True)
        self._update_tab_visibility()

        grip = tk.Frame(self.root, bg=BG, cursor="size_nw_se", width=18, height=18)
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<ButtonPress-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._resize_window)

    def _visible_tab_keys(self) -> list[str]:
        return [
            key
            for key in self.tab_button_order
            if not (
                key == "bracket"
                and self.active_competition_key != "worldcup"
            )
        ]

    def _update_tab_visibility(self) -> None:
        visible = set(self._visible_tab_keys())
        for key, button in self.tab_buttons.items():
            if key not in visible:
                button.grid_remove()
        if self.active_tab not in visible:
            self.active_tab = "live"
        for key, frame in self.tabs.items():
            if key == self.active_tab:
                if not frame.winfo_manager():
                    frame.pack(fill="both", expand=True)
            elif frame.winfo_manager():
                frame.pack_forget()
        for key, button in self.tab_buttons.items():
            active = key == self.active_tab
            button.configure(
                bg=PANEL if active else BG,
                fg=ACCENT if active else MUTED,
            )
        self._layout_tab_buttons()

    def _open_competition_popup(self) -> None:
        if (
            self.competition_popup is not None
            and self.competition_popup.winfo_exists()
        ):
            self._close_competition_popup()
            return
        self._prepare_single_popup(clear_history=True)
        popup = tk.Toplevel(self.root)
        self.competition_popup = popup
        popup.overrideredirect(True)
        popup.configure(bg=LINE)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.98)
        width = min(230, max(190, self.root.winfo_width() - 40))
        height = 6 * 40 + 48
        x = min(
            self.root.winfo_x() + self.root.winfo_width() - width - 12,
            self.root.winfo_screenwidth() - width - 8,
        )
        y = min(
            self.root.winfo_y() + 48,
            self.root.winfo_screenheight() - height - 48,
        )
        popup.geometry(f"{width}x{height}+{max(8, x)}+{max(8, y)}")
        shell = tk.Frame(
            popup,
            bg=PANEL,
            padx=6,
            pady=6,
            highlightthickness=1,
            highlightbackground=LINE,
        )
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        header = tk.Frame(shell, bg=PANEL, padx=8, pady=5)
        header.pack(fill="x")
        title = tk.Label(
            header,
            text="切换赛事",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        title.pack(side="left")
        close = tk.Label(
            header,
            text="×",
            bg=PANEL,
            fg=MUTED,
            cursor="hand2",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        close.pack(side="right")
        self._bind_click(
            close,
            lambda _event: self._close_competition_popup(),
        )
        for key, data in COMPETITIONS.items():
            active = key == self.active_competition_key
            row = tk.Label(
                shell,
                text=str(data["name"]),
                bg=PANEL_3 if active else PANEL,
                fg=ACCENT if active else TEXT,
                anchor="w",
                cursor="hand2",
                padx=10,
                pady=8,
                font=("Microsoft YaHei UI", 9, "bold" if active else "normal"),
            )
            row.pack(fill="x", pady=1)
            self._bind_click(
                row,
                lambda _event, current=key:
                self._switch_competition(current),
            )
        self._apply_fonts_to_tree(popup)

    def _switch_competition(self, competition_key: str) -> None:
        if competition_key not in COMPETITIONS:
            return
        self._close_competition_popup()
        if competition_key == self.active_competition_key:
            return
        self.competition_titles[self.active_competition_key] = (
            self.app_title_var.get().strip()
            or str(COMPETITIONS[self.active_competition_key]["title"])
        )
        self.active_competition_key = competition_key
        self.provider.set_competition(competition_key)
        self._load_news(competition_key, priority=True)
        self.app_title_var.set(self.competition_titles[competition_key])
        self.root.title(self.app_title_var.get())
        if self.tray_icon is not None:
            try:
                self.tray_icon.title = self.app_title_var.get()
            except Exception:
                pass
        self.selected_team_id = self.favorite_teams.get(competition_key, "")
        self.selected_player_id = ""
        self.team_var.set("全部球队")
        self.round_selection = {
            "upcoming": "current",
            "results": "current",
        }
        self._close_all_popups()
        self._update_tab_visibility()
        self._invalidate_render_cache()
        cached = self.snapshot_cache.get(competition_key)
        if cached is not None:
            self.provider.teams = cached.teams
            self.provider.matches = cached.matches
            self.provider.standings = cached.standings
            self.provider.leaderboards = cached.leaderboards
            self.provider.last_snapshot = cached
            self.provider.season_year = cached.season_year
            self.provider.season_name = cached.season_name
            self._apply_snapshot(cached, quiet=True)
        else:
            self.snapshot = None
            self.render_active()
        self._save_config()
        self.refresh_data(force=False, quiet=cached is not None)

    def _configure_fonts(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "WorldCup.TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_3,
            foreground=TEXT,
            arrowcolor=ACCENT,
            bordercolor=LINE,
            lightcolor=LINE,
            darkcolor=LINE,
            insertcolor=TEXT,
            relief="flat",
            borderwidth=1,
            arrowsize=11,
            padding=(7, 4),
        )
        style.map(
            "WorldCup.TCombobox",
            fieldbackground=[("readonly", PANEL_2), ("disabled", PANEL)],
            foreground=[("readonly", TEXT), ("disabled", MUTED)],
            background=[("pressed", PANEL_3), ("active", PANEL_3), ("readonly", PANEL_3)],
            arrowcolor=[("pressed", ACCENT), ("active", ACCENT_2), ("readonly", ACCENT)],
            bordercolor=[("focus", ACCENT), ("active", ACCENT), ("readonly", LINE)],
            lightcolor=[("focus", ACCENT), ("readonly", LINE)],
            darkcolor=[("focus", ACCENT), ("readonly", LINE)],
        )
        self.root.option_add("*TCombobox*Listbox.background", PANEL_2, 80)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT, 80)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT, 80)
        self.root.option_add("*TCombobox*Listbox.selectForeground", self._contrast_text_color(ACCENT), 80)
        self.root.option_add("*TCombobox*Listbox.font", (self.ui_font_var.get(), 9), 80)

    def _text_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        check_var: tk.BooleanVar | None = None,
    ) -> tk.Label:
        label = tk.Label(
            parent,
            text=text,
            bg=PANEL_2,
            fg=TEXT,
            padx=12,
            pady=5,
            cursor="hand2",
            font=("Microsoft YaHei UI", 9, "bold"),
        )

        def invoke(_event: tk.Event | None = None) -> None:
            if check_var is not None:
                check_var.set(not check_var.get())
            command()

        self._bind_click(label, invoke)
        return label

    def _layout_tab_buttons(self, event: tk.Event | None = None) -> None:
        if self.tab_bar is None or not self.tab_button_order:
            return
        width = event.width if event is not None else self.tab_bar.winfo_width()
        if width <= 1:
            self.root.after(50, self._layout_tab_buttons)
            return
        visible_keys = self._visible_tab_keys()
        columns = len(visible_keys)
        cell_width = max(1, width // max(1, columns))
        font_size = 8
        while font_size > 6:
            font = tkfont.Font(
                root=self.root,
                family=self.ui_font_var.get(),
                size=font_size,
                weight="bold",
            )
            if all(
                font.measure(str(self.tab_buttons[key].cget("text")))
                <= cell_width - 6
                for key in visible_keys
            ):
                break
            font_size -= 1
        for key in self.tab_button_order:
            if key not in visible_keys:
                self.tab_buttons[key].grid_remove()
        for index, key in enumerate(visible_keys):
            button = self.tab_buttons[key]
            button.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=1,
                pady=(0, 4),
            )
            button.configure(
                wraplength=0,
                justify="center",
                padx=1,
                font=(
                    self.ui_font_var.get(),
                    font_size,
                    "bold",
                ),
            )
        for column in range(len(self.tab_button_order)):
            self.tab_bar.columnconfigure(
                column,
                weight=1 if column < columns else 0,
            )

    def _layout_data_board_buttons(self, event: tk.Event | None = None) -> None:
        if not self.data_board_button_order:
            return
        parent = self.data_board_buttons[self.data_board_button_order[0]].master
        width = event.width if event is not None else parent.winfo_width()
        if width <= 1:
            self.root.after(50, self._layout_data_board_buttons)
            return
        columns = max(2, min(len(self.data_board_button_order), width // 96))
        for index, key in enumerate(self.data_board_button_order):
            button = self.data_board_buttons[key]
            button.grid(row=index // columns, column=index % columns, sticky="ew", padx=(0, 5), pady=(0, 5))
            button.configure(wraplength=max(54, min(92, width // columns - 16)), justify="center")
        for column in range(len(self.data_board_button_order)):
            parent.columnconfigure(column, weight=1 if column < columns else 0)

    def _global_pointer_press(self, event: tk.Event) -> None:
        self.pointer_origin = (event.x_root, event.y_root)
        self.pointer_dragged = False
        self.popups_at_pointer_press = self._existing_popups()

    def _global_pointer_motion(self, event: tk.Event) -> None:
        if abs(event.x_root - self.pointer_origin[0]) > 5 or abs(event.y_root - self.pointer_origin[1]) > 5:
            self.pointer_dragged = True

    def _global_pointer_release(self, event: tk.Event) -> None:
        if self.pointer_dragged:
            return
        try:
            clicked_main = event.widget.winfo_toplevel() is self.root
        except tk.TclError:
            clicked_main = False
        if clicked_main:
            self.popup_back_stack.clear()
            self._close_popups(self.popups_at_pointer_press)
        self.popups_at_pointer_press = []

    def _existing_popups(self) -> list[tk.Toplevel]:
        result: list[tk.Toplevel] = []
        for popup in (
            self.settings_popup,
            self.competition_popup,
            self.api_help_popup,
            self.player_popup,
            self.club_popup,
            self.news_popup,
            self.match_popup,
            self.match_notification_popup,
        ):
            try:
                if popup is not None and popup.winfo_exists():
                    result.append(popup)
            except tk.TclError:
                continue
        return result

    def _close_popups(self, popups: list[tk.Toplevel]) -> None:
        for popup in popups:
            if popup is self.settings_popup:
                self._close_settings()
            elif popup is self.competition_popup:
                self._close_competition_popup()
            elif popup is self.api_help_popup:
                self._close_api_help()
            elif popup is self.player_popup:
                self._close_player_popup()
            elif popup is self.club_popup:
                self._close_club_popup()
            elif popup is self.news_popup:
                self._close_news_popup()
            elif popup is self.match_popup:
                self._close_match_popup(popup)
            elif popup is self.match_notification_popup:
                self._close_match_notification()

    def _close_all_popups(self) -> None:
        self._close_popups(self._existing_popups())

    def _prepare_single_popup(self, back_action=None, clear_history: bool = False) -> None:
        if clear_history:
            self.popup_back_stack.clear()
        self._close_all_popups()
        if back_action is not None:
            self.popup_back_stack.append(back_action)

    def _close_and_restore(self, close_action) -> None:
        close_action()
        if self.popup_back_stack:
            action = self.popup_back_stack.pop()
            self.root.after(40, action)

    def _bind_click(self, widget: tk.Widget, command, add: str = "+") -> None:
        state = {"origin": (0, 0), "dragged": False}

        def press(event: tk.Event) -> None:
            state["origin"] = (event.x_root, event.y_root)
            state["dragged"] = False

        def motion(event: tk.Event) -> None:
            origin_x, origin_y = state["origin"]
            if abs(event.x_root - origin_x) > 5 or abs(event.y_root - origin_y) > 5:
                state["dragged"] = True

        def release(event: tk.Event) -> None:
            if state["dragged"]:
                return
            try:
                if 0 <= event.x < widget.winfo_width() and 0 <= event.y < widget.winfo_height():
                    command(event)
            except tk.TclError:
                return

        widget.bind("<ButtonPress-1>", press, add=add)
        widget.bind("<B1-Motion>", motion, add=add)
        widget.bind("<ButtonRelease-1>", release, add=add)

    def _bind_drag(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._drag_window)

    def _start_drag(self, event: tk.Event) -> None:
        target = event.widget.winfo_toplevel()
        self.drag_target = target
        self.drag_origin = (event.x_root - target.winfo_x(), event.y_root - target.winfo_y())

    def _drag_window(self, event: tk.Event) -> None:
        target = self.drag_target or self.root
        x = event.x_root - self.drag_origin[0]
        y = event.y_root - self.drag_origin[1]
        target.geometry(f"+{x}+{y}")

    def _start_resize(self, event: tk.Event) -> None:
        self.resize_origin = (event.x_root, event.y_root, self.root.winfo_width(), self.root.winfo_height())

    def _resize_window(self, event: tk.Event) -> None:
        start_x, start_y, start_w, start_h = self.resize_origin
        width = max(300, start_w + event.x_root - start_x)
        height = max(360, start_h + event.y_root - start_y)
        self.root.geometry(f"{width}x{height}")

    def _apply_alpha(self, value: float) -> None:
        value = max(0.72, min(1.0, float(value)))
        self.root.attributes("-alpha", value)
        self._save_config()

    def _toggle_topmost(self) -> None:
        self.root.attributes("-topmost", self.topmost_var.get())
        self._save_config()

    def hide_window(self) -> None:
        self._save_config()
        self._close_all_popups()
        self.root.withdraw()
        self.window_visible = False

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", self.topmost_var.get())
        self.window_visible = True
        self._mark_as_tool_window()

    def toggle_visibility(self) -> None:
        if self.window_visible and self.root.state() != "withdrawn":
            self.hide_window()
        else:
            self.show_window()

    def exit_app(self) -> None:
        self.speech_service.stop()
        self._save_config()
        try:
            if self.tray_icon is not None:
                self.tray_icon.stop()
        except Exception:
            pass
        try:
            if self.settings_popup is not None:
                self.settings_popup.destroy()
            if self.api_help_popup is not None:
                self.api_help_popup.destroy()
            if self.player_popup is not None:
                self.player_popup.destroy()
            if self.club_popup is not None:
                self.club_popup.destroy()
            if self.news_popup is not None:
                self.news_popup.destroy()
            if self.competition_popup is not None:
                self.competition_popup.destroy()
        except Exception:
            pass
        self.root.destroy()

    def _build_context_menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="显示/隐藏", command=self.toggle_visibility)
        menu.add_command(label="刷新数据", command=lambda: self.refresh_data(force=True))
        menu.add_command(label="设置", command=self.open_settings)
        menu.add_separator()
        menu.add_command(label="退出", command=self.exit_app)
        self.context_menu = menu

    def _show_context_menu(self, event: tk.Event) -> None:
        if self.context_menu is None:
            return
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _start_tray_icon(self) -> None:
        if pystray is None or Image is None or ImageDraw is None:
            return

        def schedule(callback):
            return lambda _icon=None, _item=None: self.root.after(0, callback)

        image = self._tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("显示/隐藏", schedule(self.toggle_visibility), default=True),
            pystray.MenuItem("刷新数据", schedule(lambda: self.refresh_data(force=True))),
            pystray.MenuItem("设置", schedule(self.open_settings)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", schedule(self.exit_app)),
        )
        self.tray_icon = pystray.Icon("WorldCupFloat", image, self.app_title_var.get(), menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_image(self):
        return self._make_icon_image(64)

    def open_settings(self) -> None:
        self.show_window()
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.deiconify()
            self.settings_popup.lift()
            return
        self._prepare_single_popup(clear_history=True)
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.96)
        settings_width = 380
        settings_height = 560
        settings_x = min(
            max(8, self.root.winfo_x() + 28),
            max(8, self.root.winfo_screenwidth() - settings_width - 8),
        )
        settings_y = min(
            max(8, self.root.winfo_y() + 72),
            max(8, self.root.winfo_screenheight() - settings_height - 48),
        )
        popup.geometry(f"{settings_width}x{settings_height}+{settings_x}+{settings_y}")
        self.settings_popup = popup

        header = tk.Frame(popup, bg=PANEL, padx=12, pady=9)
        header.pack(fill="x")
        settings_title = tk.Label(header, text="浮窗设置", bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 12, "bold"))
        settings_title.pack(side="left")
        close = tk.Label(header, text="×", bg=PANEL, fg=MUTED, cursor="hand2", font=("Microsoft YaHei UI", 12, "bold"))
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_settings())
        for widget in (header, settings_title):
            self._bind_drag(widget)

        body_scroll = ScrollFrame(popup, bg=PANEL)
        body_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        body = tk.Frame(body_scroll.body, bg=PANEL, padx=0, pady=8)
        body.pack(fill="both", expand=True)
        competition_name = str(
            COMPETITIONS[self.active_competition_key]["name"]
        )
        tk.Label(
            body,
            text=f"顶部标题 · {competition_name}",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")
        title_row = tk.Frame(body, bg=PANEL)
        title_row.pack(fill="x", pady=(3, 10))
        title_entry = tk.Entry(
            title_row,
            textvariable=self.app_title_var,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )
        title_entry.pack(side="left", fill="x", expand=True, ipady=5)
        title_entry.bind("<Return>", lambda _event: self._apply_title())
        title_entry.bind("<FocusOut>", lambda _event: self._apply_title())
        self._text_button(title_row, "应用", self._apply_title).pack(side="left", padx=(8, 0))
        align_row = tk.Frame(body, bg=PANEL)
        align_row.pack(fill="x", pady=(0, 10))
        tk.Label(
            align_row,
            text="标题位置",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")
        for text, value in (("居中", "center"), ("贴左", "left")):
            active = self.title_alignment_var.get() == value
            button = tk.Label(
                align_row,
                text=text,
                bg=PANEL_3 if active else PANEL_2,
                fg=ACCENT if active else MUTED,
                padx=12,
                pady=5,
                cursor="hand2",
                font=("Microsoft YaHei UI", 8, "bold"),
            )
            button.pack(side="right", padx=(6, 0))
            self._bind_click(button, lambda _event, current=value: self._set_title_alignment(current))

        tk.Label(body, text="字体", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        font_panel = tk.Frame(body, bg=PANEL_2, padx=9, pady=7, highlightthickness=1, highlightbackground=LINE)
        font_panel.pack(fill="x", pady=(3, 10))

        def font_selector(label: str, variable: tk.StringVar) -> None:
            row = tk.Frame(font_panel, bg=PANEL_2)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=PANEL_2, fg=MUTED, width=7, anchor="w", font=("Microsoft YaHei UI", 8)).pack(side="left")
            combo = ttk.Combobox(
                row,
                textvariable=variable,
                state="readonly",
                style="WorldCup.TCombobox",
                values=self.available_fonts,
                height=14,
            )
            combo.pack(side="left", fill="x", expand=True)
            combo.bind("<<ComboboxSelected>>", self._apply_font_settings)
            combo.bind(
                "<MouseWheel>",
                lambda event: (body_scroll.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"), "break")[1],
            )

        font_selector("普通字体", self.ui_font_var)
        font_selector("比分字体", self.score_font_var)

        tk.Label(body, text="图标", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        icon_row = tk.Frame(body, bg=PANEL)
        icon_row.pack(fill="x", pady=(5, 10))
        self.icon_images.clear()
        for index in range(1, 6):
            choice = f"icon_{index}"
            selected = self.icon_choice_var.get() == choice
            card = tk.Frame(
                icon_row,
                bg=PANEL_3 if selected else PANEL_2,
                cursor="hand2",
                highlightthickness=2 if selected else 1,
                highlightbackground=ACCENT if selected else LINE,
                width=54,
                height=54,
            )
            card.pack(side="left", padx=(0, 7))
            card.pack_propagate(False)
            image_label = tk.Label(card, text="", bg=card.cget("bg"), fg=TEXT, cursor="hand2", font=("Microsoft YaHei UI", 8, "bold"))
            image_label.pack(fill="both", expand=True, padx=5, pady=5)
            path = self._app_icon_path(choice)
            if path is not None and Image is not None and ImageTk is not None:
                try:
                    image = self._normalized_icon_source(path)
                    image.thumbnail((42, 42), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                    self.icon_images[choice] = photo
                    image_label.configure(image=photo, text="")
                    image_label.image = photo
                except Exception:
                    pass
            for widget in (card, image_label):
                self._bind_click(widget, lambda _event, current=choice: self._apply_icon_choice(current))

        tk.Label(body, text="主题色", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        color_row = tk.Frame(body, bg=PANEL)
        color_row.pack(fill="x", pady=(3, 10))
        color_swatch = tk.Label(color_row, text="", bg=self.theme_color_var.get(), width=3, height=1, highlightthickness=1, highlightbackground=LINE)
        color_swatch.grid(row=0, column=0, sticky="nsew", padx=(0, 8), ipady=6)
        color_entry = tk.Entry(
            color_row,
            textvariable=self.theme_color_var,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )
        color_button = self._text_button(color_row, "选色", self._choose_theme_color)
        color_entry.grid(row=0, column=1, sticky="nsew", ipady=5)
        color_button.grid(row=0, column=2, sticky="nsew", padx=(8, 4))
        color_row.columnconfigure(0, weight=0, minsize=42)
        color_row.columnconfigure(1, weight=1, minsize=150)
        color_row.columnconfigure(2, weight=0, minsize=84)
        color_entry.bind("<Return>", lambda _event: self._apply_theme_color())
        color_entry.bind("<FocusOut>", lambda _event: self._apply_theme_color())

        tk.Label(body, text="配色方案", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        palette_row = tk.Frame(body, bg=PANEL)
        palette_row.pack(fill="x", pady=(3, 8))
        palette_display = {name: data["label"] for name, data in PALETTE_PRESETS.items()}
        palette_display["custom"] = "自定义"
        palette_reverse = {label: name for name, label in palette_display.items()}
        palette_label_var = tk.StringVar(value=palette_display.get(self.palette_var.get(), palette_display["codex"]))
        palette_combo = ttk.Combobox(
            palette_row,
            textvariable=palette_label_var,
            state="readonly",
            style="WorldCup.TCombobox",
            values=list(palette_reverse.keys()),
            width=12,
        )
        palette_combo.pack(side="left", fill="x", expand=True)
        palette_combo.bind("<<ComboboxSelected>>", lambda _event: (self.palette_var.set(palette_reverse.get(palette_label_var.get(), "codex")), self._apply_palette_choice()))
        def scroll_settings(event: tk.Event) -> str:
            direction = -1 if event.delta > 0 else 1
            body_scroll.canvas.yview_scroll(direction * 3, "units")
            return "break"
        palette_combo.bind("<MouseWheel>", scroll_settings)
        self._text_button(palette_row, "保存自定义", self._save_custom_palette).pack(side="left", padx=(8, 0))

        color_grid = tk.Frame(body, bg=PANEL)
        color_grid.pack(fill="x", pady=(0, 8))
        for index, key in enumerate(PALETTE_KEYS):
            color = self.palette_colors.get(key, ACCENT)
            field = tk.Label(
                color_grid,
                text=PALETTE_FIELD_LABELS.get(key, key),
                bg=PANEL,
                fg=TEXT,
                anchor="w",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            field.grid(row=index, column=0, sticky="w", padx=(0, 8), pady=3)
            swatch = tk.Label(
                color_grid,
                text=color.upper(),
                bg=color,
                fg=self._contrast_text_color(color),
                anchor="center",
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=LINE,
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            swatch.grid(row=index, column=1, sticky="ew", pady=3, ipady=3)
            self._bind_click(swatch, lambda _event, current=key: self._choose_palette_color(current))
            color_grid.rowconfigure(index, minsize=30)
        color_grid.columnconfigure(0, weight=0, minsize=48)
        color_grid.columnconfigure(1, weight=1)

        tk.Label(body, text="刷新", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        refresh_panel = tk.Frame(body, bg=PANEL_2, padx=9, pady=8, highlightthickness=1, highlightbackground=LINE)
        refresh_panel.pack(fill="x", pady=(3, 10))
        tk.Checkbutton(
            refresh_panel,
            text="主界面快捷刷新",
            variable=self.quick_refresh_var,
            command=self._toggle_quick_refresh,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w")
        tk.Checkbutton(
            refresh_panel,
            text="显示同步状态",
            variable=self.show_status_var,
            command=self._toggle_status_visibility,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(4, 7))
        tk.Checkbutton(
            refresh_panel,
            text="比赛开始时显示通知",
            variable=self.match_notifications_var,
            command=self._toggle_match_notifications,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(0, 7))
        tk.Checkbutton(
            refresh_panel,
            text="主界面显示直播标签",
            variable=self.show_live_labels_var,
            command=self._toggle_live_labels,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(0, 7))
        interval_row = tk.Frame(refresh_panel, bg=PANEL_2)
        interval_row.pack(fill="x")
        for label, variable in (("比赛中", self.live_refresh_seconds_var), ("非比赛", self.default_refresh_seconds_var)):
            item = tk.Frame(interval_row, bg=PANEL_2)
            item.pack(side="left", fill="x", expand=True, padx=(0, 6))
            tk.Label(item, text=label, bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(anchor="w")
            value_row = tk.Frame(item, bg=PANEL_2)
            value_row.pack(fill="x", pady=(2, 0))
            entry = tk.Entry(
                value_row,
                textvariable=variable,
                bg=PANEL_3,
                fg=TEXT,
                insertbackground=TEXT,
                relief="flat",
                width=4,
                justify="center",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            entry.pack(side="left", fill="x", expand=True, ipady=3)
            tk.Label(value_row, text="秒", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(5, 0))
            entry.bind("<Return>", self._save_refresh_settings)
            entry.bind("<FocusOut>", self._save_refresh_settings)
        roster_row = tk.Frame(refresh_panel, bg=PANEL_2)
        roster_row.pack(fill="x", pady=(8, 0))
        tk.Label(roster_row, text="球员名单更新", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="left")
        roster_entry = tk.Entry(roster_row, textvariable=self.roster_refresh_hours_var, bg=PANEL_3, fg=TEXT, insertbackground=TEXT, relief="flat", width=5, justify="center", font=("Microsoft YaHei UI", 9, "bold"))
        roster_entry.pack(side="right", ipady=3)
        tk.Label(roster_row, text="小时", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="right", padx=(0, 6))
        roster_entry.bind("<Return>", self._save_refresh_settings)
        roster_entry.bind("<FocusOut>", self._save_refresh_settings)

        tk.Label(body, text="联赛资讯", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        news_panel = tk.Frame(body, bg=PANEL_2, padx=9, pady=8, highlightthickness=1, highlightbackground=LINE)
        news_panel.pack(fill="x", pady=(3, 10))
        news_row = tk.Frame(news_panel, bg=PANEL_2)
        news_row.pack(fill="x")
        tk.Label(news_row, text="显示最近", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="left")
        news_entry = tk.Entry(news_row, textvariable=self.news_weeks_var, bg=PANEL_3, fg=TEXT, insertbackground=TEXT, relief="flat", width=5, justify="center", font=("Microsoft YaHei UI", 9, "bold"))
        news_entry.pack(side="right", ipady=3)
        tk.Label(news_row, text="周", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="right", padx=(0, 6))
        news_entry.bind("<Return>", self._save_news_settings)
        news_entry.bind("<FocusOut>", self._save_news_settings)

        tk.Label(body, text="实时解说", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        commentary_panel = tk.Frame(body, bg=PANEL_2, padx=9, pady=8, highlightthickness=1, highlightbackground=LINE)
        commentary_panel.pack(fill="x", pady=(3, 10))
        tk.Checkbutton(
            commentary_panel,
            text="AI 中文解说润色",
            variable=self.ai_commentary_var,
            command=self._toggle_ai_commentary,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w")
        tk.Checkbutton(
            commentary_panel,
            text="AI 直译原始事件（与上项二选一）",
            variable=self.ai_translate_raw_var,
            command=self._toggle_raw_translation,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(5, 0))
        tk.Checkbutton(
            commentary_panel,
            text="AI 未启用或失败时使用免费中文翻译",
            variable=self.free_translate_var,
            command=self._toggle_free_translation,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(5, 0))
        tk.Label(
            commentary_panel,
            text="AI 模型",
            bg=PANEL_2,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w", pady=(8, 3))
        model_combo = ttk.Combobox(
            commentary_panel,
            textvariable=self.ai_model_name_var,
            values=[
                str(preset["label"])
                for preset in AI_MODEL_PRESETS.values()
            ],
            state="readonly",
            style="WorldCup.TCombobox",
        )
        model_combo.pack(fill="x")
        model_combo.bind(
            "<<ComboboxSelected>>",
            self._select_ai_model,
        )
        model_combo.bind("<MouseWheel>", scroll_settings)
        lines_row = tk.Frame(commentary_panel, bg=PANEL_2)
        lines_row.pack(fill="x", pady=(7, 0))
        tk.Label(lines_row, text="主界面显示行数", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="left")
        lines_entry = tk.Entry(
            lines_row,
            textvariable=self.commentary_lines_var,
            bg=PANEL_3,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            width=4,
            justify="center",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        lines_entry.pack(side="right", ipady=3)
        lines_entry.bind("<Return>", self._save_commentary_settings)
        lines_entry.bind("<FocusOut>", self._save_commentary_settings)
        tk.Label(commentary_panel, text="当前模型 API Key", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(8, 3))
        key_row = tk.Frame(commentary_panel, bg=PANEL_2)
        key_row.pack(fill="x")
        key_entry = tk.Entry(
            key_row,
            textvariable=self.agnes_api_key_var,
            show="•",
            bg=PANEL_3,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )
        key_entry.pack(side="left", fill="x", expand=True, ipady=4)
        key_entry.bind("<Return>", self._save_commentary_settings)
        key_entry.bind("<FocusOut>", self._save_commentary_settings)
        self._text_button(key_row, "测试", self._test_agnes_connection).pack(side="left", padx=(7, 0))
        tk.Label(
            commentary_panel,
            textvariable=self.ai_status_var,
            bg=PANEL_2,
            fg=MUTED,
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 8),
        ).pack(fill="x", pady=(6, 0))
        help_link = tk.Label(
            commentary_panel,
            text="如何获取免费模型 API Key",
            bg=PANEL_2,
            fg=ACCENT,
            cursor="hand2",
            anchor="w",
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        help_link.pack(fill="x", pady=(8, 0))
        self._bind_click(help_link, lambda _event: self._open_api_help())

        tk.Label(
            commentary_panel,
            text="备用翻译（腾讯云机器翻译）",
            bg=PANEL_2,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w", pady=(10, 3))
        tk.Label(
            commentary_panel,
            text="SecretId",
            bg=PANEL_2,
            fg=MUTED,
            font=("Microsoft YaHei UI", 7),
        ).pack(anchor="w")
        translate_id_entry = tk.Entry(
            commentary_panel,
            textvariable=self.tencent_translate_secret_id_var,
            bg=PANEL_3,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Microsoft YaHei UI", 8),
        )
        translate_id_entry.pack(fill="x", ipady=3)
        tk.Label(
            commentary_panel,
            text="SecretKey",
            bg=PANEL_2,
            fg=MUTED,
            font=("Microsoft YaHei UI", 7),
        ).pack(anchor="w", pady=(5, 0))
        translate_key_row = tk.Frame(
            commentary_panel,
            bg=PANEL_2,
        )
        translate_key_row.pack(fill="x", pady=(5, 0))
        translate_key_entry = tk.Entry(
            translate_key_row,
            textvariable=self.tencent_translate_secret_key_var,
            show="•",
            bg=PANEL_3,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Microsoft YaHei UI", 8),
        )
        translate_key_entry.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=3,
        )
        self._text_button(
            translate_key_row,
            "测试",
            self._test_translation_connection,
        ).pack(side="left", padx=(7, 0))
        for entry in (
            translate_id_entry,
            translate_key_entry,
        ):
            entry.bind(
                "<Return>",
                self._save_translation_credentials,
            )
            entry.bind(
                "<FocusOut>",
                self._save_translation_credentials,
            )
        tk.Label(
            commentary_panel,
            textvariable=self.translation_status_var,
            bg=PANEL_2,
            fg=MUTED,
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 7),
        ).pack(fill="x", pady=(5, 0))

        tk.Label(commentary_panel, text="语音播报", bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(10, 3))
        tk.Checkbutton(
            commentary_panel,
            text="实时播报 AI 中文解说",
            variable=self.tts_enabled_var,
            command=self._save_tts_settings,
            bg=PANEL_2,
            fg=TEXT,
            selectcolor=PANEL_3,
            activebackground=PANEL_2,
            activeforeground=TEXT,
        ).pack(anchor="w")
        voice_names = ["系统默认（本地）"] + [voice.name for voice in self.speech_voices]
        voice_ids = {"系统默认（本地）": "", **{voice.name: voice.id for voice in self.speech_voices}}
        selected_voice_name = next(
            (voice.name for voice in self.speech_voices if voice.id == self.tts_voice_var.get()),
            "系统默认（本地）",
        )
        voice_name_var = tk.StringVar(value=selected_voice_name)
        voice_row = tk.Frame(commentary_panel, bg=PANEL_2)
        voice_row.pack(fill="x", pady=(5, 0))
        voice_combo = ttk.Combobox(
            voice_row,
            textvariable=voice_name_var,
            values=voice_names,
            state="readonly",
            style="WorldCup.TCombobox",
        )
        voice_combo.pack(side="left", fill="x", expand=True)
        self._text_button(
            voice_row,
            "试听",
            self._preview_tts_voice,
        ).pack(side="left", padx=(7, 0))
        voice_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: (
                self.tts_voice_var.set(voice_ids.get(voice_name_var.get(), "")),
                self._save_tts_settings(),
            ),
        )
        voice_combo.bind("<MouseWheel>", scroll_settings)

        tk.Label(body, text="AI 缓存", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        cache_panel = tk.Frame(body, bg=PANEL_2, padx=9, pady=8, highlightthickness=1, highlightbackground=LINE)
        cache_panel.pack(fill="x", pady=(3, 10))
        cache_status = tk.Label(
            cache_panel,
            textvariable=self.ai_cache_status_var,
            bg=PANEL_2,
            fg=MUTED,
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 8),
        )
        cache_status.pack(side="left", fill="x", expand=True)
        self._bind_wrap(cache_status, reserve=104, minimum=130, maximum=240)
        self._text_button(cache_panel, "清除缓存", self._clear_ai_cache).pack(side="right", padx=(8, 0))
        tk.Checkbutton(
            body,
            text="保持置顶",
            variable=self.topmost_var,
            command=self._toggle_topmost,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(0, 10))
        tk.Checkbutton(
            body,
            text="显示球员英文名",
            variable=self.use_english_var,
            command=self._refresh_language,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(body, text="透明度", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        FlatSlider(
            body,
            variable=self.alpha_var,
            from_=0.72,
            to=1.0,
            command=self._apply_alpha,
            accent_getter=lambda: self.theme_color_var.get(),
        ).pack(fill="x", pady=(4, 12))

        size_row = tk.Frame(body, bg=PANEL)
        size_row.pack(fill="x")
        self._text_button(size_row, "紧凑", lambda: self._apply_window_preset(self._compact_geometry())).pack(side="left", padx=(0, 8))
        self._text_button(size_row, "宽屏", lambda: self._apply_window_preset("520x620")).pack(side="left")

        update_panel = tk.Frame(body, bg=PANEL_2, padx=9, pady=8, highlightthickness=1, highlightbackground=LINE)
        update_panel.pack(fill="x", pady=(12, 0))
        update_info = tk.Label(
            update_panel,
            textvariable=self.update_status_var,
            bg=PANEL_2,
            fg=MUTED,
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 8),
        )
        update_info.pack(side="left", fill="x", expand=True)
        self._text_button(update_panel, "检查并更新", self._check_for_updates).pack(side="right", padx=(8, 0))
        self._apply_fonts_to_tree(popup)

    def select_tab(self, key: str) -> None:
        if self.tab_switching:
            return
        if key == self.active_tab:
            if self._tab_needs_render(key):
                self.render_active()
            return
        self.tab_switching = True
        try:
            previous = self.active_tab
            self.active_tab = key
            if self._tab_needs_render(key):
                self.render_active()
            self.tabs[previous].pack_forget()
            self.tabs[key].pack(fill="both", expand=True)
            for tab, button in self.tab_buttons.items():
                active = tab == key
                button.configure(bg=PANEL if active else BG, fg=ACCENT if active else MUTED)
        finally:
            self.root.after_idle(lambda: setattr(self, "tab_switching", False))

    def _tab_needs_render(self, key: str | None = None) -> bool:
        key = key or self.active_tab
        frame = self.tabs.get(key)
        if frame is None:
            return True
        if not frame.body.winfo_children():
            return True
        return self.tab_rendered_signatures.get(key) != self._active_signature(tab=key)

    def refresh_data(self, force: bool = False, quiet: bool = True) -> None:
        if not self.refresh_lock.acquire(blocking=False):
            self.root.after(
                250,
                lambda: self.refresh_data(force=force, quiet=quiet),
            )
            return
        if not quiet and self.snapshot is None:
            self._set_status_text("正在加载赛事数据...")

        competition_key = self.active_competition_key
        provider = DataProvider(
            cache_dir=self.provider.cache_dir,
            competition_key=competition_key,
        )

        def worker() -> None:
            try:
                snapshot = provider.load_all(force=force)
                self._post_ui(
                    lambda current=snapshot, current_provider=provider:
                    self._apply_loaded_snapshot(
                        current,
                        current_provider,
                        quiet,
                    )
                )
            except Exception as exc:
                if not quiet or self.snapshot is None:
                    self._post_ui(lambda error=exc: self._set_status_text(f"同步失败: {error}"))
            finally:
                self.refresh_lock.release()

        threading.Thread(target=worker, daemon=True).start()

    def _apply_loaded_snapshot(
        self,
        snapshot: Snapshot,
        provider: DataProvider,
        quiet: bool,
    ) -> None:
        self.snapshot_cache[snapshot.competition_key] = snapshot
        if snapshot.competition_key != self.active_competition_key:
            return
        self.provider = provider
        self._apply_snapshot(snapshot, quiet=quiet)

    def _auto_refresh(self) -> None:
        self.refresh_data(force=False, quiet=True)
        self._schedule_next_refresh()

    def _current_refresh_ms(self) -> int:
        seconds = self.live_refresh_seconds_var.get() if self._has_live_matches() else self.default_refresh_seconds_var.get()
        return self._valid_seconds(seconds, AUTO_REFRESH_MS // 1000) * 1000

    def _schedule_next_refresh(self) -> None:
        if self.auto_refresh_after_id is not None:
            try:
                self.root.after_cancel(self.auto_refresh_after_id)
            except tk.TclError:
                pass
        if self._has_live_matches():
            delay = self._current_refresh_ms()
        else:
            seconds = self._valid_seconds(self.default_refresh_seconds_var.get(), 300)
            now = time.time()
            next_boundary = (int(now // seconds) + 1) * seconds
            delay = max(1000, int((next_boundary - now) * 1000))
        self.auto_refresh_after_id = self.root.after(delay, self._auto_refresh)

    def _has_live_matches(self) -> bool:
        return bool(self.snapshot and any(match.is_live for match in self.snapshot.matches))

    def _set_status_text(self, text: str) -> None:
        self.last_status_text = text
        if self.show_status_var.get():
            self.status_var.set(text)
        else:
            self.status_var.set("")

    def _apply_snapshot(self, snapshot: Snapshot, quiet: bool = True) -> None:
        active_frame = self.tabs.get(self.active_tab)
        if active_frame is not None and active_frame.scroll_active:
            self.pending_snapshot = (snapshot, quiet)
            if self.pending_snapshot_after_id is None:
                self.pending_snapshot_after_id = self.root.after(220, self._apply_pending_snapshot)
            return
        self.pending_snapshot = None
        if self.pending_snapshot_after_id is not None:
            try:
                self.root.after_cancel(self.pending_snapshot_after_id)
            except tk.TclError:
                pass
            self.pending_snapshot_after_id = None
        had_snapshot = self.snapshot is not None
        previous_live_ids = {
            match.id for match in self.snapshot.matches if match.is_live
        } if self.snapshot else set()
        old_signatures = {
            tab: self._active_signature(self.snapshot, tab=tab)
            for tab in self.tab_rendered_signatures
        } if had_snapshot else {}
        self.snapshot = snapshot
        self.snapshot_cache[snapshot.competition_key] = snapshot
        self.app_title_var.set(
            self.competition_titles[snapshot.competition_key]
        )
        self.root.after_idle(self._ensure_title_alignment_fits)
        options = ["全部球队"]
        self.team_options = {"全部球队": ""}
        favorite_id = self.favorite_teams.get(snapshot.competition_key, "")
        teams = sorted(
            snapshot.teams.values(),
            key=lambda team: (
                0 if team.id == favorite_id else 1,
                team.group or "Z",
                team.name,
            ),
        )
        for team in teams:
            option = self._team_option_text(team)
            options.append(option)
            self.team_options[option] = team.id
        self.team_combo.configure(values=options)
        if (
            self.selected_team_id
            and self.selected_team_id not in snapshot.teams
        ):
            self.selected_team_id = ""
        if self.selected_team_id:
            selected = self._option_for_team(self.selected_team_id)
            if selected:
                self.team_var.set(selected)
        errors = f"；{len(snapshot.errors)} 个源使用缓存/降级" if snapshot.errors else ""
        source_text = " / ".join(snapshot.sources[:3]) if snapshot.sources else "缓存"
        if not quiet or not had_snapshot:
            season = f" · {snapshot.season_name}" if snapshot.season_name else ""
            self._set_status_text(f"已同步 {len(snapshot.matches)} 场比赛，{len(snapshot.teams)} 支球队{season} · {source_text}{errors}")
        for tab, old_signature in old_signatures.items():
            if old_signature != self._active_signature(snapshot, tab=tab):
                self.tab_rendered_signatures.pop(tab, None)
        new_signature = self._active_signature(snapshot, tab=self.active_tab)
        if not had_snapshot or self.tab_rendered_signatures.get(self.active_tab) != new_signature:
            self.render_active()
        else:
            self._update_visible_text()
        self._maybe_show_match_notification(snapshot)
        self.images.prefetch(self._all_logo_urls(snapshot))
        self._request_name_localization(
            "team",
            [
                team.name
                for team in snapshot.teams.values()
                if self.localizer.team(team.name, team.abbreviation) == team.name
            ],
        )
        self._schedule_roster_name_prewarm(snapshot)
        self._refresh_live_commentary(snapshot)
        if snapshot.competition_kind == "league":
            self._load_professional_boards(snapshot)
        self._schedule_recent_ai_prewarm(snapshot)
        current_live_ids = {match.id for match in snapshot.matches if match.is_live}
        ended_ids = previous_live_ids - current_live_ids
        for match in snapshot.matches:
            if match.id in ended_ids and match.completed:
                self._load_complete_detail_commentary(match, request_summary=True)
            if (
                match.id == self.match_popup_match_id
                and match.is_live
                and match.id not in self.detail_commentary_snapshots
                and match.id not in self.detail_commentary_loading
            ):
                self._load_complete_detail_commentary(match)
        self._sync_match_notification(
            snapshot,
            current_live_ids,
        )
        self.live_match_ids = current_live_ids

    def _apply_pending_snapshot(self) -> None:
        self.pending_snapshot_after_id = None
        pending = self.pending_snapshot
        if pending is None:
            return
        snapshot, quiet = pending
        self._apply_snapshot(snapshot, quiet=quiet)

    def _active_signature(self, snapshot: Snapshot | None = None, tab: str | None = None) -> tuple:
        snapshot = snapshot or self.snapshot
        tab = tab or self.active_tab
        if snapshot is None:
            return (
                "empty",
                self.active_competition_key,
                tab,
                self.selected_team_id,
            )
        prefix = (snapshot.competition_key,)
        matches = self._filtered_matches(snapshot)
        if tab == "live":
            mode, _title, spotlight = self._spotlight_matches(snapshot)
            return prefix + ("spotlight", mode, self.selected_team_id, bool(self.show_live_labels_var.get()), tuple((m.id, m.status_state, m.home.score, m.away.score) for m in spotlight))
        if tab == "upcoming":
            return prefix + ("upcoming", self.round_selection.get("upcoming"), self.selected_team_id, bool(self.show_live_labels_var.get()), tuple((m.id, m.status_state) for m in matches if m.is_upcoming))
        if tab == "results":
            completed = [m for m in matches if m.completed]
            completed.sort(key=lambda m: m.date or MIN_DATE, reverse=True)
            return prefix + ("results", self.round_selection.get("results"), self.selected_team_id, tuple((m.id, m.home.score, m.away.score) for m in completed))
        if tab == "bracket":
            knockout = [m for m in snapshot.matches if m.round_slug != "group-stage"]
            if (
                self.selected_team_id
                and snapshot.competition_kind != "league"
            ):
                knockout = [m for m in knockout if m.home.id == self.selected_team_id or m.away.id == self.selected_team_id]
            return prefix + ("bracket", self.selected_team_id, tuple((m.id, m.status_state, m.home.score, m.away.score) for m in knockout))
        if tab == "standings":
            groups = snapshot.standings
            if self.selected_team_id:
                team = snapshot.teams.get(self.selected_team_id)
                groups = [g for g in groups if g.get("name") == (team.group if team else "")]
            return prefix + (
                "standings",
                self.selected_team_id,
                tuple((g.get("name"), tuple((row["team"].id, tuple(sorted(row.get("stats", {}).items()))) for row in g.get("entries", []))) for g in groups),
            )
        if tab == "data":
            return prefix + (
                "data",
                self.active_data_board_key,
                tuple((board.key, tuple((row.player_id, row.display_value) for row in board.rows[:12])) for board in self._data_boards(snapshot)),
            )
        if tab == "team":
            roster_key = self._roster_key(
                self.selected_team_id,
                snapshot.competition_key,
            )
            roster_state = (
                "loading" if roster_key in self.loading_rosters else
                "error" if roster_key in self.roster_errors else
                len(self.rosters.get(roster_key, []))
            )
            team_matches = [(m.id, m.status_state, m.home.score, m.away.score) for m in snapshot.matches if m.home.id == self.selected_team_id or m.away.id == self.selected_team_id]
            return prefix + ("team", self.selected_team_id, roster_state, tuple(team_matches))
        if tab == "news":
            rows = self.news_items.get(snapshot.competition_key, [])
            return prefix + (
                "news",
                self.favorite_teams.get(snapshot.competition_key, ""),
                self.news_weeks_var.get(),
                tuple((item.id, item.translated_title) for item in rows),
            )
        return prefix + (tab, self.selected_team_id)

    def _update_visible_text(self) -> None:
        if not self.snapshot:
            return
        matches_by_id = {match.id: match for match in self.snapshot.matches}
        for match_id, label_sets in list(self.match_labels.items()):
            match = matches_by_id.get(match_id)
            if not match:
                continue
            for labels in label_sets:
                self._apply_match_labels(labels, match)
        for group in self.snapshot.standings:
            for entry in group.get("entries", []):
                team = entry["team"]
                for key, value in entry["stats"].items():
                    label = self.standing_labels.get((team.id, key))
                    if label is not None:
                        self._safe_label_config(label, text=value)
        for board in self.snapshot.leaderboards:
            for row in board.rows[:12]:
                label = self.leader_labels.get((board.key, row.player_id))
                if label is not None:
                    value = row.display_value.replace("Matches:", "赛").replace("Goals:", "球").replace("Assists:", "助攻")
                    self._safe_label_config(label, text=value)

    def _apply_match_labels(self, labels: dict[str, object], match: Match) -> None:
        status_color = LIVE if match.is_live else (ACCENT if match.completed else WARNING)
        status = "LIVE " + match.status_text if match.is_live else (match.status_text or ("完赛" if match.completed else "未开始"))
        when = match.date.strftime("%m-%d %H:%M") if match.date else "时间待定"
        group = f" · {match.group} 组" if match.group else ""
        home_name = self._team_text(match.home)
        away_name = self._team_text(match.away)
        scoreline = self._scoreline(match)
        summary = f"{away_name} {match.away.score or '-'} : {match.home.score or '-'} {home_name}"
        updates = {
            "round": f"{match.round_name}{group}",
            "status": f"{when} · {status}",
            "away_score": match.away.score if (match.completed or match.is_live) and match.away.score != "" else "-",
            "home_score": match.home.score if (match.completed or match.is_live) and match.home.score != "" else "-",
            "away_name": away_name,
            "home_name": home_name,
            "scoreline": scoreline,
            "when": when,
            "summary": summary,
        }
        for key, value in updates.items():
            label = labels.get(key)
            if isinstance(label, tk.Label):
                kwargs = {"text": value}
                if key == "status":
                    kwargs["fg"] = status_color
                self._safe_label_config(label, **kwargs)
        header = labels.get("_header")
        align_header = getattr(header, "_worldcup_align_header", None)
        if callable(align_header):
            try:
                header.after_idle(align_header)
            except tk.TclError:
                pass

    def _safe_label_config(self, label: tk.Label, **kwargs) -> None:
        try:
            if label.winfo_exists():
                label.configure(**kwargs)
        except tk.TclError:
            pass

    def _scoreline(self, match: Match) -> str:
        if (match.completed or match.is_live) and (match.home.score != "" or match.away.score != ""):
            return f"{match.home.score or '0'} - {match.away.score or '0'}"
        return "VS"

    def _option_for_team(self, team_id: str) -> str:
        for option, current_id in self.team_options.items():
            if current_id == team_id:
                return option
        return ""

    def _clear_team_filter(self) -> None:
        self.selected_team_id = ""
        self.selected_player_id = ""
        self.team_var.set("全部球队")
        self.render_active()

    def _team_filter_bar(self, parent: tk.Widget) -> None:
        if not self.selected_team_id or not self.snapshot:
            return
        team = self.snapshot.teams.get(self.selected_team_id)
        if not team:
            return
        bar = tk.Frame(parent, bg=PANEL_2, padx=9, pady=7, highlightthickness=1, highlightbackground=LINE)
        bar.pack(fill="x", pady=(0, 8))
        label = tk.Label(
            bar,
            text=f"当前：{self._team_text(team)}",
            bg=PANEL_2,
            fg=ACCENT,
            anchor="w",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        label.pack(side="left", fill="x", expand=True)
        self._bind_wrap(label, reserve=88, minimum=80, maximum=210)
        self._text_button(bar, "全部", self._clear_team_filter).pack(side="right")

    def _on_team_select(self, _event: tk.Event | None = None) -> None:
        self.selected_team_id = self.team_options.get(self.team_var.get(), "")
        self.selected_player_id = ""
        if self.selected_team_id:
            self.select_tab("team")
        else:
            self.render_active()

    def _refresh_language(self) -> None:
        self._save_config()
        self._invalidate_render_cache()
        if self.snapshot:
            current_id = self.selected_team_id
            options = ["全部球队"]
            self.team_options = {"全部球队": ""}
            for team in sorted(self.snapshot.teams.values(), key=lambda t: (t.group or "Z", t.name)):
                option = self._team_option_text(team)
                options.append(option)
                self.team_options[option] = team.id
            self.team_combo.configure(values=options)
            if current_id:
                selected = self._option_for_team(current_id)
                if selected:
                    self.team_var.set(selected)
            else:
                self.team_var.set("全部球队")
        self.render_active()

    def open_team(self, team_id: str) -> None:
        if not team_id:
            return
        self.selected_team_id = team_id
        self.selected_player_id = ""
        option = self._option_for_team(team_id)
        if option:
            self.team_var.set(option)
        self.select_tab("team")

    def render_active(self) -> None:
        if self.render_in_progress:
            return
        if not self.snapshot:
            self._render_loading(self.tabs[self.active_tab])
            return
        current_signature = self._active_signature(tab=self.active_tab)
        if not self._tab_needs_render(self.active_tab):
            self.rendered_signature = current_signature
            return
        frame = self.tabs[self.active_tab]
        self.render_in_progress = True
        frame.begin_update()
        try:
            self.match_labels.clear()
            self.commentary_labels.clear()
            self.standing_labels.clear()
            self.leader_labels.clear()
            renderers = {
                "live": self.render_live,
                "upcoming": self.render_upcoming,
                "results": self.render_results,
                "standings": self.render_standings,
                "bracket": self.render_bracket,
                "data": self.render_data,
                "news": self.render_news,
                "team": self.render_team,
            }
            renderers[self.active_tab]()
            if (
                self.ui_font_var.get() != DEFAULT_UI_FONT
                or self.score_font_var.get() != DEFAULT_SCORE_FONT
            ):
                self._apply_fonts_to_tree(frame)
            frame.end_update()
            self.rendered_signature = current_signature
            self.tab_rendered_signatures[self.active_tab] = current_signature
        finally:
            self.render_in_progress = False

    def _render_loading(self, frame: ScrollFrame) -> None:
        frame.clear()
        self._empty(frame.body, "正在加载赛事数据...")

    def render_live(self) -> None:
        frame = self.tabs["live"]
        frame.clear()
        mode, title, matches = self._spotlight_matches()
        self._section(frame.body, title, "")
        self._team_filter_bar(frame.body)
        if not matches:
            self._empty(frame.body, "暂无可显示的比赛。")
            return
        for match in matches:
            self._match_card(frame.body, match, live=mode == "live")

    def _refresh_live_commentary(self, snapshot: Snapshot, force: bool = False) -> None:
        for match in snapshot.matches:
            if match.is_live:
                self._load_match_commentary(match, force=force)

    def _commentary_poll(self) -> None:
        try:
            if self.snapshot:
                self._refresh_live_commentary(self.snapshot, force=True)
            self.root.after(2000, self._commentary_poll)
        except tk.TclError:
            pass

    def _load_match_commentary(
        self,
        match: Match,
        force: bool = False,
        request_summary: bool = False,
    ) -> None:
        if request_summary:
            self.summary_requested.add(match.id)
        if match.id in self.commentary_loading:
            return
        self.commentary_loading.add(match.id)
        use_ai = bool(self.ai_commentary_var.get())
        translate_raw = bool(self.ai_translate_raw_var.get())
        free_translate = bool(self.free_translate_var.get())
        api_key = self._current_ai_credential()
        ai_slot = bool(
            api_key
            and (use_ai or translate_raw)
            and match.id not in self.commentary_ai_loading
        )
        if ai_slot:
            self.commentary_ai_loading.add(match.id)

        def worker() -> None:
            entries, _detail, error = self.provider.get_match_commentary(
                match.id,
                live=match.is_live,
                force=force,
            )
            mode = "narration_v3" if use_ai else "translations"
            translations = self.commentary_service.event_texts(match.id, mode=mode)
            translations.update(
                self.commentary_service.event_texts(
                    match.id,
                    mode="detail_narration_v4",
                )
            )
            ai_error = ""
            ai_requested = bool(entries and ai_slot)
            immediate = dict(translations)
            if not (use_ai or translate_raw or free_translate):
                for entry in entries[-6:]:
                    immediate.setdefault(entry.sequence, entry.text)
            self._post_ui(
                lambda current=match, rows=entries, texts=immediate, detail_error=error:
                self._apply_commentary_source_result(current, rows, texts, detail_error or "")
            )
            if ai_requested:
                try:
                    if use_ai:
                        translations = self.commentary_service.narrate_events(match, entries, api_key)
                    else:
                        translations = self.commentary_service.translate_events(match, entries, api_key)
                except Exception as exc:
                    ai_error = str(exc)
            if entries and free_translate and (not ai_requested or ai_error):
                glossary = self._commentary_glossary(match, entries[-6:])
                for entry in entries[-6:]:
                    if entry.sequence in translations and not ai_error:
                        continue
                    try:
                        translations[entry.sequence] = self.free_translation_service.translate(entry.text, glossary)
                    except Exception:
                        translations[entry.sequence] = entry.text
            self._post_ui(
                lambda current=match, rows=entries, texts=translations, detail_error=error, model_error=ai_error, summarize=request_summary, owns_ai_slot=ai_slot:
                self._apply_commentary_result(
                    current,
                    rows,
                    texts,
                    detail_error or model_error or "",
                    request_summary=summarize,
                    release_ai_slot=owns_ai_slot,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _commentary_glossary(self, match: Match, entries: list[CommentaryEntry]) -> dict[str, str]:
        text = " ".join(entry.text for entry in entries).casefold()
        mappings = {
            match.home.name: self._team_text(match.home),
            match.away.name: self._team_text(match.away),
            **self.localizer.players,
        }
        return {
            source: target for source, target in mappings.items()
            if source and len(source) >= 3 and source.casefold() in text
        }

    def _apply_commentary_source_result(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        translations: dict[int, str],
        error: str,
    ) -> None:
        self.commentary_loading.discard(match.id)
        self._merge_commentary_entries(match.id, entries)
        self._merge_commentary_texts(match.id, translations)
        if error:
            self.commentary_errors[match.id] = error
        else:
            self.commentary_errors.pop(match.id, None)
        self._update_commentary_labels(match.id)
        self._render_detail_commentary(match)

    def _apply_commentary_result(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        translations: dict[int, str],
        error: str,
        request_summary: bool = False,
        release_ai_slot: bool = False,
    ) -> None:
        self.commentary_loading.discard(match.id)
        if release_ai_slot:
            self.commentary_ai_loading.discard(match.id)
        self._merge_commentary_entries(match.id, entries)
        self._merge_commentary_texts(match.id, translations)
        if error:
            self.commentary_errors[match.id] = error
        else:
            self.commentary_errors.pop(match.id, None)
        self._update_commentary_labels(match.id)
        self._render_detail_commentary(match)
        self._speak_new_commentary(match)
        should_summarize = request_summary or match.id in self.summary_requested
        self.summary_requested.discard(match.id)
        latest_match = next(
            (current for current in self.snapshot.matches if current.id == match.id),
            match,
        ) if self.snapshot else match
        if should_summarize and latest_match.completed:
            self._request_match_summary(latest_match)
        elif should_summarize:
            self.summary_requested.add(match.id)
        mode = "narration_v3" if self.ai_commentary_var.get() else "translations"
        detail_open = match.id in self.detail_commentary_panels
        ai_enabled = self.ai_commentary_var.get() or self.ai_translate_raw_var.get()
        if (
            not error
            and ai_enabled
            and self.agnes_api_key_var.get().strip()
            and (latest_match.is_live or detail_open)
            and self.commentary_service.needs_event_backfill(match.id, entries, mode)
        ):
            self.root.after(
                3600,
                lambda current=latest_match: self._load_match_commentary(current, force=False),
            )
        if (
            detail_open
            and latest_match.id not in self.detail_commentary_snapshots
            and latest_match.id not in self.detail_commentary_loading
        ):
            self._load_complete_detail_commentary(
                latest_match,
                request_summary=latest_match.completed,
            )
        elif (
            latest_match.is_live
            and latest_match.id not in self.live_detail_prewarmed
            and latest_match.id not in self.detail_commentary_loading
        ):
            self.live_detail_prewarmed.add(latest_match.id)
            self.root.after(
                80,
                lambda current=latest_match:
                self._load_complete_detail_commentary(
                    current,
                    background=True,
                ),
            )

    def _merge_commentary_entries(
        self,
        match_id: str,
        entries: list[CommentaryEntry],
    ) -> None:
        if not entries:
            return
        merged = {
            entry.sequence: entry
            for entry in self.commentary_entries.get(match_id, [])
        }
        merged.update({entry.sequence: entry for entry in entries})
        self.commentary_entries[match_id] = [
            merged[sequence]
            for sequence in sorted(merged)
        ]

    def _merge_commentary_texts(
        self,
        match_id: str,
        translations: dict[int, str],
    ) -> None:
        merged = dict(self.commentary_texts.get(match_id, {}))
        merged.update(
            {
                sequence: text
                for sequence, text in translations.items()
                if str(text or "").strip()
            }
        )
        self.commentary_texts[match_id] = merged

    def _speak_new_commentary(self, match: Match) -> None:
        if not self.tts_enabled_var.get() or not match.is_live:
            return
        entries = [
            entry for entry in self.commentary_entries.get(match.id, [])
            if self._is_chinese_commentary(
                self.commentary_texts.get(match.id, {}).get(entry.sequence, "")
            )
        ]
        if not entries:
            return
        entries.sort(key=lambda entry: entry.sequence)
        previous = self.spoken_commentary_sequences.get(match.id)
        if previous is None:
            pending = entries[-1:]
        else:
            pending = [entry for entry in entries if entry.sequence > previous]
        for entry in pending[-3:]:
            text = self._localize_commentary_names(
                self.commentary_texts.get(match.id, {}).get(entry.sequence, "")
            ).strip()
            minute = str(entry.minute or "").strip()
            if minute and text.startswith(minute):
                text = text[len(minute):].lstrip(" ：:.-—")
            if text:
                self.speech_service.speak(
                    text[:180],
                    self.tts_voice_var.get(),
                    self.tts_rate_var.get(),
                )
        self.spoken_commentary_sequences[match.id] = entries[-1].sequence

    @staticmethod
    def _is_chinese_commentary(text: str) -> bool:
        value = str(text or "")
        chinese_count = len(re.findall(r"[\u3400-\u9fff]", value))
        latin_count = len(re.findall(r"[A-Za-z]", value))
        return chinese_count >= 2 and latin_count <= chinese_count * 3

    def _load_complete_detail_commentary(
        self,
        match: Match,
        request_summary: bool = False,
        background: bool = False,
    ) -> None:
        if request_summary:
            self.summary_requested.add(match.id)
        if match.id in self.detail_commentary_loading:
            return
        self.detail_commentary_loading.add(match.id)
        self.detail_commentary_errors.pop(match.id, None)
        self._render_detail_commentary(match)
        api_key = self._current_ai_credential()
        free_translate = self.free_translate_var.get()
        current_texts = dict(self.commentary_texts.get(match.id, {}))

        def worker() -> None:
            entries, _detail, source_error = self.provider.get_match_commentary(
                match.id,
                live=match.is_live,
                force=match.is_live,
            )
            translations: dict[int, str] = (
                self.commentary_service.event_texts(
                    match.id,
                    mode="detail_narration_v4",
                )
            )
            translations.update(
                {
                    sequence: text
                    for sequence, text in current_texts.items()
                    if self._is_chinese_commentary(text)
                }
            )
            error = source_error or ""
            missing_entries = [
                entry
                for entry in entries
                if entry.sequence not in translations
            ]
            if (
                not error
                and missing_entries
                and background
                and match.is_live
                and free_translate
            ):
                try:
                    glossary = self._commentary_glossary(
                        match,
                        missing_entries,
                    )
                    rows = self.free_translation_service.translate_many(
                        [entry.text for entry in missing_entries],
                        glossary,
                    )
                    translations.update(
                        {
                            entry.sequence: text
                            for entry, text in zip(missing_entries, rows)
                            if self._is_chinese_commentary(text)
                        }
                    )
                except Exception as exc:
                    error = self._friendly_commentary_error(exc)
            elif not error and missing_entries and api_key:
                try:
                    translations.update(
                        self.commentary_service.translate_complete_timeline(
                        match,
                        entries,
                        api_key,
                        )
                    )
                except Exception as exc:
                    error = self._friendly_commentary_error(exc)
            elif not error and missing_entries and free_translate:
                try:
                    glossary = self._commentary_glossary(
                        match,
                        missing_entries,
                    )
                    rows = self.free_translation_service.translate_many(
                        [entry.text for entry in missing_entries],
                        glossary,
                    )
                    translations.update(
                        {
                            entry.sequence: text
                            for entry, text in zip(missing_entries, rows)
                        }
                    )
                except Exception as exc:
                    error = self._friendly_commentary_error(exc)
            elif not error and missing_entries and not api_key:
                error = "未设置 AI API Key，且免费中文翻译未开启"
            self._post_ui(
                lambda current=match, rows=entries, texts=translations, detail_error=error, summarize=request_summary:
                self._apply_complete_detail_commentary(
                    current,
                    rows,
                    texts,
                    detail_error,
                    request_summary=summarize,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _apply_complete_detail_commentary(
        self,
        match: Match,
        entries: list[CommentaryEntry],
        translations: dict[int, str],
        error: str,
        request_summary: bool = False,
    ) -> None:
        self.detail_commentary_loading.discard(match.id)
        valid_texts = {
            entry.sequence: translations[entry.sequence]
            for entry in entries
            if (
                entry.sequence in translations
                and self._is_chinese_commentary(translations[entry.sequence])
            )
        }
        if valid_texts:
            ordered_entries = [
                entry
                for entry in sorted(entries, key=lambda row: row.sequence)
                if entry.sequence in valid_texts
            ]
            self.detail_commentary_snapshots[match.id] = (
                ordered_entries,
                valid_texts,
            )
            self._merge_commentary_entries(match.id, entries)
            self._merge_commentary_texts(match.id, valid_texts)
        complete = bool(entries) and len(valid_texts) == len(entries)
        if complete:
            self.live_detail_prewarmed.add(match.id)
            if error:
                self.detail_commentary_errors[match.id] = error
            else:
                self.detail_commentary_errors.pop(match.id, None)
        elif error:
            self.detail_commentary_errors[match.id] = error
        elif match.is_live and valid_texts:
            self.detail_commentary_errors.pop(match.id, None)
        else:
            self.detail_commentary_errors[match.id] = "完整中文时间线尚未生成"
        if not complete and match.is_live:
            self.root.after(
                60000,
                lambda match_id=match.id:
                self.live_detail_prewarmed.discard(match_id),
            )
        self._update_commentary_labels(match.id)
        self._render_detail_commentary(match)
        should_summarize = request_summary or match.id in self.summary_requested
        self.summary_requested.discard(match.id)
        if should_summarize and match.completed and entries:
            self._merge_commentary_entries(match.id, entries)
            self._request_match_summary(match)

    def _request_match_summary(self, match: Match) -> None:
        if match.id in self.summary_loading:
            return
        entries = self.commentary_entries.get(match.id, [])
        signature = self.commentary_service.summary_signature(match, entries)
        cached = self.commentary_service.summary(match.id, signature)
        if cached:
            self.summary_texts[match.id] = cached
            self._update_summary_label(match.id)
            return
        api_key = self._current_ai_credential()
        if not api_key:
            self.summary_errors[match.id] = "未设置 AI API Key，暂时无法生成比赛总结。"
            self._update_summary_label(match.id)
            return
        self.summary_loading.add(match.id)
        self._update_summary_label(match.id)

        def worker() -> None:
            try:
                text = self.commentary_service.summarize_match(match, entries, api_key)
                error = ""
            except Exception as exc:
                text = ""
                error = str(exc)
            self._post_ui(lambda: self._apply_summary_result(match.id, text, error))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_summary_result(self, match_id: str, text: str, error: str) -> None:
        self.summary_loading.discard(match_id)
        if text:
            self.summary_texts[match_id] = text
            self.summary_errors.pop(match_id, None)
        elif error:
            self.summary_errors[match_id] = f"AI 总结暂不可用：{error}"
        self._update_summary_label(match_id)

    def _commentary_text(self, match_id: str, entry: CommentaryEntry) -> str:
        if self._commentary_ai_mode():
            translated = self.commentary_texts.get(match_id, {}).get(entry.sequence)
            if translated:
                return self._localize_commentary_names(translated)
            if not self.commentary_errors.get(match_id):
                return ""
        return self._localize_commentary_names(entry.text)

    def _localize_commentary_names(self, text: str) -> str:
        value = str(text or "")
        if not value or self.use_english_var.get():
            return value
        mappings = {
            **self.localizer.teams_by_name,
            **self.localizer.players,
        }
        candidates = [
            (source, target)
            for source, target in mappings.items()
            if (
                source
                and target
                and source != target
                and len(source) >= 4
                and source.casefold() in value.casefold()
            )
        ]
        for source, target in sorted(
            candidates,
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            value = re.sub(
                rf"(?<![\w]){re.escape(source)}(?![\w])",
                target,
                value,
                flags=re.IGNORECASE,
            )
        return value

    @staticmethod
    def _friendly_commentary_error(error: Exception | str) -> str:
        text = str(error or "").strip()
        lowered = text.lower()
        if "timed out" in lowered or "timeout" in lowered or "超时" in text:
            return "AI 中文润色请求超时，已显示原始文字直播；稍后重新打开可自动重试。"
        if "401" in text or "unauthorized" in lowered:
            return "AI API Key 无效，已显示原始文字直播；请在设置中重新填写。"
        if "403" in text or "forbidden" in lowered:
            return "AI 接口拒绝访问，已显示原始文字直播；请检查 API 权限。"
        if "name or service not known" in lowered or "getaddrinfo" in lowered:
            return "当前无法解析 AI 服务地址，已显示原始文字直播；请检查网络连接。"
        if "connection" in lowered or "network" in lowered or "urlopen" in lowered:
            return "AI 服务连接暂时中断，已显示原始文字直播；稍后重新打开可自动重试。"
        return f"AI 中文润色暂时不可用，已显示原始文字直播：{text or '未知错误'}"

    def _commentary_ai_mode(self) -> bool:
        return bool(
            self.ai_commentary_var.get()
            or self.ai_translate_raw_var.get()
            or self.free_translate_var.get()
        )

    def _commentary_line(self, match_id: str, entry: CommentaryEntry) -> str:
        prefix = f"{entry.minute} " if entry.minute else ""
        return f"{prefix}{self._commentary_text(match_id, entry)}".strip()

    @staticmethod
    def _commentary_emphasis(entry: CommentaryEntry) -> tuple[str, bool]:
        text = entry.text.lower()
        if any(
            phrase in text
            for phrase in (
                "red card",
                "sent off",
                "second yellow",
                "serious injury",
                "stretcher",
                "unable to continue",
                "concussion",
                "medical emergency",
                "injury stoppage",
                "delay in match because of an injury",
                "receives medical treatment",
            )
        ):
            return LIVE, True
        if any(
            phrase in text
            for phrase in (
                "goal!",
                "penalty awarded",
                "penalty saved",
                "penalty missed",
                "penalty conceded",
                "var decision",
                "hits the post",
                "hits the crossbar",
            )
        ):
            return ACCENT, True
        if "yellow card" in text or "is shown the yellow card" in text:
            return WARNING, True
        return "", False

    def _update_all_commentary_labels(self) -> None:
        for match_id in tuple(self.commentary_labels):
            self._update_commentary_labels(match_id)
        if self.match_popup is not None and self.match_popup.winfo_exists() and self.snapshot:
            for match in self.snapshot.matches:
                if match.id in self.detail_commentary_panels:
                    self._render_detail_commentary(match)

    def _update_commentary_labels(self, match_id: str) -> None:
        labels = self.commentary_labels.get(match_id, [])
        entries = list(reversed(self.commentary_entries.get(match_id, [])))
        visible_entries = [
            entry for entry in entries
            if self._commentary_text(match_id, entry)
        ]
        for index, label in enumerate(labels):
            if index < len(visible_entries):
                entry = visible_entries[index]
                text = self._commentary_line(match_id, entry)
                emphasis_color, emphasized = self._commentary_emphasis(entry)
                color = emphasis_color or (TEXT if index == 0 else MUTED)
                font = (self.ui_font_var.get(), 8, "bold" if emphasized else "normal")
            elif (
                index == len(visible_entries)
                and self._commentary_ai_mode()
                and not self.commentary_errors.get(match_id)
                and len(visible_entries) < len(entries)
            ):
                text = "正在补全中文解说…"
                color = MUTED
                font = (self.ui_font_var.get(), 8, "normal")
            elif index == 0 and match_id in self.commentary_loading:
                text = "正在获取实时文字直播…"
                color = MUTED
                font = (self.ui_font_var.get(), 8, "normal")
            elif index == 0 and self.commentary_errors.get(match_id):
                text = "文字直播暂时不可用"
                color = MUTED
                font = (self.ui_font_var.get(), 8, "normal")
            else:
                text = ""
                color = MUTED
                font = (self.ui_font_var.get(), 8, "normal")
            try:
                label.configure(text=text, fg=color, font=font)
            except tk.TclError:
                pass

    def _commentary_preview(self, parent: tk.Widget, match: Match) -> None:
        panel = tk.Frame(parent, bg=BG, cursor="hand2")
        panel.pack(fill="x", padx=4, pady=(0, 7))
        line_count = self._valid_commentary_lines(self.commentary_lines_var.get(), 3)
        labels: list[tk.Label] = []
        for _ in range(line_count):
            label = tk.Label(
                panel,
                text="",
                bg=BG,
                fg=MUTED,
                anchor="nw",
                justify="left",
                font=("Microsoft YaHei UI", 8),
                cursor="hand2",
            )
            label.pack(fill="x", pady=1)
            self._bind_wrap(label, reserve=8, minimum=96, maximum=420)
            labels.append(label)
            self._bind_commentary_open(label, match)
        self.commentary_labels[match.id] = labels
        self._bind_commentary_open(panel, match)
        self._update_commentary_labels(match.id)

    def render_upcoming(self) -> None:
        frame = self.tabs["upcoming"]
        frame.clear()
        self._section(frame.body, "即将进行的比赛", "按开赛时间排序")
        self._team_filter_bar(frame.body)
        rounds = self._round_groups()
        selected_slug = self._selected_round_slug("upcoming", rounds)
        self._round_navigator(
            frame.body,
            "upcoming",
            rounds,
            selected_slug,
            allow_all=False,
        )
        selected_ids = {
            match.id
            for slug, _label, rows in rounds
            if slug == selected_slug
            for match in rows
        }
        matches = [
            match for match in self._filtered_matches()
            if match.is_upcoming
            and (not selected_slug or match.id in selected_ids)
        ]
        if not matches:
            self._empty(
                frame.body,
                "本轮暂无未开始比赛，可使用左右按钮切换轮次。",
            )
            return
        matches.sort(key=lambda match: match.date or MAX_DATE)
        for match in matches:
            self._match_card(frame.body, match)

    def render_results(self) -> None:
        frame = self.tabs["results"]
        frame.clear()
        self._section(frame.body, "已完赛赛果", "点击队徽或队名可查看球队资料")
        self._team_filter_bar(frame.body)
        rounds = self._round_groups()
        selected_slug = self._selected_round_slug("results", rounds)
        self._round_navigator(
            frame.body,
            "results",
            rounds,
            selected_slug,
            allow_all=True,
        )
        show_all = self.round_selection.get("results") == "all"
        selected_ids = {
            match.id
            for slug, _label, rows in rounds
            if slug == selected_slug
            for match in rows
        }
        matches = [
            match for match in self._filtered_matches()
            if match.completed
            and (
                show_all
                or not selected_slug
                or match.id in selected_ids
            )
        ]
        matches.sort(key=lambda m: m.date or MIN_DATE, reverse=True)
        if not matches:
            self._empty(frame.body, "还没有已完赛结果。")
            return
        for match in matches:
            self._match_card(frame.body, match)

    def _round_groups(
        self,
        snapshot: Snapshot | None = None,
    ) -> list[tuple[str, str, list[Match]]]:
        snapshot = snapshot or self.snapshot
        if snapshot is None:
            return []
        order: list[str] = []
        groups: dict[str, list[Match]] = {}
        labels: dict[str, str] = {}
        for match in sorted(
            snapshot.matches,
            key=lambda item: (
                item.date or MAX_DATE,
                item.id,
            ),
        ):
            slug = match.round_slug or "round"
            if slug not in groups:
                groups[slug] = []
                order.append(slug)
                labels[slug] = match.round_name or "比赛轮次"
            groups[slug].append(match)
        if snapshot.competition_kind == "tournament":
            knockout_order = [
                "group-stage",
                "round-of-32",
                "round-of-16",
                "quarterfinals",
                "semifinals",
                "third-place",
                "final",
            ]
            group_rounds = sorted(
                (
                    slug for slug in order
                    if slug == "group-stage"
                ),
                key=lambda _slug: 0,
            )
            expanded: list[tuple[str, str, list[Match]]] = []
            if group_rounds:
                group_matches = groups["group-stage"]
                for number in sorted({
                    match.round_number
                    for match in group_matches
                    if match.round_number
                }):
                    slug = f"group-stage-{number}"
                    rows = [
                        match for match in group_matches
                        if match.round_number == number
                    ]
                    expanded.append(
                        (slug, f"小组赛第 {number} 轮", rows)
                    )
            for slug in knockout_order[1:]:
                if slug in groups:
                    expanded.append((slug, labels[slug], groups[slug]))
            return expanded
        return [
            (slug, labels[slug], groups[slug])
            for slug in sorted(
                order,
                key=lambda current: min(
                    (
                        match.round_number or 10**6
                        for match in groups[current]
                    ),
                    default=10**6,
                ),
            )
        ]

    def _current_round_slug(
        self,
        rounds: list[tuple[str, str, list[Match]]],
    ) -> str:
        for slug, _label, matches in rounds:
            if any(match.is_live for match in matches):
                return slug
        for slug, _label, matches in rounds:
            if any(match.is_upcoming for match in matches):
                return slug
        for slug, _label, matches in reversed(rounds):
            if any(match.completed for match in matches):
                return slug
        return rounds[0][0] if rounds else ""

    def _selected_round_slug(
        self,
        tab: str,
        rounds: list[tuple[str, str, list[Match]]],
    ) -> str:
        selection = self.round_selection.get(tab, "current")
        if selection == "all":
            return ""
        available = {slug for slug, _label, _matches in rounds}
        if selection in available:
            return selection
        return self._current_round_slug(rounds)

    def _round_navigator(
        self,
        parent: tk.Widget,
        tab: str,
        rounds: list[tuple[str, str, list[Match]]],
        selected_slug: str,
        allow_all: bool,
    ) -> None:
        if not rounds:
            return
        bar = tk.Frame(
            parent,
            bg=PANEL_2,
            padx=6,
            pady=5,
            highlightthickness=1,
            highlightbackground=LINE,
        )
        bar.pack(fill="x", pady=(0, 8))
        self._icon_text_button(
            bar,
            "◀",
            lambda: self._shift_round(tab, -1),
        ).pack(side="left")
        label = next(
            (
                current_label
                for slug, current_label, _matches in rounds
                if slug == selected_slug
            ),
            "全部赛果" if self.round_selection.get(tab) == "all" else "当前轮次",
        )
        center = tk.Label(
            bar,
            text=label,
            bg=PANEL_2,
            fg=TEXT,
            anchor="center",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        center.pack(side="left", fill="x", expand=True, padx=6)
        self._bind_wrap(center, reserve=118 if allow_all else 72, minimum=90, maximum=230)
        self._icon_text_button(
            bar,
            "▶",
            lambda: self._shift_round(tab, 1),
        ).pack(side="right")
        if allow_all:
            all_button = tk.Label(
                bar,
                text="全部",
                bg=PANEL_3 if self.round_selection.get(tab) == "all" else PANEL_2,
                fg=ACCENT if self.round_selection.get(tab) == "all" else MUTED,
                cursor="hand2",
                padx=6,
                pady=4,
                font=("Microsoft YaHei UI", 8, "bold"),
            )
            all_button.pack(side="right", padx=(5, 0))
            self._bind_click(
                all_button,
                lambda _event: self._toggle_all_rounds(tab),
            )

    def _icon_text_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
    ) -> tk.Label:
        button = tk.Label(
            parent,
            text=text,
            bg=PANEL_2,
            fg=ACCENT,
            cursor="hand2",
            padx=6,
            pady=4,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self._bind_click(button, lambda _event: command())
        return button

    def _shift_round(self, tab: str, direction: int) -> None:
        rounds = self._round_groups()
        if not rounds:
            return
        current = self._selected_round_slug(tab, rounds)
        slugs = [slug for slug, _label, _matches in rounds]
        try:
            index = slugs.index(current)
        except ValueError:
            index = 0
        index = max(0, min(len(slugs) - 1, index + direction))
        self.round_selection[tab] = slugs[index]
        self._invalidate_render_cache(tab)
        if self.active_tab == tab:
            self.render_active()

    def _toggle_all_rounds(self, tab: str) -> None:
        self.round_selection[tab] = (
            "current"
            if self.round_selection.get(tab) == "all"
            else "all"
        )
        self._invalidate_render_cache(tab)
        if self.active_tab == tab:
            self.render_active()

    def render_standings(self) -> None:
        frame = self.tabs["standings"]
        frame.clear()
        is_league = bool(
            self.snapshot
            and self.snapshot.competition_kind == "league"
        )
        self._section(
            frame.body,
            "联赛积分" if is_league else "小组积分",
            (
                f"{self._season_label(snapshot=self.snapshot)} · "
                "胜平负、进失球、净胜球与积分"
            ),
        )
        self._team_filter_bar(frame.body)
        groups = self.snapshot.standings if self.snapshot else []
        if self.selected_team_id and not is_league:
            team = self.snapshot.teams.get(self.selected_team_id)
            groups = [g for g in groups if g.get("name") == (team.group if team else "")]
        if not groups:
            self._empty(frame.body, "积分榜暂时不可用。")
            return
        for group in groups:
            self._standings_group(frame.body, group)

    def render_bracket(self) -> None:
        frame = self.tabs["bracket"]
        frame.clear()
        if self.snapshot and self.snapshot.competition_kind == "league":
            self._empty(frame.body, "联赛没有淘汰赛阶段。")
            return
        self._section(frame.body, "淘汰赛对阵图", "未出结果的位置会显示组别排名或待定")
        self._team_filter_bar(frame.body)
        order = ["round-of-32", "round-of-16", "quarterfinals", "semifinals", "third-place", "final"]
        knockout = [m for m in self.snapshot.matches if m.round_slug != "group-stage"] if self.snapshot else []
        if self.selected_team_id:
            knockout = [m for m in knockout if m.home.id == self.selected_team_id or m.away.id == self.selected_team_id]
        if not knockout:
            self._empty(frame.body, "淘汰赛对阵尚未生成，或当前球队暂未进入淘汰赛。")
            return
        for slug in order:
            round_matches = [m for m in knockout if m.round_slug == slug]
            if not round_matches:
                continue
            self._section(frame.body, round_matches[0].round_name)
            for match in round_matches:
                self._match_card(frame.body, match)

    def render_data(self) -> None:
        frame = self.tabs["data"]
        frame.clear()
        is_league = bool(
            self.snapshot
            and self.snapshot.competition_kind == "league"
        )
        self._section(
            frame.body,
            "联赛数据中心" if is_league else "数据面板",
            (
                f"{self._data_board_season_label()} · "
                "射手、助攻、参与进球、球队表现与积分数据"
            ),
        )
        boards = self._data_boards()
        if not boards:
            self._empty(frame.body, "球员榜单暂时不可用。")
            return
        if not self.active_data_board_key or self.active_data_board_key not in {board.key for board in boards}:
            self.active_data_board_key = boards[0].key
        switch = tk.Frame(frame.body, bg=BG)
        switch.pack(fill="x", pady=(0, 8))
        self.data_board_buttons.clear()
        self.data_board_button_order = []
        for board in boards:
            active = board.key == self.active_data_board_key
            button = tk.Label(
                switch,
                text=self._board_text(board.key, board.name),
                bg=PANEL_3 if active else PANEL,
                fg=ACCENT if active else MUTED,
                padx=10,
                pady=6,
                cursor="hand2",
                font=("Microsoft YaHei UI", 8, "bold"),
            )
            self._bind_click(button, lambda _event, key=board.key: self._select_data_board(key))
            self.data_board_buttons[board.key] = button
            self.data_board_button_order.append(board.key)
        switch.bind("<Configure>", self._layout_data_board_buttons, add="+")
        self.root.after_idle(self._layout_data_board_buttons)
        selected = next(board for board in boards if board.key == self.active_data_board_key)
        self._leaderboard(frame.body, selected)

    def render_news(self) -> None:
        frame = self.tabs["news"]
        frame.clear()
        if not self.snapshot:
            self._empty(frame.body, "正在准备赛事资讯…")
            return
        self._section(
            frame.body,
            f"{self.snapshot.competition_name}资讯",
            f"近 {self.news_weeks_var.get()} 周 · 赛事与主队重要动态",
        )
        key = self.snapshot.competition_key
        if key not in self.news_items:
            self._load_news(self.snapshot, priority=True)
        items = self.news_items.get(key, [])
        if key in self.news_loading and not items:
            self._empty(frame.body, "正在整理赛事资讯…")
            return
        if not items:
            self._empty(frame.body, "所选时间范围内暂无资讯。")
            return
        favorite = self.favorite_teams.get(key, "")
        for item in items:
            if not self._contains_chinese(item.translated_title):
                continue
            glossary = self._news_glossary(item)
            item.translated_title = self._enforce_glossary(item.translated_title, glossary)
            item.translated_summary = self._enforce_glossary(item.translated_summary, glossary)
            card = tk.Frame(
                frame.body,
                bg=PANEL,
                padx=11,
                pady=9,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=ACCENT if favorite and favorite in item.team_ids else LINE,
            )
            card.pack(fill="x", pady=4)
            meta = f"{item.published.strftime('%m-%d %H:%M')} · {item.source}"
            if favorite and favorite in item.team_ids:
                meta += " · 主队"
            tk.Label(card, text=meta, bg=PANEL, fg=ACCENT, anchor="w", font=("Microsoft YaHei UI", 8, "bold")).pack(fill="x")
            title = tk.Label(
                card,
                text=item.translated_title,
                bg=PANEL,
                fg=TEXT,
                anchor="w",
                justify="left",
                font=("Microsoft YaHei UI", 10, "bold"),
            )
            title.pack(fill="x", pady=(4, 0))
            self._bind_wrap(title, reserve=6, minimum=120, maximum=390)
            for widget in (card, title):
                self._bind_click(widget, lambda _event, current=item: self._open_news_detail(current))

    def _queue_startup_news(self) -> None:
        favorite_keys = [
            key
            for key in COMPETITIONS
            if self.favorite_teams.get(key)
        ]
        if self.active_competition_key in favorite_keys:
            ordered = [
                self.active_competition_key,
                *(
                    key
                    for key in favorite_keys
                    if key != self.active_competition_key
                ),
            ]
        else:
            ordered = [
                *favorite_keys,
                self.active_competition_key,
            ]
        for key in ordered:
            self._load_news(key, priority=False)

    def _load_news(
        self,
        snapshot_or_key: Snapshot | str,
        force: bool = False,
        priority: bool = True,
    ) -> None:
        key = (
            snapshot_or_key.competition_key
            if isinstance(snapshot_or_key, Snapshot)
            else str(snapshot_or_key)
        )
        if key not in COMPETITIONS:
            return
        with self.news_queue_lock:
            if key == self.news_active_key:
                return
            if key in self.news_items and not force:
                return
            if key in self.news_queued:
                if priority:
                    queued_task = next(
                        (
                            task
                            for task in self.news_queue
                            if task[0] == key
                        ),
                        None,
                    )
                    if queued_task is not None:
                        self.news_queue.remove(queued_task)
                        self.news_queue.appendleft(queued_task)
                return
            if key in self.news_loading:
                return
            task = (
                key,
                force,
                self.news_weeks_var.get(),
                self._current_ai_credential(),
                self.favorite_teams.get(key, ""),
            )
            if priority:
                self.news_queue.appendleft(task)
            else:
                self.news_queue.append(task)
            self.news_queued.add(key)
            self.news_loading.add(key)
            if self.news_worker_running:
                return
            self.news_worker_running = True
        threading.Thread(
            target=self._news_worker_loop,
            daemon=True,
        ).start()

    def _news_worker_loop(self) -> None:
        while True:
            with self.news_queue_lock:
                if not self.news_queue:
                    self.news_worker_running = False
                    return
                key, force, weeks, api_key, favorite = (
                    self.news_queue.popleft()
                )
                self.news_queued.discard(key)
                self.news_active_key = key
            try:
                self._prepare_news(
                    key,
                    force,
                    weeks,
                    api_key,
                    favorite,
                )
            except Exception:
                self._post_ui(
                    lambda current_key=key:
                    self._apply_news(
                        current_key,
                        [],
                        translating=False,
                    )
                )
            finally:
                with self.news_queue_lock:
                    if self.news_active_key == key:
                        self.news_active_key = ""

    def _prepare_news(
        self,
        key: str,
        force: bool,
        weeks: int,
        api_key: object,
        favorite: str,
    ) -> None:
        espn_league = str(COMPETITIONS[key]["espn"])
        items = self.news_service.fetch(
            espn_league,
            weeks=weeks,
            favorite_team_id=favorite,
            force=force,
        )
        pending: list[NewsItem] = []
        for item in items:
            item.translated_title, item.translated_summary = (
                self.news_service.cached_translation(
                    item.id,
                    require_ai=bool(api_key),
                    source_title=item.title,
                    source_summary=item.summary,
                )
            )
            if item.translated_title:
                item_glossary = self._news_glossary(item)
                item.translated_title = self._enforce_glossary(
                    item.translated_title,
                    item_glossary,
                )
                item.translated_summary = self._enforce_glossary(
                    item.translated_summary,
                    item_glossary,
                )
            if not self._contains_chinese(item.translated_title):
                item.translated_title = ""
                item.translated_summary = ""
                pending.append(item)
        ready = [
            item
            for item in items
            if self._contains_chinese(item.translated_title)
        ]
        if ready:
            self._post_ui(
                lambda current=list(ready), current_key=key:
                self._apply_news(
                    current_key,
                    current,
                    translating=True,
                )
            )
        glossary: dict[str, str] = {}
        for item in pending:
            glossary.update(self._news_glossary(item))
        if api_key:
            for start in range(0, len(pending), 8):
                batch = pending[start:start + 8]
                try:
                    translated = (
                        self.commentary_service.translate_news_batch(
                            [
                                {
                                    "id": item.id,
                                    "title": self._normalize_news_source_title(
                                        item.title,
                                        self._news_glossary(item),
                                    ),
                                    "summary": item.summary,
                                }
                                for item in batch
                            ],
                            glossary,
                            api_key,
                        )
                    )
                except Exception:
                    translated = {}
                for item in batch:
                    item.translated_title, item.translated_summary = (
                        translated.get(item.id, ("", ""))
                    )
        unresolved = [
            item
            for item in pending
            if not self._contains_chinese(item.translated_title)
        ]
        if unresolved:
            texts = [
                text
                for item in unresolved
                for text in (
                    self._normalize_news_source_title(
                        item.title,
                        self._news_glossary(item),
                    ),
                    item.summary,
                )
            ]
            try:
                translated_rows = (
                    self.free_translation_service.translate_many(
                        texts,
                        glossary,
                    )
                )
            except Exception:
                translated_rows = []
            for index, item in enumerate(unresolved):
                item.translated_title = (
                    translated_rows[index * 2]
                    if index * 2 < len(translated_rows)
                    else ""
                )
                item.translated_summary = (
                    translated_rows[index * 2 + 1]
                    if index * 2 + 1 < len(translated_rows)
                    else ""
                )
        for item in pending:
            provider = (
                "ai"
                if api_key and item not in unresolved
                else "free"
            )
            item_glossary = self._news_glossary(item)
            item.translated_title = self._enforce_glossary(
                item.translated_title,
                item_glossary,
            )
            item.translated_summary = self._enforce_glossary(
                item.translated_summary,
                item_glossary,
            )
            valid_title = self._contains_chinese(
                item.translated_title
            )
            valid_summary = self._contains_chinese(
                item.translated_summary
            )
            if valid_title:
                if not valid_summary:
                    item.translated_summary = (
                        "该资讯暂未提供可用的中文摘要。"
                    )
                self.news_service.store_translation(
                    item.id,
                    item.translated_title,
                    item.translated_summary,
                    provider=provider,
                    source_title=item.title,
                    source_summary=item.summary,
                )
            else:
                item.translated_title = "资讯中文化暂时不可用"
                item.translated_summary = (
                    "暂时无法生成中文内容，请稍后刷新。"
                )
        self._post_ui(
            lambda current=items, current_key=key:
            self._apply_news(
                current_key,
                current,
                translating=False,
            )
        )

    def _news_glossary(
        self,
        item: NewsItem,
        extra_text: str = "",
    ) -> dict[str, str]:
        text = f"{item.title} {item.summary} {extra_text}".casefold()
        mappings = {
            **self.localizer.teams_by_name,
            **self.localizer.players,
        }
        return {
            source: target
            for source, target in mappings.items()
            if len(source) >= 3 and source.casefold() in text
        }

    @staticmethod
    def _normalize_news_source_title(
        title: str,
        glossary: dict[str, str],
    ) -> str:
        result = " ".join(str(title or "").split())
        for source in sorted(glossary, key=len, reverse=True):
            if not source:
                continue
            escaped = re.escape(source)
            result = re.sub(
                rf"\bafter\s+{escaped}\s+strike\b",
                f"after scoring against {source}",
                result,
                flags=re.IGNORECASE,
            )
            result = re.sub(
                rf"\bafter\s+{escaped}\s+double\b",
                f"after scoring twice against {source}",
                result,
                flags=re.IGNORECASE,
            )
        return result

    @staticmethod
    def _enforce_glossary(text: str, glossary: dict[str, str]) -> str:
        result = str(text or "")
        for source, target in sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True):
            result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
        return result

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        return bool(re.search(r"[\u3400-\u9fff]", str(text or "")))

    @staticmethod
    def _news_translation_chunks(text: str, limit: int = 330) -> list[str]:
        paragraphs = [
            re.sub(r"\s+", " ", paragraph).strip()
            for paragraph in re.split(r"\n+", str(text or ""))
            if paragraph.strip()
        ]
        chunks: list[str] = []
        for paragraph in paragraphs:
            remaining = paragraph
            while len(remaining) > limit:
                split_at = max(
                    remaining.rfind(". ", 0, limit),
                    remaining.rfind("? ", 0, limit),
                    remaining.rfind("! ", 0, limit),
                    remaining.rfind("; ", 0, limit),
                )
                if split_at < limit // 2:
                    split_at = limit
                else:
                    split_at += 1
                chunks.append(remaining[:split_at].strip())
                remaining = remaining[split_at:].strip()
            if remaining:
                chunks.append(remaining)
        return chunks

    def _translate_news_content_free(
        self,
        text: str,
        glossary: dict[str, str],
    ) -> str:
        chunks = self._news_translation_chunks(text)
        if not chunks:
            return ""
        try:
            translated = self.free_translation_service.translate_many(
                chunks,
                glossary,
            )
        except Exception:
            return ""
        rows = [
            self._enforce_glossary(row, glossary)
            for row in translated
            if self._contains_chinese(row)
        ]
        return "\n\n".join(rows)

    def _apply_news(self, key: str, items: list[NewsItem], translating: bool) -> None:
        self.news_items[key] = items
        if not translating:
            self.news_loading.discard(key)
        self._invalidate_render_cache("news")
        if self.active_competition_key == key and self.active_tab == "news":
            self.render_news()

    def _open_news_detail(self, item: NewsItem) -> None:
        self._prepare_single_popup(clear_history=True)
        popup = tk.Toplevel(self.root)
        self.news_popup = popup
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.98)
        popup.bind(
            "<Destroy>",
            lambda event, current=popup:
            setattr(self, "news_popup", None)
            if event.widget is current and self.news_popup is current else None,
            add="+",
        )
        width = min(350, max(286, self.root.winfo_width() - 16))
        height = min(430, max(330, self.root.winfo_height() - 36))
        popup.geometry(f"{width}x{height}+{self.root.winfo_x() + 8}+{self.root.winfo_y() + 20}")
        header = tk.Frame(popup, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        title = tk.Label(header, text="资讯详情", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 11, "bold"))
        title.pack(side="left")
        close = tk.Label(header, text="×", bg=PANEL, fg=MUTED, cursor="hand2", font=("Microsoft YaHei UI", 13, "bold"))
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_news_popup())
        self._bind_drag(header)
        body = ScrollFrame(popup, bg=PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        headline = tk.Label(body.body, text=item.translated_title, bg=PANEL, fg=TEXT, anchor="w", justify="left", font=("Microsoft YaHei UI", 13, "bold"))
        headline.pack(fill="x")
        self._bind_wrap(headline, reserve=8, minimum=150, maximum=320)
        tk.Label(body.body, text=f"{item.published.strftime('%Y-%m-%d %H:%M')} · {item.source}", bg=PANEL, fg=MUTED, anchor="w", font=("Microsoft YaHei UI", 8)).pack(fill="x", pady=(6, 12))
        content = tk.Label(
            body.body,
            text="正在整理完整中文资讯…",
            bg=PANEL_2,
            fg=TEXT,
            padx=10,
            pady=10,
            anchor="nw",
            justify="left",
            font=("Microsoft YaHei UI", 9),
        )
        content.pack(fill="x")
        self._bind_wrap(content, reserve=26, minimum=130, maximum=300)
        self._text_button(body.body, "打开原文", lambda: webbrowser.open(item.url)).pack(anchor="w", pady=(12, 0))
        self._apply_fonts_to_tree(popup)
        api_key = self._current_ai_credential()
        cached_content = self.news_service.cached_content(
            item.id,
            require_ai=bool(api_key),
        )
        if self._contains_chinese(cached_content):
            item.translated_content = cached_content
            content.configure(text=cached_content)
            return

        def worker() -> None:
            raw_text = self.news_service.fetch_full_text(item)
            glossary = self._news_glossary(item, raw_text)
            translated_title = item.translated_title
            translated_content = ""
            provider = ""
            if api_key and raw_text:
                try:
                    ai_title, ai_content = (
                        self.commentary_service.rewrite_news_article(
                            item.title,
                            item.summary,
                            raw_text,
                            glossary,
                            api_key,
                        )
                    )
                    if self._contains_chinese(ai_content):
                        translated_title = (
                            ai_title
                            if self._contains_chinese(ai_title)
                            else translated_title
                        )
                        translated_content = ai_content
                        provider = "ai"
                except Exception:
                    pass
            if not translated_content:
                translated_content = self._translate_news_content_free(
                    raw_text or item.summary,
                    glossary,
                )
                if translated_content:
                    provider = "free"
            translated_title = self._enforce_glossary(
                translated_title,
                glossary,
            )
            translated_content = self._enforce_glossary(
                translated_content,
                glossary,
            )
            if not self._contains_chinese(translated_content):
                translated_content = (
                    item.translated_summary
                    if self._contains_chinese(item.translated_summary)
                    else "完整中文资讯暂时无法生成，请稍后重试。"
                )
            elif provider:
                self.news_service.store_content(
                    item.id,
                    translated_content,
                    provider=provider,
                )

            def apply() -> None:
                if self.news_popup is not popup or not popup.winfo_exists():
                    return
                item.translated_title = translated_title
                item.translated_content = translated_content
                headline.configure(text=translated_title)
                content.configure(text=translated_content)

            self._post_ui(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _select_data_board(self, key: str) -> None:
        self.active_data_board_key = key
        if self.active_tab == "data":
            self.render_data()

    def _data_boards(self, snapshot: Snapshot | None = None) -> list[Leaderboard]:
        snapshot = snapshot or self.snapshot
        if not snapshot:
            return []
        boards = list(
            self.professional_boards_cache.get(
                snapshot.competition_key,
                snapshot.leaderboards,
            )
        )
        goals_board = next((board for board in boards if board.key == "goalsLeaders"), None)
        assists_board = next((board for board in boards if board.key == "assistsLeaders"), None)
        combined: dict[str, LeaderRow] = {}
        for board in [goals_board, assists_board]:
            if not board:
                continue
            for row in board.rows:
                current = combined.get(row.player_id)
                if current is None:
                    current = LeaderRow(
                        rank=0,
                        player_id=row.player_id,
                        player_name=row.player_name,
                        team_id=row.team_id,
                        team_name=row.team_name,
                        team_abbreviation=row.team_abbreviation,
                        team_logo=row.team_logo,
                        display_value="",
                        stats=dict(row.stats),
                    )
                    combined[row.player_id] = current
                else:
                    current.stats.update(row.stats)
        contribution_rows = []
        for row in combined.values():
            goals = self._stat_int(row.stats, "G")
            assists = self._stat_int(row.stats, "A")
            total = goals + assists
            if total <= 0:
                continue
            row.display_value = f"{total} 次 · {goals} 球 {assists} 助"
            contribution_rows.append(row)
        contribution_rows.sort(key=lambda row: (-self._stat_int(row.stats, "G") - self._stat_int(row.stats, "A"), -self._stat_int(row.stats, "G"), row.player_name))
        for index, row in enumerate(contribution_rows, start=1):
            row.rank = index
        if contribution_rows and not any(board.key == "goalContributions" for board in boards):
            boards.append(Leaderboard("goalContributions", "Goal Contributions", contribution_rows[:50]))

        team_rows: list[tuple[str, str, str]] = []
        for group in snapshot.standings:
            for entry in group.get("entries", []):
                team = entry["team"]
                stats = entry["stats"]
                team_rows.append((team.id, "teamGoals", stats.get("进", "0")))
                team_rows.append((team.id, "teamGoalDifference", stats.get("净", "0")))
                team_rows.append((team.id, "teamPoints", stats.get("分", "0")))
                team_rows.append((team.id, "teamWins", stats.get("胜", "0")))
                team_rows.append((team.id, "teamDefense", stats.get("失", "0")))
                team_rows.append((team.id, "teamPlayed", stats.get("赛", "0")))

        def team_board(key: str, label: str, suffix: str) -> Leaderboard:
            rows = []
            for team_id, row_key, value in team_rows:
                if row_key != key or team_id not in snapshot.teams:
                    continue
                team = snapshot.teams[team_id]
                display = f"{value} {suffix}".strip()
                rows.append(
                    LeaderRow(
                        rank=0,
                        player_id=team.id,
                        player_name=team.name,
                        team_id=team.id,
                        team_name=team.name,
                        team_abbreviation=team.abbreviation,
                        team_logo=team.logo,
                        display_value=display,
                        stats={"value": value},
                    )
                )
            rows.sort(key=lambda row: (-self._stat_int(row.stats, "value"), row.team_name))
            for index, row in enumerate(rows, start=1):
                row.rank = index
            return Leaderboard(key, label, rows)

        boards.append(team_board("teamGoals", "Team Goals", "球"))
        boards.append(team_board("teamGoalDifference", "Goal Difference", ""))
        boards.append(team_board("teamPoints", "Team Points", "分"))
        if snapshot.competition_kind == "league":
            boards.append(team_board("teamWins", "Team Wins", "胜"))
            defense = team_board("teamDefense", "Best Defense", "失")
            defense.rows.sort(
                key=lambda row: (
                    self._stat_int(row.stats, "value"),
                    row.team_name,
                )
            )
            for index, row in enumerate(defense.rows, start=1):
                row.rank = index
            boards.append(defense)
            boards.append(team_board("teamPlayed", "Matches Played", "场"))
        return [board for board in boards if board.rows]

    def _data_board_season_label(self) -> str:
        if not self.snapshot:
            return "赛季待定"
        seasons = self.professional_board_seasons.get(
            self.snapshot.competition_key,
            set(),
        )
        if not seasons:
            return self._season_label(snapshot=self.snapshot)
        return " / ".join(
            self._season_label(year, self.snapshot)
            for year in sorted(seasons)
        )

    def _load_professional_boards(self, snapshot: Snapshot) -> None:
        key = snapshot.competition_key
        max_age = self.roster_refresh_hours_var.get() * 3600
        if (
            key in self.professional_boards_cache
            and time.time() - self.professional_boards_loaded_at.get(key, 0) < max_age
        ) or key in self.professional_boards_loading:
            return
        self.professional_boards_loading.add(key)
        provider = DataProvider(self.provider.cache_dir, key)
        provider.teams = snapshot.teams
        provider.season_year = snapshot.season_year
        roster_ttl_hours = self.roster_refresh_hours_var.get()

        def worker() -> None:
            players: list[tuple[Player, Team]] = []
            seasons_used: set[int] = set()
            for team in snapshot.teams.values():
                roster, _error = provider.get_roster(team.id, season_year=snapshot.season_year, ttl_hours=roster_ttl_hours)
                if not any(player.stats for player in roster) and snapshot.season_year > 2000:
                    roster, _error = provider.get_roster(team.id, season_year=snapshot.season_year - 1, ttl_hours=roster_ttl_hours)
                seasons_used.update(
                    player.data_season_year
                    for player in roster
                    if player.stats and player.data_season_year
                )
                players.extend((player, team) for player in roster if player.stats)
            boards = self._professional_boards(players)
            self._post_ui(
                lambda current_seasons=seasons_used:
                self._apply_professional_boards(
                    key,
                    boards,
                    current_seasons,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _professional_boards(self, players: list[tuple[Player, Team]]) -> list[Leaderboard]:
        boards: list[Leaderboard] = []
        for key, name, stat_key, descending, suffix in PROFESSIONAL_BOARD_DEFS:
            rows: list[LeaderRow] = []
            for player, team in players:
                goals = self._stat_int(player.stats, "G")
                assists = self._stat_int(player.stats, "A")
                shots = self._stat_int(player.stats, "SHOT")
                if stat_key == "GA_TOTAL":
                    value = goals + assists
                elif stat_key == "STARTS":
                    value = max(0, self._stat_int(player.stats, "APP") - self._stat_int(player.stats, "SUB"))
                elif stat_key == "CONVERSION":
                    value = round(goals * 100 / shots, 1) if shots >= 5 else 0
                else:
                    value = self._stat_int(player.stats, stat_key)
                if value <= 0:
                    continue
                display = f"{value:g}{suffix}" if isinstance(value, float) else f"{value}{suffix}"
                rows.append(LeaderRow(0, player.id, player.name, team.id, team.name, team.abbreviation, team.logo, display, {**player.stats, "value": str(value)}))
            rows.sort(key=lambda row: (-float(row.stats.get("value", 0)), row.player_name) if descending else (float(row.stats.get("value", 0)), row.player_name))
            for index, row in enumerate(rows[:50], 1):
                row.rank = index
            if rows:
                boards.append(Leaderboard(key, name, rows[:50]))
        return boards

    def _apply_professional_boards(
        self,
        key: str,
        boards: list[Leaderboard],
        seasons: set[int] | None = None,
    ) -> None:
        self.professional_boards_loading.discard(key)
        if boards:
            self.professional_boards_cache[key] = boards
            self.professional_boards_loaded_at[key] = time.time()
            self.professional_board_seasons[key] = set(seasons or ())
            self._request_name_localization(
                "player",
                [
                    row.player_name
                    for board in boards
                    for row in board.rows
                    if self.localizer.player(row.player_name, row.player_id) == row.player_name
                ],
            )
            self._invalidate_render_cache("data")
            if self.active_competition_key == key and self.active_tab == "data":
                self.render_data()

    def _stat_int(self, stats: dict[str, str], key: str) -> int:
        try:
            return int(str(stats.get(key, "0")).replace("+", "") or 0)
        except ValueError:
            return 0

    def render_team(self) -> None:
        frame = self.tabs["team"]
        frame.clear()
        if not self.snapshot:
            self._empty(frame.body, "正在加载球队数据...")
            return
        if not self.selected_team_id:
            label = "选择俱乐部" if self.snapshot.competition_kind == "league" else "选择国家队"
            self._section(frame.body, label, "设为主队后固定置顶")
            self._team_grid(frame.body)
            return
        team = self.snapshot.teams.get(self.selected_team_id)
        if not team:
            self._empty(frame.body, "没有找到该球队。")
            return
        self._team_filter_bar(frame.body)
        self._team_header(frame.body, team)
        if self.snapshot.competition_kind == "league":
            self._team_performance_panel(frame.body, team)
        self._team_match_chain(frame.body, team)
        self._team_roster(frame.body, team)

    def _team_performance_panel(
        self,
        parent: tk.Widget,
        team: Team,
    ) -> None:
        matches = [
            match for match in self.snapshot.matches
            if match.completed
            and team.id in {match.home.id, match.away.id}
        ] if self.snapshot else []
        matches.sort(key=lambda match: match.date or MIN_DATE)
        wins = draws = losses = goals_for = goals_against = 0
        form: list[str] = []
        for match in matches:
            is_home = match.home.id == team.id
            try:
                own = int(match.home.score if is_home else match.away.score)
                other = int(match.away.score if is_home else match.home.score)
            except (TypeError, ValueError):
                continue
            goals_for += own
            goals_against += other
            if own > other:
                wins += 1
                form.append("胜")
            elif own == other:
                draws += 1
                form.append("平")
            else:
                losses += 1
                form.append("负")
        self._section(parent, "赛季概览", "联赛表现与近期状态")
        panel = tk.Frame(
            parent,
            bg=PANEL_2,
            padx=8,
            pady=8,
            highlightthickness=1,
            highlightbackground=LINE,
        )
        panel.pack(fill="x", pady=(0, 8))
        metrics = [
            ("场次", str(wins + draws + losses)),
            ("胜-平-负", f"{wins}-{draws}-{losses}"),
            ("进失球", f"{goals_for}-{goals_against}"),
            ("近五场", " ".join(form[-5:]) or "-"),
        ]
        for index, (label, value) in enumerate(metrics):
            cell = tk.Frame(panel, bg=PANEL_2)
            cell.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=4,
                pady=4,
            )
            tk.Label(
                cell,
                text=label,
                bg=PANEL_2,
                fg=MUTED,
                anchor="w",
                font=("Microsoft YaHei UI", 8),
            ).pack(fill="x")
            value_label = tk.Label(
                cell,
                text=value,
                bg=PANEL_2,
                fg=TEXT,
                anchor="w",
                justify="left",
                font=("Microsoft YaHei UI", 11, "bold"),
            )
            value_label.pack(fill="x", pady=(2, 0))
            self._bind_wrap(value_label, reserve=8, minimum=90, maximum=150)
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=1)

    def _filtered_matches(self, snapshot: Snapshot | None = None) -> list[Match]:
        snapshot = snapshot or self.snapshot
        if not snapshot:
            return []
        matches = list(snapshot.matches)
        if self.selected_team_id:
            matches = [m for m in matches if m.home.id == self.selected_team_id or m.away.id == self.selected_team_id]
        return matches

    def _time_bucket(self, match: Match) -> str:
        if not match.date:
            return ""
        return match.date.strftime("%Y-%m-%d %H:%M")

    def _spotlight_matches(self, snapshot: Snapshot | None = None) -> tuple[str, str, list[Match]]:
        matches = self._filtered_matches(snapshot)
        live = [m for m in matches if m.is_live]
        now = datetime.now().astimezone()
        imminent = [
            match for match in matches
            if match.is_upcoming
            and match.date is not None
            and timedelta(0) <= match.date - now <= timedelta(minutes=5)
        ]
        if live:
            buckets = {self._time_bucket(match) for match in live}
            spotlight = [match for match in matches if self._time_bucket(match) in buckets and (match.is_live or match.completed)]
            spotlight.extend(match for match in imminent if match not in spotlight)
            spotlight.sort(key=lambda match: (match.date or MAX_DATE, match.id))
            return "live", "正在进行与即将开始", spotlight
        if imminent:
            imminent.sort(key=lambda match: (match.date or MAX_DATE, match.id))
            return "imminent", "五分钟内开赛", imminent

        completed = [m for m in matches if m.completed]
        completed.sort(key=lambda match: match.date or MIN_DATE, reverse=True)
        if completed:
            latest_bucket = self._time_bucket(completed[0])
            spotlight = [match for match in completed if self._time_bucket(match) == latest_bucket]
            spotlight.sort(key=lambda match: (match.date or MAX_DATE, match.id))
            return "completed", "最近完赛", spotlight

        upcoming = [m for m in matches if m.is_upcoming]
        upcoming.sort(key=lambda match: match.date or MAX_DATE)
        if upcoming:
            first_bucket = self._time_bucket(upcoming[0])
            spotlight = [match for match in upcoming if self._time_bucket(match) == first_bucket]
            return "upcoming", "下一批比赛", spotlight
        return "empty", "比赛", []

    def _section(self, parent: tk.Widget, title: str, subtitle: str = "") -> None:
        box = tk.Frame(parent, bg=BG)
        box.pack(fill="x", pady=(6, 8))
        title_label = tk.Label(box, text=title, bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 13, "bold"), justify="left")
        title_label.pack(anchor="w", fill="x")
        self._bind_wrap(title_label, reserve=8, minimum=120, maximum=420)
        if subtitle:
            subtitle_label = tk.Label(box, text=subtitle, bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 9), justify="left")
            subtitle_label.pack(anchor="w", fill="x", pady=(2, 0))
            self._bind_wrap(subtitle_label, reserve=8, minimum=120, maximum=420)

    def _empty(self, parent: tk.Widget, text: str) -> None:
        box = tk.Frame(parent, bg=PANEL, padx=14, pady=14)
        box.pack(fill="x", pady=10)
        label = tk.Label(
            box,
            text=text,
            bg=PANEL,
            fg=MUTED,
            anchor="nw",
            font=("Microsoft YaHei UI", 9),
            justify="left",
        )
        label.pack(anchor="w", fill="x")
        self._bind_wrap(label, reserve=30, minimum=110, maximum=390)

    def _match_card(self, parent: tk.Widget, match: Match, live: bool = False) -> None:
        card = tk.Frame(parent, bg=PANEL, padx=12, pady=11, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="x", pady=6)
        header = tk.Frame(card, bg=PANEL, height=22)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)
        layout = tk.Frame(card, bg=PANEL)
        layout.pack(fill="x")
        layout.columnconfigure(0, weight=1, uniform="match_team", minsize=72)
        layout.columnconfigure(1, weight=0, minsize=100)
        layout.columnconfigure(2, weight=1, uniform="match_team", minsize=72)
        layout.rowconfigure(0, minsize=82)
        status_color = LIVE if match.is_live or live else (ACCENT if match.completed else WARNING)
        status = "LIVE " + match.status_text if match.is_live else (match.status_text or ("完赛" if match.completed else "未开始"))
        when = match.date.strftime("%m-%d %H:%M") if match.date else "时间待定"
        group = f" · {match.group} 组" if match.group else ""
        round_label = tk.Label(
            header,
            text=f"{match.round_name}{group}",
            bg=PANEL,
            fg=ACCENT,
            anchor="center",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        status_label = tk.Label(
            header,
            text=f"{when} · {status}",
            bg=PANEL,
            fg=status_color,
            anchor="e",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        round_label.place(x=0, y=0, width=1, relheight=1)
        status_label.place(relx=1.0, x=-1, y=0, width=1, relheight=1, anchor="ne")

        home_labels = self._score_team_block(layout, match.home, align="left", column=0, row=0)
        score_box = tk.Frame(
            layout,
            bg=PANEL,
            width=100,
            height=82,
        )
        score_box.grid(row=0, column=1, sticky="nsew", padx=3)
        score_box.grid_propagate(False)
        scoreline_label = tk.Label(
            score_box,
            text=self._scoreline(match),
            bg=PANEL,
            fg=TEXT,
            anchor="center",
            justify="center",
            font=("Microsoft YaHei UI", 20, "bold"),
        )
        scoreline_label._worldcup_score_font = True
        scoreline_label.place(relx=0.5, rely=0.5, anchor="center")
        away_labels = self._score_team_block(layout, match.away, align="right", column=2, row=0)

        def align_header(_event: tk.Event | None = None) -> None:
            try:
                header_width = header.winfo_width()
                if header_width <= 1:
                    return
                center_width = 100
                team_width = max(72, (header_width - center_width) // 2)
                status_font = tkfont.Font(root=self.root, font=status_label.cget("font"))
                font_actual = status_font.actual()
                font_family = font_actual.get("family", self.ui_font_var.get())
                font_weight = font_actual.get("weight", "bold")
                font_slant = font_actual.get("slant", "roman")
                font_size = 9
                gap = 6
                while font_size >= 4:
                    probe = tkfont.Font(
                        root=self.root,
                        family=font_family,
                        size=font_size,
                        weight=font_weight,
                        slant=font_slant,
                    )
                    round_width = probe.measure(round_label.cget("text")) + 6
                    status_width = probe.measure(status_label.cget("text")) + 6
                    centered_available = max(1, team_width - 8)
                    left_edge = round_width > centered_available
                    right_edge = status_width > centered_available
                    left_x = (
                        0
                        if left_edge
                        else max(0, (team_width - round_width) // 2)
                    )
                    right_x = (
                        header_width - status_width
                        if right_edge
                        else header_width - team_width
                        + max(0, (team_width - status_width) // 2)
                    )
                    if (
                        left_x >= 0
                        and right_x + status_width <= header_width
                        and left_x + round_width + gap <= right_x
                    ):
                        break
                    font_size -= 1
                font_size = max(4, font_size)
                target = (
                    "edge" if left_edge else "center",
                    "edge" if right_edge else "center",
                    font_size,
                    left_x,
                    round_width,
                    right_x,
                    status_width,
                    header_width,
                )
                if getattr(status_label, "_worldcup_alignment", None) == target:
                    return
                round_label.configure(
                    font=(font_family, font_size, font_weight, font_slant),
                    anchor="w" if left_edge else "center",
                )
                status_label.configure(
                    font=(font_family, font_size, font_weight, font_slant),
                    wraplength=0,
                    justify="right" if right_edge else "center",
                    anchor="e" if right_edge else "center",
                )
                round_label.place_configure(
                    relx=0,
                    x=left_x,
                    width=max(1, round_width),
                    anchor="nw",
                )
                status_label.place_configure(
                    relx=0,
                    x=right_x,
                    width=max(1, status_width),
                    anchor="nw",
                )
                team_wraplength = max(68, min(132, team_width - 4))
                for team_label in (home_labels["name"], away_labels["name"]):
                    if getattr(team_label, "_worldcup_wraplength", None) != team_wraplength:
                        team_label._worldcup_wraplength = team_wraplength
                        team_label.configure(wraplength=team_wraplength)
                status_label._worldcup_alignment = target
            except tk.TclError:
                return

        header.bind("<Configure>", align_header, add="+")
        header._worldcup_align_header = align_header
        header.after_idle(align_header)
        labels = {
            "round": round_label,
            "status": status_label,
            "away_name": away_labels["name"],
            "home_name": home_labels["name"],
            "scoreline": scoreline_label,
            "_header": header,
        }
        self.match_labels.setdefault(match.id, []).append(labels)
        self._bind_match_open(card, match)
        self._bind_match_open(layout, match)
        self._bind_match_open(score_box, match)
        self._bind_match_open(scoreline_label, match)
        live_target = self._official_live_target(match)
        if live_target is not None and self.show_live_labels_var.get():
            live_button = tk.Label(
                score_box,
                text="直播",
                bg=PANEL_3,
                fg=ACCENT,
                cursor="hand2",
                padx=5,
                pady=1,
                font=("Microsoft YaHei UI", 7, "bold"),
            )
            live_button.place(relx=0.5, rely=1.0, y=-1, anchor="s")
            self._bind_click(live_button, lambda _event, current=match: self._open_official_live(current))
        if match.is_live:
            self._commentary_preview(parent, match)

    def _official_live_target(self, match: Match) -> tuple[str, str] | None:
        targets = OFFICIAL_LIVE_TARGETS.get(match.competition_key or self.active_competition_key, [])
        if match.is_live:
            return targets[0] if targets else None
        if not match.is_upcoming or match.date is None:
            return None
        delta = match.date - datetime.now().astimezone()
        if timedelta(0) <= delta <= timedelta(minutes=5):
            return targets[0] if targets else None
        return None

    def _open_official_live(self, match: Match) -> None:
        if self._official_live_target(match) is None:
            return
        targets = OFFICIAL_LIVE_TARGETS.get(match.competition_key or self.active_competition_key, [])

        def worker() -> None:
            for _platform, url in targets:
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(request, timeout=6) as response:
                        if 200 <= response.status < 400:
                            webbrowser.open(url)
                            return
                except Exception:
                    continue
            self._post_ui(lambda: self._set_status_text("官方直播入口暂时无法连接"))

        threading.Thread(target=worker, daemon=True).start()

    def _bind_match_open(self, widget: tk.Widget, match: Match) -> None:
        widget.configure(cursor="hand2")

        def toggle_detail(_event: tk.Event, current: Match = match) -> None:
            if self.match_popup is not None and self.match_popup.winfo_exists():
                self._close_match_popup()
            self._open_match_detail(current)

        self._bind_click(widget, toggle_detail)

    def _bind_commentary_open(self, widget: tk.Widget, match: Match) -> None:
        widget.configure(cursor="hand2")

        def toggle_commentary(_event: tk.Event, current: Match = match) -> None:
            if (
                self.match_popup is not None
                and self.match_popup.winfo_exists()
                and self.match_popup_match_id == current.id
                and self.match_popup_mode == "commentary"
            ):
                self._close_match_popup()
                return
            self._open_commentary_detail(current)

        self._bind_click(widget, toggle_commentary)

    def _close_match_popup(self, popup: tk.Toplevel | None = None) -> None:
        popup = popup or self.match_popup
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        if popup is self.match_popup or popup is None:
            self.match_popup = None
            self.match_popup_match_id = ""
            self.match_popup_mode = ""
            self.match_detail_scroll = None
            self.detail_commentary_panels.clear()
            self.detail_summary_labels.clear()

    def _maybe_close_match_popup(self, event: tk.Event) -> None:
        if self.match_popup_opening or self.match_popup is None or not self.match_popup.winfo_exists():
            return
        if self._widget_inside(event.widget, self.match_popup):
            return
        if self._widget_inside(event.widget, self.root):
            self._close_match_popup()

    def _widget_inside(self, widget: tk.Widget, ancestor: tk.Widget) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _close_match_notification(self) -> None:
        popup = self.match_notification_popup
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        self.match_notification_popup = None
        self.match_notification_ids.clear()

    def _maybe_close_match_notification(self, _event: tk.Event) -> None:
        if self.match_notification_popup is not None and self.match_notification_popup.winfo_exists():
            self._close_match_notification()

    def _maybe_show_match_notification(self, snapshot: Snapshot, include_seen: bool = False) -> None:
        if not self.match_notifications_var.get():
            return
        live_matches = [match for match in snapshot.matches if match.is_live]
        if include_seen:
            matches = live_matches
        else:
            matches = [match for match in live_matches if match.id not in self.notified_live_match_ids]
        if not matches:
            return
        self.notified_live_match_ids.update(match.id for match in matches)
        self._show_match_notification(matches)

    def _show_match_notification(self, matches: list[Match]) -> None:
        if any(popup is not self.match_notification_popup for popup in self._existing_popups()):
            return
        self._close_match_notification()
        popup = tk.Toplevel(self.root)
        self.match_notification_popup = popup
        self.match_notification_ids = {
            match.id
            for match in matches
        }
        popup.overrideredirect(True)
        popup.configure(bg=LINE)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.98)
        popup.bind(
            "<Destroy>",
            lambda _event, current=popup: setattr(self, "match_notification_popup", None)
            if self.match_notification_popup is current else None,
            add="+",
        )

        width = min(330, max(286, self.root.winfo_screenwidth() // 5))
        visible_matches = matches[:4]
        x = max(18, self.root.winfo_screenwidth() - width - 24)
        popup.geometry(f"{width}x1+{x}+18")

        shell = tk.Frame(popup, bg=PANEL, padx=12, pady=11, highlightthickness=1, highlightbackground=LINE)
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        title_row = tk.Frame(shell, bg=PANEL)
        title_row.pack(fill="x", pady=(0, 7))
        tk.Label(
            title_row,
            text="●",
            bg=PANEL,
            fg=LIVE,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")
        tk.Label(
            title_row,
            text="比赛正在进行",
            bg=PANEL,
            fg=TEXT,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(side="left", padx=(7, 0))
        close = tk.Label(
            title_row,
            text="×",
            bg=PANEL,
            fg=MUTED,
            cursor="hand2",
            font=("Microsoft YaHei UI", 13, "bold"),
        )
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_match_notification())
        self._bind_drag(title_row)

        for match in visible_matches:
            row = tk.Frame(shell, bg=PANEL_2, padx=9, pady=7, highlightthickness=1, highlightbackground=LINE)
            row.pack(fill="x", pady=3)
            names = tk.Label(
                row,
                text=f"{self._team_text(match.home)}  vs  {self._team_text(match.away)}",
                bg=PANEL_2,
                fg=TEXT,
                anchor="w",
                justify="left",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            names.pack(fill="x")
            score = self._scoreline(match)
            detail = tk.Label(
                row,
                text=f"{score}  ·  {match.status_text or '进行中'}",
                bg=PANEL_2,
                fg=ACCENT,
                anchor="w",
                font=("Microsoft YaHei UI", 8, "bold"),
            )
            detail.pack(fill="x", pady=(2, 0))
        if len(matches) > len(visible_matches):
            tk.Label(
                shell,
                text=f"另有 {len(matches) - len(visible_matches)} 场比赛正在进行",
                bg=PANEL,
                fg=MUTED,
                font=("Microsoft YaHei UI", 8),
            ).pack(anchor="w", pady=(5, 0))

        self._apply_fonts_to_tree(popup)
        popup.update_idletasks()
        height = min(
            popup.winfo_screenheight() - 82,
            max(110, shell.winfo_reqheight() + 2),
        )
        y = max(18, popup.winfo_screenheight() - height - 64)
        popup.geometry(f"{width}x{height}+{x}+{y}")
        popup.deiconify()
        popup.lift()

    def _sync_match_notification(
        self,
        snapshot: Snapshot,
        current_live_ids: set[str],
    ) -> None:
        if (
            self.match_notification_popup is None
            or not self.match_notification_popup.winfo_exists()
        ):
            return
        remaining = [
            match
            for match in snapshot.matches
            if match.id in self.match_notification_ids
            and match.id in current_live_ids
        ]
        remaining_ids = {match.id for match in remaining}
        if not remaining:
            self._close_match_notification()
        elif remaining_ids != self.match_notification_ids:
            self._show_match_notification(remaining)

    def _bind_notification_close(self, widget: tk.Widget) -> None:
        self._bind_click(widget, lambda _event: self._close_match_notification())
        for child in widget.winfo_children():
            self._bind_notification_close(child)

    def _bind_popup_close(self, widget: tk.Widget, popup: tk.Toplevel) -> None:
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass
        self._bind_click(widget, lambda _event, current=popup: self._close_match_popup(current))
        for child in widget.winfo_children():
            self._bind_popup_close(child, popup)

    def _open_match_detail(self, match: Match) -> None:
        if self.match_popup is not None and self.match_popup.winfo_exists():
            self._close_match_popup()
            return
        self._prepare_single_popup(clear_history=True)
        self.match_popup_opening = True
        self.root.after_idle(lambda: setattr(self, "match_popup_opening", False))
        popup = tk.Toplevel(self.root)
        self.match_popup = popup
        self.match_popup_match_id = match.id
        self.match_popup_mode = "match"
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.97)
        def clear_popup_reference(event: tk.Event, current: tk.Toplevel = popup) -> None:
            if event.widget is current and self.match_popup is current:
                self.match_popup = None
                self.match_popup_match_id = ""
                self.match_popup_mode = ""
                self.match_detail_scroll = None
                self.detail_commentary_panels.clear()
                self.detail_summary_labels.clear()

        popup.bind("<Destroy>", clear_popup_reference, add="+")
        width = min(340, max(286, self.root.winfo_width() - 20))
        height = min(410, max(320, self.root.winfo_height() - 46))
        popup.geometry(f"{width}x{height}+{self.root.winfo_x() + 10}+{self.root.winfo_y() + 28}")
        header = tk.Frame(popup, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        header_label = tk.Label(header, text="对局资料", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 11, "bold"))
        header_label.pack(side="left")
        close = tk.Label(
            header,
            text="×",
            bg=PANEL,
            fg=MUTED,
            cursor="hand2",
            font=("Microsoft YaHei UI", 13, "bold"),
        )
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_match_popup())
        self._bind_drag(header)
        self._bind_drag(header_label)
        body = ScrollFrame(popup, bg=PANEL)
        self.match_detail_scroll = body
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._match_detail(body.body, match)
        self._apply_fonts_to_tree(popup)
        self._load_complete_detail_commentary(
            match,
            request_summary=match.completed,
        )

    def _open_commentary_detail(self, match: Match) -> None:
        if self.match_popup is not None and self.match_popup.winfo_exists():
            self._close_match_popup()
        self._prepare_single_popup(clear_history=True)
        self.match_popup_opening = True
        self.root.after_idle(lambda: setattr(self, "match_popup_opening", False))
        popup = tk.Toplevel(self.root)
        self.match_popup = popup
        self.match_popup_match_id = match.id
        self.match_popup_mode = "commentary"
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.97)

        def clear_popup_reference(
            event: tk.Event,
            current: tk.Toplevel = popup,
        ) -> None:
            if event.widget is current and self.match_popup is current:
                self.match_popup = None
                self.match_popup_match_id = ""
                self.match_popup_mode = ""
                self.match_detail_scroll = None
                self.detail_commentary_panels.clear()

        popup.bind("<Destroy>", clear_popup_reference, add="+")
        width = min(360, max(292, self.root.winfo_width() - 12))
        height = min(540, max(360, self.root.winfo_height() - 24))
        x = min(
            max(8, self.root.winfo_x() + 6),
            max(8, self.root.winfo_screenwidth() - width - 8),
        )
        y = min(
            max(8, self.root.winfo_y() + 18),
            max(8, self.root.winfo_screenheight() - height - 48),
        )
        popup.geometry(f"{width}x{height}+{x}+{y}")

        header = tk.Frame(popup, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        header_label = tk.Label(
            header,
            text="直播文字解说",
            bg=PANEL,
            fg=ACCENT,
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        header_label.pack(side="left")
        close = tk.Label(
            header,
            text="×",
            bg=PANEL,
            fg=MUTED,
            cursor="hand2",
            font=("Microsoft YaHei UI", 13, "bold"),
        )
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_match_popup())
        self._bind_drag(header)
        self._bind_drag(header_label)

        body = ScrollFrame(popup, bg=PANEL)
        self.match_detail_scroll = body
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        title = (
            f"{self._team_text(match.home)}  {self._scoreline(match)}  "
            f"{self._team_text(match.away)}"
        )
        title_label = tk.Label(
            body.body,
            text=title,
            bg=PANEL,
            fg=TEXT,
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        title_label.pack(fill="x", pady=(0, 4))
        self._bind_wrap(title_label, reserve=8, minimum=140, maximum=330)
        status_label = tk.Label(
            body.body,
            text=f"LIVE {match.status_text}" if match.is_live else match.status_text,
            bg=PANEL,
            fg=LIVE if match.is_live else MUTED,
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        status_label.pack(fill="x", pady=(0, 5))
        self._bind_wrap(status_label, reserve=8, minimum=140, maximum=330)
        self._match_commentary_panel(body.body, match)
        self._apply_fonts_to_tree(popup)
        self._load_complete_detail_commentary(match)

    def _match_detail(self, parent: tk.Widget, match: Match) -> None:
        title = f"{self._team_text(match.home)}  {self._scoreline(match)}  {self._team_text(match.away)}"
        title_label = tk.Label(parent, text=title, bg=PANEL, fg=TEXT, justify="left", font=("Microsoft YaHei UI", 13, "bold"))
        title_label.pack(anchor="w", fill="x")
        self._bind_wrap(title_label, reserve=8, minimum=140, maximum=310)
        status = "LIVE " + match.status_text if match.is_live else (match.status_text or ("完赛" if match.completed else "未开始"))
        when = match.date.strftime("%Y-%m-%d %H:%M") if match.date else "时间待定"
        rows = [
            ("时间", when),
            ("阶段", f"{match.round_name}{' · ' + match.group + ' 组' if match.group else ''}"),
            ("状态", status),
            ("场馆", match.venue or "场馆待定"),
        ]
        if match.detail:
            rows.append(("备注", match.detail))
        box = tk.Frame(parent, bg=PANEL)
        box.pack(fill="x", pady=(10, 0))
        for label, value in rows:
            row = tk.Frame(box, bg=PANEL_2, padx=9, pady=7)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=PANEL_2, fg=MUTED, width=5, anchor="w", font=("Microsoft YaHei UI", 8, "bold")).pack(side="left")
            value_label = tk.Label(row, text=value, bg=PANEL_2, fg=TEXT, anchor="w", justify="left", font=("Microsoft YaHei UI", 9, "bold"))
            value_label.pack(side="left", fill="x", expand=True)
            self._bind_wrap(value_label, reserve=56, minimum=130, maximum=260)
        if not match.completed:
            live_target = self._official_live_target(match)
            live_row = tk.Frame(box, bg=PANEL_2, padx=9, pady=7)
            live_row.pack(fill="x", pady=3)
            tk.Label(live_row, text="直播", bg=PANEL_2, fg=MUTED, width=5, anchor="w", font=("Microsoft YaHei UI", 8, "bold")).pack(side="left")
            if live_target is None:
                tk.Label(live_row, text="暂无匹配的官方直播入口", bg=PANEL_2, fg=MUTED, anchor="w", font=("Microsoft YaHei UI", 9)).pack(side="left", fill="x", expand=True)
            else:
                platform, _url = live_target
                button = tk.Label(live_row, text=f"▶ 前往 {platform}", bg=PANEL_3, fg=ACCENT, cursor="hand2", padx=8, pady=4, font=("Microsoft YaHei UI", 8, "bold"))
                button.pack(side="left")
                self._bind_click(button, lambda _event, current=match: self._open_official_live(current))
        self._match_events_panel(parent, match)
        self._match_stats_panel(parent, match)
        self._match_commentary_panel(parent, match)
        if match.completed:
            self._match_summary_panel(parent, match)

    def _match_commentary_panel(self, parent: tk.Widget, match: Match) -> None:
        tk.Label(
            parent,
            text="完整文字直播",
            bg=PANEL,
            fg=ACCENT,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="w", pady=(12, 4))
        panel = tk.Frame(parent, bg=PANEL)
        panel.pack(fill="x")
        self.detail_commentary_panels[match.id] = panel
        self._render_detail_commentary(match)

    def _render_detail_commentary(self, match: Match) -> None:
        panel = self.detail_commentary_panels.get(match.id)
        if panel is None:
            return
        scroll_state = self.commentary_scroll_states.setdefault(
            match.id,
            {
                "top": 0.0,
                "index": "1.0",
                "at_bottom": True,
                "dragging": False,
                "pending_render": False,
                "interaction_revision": 0,
            },
        )
        if bool(scroll_state.get("dragging")):
            scroll_state["pending_render"] = True
            return
        old_view: tuple[float, float] | None = None
        try:
            if not panel.winfo_exists():
                self.detail_commentary_panels.pop(match.id, None)
                return
            for child in panel.winfo_children():
                if isinstance(child, (tk.Listbox, tk.Text)):
                    old_view = child.yview()
                    scroll_state["top"] = old_view[0]
                    scroll_state["at_bottom"] = old_view[1] >= 0.995
                    if isinstance(child, tk.Text):
                        scroll_state["index"] = child.index("@8,7")
                    break
        except tk.TclError:
            return
        snapshot = self.detail_commentary_snapshots.get(match.id)
        merged_entries: dict[int, CommentaryEntry] = {}
        merged_texts: dict[int, str] = {}
        if snapshot is not None:
            snapshot_entries, snapshot_texts = snapshot
            for entry in snapshot_entries:
                text = str(snapshot_texts.get(entry.sequence) or "").strip()
                if text:
                    merged_entries[entry.sequence] = entry
                    merged_texts[entry.sequence] = text
        for entry in self.commentary_entries.get(match.id, []):
            text = self._commentary_text(match.id, entry).strip()
            if text:
                merged_entries[entry.sequence] = entry
                merged_texts[entry.sequence] = text
        if not merged_entries:
            if match.id in self.detail_commentary_loading:
                text = "正在获取中文文字直播…"
            elif self.detail_commentary_errors.get(match.id):
                text = f"完整中文文字直播暂时不可用：{self.detail_commentary_errors[match.id]}"
            else:
                text = "正在准备完整中文文字直播…"
            signature = ("status", text)
            if getattr(panel, "_worldcup_commentary_signature", None) == signature:
                return
            panel._worldcup_commentary_signature = signature
            for child in panel.winfo_children():
                child.destroy()
            error_label = tk.Label(
                panel,
                text=text,
                bg=PANEL,
                fg=MUTED,
                anchor="w",
                justify="left",
            )
            error_label.pack(fill="x", pady=5)
            self._bind_wrap(error_label, reserve=4, minimum=120, maximum=306)
            return
        visible_entries = [
            merged_entries[sequence]
            for sequence in sorted(merged_entries)
        ]
        translated = merged_texts
        notice = self.detail_commentary_errors.get(match.id)
        signature = (
            "timeline",
            self.match_popup_mode,
            notice,
            tuple(
                (
                    entry.sequence,
                    entry.minute,
                    translated[entry.sequence],
                )
                for entry in visible_entries
            ),
        )
        if getattr(panel, "_worldcup_commentary_signature", None) == signature:
            return
        panel._worldcup_commentary_signature = signature
        for child in panel.winfo_children():
            child.destroy()
        if notice:
            notice_label = tk.Label(
                panel,
                text=notice,
                bg=PANEL_2,
                fg=WARNING,
                anchor="w",
                justify="left",
                padx=7,
                pady=6,
            )
            notice_label.pack(fill="x", pady=(0, 5))
            self._bind_wrap(notice_label, reserve=18, minimum=110, maximum=292)
        timeline_font = tkfont.Font(
            root=self.root,
            family=self.ui_font_var.get() or "Microsoft YaHei UI",
            size=8,
        )
        timeline = tk.Text(
            panel,
            bg=PANEL_2,
            fg=TEXT,
            width=1,
            height=14 if self.match_popup_mode == "commentary" else 8,
            wrap="char",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=LINE,
            font=timeline_font,
            cursor="arrow",
            takefocus=False,
            padx=6,
            pady=5,
            spacing1=1,
            spacing3=2,
        )
        timeline.pack(fill="x")
        timeline._worldcup_font = timeline_font
        timeline.tag_configure("normal", foreground=TEXT)
        timeline.tag_configure("muted", foreground=MUTED)
        timeline.tag_configure("live", foreground=LIVE)
        timeline.tag_configure("accent", foreground=ACCENT)
        timeline.tag_configure("warning", foreground=WARNING)
        for entry in visible_entries:
            emphasis_color, _emphasized = self._commentary_emphasis(entry)
            tag = (
                "live" if emphasis_color == LIVE else
                "accent" if emphasis_color == ACCENT else
                "warning" if emphasis_color == WARNING else
                "normal"
            )
            text = self._localize_commentary_names(
                translated[entry.sequence]
            )
            timeline.insert(
                "end",
                f"{entry.minute or '·'}  {text}\n",
                tag,
            )
        timeline.configure(state="disabled")
        keep_bottom = bool(scroll_state.get("at_bottom", True))
        saved_top = float(scroll_state.get("top", 0.0) or 0.0)
        saved_index = str(scroll_state.get("index") or "1.0")
        restore_revision = int(
            scroll_state.get("interaction_revision", 0) or 0
        )

        def restore_timeline_position() -> None:
            try:
                if int(
                    scroll_state.get("interaction_revision", 0) or 0
                ) != restore_revision:
                    return
                if keep_bottom:
                    timeline.yview_moveto(1.0)
                else:
                    try:
                        timeline.yview(saved_index)
                    except tk.TclError:
                        timeline.yview_moveto(saved_top)
                top, bottom = timeline.yview()
                scroll_state["top"] = top
                scroll_state["at_bottom"] = bottom >= 0.995
                scroll_state["index"] = timeline.index("@8,7")
            except tk.TclError:
                pass

        timeline.after_idle(restore_timeline_position)

        def mark_interaction() -> None:
            scroll_state["interaction_revision"] = (
                int(scroll_state.get("interaction_revision", 0) or 0) + 1
            )

        def remember_position() -> None:
            try:
                top, bottom = timeline.yview()
            except tk.TclError:
                return
            scroll_state["top"] = top
            scroll_state["at_bottom"] = bottom >= 0.995
            scroll_state["index"] = timeline.index("@8,7")

        def scroll_text(event: tk.Event) -> str:
            mark_interaction()
            direction = -1 if event.delta > 0 else 1
            top, bottom = timeline.yview()
            at_boundary = (direction < 0 and top <= 0.0001) or (direction > 0 and bottom >= 0.9999)
            if at_boundary and self.match_detail_scroll is not None:
                self.match_detail_scroll.canvas.yview_scroll(direction * 3, "units")
            else:
                timeline.yview_scroll(direction * 2, "units")
                remember_position()
            return "break"

        drag_state = {
            "active": False,
            "moved": False,
            "start_y": 0,
            "start_top": 0.0,
            "content_pixels": 1,
        }

        def stop_drag(
            _event: tk.Event | None = None,
            render_pending: bool = True,
        ) -> str:
            drag_state["active"] = False
            scroll_state["dragging"] = False
            remember_position()
            if (
                render_pending
                and bool(scroll_state.pop("pending_render", False))
            ):
                self.root.after_idle(
                    lambda current=match: self._render_detail_commentary(current)
                )
            return "break"

        def pointer_inside(x_root: int, y_root: int) -> bool:
            try:
                left = timeline.winfo_rootx()
                top = timeline.winfo_rooty()
                return (
                    left <= x_root < left + timeline.winfo_width()
                    and top <= y_root < top + timeline.winfo_height()
                )
            except tk.TclError:
                return False

        def start_drag(event: tk.Event) -> str:
            mark_interaction()
            drag_state["active"] = True
            scroll_state["dragging"] = True
            scroll_state["pending_render"] = False
            drag_state["moved"] = False
            try:
                drag_state["start_y"] = event.y_root
                drag_state["start_top"] = timeline.yview()[0]
                display_lines = int(
                    timeline.count(
                        "1.0",
                        "end-1c",
                        "displaylines",
                    )[0]
                    or 1
                )
                drag_state["content_pixels"] = max(
                    timeline.winfo_height() + 1,
                    display_lines
                    * max(1, timeline_font.metrics("linespace"))
                    + 10,
                )
            except tk.TclError:
                drag_state["active"] = False
                scroll_state["dragging"] = False
            return "break"

        def drag_text(event: tk.Event) -> str:
            if not drag_state["active"]:
                return "break"
            if not pointer_inside(event.x_root, event.y_root):
                return stop_drag(event)
            drag_state["moved"] = True
            try:
                delta = event.y_root - int(drag_state["start_y"])
                target = (
                    float(drag_state["start_top"])
                    - delta / max(1, int(drag_state["content_pixels"]))
                )
                timeline.yview_moveto(max(0.0, min(1.0, target)))
            except (tk.TclError, TypeError, ValueError):
                return stop_drag(event)
            remember_position()
            return "break"

        timeline.bind("<MouseWheel>", scroll_text)
        timeline.bind("<ButtonPress-1>", start_drag)
        timeline.bind("<B1-Motion>", drag_text)
        timeline.bind("<ButtonRelease-1>", stop_drag)
        timeline.bind(
            "<Leave>",
            lambda event: stop_drag(event)
            if drag_state["active"] else None,
        )
        timeline.bind(
            "<Destroy>",
            lambda event: stop_drag(event, render_pending=False),
        )

    def _match_summary_panel(self, parent: tk.Widget, match: Match) -> None:
        tk.Label(
            parent,
            text="AI 比赛总结",
            bg=PANEL,
            fg=ACCENT,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="w", pady=(12, 4))
        summary = tk.Label(
            parent,
            text="正在准备比赛总结…",
            bg=PANEL_2,
            fg=TEXT,
            anchor="w",
            justify="left",
            padx=9,
            pady=8,
            font=("Microsoft YaHei UI", 9),
        )
        summary.pack(fill="x", pady=(0, 4))
        self.detail_summary_labels[match.id] = summary
        self._bind_wrap(summary, reserve=18, minimum=160, maximum=300)
        self._update_summary_label(match.id)

    def _update_summary_label(self, match_id: str) -> None:
        label = self.detail_summary_labels.get(match_id)
        if label is None:
            return
        if match_id in self.summary_loading:
            text = "正在生成比赛总结…"
            color = MUTED
        elif self.summary_texts.get(match_id):
            text = self.summary_texts[match_id]
            color = TEXT
        elif self.summary_errors.get(match_id):
            text = self.summary_errors[match_id]
            color = MUTED
        else:
            text = "等待获取完整比赛数据…"
            color = MUTED
        try:
            label.configure(text=text, fg=color)
        except tk.TclError:
            self.detail_summary_labels.pop(match_id, None)

    def _match_events_panel(self, parent: tk.Widget, match: Match) -> None:
        events = [event for event in match.events if event.get("kind") in {"goal", "yellow", "red"}]
        if not events:
            return
        tk.Label(parent, text="关键事件", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(12, 4))
        panel = tk.Frame(parent, bg=PANEL)
        panel.pack(fill="x")
        for event in events:
            kind = event.get("kind")
            icon = "进" if kind == "goal" else ("红" if kind == "red" else "黄")
            minute = event.get("minute") or "-"
            player = self._player_text(event.get("player_name") or "未知球员", player_id=event.get("player_id") or "")
            team_name = self._event_team_name(match, event.get("team_id") or "")
            extras = []
            if event.get("penalty"):
                extras.append("点球")
            if event.get("own_goal"):
                extras.append("乌龙")
            suffix = f" · {' / '.join(extras)}" if extras else ""
            row = tk.Frame(panel, bg=PANEL_2, padx=8, pady=6)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=icon, bg=PANEL_2, fg=TEXT, width=3, anchor="w", font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
            text = f"{minute}  {player} · {team_name}{suffix}"
            label = tk.Label(row, text=text, bg=PANEL_2, fg=TEXT, anchor="w", justify="left", font=("Microsoft YaHei UI", 8, "bold"))
            label.pack(side="left", fill="x", expand=True)
            self._bind_wrap(label, reserve=38, minimum=150, maximum=280)

    def _match_stats_panel(self, parent: tk.Widget, match: Match) -> None:
        if not match.statistics:
            return
        home_stats = match.statistics.get(match.home.id, {})
        away_stats = match.statistics.get(match.away.id, {})
        if not home_stats and not away_stats:
            return
        tk.Label(parent, text="关键数据", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(12, 4))
        panel = tk.Frame(parent, bg=PANEL_2, padx=8, pady=7, highlightthickness=1, highlightbackground=LINE)
        panel.pack(fill="x")
        head = tk.Frame(panel, bg=PANEL_2)
        head.pack(fill="x", pady=(0, 4))
        tk.Label(head, text=self._team_text(match.home), bg=PANEL_2, fg=TEXT, anchor="w", font=("Microsoft YaHei UI", 8, "bold")).pack(side="left", fill="x", expand=True)
        tk.Label(head, text=self._team_text(match.away), bg=PANEL_2, fg=TEXT, anchor="e", font=("Microsoft YaHei UI", 8, "bold")).pack(side="right", fill="x", expand=True)
        for key, label in MATCH_STAT_ROWS:
            home_value = self._match_stat_value(match, match.home.id, key)
            away_value = self._match_stat_value(match, match.away.id, key)
            if not home_value and not away_value:
                continue
            row = tk.Frame(panel, bg=PANEL_2)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=home_value or "-", bg=PANEL_2, fg=TEXT, width=6, anchor="w", font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
            tk.Label(row, text=label, bg=PANEL_2, fg=MUTED, anchor="center", font=("Microsoft YaHei UI", 8)).pack(side="left", fill="x", expand=True)
            tk.Label(row, text=away_value or "-", bg=PANEL_2, fg=TEXT, width=6, anchor="e", font=("Microsoft YaHei UI", 9, "bold")).pack(side="right")

    def _event_team_name(self, match: Match, team_id: str) -> str:
        if team_id == match.home.id:
            return self._team_text(match.home)
        if team_id == match.away.id:
            return self._team_text(match.away)
        team = self.snapshot.teams.get(team_id) if self.snapshot else None
        return self._team_text(team) if team else "未知球队"

    def _match_stat_value(self, match: Match, team_id: str, key: str) -> str:
        if key == "cards":
            yellow = sum(1 for event in match.events if event.get("team_id") == team_id and event.get("kind") == "yellow")
            red = sum(1 for event in match.events if event.get("team_id") == team_id and event.get("kind") == "red")
            if yellow or red:
                return f"{yellow}黄/{red}红"
            return ""
        value = (match.statistics.get(team_id) or {}).get(key, "")
        if key == "possessionPct" and value and "%" not in value:
            return f"{value}%"
        return value

    def _score_team_block(
        self,
        parent: tk.Widget,
        team: MatchTeam,
        align: str,
        column: int,
        row: int = 0,
    ) -> dict[str, tk.Label]:
        block = tk.Frame(parent, bg=PANEL)
        block.grid(row=row, column=column, sticky="nsew")
        text_anchor = "center"
        justify = "center"
        icon = self._team_icon(block, team.id, team.logo, size=34, clickable=team.clickable)
        icon.pack(anchor="center", pady=(0, 4))
        text_box = tk.Frame(block, bg=PANEL)
        text_box.pack(fill="x", expand=True)
        name_label = tk.Label(
            text_box,
            text=self._team_text(team),
            bg=PANEL,
            fg=TEXT if team.winner is not False else MUTED,
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor=text_anchor,
            justify=justify,
            width=1,
            wraplength=110,
        )
        name_label.pack(fill="x")
        self._bind_team_open(name_label, team.id)
        code_label = tk.Label(
            text_box,
            text=team.abbreviation,
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8, "bold"),
            anchor=text_anchor,
        )
        code_label.pack(fill="x", pady=(2, 0))
        self._bind_team_open(code_label, team.id)
        return {"name": name_label, "code": code_label}

    def _match_team_row(self, parent: tk.Widget, team: MatchTeam, show_score: bool) -> dict[str, tk.Label]:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=2)
        self._team_icon(row, team.id, team.logo, size=26, clickable=team.clickable).pack(side="left")
        name = f"{team.abbreviation}  {team.name}" if team.abbreviation else team.name
        fg = TEXT if team.winner is not False else MUTED
        name_label = tk.Label(row, text=name, bg=PANEL, fg=fg, font=("Microsoft YaHei UI", 11, "bold"))
        name_label.pack(side="left", padx=(10, 8))
        score = team.score if show_score and team.score != "" else "-"
        score_label = tk.Label(row, text=score, bg=PANEL, fg=TEXT, font=("Microsoft YaHei UI", 16, "bold"))
        score_label._worldcup_score_font = True
        score_label.pack(side="right")
        return {"name": name_label, "score": score_label}

    def _team_icon(self, parent: tk.Widget, team_id: str, logo: str, size: int = 24, clickable: bool = True) -> tk.Label:
        photo = self.images.get(logo, size=size)
        label = tk.Label(parent, bg=parent.cget("bg"))
        if photo:
            label.configure(image=photo)
            label.image = photo
        else:
            label.configure(text="●", fg=ACCENT, width=max(2, size // 10), height=1, font=("Microsoft YaHei UI", max(9, size // 2), "bold"))
        if clickable and team_id:
            label.configure(cursor="hand2")
            self._bind_click(label, lambda _event, tid=team_id: self.open_team(tid))
        return label

    def _bind_team_open(self, widget: tk.Widget, team_id: str) -> None:
        if not team_id:
            return
        widget.configure(cursor="hand2")
        self._bind_click(widget, lambda _event, tid=team_id: self.open_team(tid))

    def _standings_group(self, parent: tk.Widget, group: dict) -> None:
        wrap = tk.Frame(parent, bg=PANEL, padx=10, pady=10, highlightthickness=1, highlightbackground=LINE)
        wrap.pack(fill="x", pady=6)
        heading = (
            str(group.get("name") or "积分榜")
            if self.snapshot and self.snapshot.competition_kind == "league"
            else f"{group.get('name')} 组"
        )
        tk.Label(wrap, text=heading, bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        for entry in group.get("entries", []):
            team: Team = entry["team"]
            stats = entry["stats"]
            row = tk.Frame(wrap, bg=PANEL_2, padx=8, pady=7)
            row.pack(fill="x", pady=3)
            head = tk.Frame(row, bg=PANEL_2)
            head.pack(fill="x")
            self._team_icon(head, team.id, team.logo, size=24).pack(side="left")
            team_label = tk.Label(head, text=f"{entry.get('rank', '')}. {self._team_text(team)}", bg=PANEL_2, fg=TEXT, anchor="w", font=("Microsoft YaHei UI", 10, "bold"))
            team_label.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self._bind_team_open(team_label, team.id)
            pts_label = tk.Label(head, text=f"{stats.get('分', '')} 分", bg=PANEL_2, fg=ACCENT, font=("Microsoft YaHei UI", 11, "bold"))
            pts_label.pack(side="right")
            self.standing_labels[(team.id, "分")] = pts_label
            metrics = tk.Frame(row, bg=PANEL_2)
            metrics.pack(fill="x", pady=(6, 0))
            for key in ["赛", "胜", "平", "负", "进", "失", "净"]:
                color = ACCENT if key == "分" else TEXT
                stat = tk.Frame(metrics, bg=PANEL_2)
                stat.pack(side="left", expand=True, fill="x")
                tk.Label(stat, text=key, bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 7)).pack()
                stat_label = tk.Label(stat, text=stats.get(key, ""), bg=PANEL_2, fg=color, font=("Microsoft YaHei UI", 9, "bold"))
                stat_label.pack()
                self.standing_labels[(team.id, key)] = stat_label

    def _leaderboard(self, parent: tk.Widget, board: Leaderboard) -> None:
        wrap = tk.Frame(parent, bg=PANEL, padx=10, pady=10, highlightthickness=1, highlightbackground=LINE)
        wrap.pack(fill="x", pady=6)
        tk.Label(wrap, text=self._board_text(board.key, board.name), bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        for row in board.rows[:12]:
            line = tk.Frame(wrap, bg=PANEL)
            line.pack(fill="x", pady=3)
            tk.Label(line, text=str(row.rank), bg=PANEL, fg=MUTED, width=3, anchor="w").pack(side="left")
            self._team_icon(line, row.team_id, row.team_logo, size=22, clickable=bool(row.team_id)).pack(side="left")
            is_team_row = row.player_id == row.team_id and row.player_name == row.team_name
            main_name = self._team_text(row) if is_team_row else self._player_text(row.player_name, row.player_id)
            name_box = tk.Frame(line, bg=PANEL)
            name_box.pack(side="left", fill="x", expand=True, padx=(8, 0))
            main_label = tk.Label(name_box, text=main_name, bg=PANEL, fg=TEXT, anchor="w", justify="left", font=("Microsoft YaHei UI", 10, "bold"))
            main_label.pack(fill="x")
            self._bind_wrap(main_label, reserve=6, minimum=80, maximum=190)
            if is_team_row:
                self._bind_team_open(main_label, row.team_id)
            else:
                self._bind_click(
                    main_label,
                    lambda _event, current=row:
                    self._open_player_detail(
                        Player(
                            id=current.player_id,
                            name=current.player_name,
                            stats=dict(current.stats),
                            club_team_id=current.team_id,
                            club_team_name=current.team_name,
                            club_competition_key=(
                                self.active_competition_key
                                if self.active_competition_key != "worldcup"
                                else ""
                            ),
                            data_season_year=(
                                self.snapshot.season_year
                                if self.snapshot else 0
                            ),
                            data_competition_key=self.active_competition_key,
                        )
                    ),
                )
            team_name = row.team_abbreviation if is_team_row else self._team_text(row)
            team_label = tk.Label(name_box, text=team_name, bg=PANEL, fg=MUTED, anchor="w", justify="left", font=("Microsoft YaHei UI", 8))
            team_label.pack(fill="x")
            self._bind_wrap(team_label, reserve=6, minimum=80, maximum=190)
            self._bind_team_open(team_label, row.team_id)
            value = row.display_value.replace("Matches:", "赛").replace("Goals:", "球").replace("Assists:", "助攻")
            value_label = tk.Label(line, text=value, bg=PANEL, fg=WARNING, anchor="e", justify="right", font=("Microsoft YaHei UI", 8, "bold"), wraplength=82)
            value_label.pack(side="right")
            self.leader_labels[(board.key, row.player_id)] = value_label

    def _team_grid(self, parent: tk.Widget) -> None:
        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="x")
        favorite_id = self.favorite_teams.get(
            self.active_competition_key,
            "",
        )
        teams = sorted(
            self.snapshot.teams.values(),
            key=lambda team: (
                0 if team.id == favorite_id else 1,
                team.group or "Z",
                team.name,
            ),
        ) if self.snapshot else []
        for index, team in enumerate(teams):
            cell = tk.Frame(grid, bg=PANEL, padx=8, pady=8, highlightthickness=1, highlightbackground=LINE)
            cell.pack(fill="x", pady=4)
            self._team_icon(cell, team.id, team.logo, size=28).pack(side="left")
            team_label = tk.Label(cell, text=f"{team.abbreviation}\n{self._team_text(team)}", bg=PANEL, fg=TEXT, justify="left", font=("Microsoft YaHei UI", 9, "bold"))
            team_label.pack(side="left", padx=(8, 0))
            self._bind_team_open(team_label, team.id)
            favorite = team.id == favorite_id
            favorite_button = tk.Label(
                cell,
                text="主队" if favorite else "设为主队",
                bg=PANEL_3 if favorite else PANEL,
                fg=ACCENT if favorite else MUTED,
                cursor="hand2",
                padx=7,
                pady=4,
                font=("Microsoft YaHei UI", 8, "bold"),
            )
            favorite_button.pack(side="right")
            self._bind_click(
                favorite_button,
                lambda _event, tid=team.id:
                self._set_favorite_team(tid),
            )
            cell.configure(cursor="hand2")
            self._bind_click(cell, lambda _event, tid=team.id: self.open_team(tid))

    def _team_header(self, parent: tk.Widget, team: Team) -> None:
        box = tk.Frame(parent, bg=PANEL, padx=14, pady=12, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill="x", pady=(4, 10))
        self._team_icon(box, team.id, team.logo, size=48, clickable=False).pack(side="left")
        info = tk.Frame(box, bg=PANEL)
        info.pack(side="left", fill="x", expand=True, padx=(14, 0))
        title_label = tk.Label(info, text=f"{self._team_text(team)}  {team.abbreviation}", bg=PANEL, fg=TEXT, justify="left", font=("Microsoft YaHei UI", 15, "bold"))
        title_label.pack(anchor="w", fill="x")
        self._bind_wrap(title_label, reserve=4, minimum=120, maximum=260)
        standing = team.standing
        if self.snapshot and self.snapshot.competition_kind == "league":
            group_text = self.snapshot.competition_name
        else:
            group_text = f"{team.group} 组" if team.group else "小组待定"
        rank = f"第 {standing.get('rank')} 名" if standing.get("rank") else "排名待定"
        meta_label = tk.Label(info, text=f"{group_text} · {rank}", bg=PANEL, fg=ACCENT, justify="left", font=("Microsoft YaHei UI", 10, "bold"))
        meta_label.pack(anchor="w", fill="x", pady=(3, 0))
        self._bind_wrap(meta_label, reserve=4, minimum=120, maximum=260)
        if standing:
            values = "  ".join(f"{key}{standing.get(key, '')}" for key in ["赛", "胜", "平", "负", "进", "失", "净", "分"])
            values_label = tk.Label(info, text=values, bg=PANEL, fg=MUTED, justify="left", font=("Microsoft YaHei UI", 9))
            values_label.pack(anchor="w", fill="x", pady=(5, 0))
            self._bind_wrap(values_label, reserve=4, minimum=120, maximum=260)
        favorite = self.favorite_teams.get(
            self.active_competition_key,
            "",
        ) == team.id
        favorite_button = tk.Label(
            box,
            text="主队" if favorite else "设为主队",
            bg=PANEL_3 if favorite else PANEL_2,
            fg=ACCENT if favorite else MUTED,
            cursor="hand2",
            padx=7,
            pady=4,
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        favorite_button.pack(side="right", anchor="n")
        self._bind_click(
            favorite_button,
            lambda _event, tid=team.id:
            self._set_favorite_team(tid),
        )

    def _set_favorite_team(self, team_id: str) -> None:
        if self.favorite_teams.get(self.active_competition_key) == team_id:
            self.favorite_teams.pop(self.active_competition_key, None)
        else:
            self.favorite_teams[self.active_competition_key] = team_id
        self._save_config()
        self._invalidate_render_cache("team")
        self.news_items.pop(self.active_competition_key, None)
        self._invalidate_render_cache("news")
        self._load_news(
            self.active_competition_key,
            priority=True,
        )
        if self.active_tab == "team":
            self.render_team()

    def _team_match_chain(self, parent: tk.Widget, team: Team) -> None:
        matches = [m for m in self.snapshot.matches if m.home.id == team.id or m.away.id == team.id] if self.snapshot else []
        completed = [m for m in matches if m.completed]
        upcoming = [m for m in matches if m.is_upcoming]
        live = [m for m in matches if m.is_live]
        self._section(parent, "该队比赛链", "进行中、最近赛果与下一场")
        chain = tk.Frame(parent, bg=BG)
        chain.pack(fill="x")
        buckets = [("进行中", live[:1]), ("最近赛果", completed[-1:]), ("下一场", upcoming[:1])]
        for title, items in buckets:
            box = tk.Frame(chain, bg=PANEL_2, padx=10, pady=8, highlightthickness=1, highlightbackground=LINE)
            box.pack(fill="x", pady=4)
            tk.Label(box, text=title, bg=PANEL_2, fg=ACCENT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
            if not items:
                tk.Label(box, text="暂无", bg=PANEL_2, fg=MUTED).pack(anchor="w", pady=(8, 0))
            for match in items:
                when = match.date.strftime("%m-%d %H:%M") if match.date else "时间待定"
                score = f"{self._team_text(match.away)} {match.away.score or '-'} : {match.home.score or '-'} {self._team_text(match.home)}"
                when_label = tk.Label(box, text=when, bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 8))
                when_label.pack(anchor="w", pady=(6, 0))
                summary_label = tk.Label(box, text=score, bg=PANEL_2, fg=TEXT, justify="left", font=("Microsoft YaHei UI", 10, "bold"))
                summary_label.pack(anchor="w", fill="x")
                self._bind_wrap(summary_label, reserve=8, minimum=120, maximum=300)
                self.match_labels.setdefault(match.id, []).append({"when": when_label, "summary": summary_label})

    def _team_roster(self, parent: tk.Widget, team: Team) -> None:
        self._section(
            parent,
            "球员名单",
            "点击球员进入详细数据页面",
        )
        roster_key = self._roster_key(team.id)
        roster_stale = (
            roster_key in self.rosters
            and time.time() - self.roster_loaded_at.get(roster_key, 0)
            >= self.roster_refresh_hours_var.get() * 3600
        )
        error_retry_ready = (
            roster_key not in self.roster_errors
            or time.time() - self.roster_error_at.get(roster_key, 0) >= 300
        )
        if (
            (roster_key not in self.rosters or roster_stale)
            and roster_key not in self.loading_rosters
            and error_retry_ready
        ):
            self.loading_rosters.add(roster_key)
            self._load_roster_async(team.id)
        if roster_key in self.loading_rosters and roster_key not in self.rosters:
            self._empty(parent, "正在加载球员名单...")
            return
        error = self.roster_errors.get(roster_key)
        if error:
            self._empty(parent, error)
            return
        players = self.rosters.get(roster_key, [])
        if not players:
            self._empty(parent, "暂未取得球员名单。")
            return

        roster = tk.Frame(parent, bg=BG)
        roster.pack(fill="both", expand=True)
        for player in players:
            card = tk.Frame(roster, bg=PANEL, padx=10, pady=8, highlightthickness=1, highlightbackground=LINE, cursor="hand2")
            card.pack(fill="x", pady=4)
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill="x")
            number = f"#{player.jersey}" if player.jersey else "--"
            tk.Label(top, text=number, bg=PANEL_2, fg=ACCENT, width=5, pady=3, font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=(0, 8))
            name_box = tk.Frame(top, bg=PANEL)
            name_box.pack(side="left", fill="x", expand=True)
            name_label = tk.Label(name_box, text=self._player_text(player.name, player.id), bg=PANEL, fg=TEXT, anchor="w", justify="left", font=("Microsoft YaHei UI", 10, "bold"))
            name_label.pack(fill="x")
            self._bind_wrap(name_label, reserve=4, minimum=110, maximum=260)
            meta = " · ".join(part for part in [self._position_text(player.position), f"{player.age} 岁" if player.age else ""] if part)
            meta_label = tk.Label(name_box, text=meta or "球员", bg=PANEL, fg=MUTED, anchor="w", justify="left", font=("Microsoft YaHei UI", 8))
            meta_label.pack(fill="x", pady=(2, 0))
            self._bind_wrap(meta_label, reserve=4, minimum=110, maximum=260)
            club_label = None
            if player.club_team_name:
                club_name = self.localizer.team(player.club_team_name)
                club_label = tk.Label(
                    name_box,
                    text=f"效力球队 · {club_name}",
                    bg=PANEL,
                    fg=(
                        ACCENT
                        if player.club_competition_key
                        else MUTED
                    ),
                    anchor="w",
                    justify="left",
                    cursor=(
                        "hand2"
                        if player.club_competition_key
                        else "arrow"
                    ),
                    font=("Microsoft YaHei UI", 8, "bold"),
                )
                club_label.pack(fill="x", pady=(2, 0))
                self._bind_wrap(
                    club_label,
                    reserve=4,
                    minimum=110,
                    maximum=260,
                )
            stats_box = None
            if (
                self.snapshot
                and self.snapshot.competition_kind != "league"
            ):
                stats_box = tk.Frame(card, bg=PANEL)
                stats_box.pack(fill="x", pady=(7, 0))
                for label, key in [("出场", "APP"), ("进球", "G"), ("助攻", "A")]:
                    value = player.stats.get(key, "-")
                    item = tk.Frame(stats_box, bg=PANEL_2, padx=7, pady=4)
                    item.pack(side="left", fill="x", expand=True, padx=(0, 5))
                    tk.Label(item, text=label if not self.use_english_var.get() else key, bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 7)).pack(anchor="w")
                    tk.Label(item, text=value or "-", bg=PANEL_2, fg=TEXT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
            open_player = (
                lambda _event, current=player:
                self._open_player_detail(current)
            )
            self._bind_click_tree(card, open_player)
            if club_label is not None and player.club_competition_key:
                self._bind_click(
                    club_label,
                    lambda _event, current=player:
                    self._open_external_club(
                        current,
                        back_action=(
                            lambda selected=current:
                            self._open_player_detail(selected)
                        ),
                    ),
                    add="",
                )

    def _load_roster_async(self, team_id: str) -> None:
        competition_key = self.active_competition_key
        roster_key = self._roster_key(team_id, competition_key)
        snapshot = self.snapshot
        provider = DataProvider(
            cache_dir=self.provider.cache_dir,
            competition_key=competition_key,
        )
        if snapshot is not None:
            provider.teams = snapshot.teams
            provider.season_year = snapshot.season_year
            provider.season_name = snapshot.season_name
        roster_ttl_hours = self.roster_refresh_hours_var.get()

        def worker() -> None:
            players, error = provider.get_roster(team_id, ttl_hours=roster_ttl_hours)

            def apply(current_players: list[Player], current_error: str | None, final: bool) -> None:
                if final:
                    self.loading_rosters.discard(roster_key)
                if current_error:
                    self.roster_errors[roster_key] = current_error
                    self.roster_error_at[roster_key] = time.time()
                else:
                    self.rosters[roster_key] = current_players
                    self.roster_loaded_at[roster_key] = time.time()
                    self.roster_errors.pop(roster_key, None)
                    self.roster_error_at.pop(roster_key, None)
                    self._request_name_localization(
                        "player",
                        [
                            player.name
                            for player in current_players
                            if self.localizer.player(
                                player.name,
                                player.id,
                            ) == player.name
                        ],
                    )
                if (
                    self.active_competition_key == competition_key
                    and self.active_tab == "team"
                    and self.selected_team_id == team_id
                ):
                    self.render_team()

            if error or not players:
                self._post_ui(
                    lambda current=list(players), message=error:
                    apply(current, message, True)
                )
                return

            if competition_key != "worldcup":
                self._post_ui(
                    lambda current=list(players):
                    apply(current, None, True)
                )
                return

            # Show the roster immediately, then enrich it with current clubs.
            self._post_ui(
                lambda current=list(players):
                apply(current, None, False)
            )
            with ThreadPoolExecutor(max_workers=6) as executor:
                enriched = list(executor.map(provider.get_player_profile, players))
            self._post_ui(
                lambda current=enriched:
                apply(current, None, True)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _select_player(self, player_id: str) -> None:
        self.selected_player_id = player_id
        if self.active_tab == "team":
            self.render_team()

    def _open_player_detail(self, player: Player, back_action=None) -> None:
        self._prepare_single_popup(back_action=back_action, clear_history=back_action is None)
        popup = tk.Toplevel(self.root)
        self.player_popup = popup
        self.player_popup_player_id = player.id
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.97)
        popup.bind(
            "<Destroy>",
            lambda event, current=popup:
            setattr(self, "player_popup", None)
            if event.widget is current and self.player_popup is current else None,
            add="+",
        )
        width = min(330, max(280, self.root.winfo_width() - 24))
        height = min(470, max(360, self.root.winfo_height() - 40))
        popup.geometry(f"{width}x{height}+{self.root.winfo_x() + 12}+{self.root.winfo_y() + 24}")
        header = tk.Frame(popup, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        title = tk.Label(header, text="球员详情", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 11, "bold"))
        title.pack(side="left")
        close = tk.Label(header, text="×", bg=PANEL, fg=MUTED, cursor="hand2", font=("Microsoft YaHei UI", 13, "bold"))
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_and_restore(self._close_player_popup))
        self._bind_drag(header)
        self._bind_drag(title)
        body = ScrollFrame(popup, bg=PANEL)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.player_popup_body = body.body
        self._player_detail(body.body, player)
        self._apply_fonts_to_tree(popup)

        profile_provider = DataProvider(
            cache_dir=self.provider.cache_dir,
            competition_key=self.active_competition_key,
        )

        def worker() -> None:
            enriched = profile_provider.get_player_profile(player)
            self._post_ui(
                lambda current=enriched:
                self._apply_player_profile(current)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _request_name_localization(
        self,
        kind: str,
        names: list[str],
    ) -> None:
        key = self._current_ai_credential()
        cache_key = "players" if kind == "player" else "teams"
        missing = [
            name for name in dict.fromkeys(names)
            if name
            and name not in self.name_localization_cache[cache_key]
            and f"{kind}:{name}" not in self.name_localization_loading
        ]
        if not missing or (not key and kind != "player"):
            return
        for name in missing:
            self.name_localization_loading.add(f"{kind}:{name}")

        def worker() -> None:
            translated: dict[str, str] = {}
            if key:
                try:
                    for start in range(0, len(missing), 60):
                        translated.update(
                            self.commentary_service.localize_football_names(
                                missing[start : start + 60],
                                kind,
                                key,
                            )
                        )
                except Exception:
                    pass
            if kind == "player":
                unresolved = [name for name in missing if name not in translated]
                translated.update(self.wikidata_name_service.localize_players(unresolved))
            self._post_ui(
                lambda rows=translated:
                self._apply_name_localization(kind, missing, rows)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _apply_name_localization(
        self,
        kind: str,
        requested: list[str],
        translated: dict[str, str],
    ) -> None:
        cache_key = "players" if kind == "player" else "teams"
        self.name_localization_cache[cache_key].update(translated)
        if kind == "player":
            self.localizer.players.update(translated)
        else:
            self.localizer.teams_by_name.update(translated)
        for name in requested:
            self.name_localization_loading.discard(f"{kind}:{name}")
        if translated:
            self._save_name_localization_cache()
            self._invalidate_render_cache()
            self._update_all_commentary_labels()
            if self.snapshot:
                self.render_active()

    def _clear_club_popup_reference(
        self,
        popup: tk.Toplevel,
    ) -> None:
        if self.club_popup is popup:
            self.club_popup = None
            self.club_popup_body = None

    def _apply_player_profile(self, player: Player) -> None:
        if (
            self.player_popup is None
            or not self.player_popup.winfo_exists()
            or self.player_popup_player_id != player.id
            or self.player_popup_body is None
        ):
            return
        self._player_detail(self.player_popup_body, player)
        self._apply_fonts_to_tree(self.player_popup)

    def _open_external_club(self, player: Player, back_action=None, restore_only: bool = False) -> None:
        if (
            not player.club_competition_key
            or not player.club_team_id
        ):
            return
        if back_action is None and not restore_only:
            back_action = lambda current=player: self._open_player_detail(current)
        self._prepare_single_popup(back_action=back_action)
        self.club_source_player = player
        popup = tk.Toplevel(self.root)
        self.club_popup = popup
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.98)
        popup.bind(
            "<Destroy>",
            lambda event, current=popup:
            self._clear_club_popup_reference(current)
            if event.widget is current else None,
            add="+",
        )
        width = min(340, max(286, self.root.winfo_width() - 16))
        height = min(500, max(380, self.root.winfo_height() - 28))
        popup.geometry(
            f"{width}x{height}+{self.root.winfo_x() + 8}+"
            f"{self.root.winfo_y() + 18}"
        )
        header = tk.Frame(popup, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        title = tk.Label(
            header,
            text="俱乐部资料",
            bg=PANEL,
            fg=ACCENT,
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        title.pack(side="left")
        close = tk.Label(
            header,
            text="×",
            bg=PANEL,
            fg=MUTED,
            cursor="hand2",
            font=("Microsoft YaHei UI", 13, "bold"),
        )
        close.pack(side="right")
        self._bind_click(close, lambda _event: self._close_and_restore(self._close_club_popup))
        self._bind_drag(header)
        self._bind_drag(title)
        body = ScrollFrame(popup, bg=PANEL)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.club_popup_body = body.body
        self._empty(body.body, "正在加载俱乐部资料…")
        roster_ttl_hours = self.roster_refresh_hours_var.get()

        def worker() -> None:
            provider = DataProvider(
                cache_dir=self.provider.cache_dir,
                competition_key=player.club_competition_key,
            )
            snapshot = provider.load_all(force=False)
            team = snapshot.teams.get(player.club_team_id)
            roster: list[Player] = []
            error = ""
            if team is not None:
                roster, roster_error = provider.get_roster(team.id, ttl_hours=roster_ttl_hours)
                error = roster_error or ""
            else:
                error = "未在当前联赛赛季中找到该俱乐部。"
            self._post_ui(
                lambda current_snapshot=snapshot, current_team=team,
                current_roster=roster, current_error=error:
                self._render_external_club(
                    current_snapshot,
                    current_team,
                    current_roster,
                    current_error,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _render_external_club(
        self,
        snapshot: Snapshot,
        team: Team | None,
        roster: list[Player],
        error: str,
    ) -> None:
        if (
            self.club_popup is None
            or not self.club_popup.winfo_exists()
            or self.club_popup_body is None
        ):
            return
        parent = self.club_popup_body
        for child in parent.winfo_children():
            child.destroy()
        if team is None:
            self._empty(parent, error or "俱乐部资料暂时不可用。")
            return
        header = tk.Frame(
            parent,
            bg=PANEL,
            padx=12,
            pady=11,
            highlightthickness=1,
            highlightbackground=LINE,
        )
        header.pack(fill="x", pady=(0, 8))
        self._team_icon(
            header,
            team.id,
            team.logo,
            size=44,
            clickable=False,
        ).pack(side="left")
        info = tk.Frame(header, bg=PANEL)
        info.pack(side="left", fill="x", expand=True, padx=(12, 0))
        name = tk.Label(
            info,
            text=self._team_text(team),
            bg=PANEL,
            fg=TEXT,
            anchor="w",
            font=("Microsoft YaHei UI", 14, "bold"),
        )
        name.pack(fill="x")
        self._bind_wrap(name, reserve=4, minimum=130, maximum=250)
        standing = team.standing
        meta = (
            f"{snapshot.competition_name} · "
            f"{snapshot.season_name or '当前赛季'}"
        )
        if standing.get("rank"):
            meta += f" · 第 {standing['rank']} 名"
        meta_label = tk.Label(
            info,
            text=meta,
            bg=PANEL,
            fg=ACCENT,
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        meta_label.pack(fill="x", pady=(3, 0))
        self._bind_wrap(meta_label, reserve=4, minimum=130, maximum=250)
        if standing:
            values = "  ".join(
                f"{key}{standing.get(key, '')}"
                for key in ["赛", "胜", "平", "负", "进", "失", "净", "分"]
            )
            stats = tk.Label(
                parent,
                text=values,
                bg=PANEL_2,
                fg=TEXT,
                anchor="w",
                justify="left",
                padx=9,
                pady=7,
                font=("Microsoft YaHei UI", 9),
            )
            stats.pack(fill="x", pady=(0, 8))
            self._bind_wrap(stats, reserve=18, minimum=150, maximum=300)
        team_matches = [
            match for match in snapshot.matches
            if team.id in {match.home.id, match.away.id}
        ]
        completed = sorted(
            (match for match in team_matches if match.completed),
            key=lambda match: match.date or MIN_DATE,
            reverse=True,
        )[:5]
        self._section(parent, "近期赛果", "最近五场正式比赛")
        for match in completed:
            row = tk.Frame(parent, bg=PANEL_2, padx=9, pady=7)
            row.pack(fill="x", pady=2)
            text = (
                f"{self._team_text(match.home)} "
                f"{match.home.score or '-'} - {match.away.score or '-'} "
                f"{self._team_text(match.away)}"
            )
            label = tk.Label(
                row,
                text=text,
                bg=PANEL_2,
                fg=TEXT,
                anchor="w",
                justify="left",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            label.pack(fill="x")
            self._bind_wrap(label, reserve=4, minimum=150, maximum=300)
        self._section(parent, "球员名单", "点击球员查看详细数据")
        if error:
            self._empty(parent, error)
        for current in roster:
            row = tk.Frame(
                parent,
                bg=PANEL,
                padx=9,
                pady=7,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=LINE,
            )
            row.pack(fill="x", pady=2)
            number = f"#{current.jersey}" if current.jersey else "--"
            tk.Label(
                row,
                text=number,
                bg=PANEL_2,
                fg=ACCENT,
                width=5,
                font=("Microsoft YaHei UI", 8, "bold"),
            ).pack(side="left")
            label = tk.Label(
                row,
                text=(
                    f"{self._player_text(current.name, current.id)} · "
                    f"{self._position_text(current.position)}"
                ),
                bg=PANEL,
                fg=TEXT,
                anchor="w",
                justify="left",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            label.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self._bind_wrap(label, reserve=58, minimum=130, maximum=250)
            self._bind_click_tree(
                row,
                lambda _event, selected=current, source=self.club_source_player:
                self._open_player_detail(
                    selected,
                    back_action=(
                        (
                            lambda current_source=source:
                            self._open_external_club(
                                current_source,
                                restore_only=True,
                            )
                        )
                        if source is not None else None
                    ),
                ),
            )
        self._apply_fonts_to_tree(self.club_popup)

    def _player_detail(self, parent: tk.Widget, player: Player) -> None:
        for child in parent.winfo_children():
            child.destroy()
        name_label = tk.Label(parent, text=self._player_text(player.name, player.id), bg=PANEL, fg=TEXT, justify="left", font=("Microsoft YaHei UI", 13, "bold"))
        name_label.pack(anchor="w", fill="x")
        self._bind_wrap(name_label, reserve=8, minimum=140, maximum=300)
        meta = " · ".join(part for part in [f"#{player.jersey}" if player.jersey else "", self._position_text(player.position), f"{player.age} 岁" if player.age else ""] if part)
        meta_label = tk.Label(parent, text=meta or "球员资料", bg=PANEL, fg=ACCENT, justify="left", font=("Microsoft YaHei UI", 10, "bold"))
        meta_label.pack(anchor="w", fill="x", pady=(4, 8))
        self._bind_wrap(meta_label, reserve=8, minimum=140, maximum=300)
        physical = "  ".join(part for part in [player.height, player.weight, player.birthplace] if part)
        if physical:
            physical_label = tk.Label(parent, text=physical, bg=PANEL, fg=MUTED, justify="left")
            physical_label.pack(anchor="w", fill="x", pady=(0, 10))
            self._bind_wrap(physical_label, reserve=8, minimum=140, maximum=300)
        if player.club_team_name:
            club_row = tk.Frame(parent, bg=PANEL_2, padx=9, pady=7)
            club_row.pack(fill="x", pady=(0, 10))
            tk.Label(
                club_row,
                text="所在俱乐部",
                bg=PANEL_2,
                fg=MUTED,
                font=("Microsoft YaHei UI", 8),
            ).pack(side="left")
            club_name = self.localizer.team(player.club_team_name)
            club = tk.Label(
                club_row,
                text=club_name,
                bg=PANEL_2,
                fg=ACCENT if player.club_competition_key else TEXT,
                cursor="hand2" if player.club_competition_key else "arrow",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            club.pack(side="right")
            if player.club_competition_key:
                self._bind_click_tree(
                    club_row,
                    lambda _event, current=player:
                    self._open_external_club(current),
                )
        data_header = tk.Frame(parent, bg=PANEL)
        data_header.pack(fill="x")
        tk.Label(
            data_header,
            text="赛事数据",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")
        tk.Label(
            data_header,
            text=self._season_label(
                player.data_season_year,
                self.snapshot,
                player.data_competition_key,
            ),
            bg=PANEL,
            fg=ACCENT,
            font=("Microsoft YaHei UI", 8, "bold"),
        ).pack(side="right")
        if not player.stats:
            tk.Label(parent, text="暂无出场统计", bg=PANEL, fg=MUTED).pack(anchor="w", pady=(8, 0))
            return
        stat_grid = tk.Frame(parent, bg=PANEL)
        stat_grid.pack(fill="x", pady=(8, 0))
        cells: list[tk.Frame] = []
        for index, (key, value) in enumerate(player.stats.items()):
            cell = tk.Frame(stat_grid, bg=PANEL_2, padx=9, pady=7)
            cells.append(cell)
            stat_name = tk.Label(cell, text=self._stat_label(key), bg=PANEL_2, fg=MUTED, justify="left", font=("Microsoft YaHei UI", 8))
            stat_name.pack(anchor="w", fill="x")
            self._bind_wrap(stat_name, reserve=8, minimum=80, maximum=150)
            stat_value = tk.Label(cell, text=value, bg=PANEL_2, fg=TEXT, justify="left", font=("Microsoft YaHei UI", 12, "bold"))
            stat_value.pack(anchor="w", fill="x")
            self._bind_wrap(stat_value, reserve=8, minimum=80, maximum=150)

        def layout_stats(event: tk.Event | None = None) -> None:
            width = event.width if event is not None else stat_grid.winfo_width()
            columns = 1 if width < 300 else 2
            for column in range(2):
                stat_grid.columnconfigure(column, weight=1 if column < columns else 0)
            for index, cell in enumerate(cells):
                cell.grid(row=index // columns, column=index % columns, sticky="ew", padx=3, pady=3)

        stat_grid.bind("<Configure>", layout_stats, add="+")
        stat_grid.after_idle(layout_stats)


def main() -> None:
    app = WorldCupFloatApp()
    app.run()


if __name__ == "__main__":
    main()
