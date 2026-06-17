from __future__ import annotations

import hashlib
import ctypes
import json
import subprocess
import sys
import threading
import traceback
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from tkinter import colorchooser, ttk
import tkinter as tk
import tkinter.font as tkfont

from data_provider import DataProvider, LeaderRow, Leaderboard, Match, MatchTeam, Player, Snapshot, Team
from localization import NameLocalizer


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
PALETTE_PRESETS = {
    "codex": {
        "label": "Codex 深色",
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


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = runtime_dir() / "config.json"


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
    def __init__(self, parent: tk.Widget, bg: str = BG) -> None:
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.body = tk.Frame(self.canvas, bg=bg)
        self.window_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._drag_active = False
        self._drag_start_y = 0
        self._drag_start_fraction = 0.0
        self.body.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._update_width)
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<ButtonPress-1>", self._start_content_drag, add="+")
        self.bind_all("<B1-Motion>", self._drag_content, add="+")
        self.bind_all("<ButtonRelease-1>", self._stop_content_drag, add="+")

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _update_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.winfo_viewable() and self._contains_widget(event.widget):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _contains_widget(self, widget: tk.Widget) -> bool:
        if widget.winfo_toplevel() is not self.winfo_toplevel():
            return False
        current = widget
        while current is not None:
            if current in (self.canvas, self.body):
                return True
            current = getattr(current, "master", None)
        return False

    def _is_interactive_drag_widget(self, widget: tk.Widget) -> bool:
        interactive_types = (tk.Entry, tk.Text, tk.Checkbutton, tk.Button, tk.Scale, ttk.Combobox, FlatSlider)
        return isinstance(widget, interactive_types)

    def _start_content_drag(self, event: tk.Event) -> None:
        if (
            not self.winfo_viewable()
            or not self._contains_widget(event.widget)
            or self._is_interactive_drag_widget(event.widget)
        ):
            return
        self._drag_active = True
        self._drag_start_y = event.y_root
        self._drag_start_fraction = self.canvas.yview()[0]

    def _drag_content(self, event: tk.Event) -> None:
        if not self._drag_active or not self.winfo_viewable():
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

    def _stop_content_drag(self, _event: tk.Event) -> None:
        if not self._drag_active:
            return
        self._drag_active = False


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
        self.config = self._load_config()
        self.available_fonts = sorted(set(tkfont.families(self.root)), key=str.casefold)
        self.ui_font_var = tk.StringVar(value=self._valid_font_name(self.config.get("ui_font"), DEFAULT_UI_FONT))
        self.score_font_var = tk.StringVar(value=self._valid_font_name(self.config.get("score_font"), DEFAULT_SCORE_FONT))
        self.app_title_var = tk.StringVar(value=self.config.get("title") or DEFAULT_APP_TITLE)
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

        self.provider = DataProvider()
        self.root.report_callback_exception = self._log_tk_exception
        self.images = ImageCache(self.root, self.provider.cache_dir / "images", on_loaded=self._schedule_image_refresh)
        self.localizer = NameLocalizer()
        self.snapshot: Snapshot | None = None
        self.active_tab = "live"
        self.team_options: dict[str, str] = {"全部球队": ""}
        self.selected_team_id = ""
        self.selected_player_id = ""
        self.active_data_board_key = ""
        self.data_board_buttons: dict[str, tk.Label] = {}
        self.rosters: dict[str, list[Player]] = {}
        self.roster_errors: dict[str, str | None] = {}
        self.loading_rosters: set[str] = set()
        self.match_labels: dict[str, list[dict[str, tk.Label]]] = {}
        self.standing_labels: dict[tuple[str, str], tk.Label] = {}
        self.leader_labels: dict[tuple[str, str], tk.Label] = {}
        self.rendered_signature: tuple | None = None
        self.tab_rendered_signatures: dict[str, tuple] = {}
        self.image_refresh_pending = False
        self.tab_switching = False
        self.window_visible = True
        self.context_menu: tk.Menu | None = None
        self.settings_popup: tk.Toplevel | None = None
        self.match_popup: tk.Toplevel | None = None
        self.match_popup_opening = False
        self.match_notification_popup: tk.Toplevel | None = None
        self.notified_live_match_ids: set[str] = set()
        self.tray_icon = None
        self.drag_origin = (0, 0)
        self.drag_target: tk.Tk | tk.Toplevel | None = None
        self.pointer_origin = (0, 0)
        self.pointer_dragged = False
        self.resize_origin = (0, 0, 0, 0)
        self.title_label: tk.Label | None = None
        self.status_label: tk.Label | None = None
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
        self.team_var = tk.StringVar(value="全部球队")
        self.alpha_var = tk.DoubleVar(value=float(self.config.get("alpha", 0.93)))
        self.topmost_var = tk.BooleanVar(value=bool(self.config.get("topmost", True)))
        self.use_english_var = tk.BooleanVar(value=bool(self.config.get("use_english", False)))
        self.quick_refresh_var = tk.BooleanVar(value=bool(self.config.get("quick_refresh", False)))
        self.show_status_var = tk.BooleanVar(value=bool(self.config.get("show_status", True)))
        self.match_notifications_var = tk.BooleanVar(value=bool(self.config.get("match_notifications", True)))
        self.live_refresh_seconds_var = tk.IntVar(value=self._valid_seconds(self.config.get("live_refresh_seconds"), 5))
        self.default_refresh_seconds_var = tk.IntVar(value=self._valid_seconds(self.config.get("default_refresh_seconds"), 15))
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
        self.root.after(self._current_refresh_ms(), self._auto_refresh)

    def run(self) -> None:
        self.root.mainloop()

    def _load_config(self) -> dict[str, str]:
        if not CONFIG_PATH.exists():
            return {}
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_config(self) -> None:
        try:
            palette = {key: self._valid_color(self.palette_colors.get(key), PALETTE_PRESETS["codex"][key]) for key in PALETTE_KEYS}
            CONFIG_PATH.write_text(
                json.dumps(
                    {
                        "title": self.app_title_var.get().strip() or DEFAULT_APP_TITLE,
                        "theme_color": self._valid_color(self.theme_color_var.get(), ACCENT),
                        "icon_choice": self._valid_icon_choice(self.icon_choice_var.get()),
                        "palette": self._valid_palette_name(self.palette_var.get()),
                        "custom_palette": palette,
                        "quick_refresh": bool(self.quick_refresh_var.get()) if hasattr(self, "quick_refresh_var") else False,
                        "show_status": bool(self.show_status_var.get()) if hasattr(self, "show_status_var") else True,
                        "match_notifications": bool(self.match_notifications_var.get()) if hasattr(self, "match_notifications_var") else True,
                        "topmost": bool(self.topmost_var.get()) if hasattr(self, "topmost_var") else True,
                        "use_english": bool(self.use_english_var.get()) if hasattr(self, "use_english_var") else False,
                        "alpha": round(float(self.alpha_var.get()), 2) if hasattr(self, "alpha_var") else 0.93,
                        "window_geometry": self.root.geometry() if hasattr(self, "root") else "",
                        "live_refresh_seconds": self._valid_seconds(self.live_refresh_seconds_var.get(), 5) if hasattr(self, "live_refresh_seconds_var") else 5,
                        "default_refresh_seconds": self._valid_seconds(self.default_refresh_seconds_var.get(), 15) if hasattr(self, "default_refresh_seconds_var") else 15,
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
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.destroy()
        self.settings_popup = None

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
        return max(3, min(seconds, 180))

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
        for popup in (self.settings_popup, self.match_popup, self.match_notification_popup):
            if popup is not None and popup.winfo_exists():
                self._apply_fonts_to_tree(popup)
        self._save_config()

    def _valid_palette_name(self, value: str | None) -> str:
        value = str(value or "").strip()
        if value in PALETTE_PRESETS or value == "custom":
            return value
        return "codex"

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
                current = widget.cget(option)
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
        self.root.title(title)
        if self.tray_icon is not None:
            try:
                self.tray_icon.title = title
            except Exception:
                pass
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

    def _toggle_match_notifications(self) -> None:
        self._save_config()
        if not self.match_notifications_var.get():
            self._close_match_notification()
            return
        if self.snapshot:
            self.root.after(120, lambda: self._maybe_show_match_notification(self.snapshot, include_seen=True) if self.snapshot else None)

    def _apply_quick_refresh_visibility(self) -> None:
        if self.quick_refresh_button is None:
            return
        if self.quick_refresh_var.get():
            if not self.quick_refresh_button.winfo_manager():
                self.quick_refresh_button.pack(side="right", padx=(8, 0))
        else:
            self.quick_refresh_button.pack_forget()

    def _apply_status_visibility(self) -> None:
        if self.status_label is None:
            return
        if self.show_status_var.get():
            if not self.status_label.winfo_manager():
                self.status_label.pack(anchor="w", pady=(2, 0))
        else:
            self.status_label.pack_forget()

    def _save_refresh_settings(self, *_args) -> None:
        self.live_refresh_seconds_var.set(self._valid_seconds(self.live_refresh_seconds_var.get(), 5))
        self.default_refresh_seconds_var.set(self._valid_seconds(self.default_refresh_seconds_var.get(), 15))
        self._save_config()

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

        def update(event: tk.Event | None = None) -> None:
            try:
                if not label.winfo_exists():
                    return
                width = event.width if event is not None and event.widget == parent else parent.winfo_width()
                if width <= 1:
                    label.after(50, update)
                    return
                label.configure(wraplength=max(minimum, min(maximum, width - reserve)))
            except tk.TclError:
                return

        parent.bind("<Configure>", update, add="+")
        label.after_idle(update)
        return label

    def _log_tk_exception(self, exc_type, exc_value, exc_tb) -> None:
        log_path = self.provider.cache_dir.parent / "worldcup_error.log"
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("\n--- Tk callback exception ---\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
        except Exception:
            pass

    def _schedule_image_refresh(self) -> None:
        if self.image_refresh_pending or not self.snapshot:
            return
        self.image_refresh_pending = True
        self.root.after(500, self._refresh_images)

    def _refresh_images(self) -> None:
        self.image_refresh_pending = False
        if self.snapshot and self.root.state() != "withdrawn":
            self.render_active()

    def _team_text(self, team: Team | MatchTeam | LeaderRow) -> str:
        name = getattr(team, "name", "") or getattr(team, "team_name", "")
        abbreviation = getattr(team, "abbreviation", "") or getattr(team, "team_abbreviation", "")
        return self.localizer.team(name, abbreviation, english=self.use_english_var.get())

    def _player_text(self, name: str, player_id: str = "") -> str:
        return self.localizer.player(name, player_id=player_id, english=self.use_english_var.get())

    def _position_text(self, name: str) -> str:
        return self.localizer.position(name, english=self.use_english_var.get())

    def _board_text(self, key: str, fallback: str) -> str:
        return self.localizer.board(key, fallback, english=self.use_english_var.get())

    def _stat_label(self, key: str) -> str:
        return key if self.use_english_var.get() else PLAYER_STAT_LABELS.get(key, key)

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
        self.root.bind("<Button-3>", self._show_context_menu)

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left", fill="x", expand=True)
        quick_refresh = tk.Label(
            header,
            text="↻",
            bg=BG,
            fg=ACCENT,
            padx=3,
            pady=1,
            cursor="hand2",
            font=("Microsoft YaHei UI", 11, "bold"),
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
        title_label.pack(anchor="w")
        self.title_label = title_label
        self._bind_wrap(title_label, reserve=12, minimum=120, maximum=260)
        status_label = tk.Label(
            title_box,
            textvariable=self.status_var,
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        )
        status_label.pack(anchor="w", pady=(2, 0))
        self.status_label = status_label
        self._bind_wrap(status_label, reserve=12, minimum=120, maximum=260)
        self._apply_status_visibility()
        self._apply_quick_refresh_visibility()
        for widget in (header, title_box, title_label, status_label):
            self._bind_drag(widget)

        controls = tk.Frame(self.root, bg=BG)
        self.team_combo = ttk.Combobox(
            controls,
            textvariable=self.team_var,
            state="readonly",
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

        grip = tk.Frame(self.root, bg=BG, cursor="size_nw_se", width=18, height=18)
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<ButtonPress-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._resize_window)

    def _configure_fonts(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT)

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
        columns = len(self.tab_button_order)
        for index, key in enumerate(self.tab_button_order):
            button = self.tab_buttons[key]
            button.grid(row=0, column=index, sticky="ew", padx=(0, 3), pady=(0, 4))
            button.configure(wraplength=max(26, min(48, width // columns - 6)))
        for column in range(len(self.tab_button_order)):
            self.tab_bar.columnconfigure(column, weight=1)

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

    def _global_pointer_motion(self, event: tk.Event) -> None:
        if abs(event.x_root - self.pointer_origin[0]) > 5 or abs(event.y_root - self.pointer_origin[1]) > 5:
            self.pointer_dragged = True

    def _global_pointer_release(self, event: tk.Event) -> None:
        if self.pointer_dragged:
            return
        self._maybe_close_match_popup(event)
        self._maybe_close_match_notification(event)

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
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.withdraw()
        self._close_match_popup()
        self.root.withdraw()
        self.window_visible = False

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.deiconify()
            self.settings_popup.lift()
        self.root.attributes("-topmost", self.topmost_var.get())
        self.window_visible = True
        self._mark_as_tool_window()

    def toggle_visibility(self) -> None:
        if self.window_visible and self.root.state() != "withdrawn":
            self.hide_window()
        else:
            self.show_window()

    def exit_app(self) -> None:
        self._save_config()
        try:
            if self.tray_icon is not None:
                self.tray_icon.stop()
        except Exception:
            pass
        try:
            if self.settings_popup is not None:
                self.settings_popup.destroy()
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
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.96)
        popup.geometry(f"330x560+{self.root.winfo_x() + 28}+{self.root.winfo_y() + 72}")
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
        tk.Label(body, text="顶部标题", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
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

        tk.Label(body, text="字体", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        font_panel = tk.Frame(body, bg=PANEL_2, padx=9, pady=7, highlightthickness=1, highlightbackground=LINE)
        font_panel.pack(fill="x", pady=(3, 10))

        def font_selector(label: str, variable: tk.StringVar) -> None:
            row = tk.Frame(font_panel, bg=PANEL_2)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=PANEL_2, fg=MUTED, width=7, anchor="w", font=("Microsoft YaHei UI", 8)).pack(side="left")
            combo = ttk.Combobox(row, textvariable=variable, state="readonly", values=self.available_fonts, height=14)
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
        color_swatch.pack(side="left", padx=(0, 8), ipady=6)
        color_entry = tk.Entry(
            color_row,
            textvariable=self.theme_color_var,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )
        color_entry.pack(side="left", fill="x", expand=True, ipady=5)
        color_entry.bind("<Return>", lambda _event: self._apply_theme_color())
        color_entry.bind("<FocusOut>", lambda _event: self._apply_theme_color())
        self._text_button(color_row, "选色", self._choose_theme_color).pack(side="left", padx=(8, 0))

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
            text="显示英文名",
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
        self._text_button(size_row, "紧凑", lambda: self.root.geometry(self._compact_geometry())).pack(side="left", padx=(0, 8))
        self._text_button(size_row, "宽屏", lambda: self.root.geometry("520x620")).pack(side="left")
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
            self.tabs[self.active_tab].pack_forget()
            self.active_tab = key
            self.tabs[key].pack(fill="both", expand=True)
            for tab, button in self.tab_buttons.items():
                active = tab == key
                button.configure(bg=PANEL if active else BG, fg=ACCENT if active else MUTED)
            if self._tab_needs_render(key):
                self.render_active()
        finally:
            self.root.after(40, lambda: setattr(self, "tab_switching", False))

    def _tab_needs_render(self, key: str | None = None) -> bool:
        key = key or self.active_tab
        frame = self.tabs.get(key)
        if frame is None:
            return True
        if not frame.body.winfo_children():
            return True
        return self.tab_rendered_signatures.get(key) != self._active_signature(tab=key)

    def refresh_data(self, force: bool = False, quiet: bool = True) -> None:
        if not quiet and self.snapshot is None:
            self._set_status_text("正在加载赛事数据...")

        def worker() -> None:
            try:
                snapshot = self.provider.load_all(force=force)
                self.root.after(0, lambda: self._apply_snapshot(snapshot, quiet=quiet))
            except Exception as exc:
                if not quiet or self.snapshot is None:
                    self.root.after(0, lambda: self._set_status_text(f"同步失败: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _auto_refresh(self) -> None:
        self.refresh_data(force=False, quiet=True)
        self.root.after(self._current_refresh_ms(), self._auto_refresh)

    def _current_refresh_ms(self) -> int:
        seconds = self.live_refresh_seconds_var.get() if self._has_live_matches() else self.default_refresh_seconds_var.get()
        return self._valid_seconds(seconds, AUTO_REFRESH_MS // 1000) * 1000

    def _has_live_matches(self) -> bool:
        return bool(self.snapshot and any(match.is_live for match in self.snapshot.matches))

    def _set_status_text(self, text: str) -> None:
        if self.show_status_var.get():
            self.status_var.set(text)
        else:
            self.status_var.set("")

    def _apply_snapshot(self, snapshot: Snapshot, quiet: bool = True) -> None:
        had_snapshot = self.snapshot is not None
        old_signatures = {
            tab: self._active_signature(self.snapshot, tab=tab)
            for tab in self.tab_rendered_signatures
        } if had_snapshot else {}
        self.snapshot = snapshot
        options = ["全部球队"]
        self.team_options = {"全部球队": ""}
        for team in sorted(snapshot.teams.values(), key=lambda t: (t.group or "Z", t.name)):
            option = self._team_option_text(team)
            options.append(option)
            self.team_options[option] = team.id
        self.team_combo.configure(values=options)
        if self.selected_team_id:
            selected = self._option_for_team(self.selected_team_id)
            if selected:
                self.team_var.set(selected)
        errors = f"；{len(snapshot.errors)} 个源使用缓存/降级" if snapshot.errors else ""
        source_text = " / ".join(snapshot.sources[:3]) if snapshot.sources else "缓存"
        if not quiet or not had_snapshot:
            self._set_status_text(f"已同步 {len(snapshot.matches)} 场比赛，{len(snapshot.teams)} 支球队 · {source_text}{errors}")
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

    def _active_signature(self, snapshot: Snapshot | None = None, tab: str | None = None) -> tuple:
        snapshot = snapshot or self.snapshot
        tab = tab or self.active_tab
        if snapshot is None:
            return ("empty", tab, self.selected_team_id)
        matches = self._filtered_matches(snapshot)
        if tab == "live":
            mode, _title, spotlight = self._spotlight_matches(snapshot)
            return ("spotlight", mode, self.selected_team_id, tuple((m.id, m.status_state, m.home.score, m.away.score) for m in spotlight))
        if tab == "upcoming":
            return ("upcoming", self.selected_team_id, tuple((m.id, m.status_state) for m in [m for m in matches if m.is_upcoming][:40]))
        if tab == "results":
            completed = [m for m in matches if m.completed]
            completed.sort(key=lambda m: m.date or MIN_DATE, reverse=True)
            return ("results", self.selected_team_id, tuple((m.id, m.home.score, m.away.score) for m in completed))
        if tab == "bracket":
            knockout = [m for m in snapshot.matches if m.round_slug != "group-stage"]
            if self.selected_team_id:
                knockout = [m for m in knockout if m.home.id == self.selected_team_id or m.away.id == self.selected_team_id]
            return ("bracket", self.selected_team_id, tuple((m.id, m.status_state, m.home.score, m.away.score) for m in knockout))
        if tab == "standings":
            groups = snapshot.standings
            if self.selected_team_id:
                team = snapshot.teams.get(self.selected_team_id)
                groups = [g for g in groups if g.get("name") == (team.group if team else "")]
            return (
                "standings",
                self.selected_team_id,
                tuple((g.get("name"), tuple((row["team"].id, tuple(sorted(row.get("stats", {}).items()))) for row in g.get("entries", []))) for g in groups),
            )
        if tab == "data":
            return (
                "data",
                self.active_data_board_key,
                tuple((board.key, tuple((row.player_id, row.display_value) for row in board.rows[:12])) for board in self._data_boards(snapshot)),
            )
        if tab == "team":
            roster_state = (
                "loading" if self.selected_team_id in self.loading_rosters else
                "error" if self.selected_team_id in self.roster_errors else
                len(self.rosters.get(self.selected_team_id, []))
            )
            team_matches = [(m.id, m.status_state, m.home.score, m.away.score) for m in snapshot.matches if m.home.id == self.selected_team_id or m.away.id == self.selected_team_id]
            return ("team", self.selected_team_id, roster_state, tuple(team_matches))
        return (tab, self.selected_team_id)

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

    def _apply_match_labels(self, labels: dict[str, tk.Label], match: Match) -> None:
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
            if label is not None:
                kwargs = {"text": value}
                if key == "status":
                    kwargs["fg"] = status_color
                self._safe_label_config(label, **kwargs)

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
        if not self.snapshot:
            self._render_loading(self.tabs[self.active_tab])
            return
        current_signature = self._active_signature(tab=self.active_tab)
        if not self._tab_needs_render(self.active_tab):
            self.rendered_signature = current_signature
            return
        self.match_labels.clear()
        self.standing_labels.clear()
        self.leader_labels.clear()
        renderers = {
            "live": self.render_live,
            "upcoming": self.render_upcoming,
            "results": self.render_results,
            "standings": self.render_standings,
            "bracket": self.render_bracket,
            "data": self.render_data,
            "team": self.render_team,
        }
        renderers[self.active_tab]()
        self._apply_fonts_to_tree(self.tabs[self.active_tab])
        self.rendered_signature = current_signature
        self.tab_rendered_signatures[self.active_tab] = current_signature

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

    def render_upcoming(self) -> None:
        frame = self.tabs["upcoming"]
        frame.clear()
        self._section(frame.body, "即将进行的比赛", "按开赛时间排序")
        self._team_filter_bar(frame.body)
        matches = [m for m in self._filtered_matches() if m.is_upcoming]
        if not matches:
            self._empty(frame.body, "没有找到即将进行的比赛。")
            return
        for match in matches[:40]:
            self._match_card(frame.body, match)

    def render_results(self) -> None:
        frame = self.tabs["results"]
        frame.clear()
        self._section(frame.body, "已完赛赛果", "点击队徽可查看国家队资料和球员")
        self._team_filter_bar(frame.body)
        matches = [m for m in self._filtered_matches() if m.completed]
        matches.sort(key=lambda m: m.date or MIN_DATE, reverse=True)
        if not matches:
            self._empty(frame.body, "还没有已完赛结果。")
            return
        for match in matches:
            self._match_card(frame.body, match)

    def render_standings(self) -> None:
        frame = self.tabs["standings"]
        frame.clear()
        self._section(frame.body, "小组积分", "胜平负、进失球、净胜球与积分")
        self._team_filter_bar(frame.body)
        groups = self.snapshot.standings if self.snapshot else []
        if self.selected_team_id:
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
        self._section(frame.body, "数据面板", "射手、助攻、参与进球与球队表现")
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

    def _select_data_board(self, key: str) -> None:
        self.active_data_board_key = key
        if self.active_tab == "data":
            self.render_data()

    def _data_boards(self, snapshot: Snapshot | None = None) -> list[Leaderboard]:
        snapshot = snapshot or self.snapshot
        if not snapshot:
            return []
        boards = list(snapshot.leaderboards)
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
        if contribution_rows:
            boards.append(Leaderboard("goalContributions", "Goal Contributions", contribution_rows[:50]))

        team_rows: list[tuple[str, str, str]] = []
        for group in snapshot.standings:
            for entry in group.get("entries", []):
                team = entry["team"]
                stats = entry["stats"]
                team_rows.append((team.id, "teamGoals", stats.get("进", "0")))
                team_rows.append((team.id, "teamGoalDifference", stats.get("净", "0")))
                team_rows.append((team.id, "teamPoints", stats.get("分", "0")))

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
        return [board for board in boards if board.rows]

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
            self._section(frame.body, "选择国家队", "从任意队徽或顶部下拉框进入球队资料")
            self._team_grid(frame.body)
            return
        team = self.snapshot.teams.get(self.selected_team_id)
        if not team:
            self._empty(frame.body, "没有找到该国家队。")
            return
        self._team_filter_bar(frame.body)
        self._team_header(frame.body, team)
        self._team_match_chain(frame.body, team)
        self._team_roster(frame.body, team)

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
        if live:
            buckets = {self._time_bucket(match) for match in live}
            spotlight = [
                match for match in matches
                if self._time_bucket(match) in buckets and (match.is_live or match.completed)
            ]
            spotlight.sort(key=lambda match: (match.date or MAX_DATE, match.id))
            return "live", "正在进行的比赛", spotlight

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
        box = tk.Frame(parent, bg=PANEL, padx=18, pady=18)
        box.pack(fill="x", pady=10)
        label = tk.Label(box, text=text, bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 11), justify="left")
        label.pack(anchor="w", fill="x")
        self._bind_wrap(label, reserve=8, minimum=120, maximum=420)

    def _match_card(self, parent: tk.Widget, match: Match, live: bool = False) -> None:
        card = tk.Frame(parent, bg=PANEL, padx=12, pady=11, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="x", pady=6)
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", pady=(0, 10))
        status_color = LIVE if match.is_live or live else (ACCENT if match.completed else WARNING)
        status = "LIVE " + match.status_text if match.is_live else (match.status_text or ("完赛" if match.completed else "未开始"))
        when = match.date.strftime("%m-%d %H:%M") if match.date else "时间待定"
        group = f" · {match.group} 组" if match.group else ""
        round_label = tk.Label(top, text=f"{match.round_name}{group}", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 9, "bold"))
        round_label.pack(side="left")
        status_label = tk.Label(top, text=f"{when} · {status}", bg=PANEL, fg=status_color, font=("Microsoft YaHei UI", 9, "bold"))
        status_label.pack(side="right")
        self._bind_wrap(round_label, reserve=138, minimum=80, maximum=190)

        body = tk.Frame(card, bg=PANEL)
        body.pack(fill="x")
        body.columnconfigure(0, weight=1, uniform="match_team", minsize=72)
        body.columnconfigure(1, weight=0, minsize=82)
        body.columnconfigure(2, weight=1, uniform="match_team", minsize=72)
        body.rowconfigure(0, minsize=82)
        home_labels = self._score_team_block(body, match.home, align="left", column=0)
        scoreline_label = tk.Label(
            body,
            text=self._scoreline(match),
            bg=PANEL,
            fg=TEXT,
            anchor="center",
            justify="center",
            font=("Microsoft YaHei UI", 20, "bold"),
        )
        scoreline_label._worldcup_score_font = True
        scoreline_label.grid(row=0, column=1, sticky="nsew", padx=3)
        away_labels = self._score_team_block(body, match.away, align="right", column=2)
        labels = {
            "round": round_label,
            "status": status_label,
            "away_name": away_labels["name"],
            "home_name": home_labels["name"],
            "scoreline": scoreline_label,
        }
        self.match_labels.setdefault(match.id, []).append(labels)
        self._bind_match_open(card, match)
        self._bind_match_open(top, match)
        self._bind_match_open(body, match)
        self._bind_match_open(scoreline_label, match)

    def _bind_match_open(self, widget: tk.Widget, match: Match) -> None:
        widget.configure(cursor="hand2")
        self._bind_click(widget, lambda _event, current=match: self._open_match_detail(current))

    def _close_match_popup(self, popup: tk.Toplevel | None = None) -> None:
        popup = popup or self.match_popup
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        if popup is self.match_popup or popup is None:
            self.match_popup = None

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
        self._close_match_notification()
        popup = tk.Toplevel(self.root)
        self.match_notification_popup = popup
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
        height = 74 + len(visible_matches) * 56 + (24 if len(matches) > len(visible_matches) else 0)
        x = max(18, self.root.winfo_screenwidth() - width - 24)
        y = max(18, self.root.winfo_screenheight() - height - 64)
        popup.geometry(f"{width}x{height}+{x}+{y}")

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
        tk.Label(
            title_row,
            text="点击关闭",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(side="right")

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

        self._bind_notification_close(popup)
        self._apply_fonts_to_tree(popup)
        popup.deiconify()
        popup.lift()

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
        self._close_match_popup()
        self.match_popup_opening = True
        self.root.after(180, lambda: setattr(self, "match_popup_opening", False))
        popup = tk.Toplevel(self.root)
        self.match_popup = popup
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.97)
        popup.bind("<Destroy>", lambda _event, current=popup: setattr(self, "match_popup", None) if self.match_popup is current else None, add="+")
        width = min(340, max(286, self.root.winfo_width() - 20))
        height = min(410, max(320, self.root.winfo_height() - 46))
        popup.geometry(f"{width}x{height}+{self.root.winfo_x() + 10}+{self.root.winfo_y() + 28}")
        header = tk.Frame(popup, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        header_label = tk.Label(header, text="对局资料", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 11, "bold"))
        header_label.pack(side="left")
        self._bind_drag(header)
        self._bind_drag(header_label)
        body = ScrollFrame(popup, bg=PANEL)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._match_detail(body.body, match)
        self._apply_fonts_to_tree(popup)

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
        self._match_events_panel(parent, match)
        self._match_stats_panel(parent, match)

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

    def _score_team_block(self, parent: tk.Widget, team: MatchTeam, align: str, column: int) -> dict[str, tk.Label]:
        block = tk.Frame(parent, bg=PANEL)
        block.grid(row=0, column=column, sticky="nsew")
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
        )
        name_label.pack(fill="x")
        self._bind_wrap(name_label, reserve=4, minimum=68, maximum=132)
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
        tk.Label(wrap, text=f"{group.get('name')} 组", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
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
        teams = sorted(self.snapshot.teams.values(), key=lambda t: (t.group or "Z", t.name)) if self.snapshot else []
        for index, team in enumerate(teams):
            cell = tk.Frame(grid, bg=PANEL, padx=8, pady=8, highlightthickness=1, highlightbackground=LINE)
            cell.pack(fill="x", pady=4)
            self._team_icon(cell, team.id, team.logo, size=28).pack(side="left")
            team_label = tk.Label(cell, text=f"{team.abbreviation}\n{self._team_text(team)}", bg=PANEL, fg=TEXT, justify="left", font=("Microsoft YaHei UI", 9, "bold"))
            team_label.pack(side="left", padx=(8, 0))
            self._bind_team_open(team_label, team.id)
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
        self._section(parent, "球员名单与数据", "点击球员可查看赛事统计")
        if team.id not in self.rosters and team.id not in self.loading_rosters and team.id not in self.roster_errors:
            self.loading_rosters.add(team.id)
            self._load_roster_async(team.id)
        if team.id in self.loading_rosters:
            self._empty(parent, "正在加载球员名单...")
            return
        error = self.roster_errors.get(team.id)
        if error:
            self._empty(parent, error)
            return
        players = self.rosters.get(team.id, [])
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
            stats_box = tk.Frame(card, bg=PANEL)
            stats_box.pack(fill="x", pady=(7, 0))
            for label, key in [("出场", "APP"), ("进球", "G"), ("助攻", "A")]:
                value = player.stats.get(key, "-")
                item = tk.Frame(stats_box, bg=PANEL_2, padx=7, pady=4)
                item.pack(side="left", fill="x", expand=True, padx=(0, 5))
                tk.Label(item, text=label if not self.use_english_var.get() else key, bg=PANEL_2, fg=MUTED, font=("Microsoft YaHei UI", 7)).pack(anchor="w")
                tk.Label(item, text=value or "-", bg=PANEL_2, fg=TEXT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
            for widget in [card, top, name_box, stats_box, *card.winfo_children()]:
                self._bind_click(widget, lambda _event, p=player: self._open_player_detail(p))

    def _load_roster_async(self, team_id: str) -> None:
        def worker() -> None:
            players, error = self.provider.get_roster(team_id)

            def apply() -> None:
                self.loading_rosters.discard(team_id)
                if error:
                    self.roster_errors[team_id] = error
                else:
                    self.rosters[team_id] = players
                    self.roster_errors.pop(team_id, None)
                if self.active_tab == "team" and self.selected_team_id == team_id:
                    self.render_team()

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _select_player(self, player_id: str) -> None:
        self.selected_player_id = player_id
        if self.active_tab == "team":
            self.render_team()

    def _open_player_detail(self, player: Player) -> None:
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=PANEL)
        popup.attributes("-topmost", True)
        popup.attributes("-alpha", 0.97)
        width = min(330, max(280, self.root.winfo_width() - 24))
        height = min(470, max(360, self.root.winfo_height() - 40))
        popup.geometry(f"{width}x{height}+{self.root.winfo_x() + 12}+{self.root.winfo_y() + 24}")
        header = tk.Frame(popup, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="球员详情", bg=PANEL, fg=ACCENT, font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        close = tk.Label(header, text="×", bg=PANEL, fg=MUTED, cursor="hand2", font=("Microsoft YaHei UI", 13, "bold"))
        close.pack(side="right")
        self._bind_click(close, lambda _event: popup.destroy())
        body = ScrollFrame(popup, bg=PANEL)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._player_detail(body.body, player)
        self._apply_fonts_to_tree(popup)

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
        tk.Label(parent, text="赛事数据", bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
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
