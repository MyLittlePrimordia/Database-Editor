#!/usr/bin/env python3
"""
IEM / Headphone Database Editor
--------------------------------
A standalone GUI tool for maintaining the audio database (database.json)
used by the offline IEM discovery / recommendation app.

Run directly with:  python main.py
Package as exe with PyInstaller (see README.md).
"""

import os
import sys
import json
import math
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import db_logic as L
import spell_logic as SP

APP_TITLE = "Database Editor"
APP_VERSION = "1.0"

# ---------------------------------------------------------------------------
# THEME
# ---------------------------------------------------------------------------
BG_MAIN = "#12141c"
BG_PANEL = "#181b26"
BG_CARD = "#1f2330"
BG_INPUT = "#0e1017"
BORDER = "#33405a"
BORDER_LIGHT = "#4a5f85"
ACCENT_BLUE = "#5b9bd9"
ACCENT_ORANGE = "#e8963c"
ACCENT_PURPLE = "#8a6ae8"
ACCENT_GREEN = "#4fbf82"
ACCENT_RED = "#e05a52"
TEXT_MAIN = "#e7e9f0"
TEXT_DIM = "#8892a8"

PREFERRED_FONTS = ["Consolas", "Courier New", "DejaVu Sans Mono", "Menlo", "Monaco"]

# Display-only emoji shown next to each tag in the picker so tags are faster
# to scan visually. The underlying tag strings saved to database.json are
# never changed -- this is purely cosmetic in the UI.
TAG_EMOJI = {
    "Basshead": "💥",
    "Sub-Bass": "🌊",
    "Punchy Bass": "🥊",
    "Warm": "🌿",
    "Neutral": "⚖️",
    "V-Shaped": "🔺",
    "U-Shaped": "🧲",
    "Balanced": "☯️",
    "Bright": "✨",
    "Treblehead": "⚡",
    "Dark": "🌑",
    "Vocal-Focused": "🗣️",
    "Detailed": "💎",
    "Resolving": "🔍",
    "Technical": "🔬",
    "Wide-Stage": "🏟️",
    "Good-Imaging": "🔭",
    "Smooth": "🧈",
    "Reference": "📐",
    "Analytical": "🧠",
    "Fun": "🔥",
    "Relaxed": "😌",
    "Gaming": "🎮",
    "Competitive-Gaming": "🏆",
    "Studio-Monitoring": "🎛️",
    "Collab": "🤝",
    "Limited-Edition": "🌟",
}


def tag_label(tag):
    emoji = TAG_EMOJI.get(tag)
    return "{} {}".format(tag, emoji) if emoji else tag


def pick_emoji_font():
    """Prefer an OS font with COLOR emoji glyphs. The app's monospace fonts
    (Consolas etc.) contain no emoji, which is why emojis previously showed
    as monochrome outlines -- tk falls back inconsistently. Rendering them
    in an explicit emoji font restores color on Win10/11+."""
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families())
        for f in ("Segoe UI Emoji",       # Windows 10/11 (color)
                  "Apple Color Emoji",    # macOS
                  "Noto Color Emoji"):    # Linux
            if f in families:
                return f
    except Exception:
        pass
    return None


def pick_font_family():
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families())
        for f in PREFERRED_FONTS:
            if f in families:
                return f
    except Exception:
        pass
    return "Courier"


# ---------------------------------------------------------------------------
# RIGHT-CLICK CONTEXT MENU FOR TEXT ENTRY WIDGETS
# ---------------------------------------------------------------------------

def entry_select_all(entry):
    entry.select_range(0, "end")
    entry.icursor("end")
    return "break"


def entry_copy(entry):
    try:
        sel = entry.selection_get()
    except Exception:
        sel = ""
    if sel:
        entry.clipboard_clear()
        entry.clipboard_append(sel)


def entry_cut(entry):
    try:
        sel = entry.selection_get()
    except Exception:
        sel = ""
    if sel:
        entry.clipboard_clear()
        entry.clipboard_append(sel)
        entry.delete("sel.first", "sel.last")


def entry_paste(entry):
    """Paste clipboard text at the cursor, replacing any selection."""
    try:
        text = entry.clipboard_get()
    except Exception:
        return
    if not text:
        return
    try:
        entry.delete("sel.first", "sel.last")
    except Exception:
        pass
    entry.insert(entry.index("insert"), text)


def entry_delete_selection(entry):
    """Delete selected text; with no selection, delete the character under
    the cursor (like Backspace-forward)."""
    try:
        if entry.selection_present():
            entry.delete("sel.first", "sel.last")
            return
    except Exception:
        pass
    pos = entry.index("insert")
    if pos < len(entry.get()):
        entry.delete(pos)


def attach_entry_context_menu(entry, extra_items=None):
    """Attach a right-click context menu (Cut / Copy / Paste / Delete /
    Select All) to an Entry widget. The menu is rebuilt on every right-click
    so Cut/Copy/Delete are enabled only when a selection exists and Paste
    only when the clipboard holds text.

    `extra_items(event, menu)`, when provided, is called first so callers
    can insert items at the top (used for spellcheck correction suggestions).

    Also binds Ctrl+A (select all), which Tk does not provide by default,
    complementing the native Ctrl+X / Ctrl+C / Ctrl+V shortcuts."""

    def _has_selection():
        try:
            return bool(entry.selection_present())
        except Exception:
            return False

    def _clipboard_has_text():
        try:
            return bool(entry.clipboard_get())
        except Exception:
            return False

    def _show_menu(event):
        has_sel = _has_selection()
        has_text = len(entry.get()) > 0
        menu = tk.Menu(entry, tearoff=0,
                       background=BG_CARD, foreground=TEXT_MAIN,
                       activebackground=BORDER_LIGHT, activeforeground=TEXT_MAIN,
                       font=(pick_font_family(), 10))
        if extra_items:
            try:
                extra_items(event, menu)
            except Exception:
                pass
        menu.add_command(label="Cut", state="normal" if has_sel else "disabled",
                         command=lambda: entry_cut(entry))
        menu.add_command(label="Copy", state="normal" if has_sel else "disabled",
                         command=lambda: entry_copy(entry))
        menu.add_command(label="Paste", state="normal" if _clipboard_has_text() else "disabled",
                         command=lambda: entry_paste(entry))
        menu.add_command(label="Delete", state="normal" if (has_sel or has_text) else "disabled",
                         command=lambda: entry_delete_selection(entry))
        menu.add_separator()
        menu.add_command(label="Select All", state="normal" if has_text else "disabled",
                         command=lambda: entry_select_all(entry))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    entry.bind("<Button-3>", _show_menu)
    # macOS aqua reports right-click as Button-2; only bind there so Linux
    # middle-click paste keeps working.
    if sys.platform == "darwin":
        entry.bind("<Button-2>", _show_menu)

    def _ctrl_a(_event=None):
        return entry_select_all(entry)

    entry.bind("<Control-a>", _ctrl_a)
    entry.bind("<Control-A>", _ctrl_a)


def resource_base():
    """Folder to look for bundled assets (icons)."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.isdir(os.path.join(exe_dir, "assets")):
            return exe_dir
        return getattr(sys, "_MEIPASS", exe_dir)
    return os.path.dirname(os.path.abspath(__file__))


def script_folder():
    """Folder the script/exe itself lives in (used for auto-detecting a
    database.json sitting right next to it)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class IconManager:
    def __init__(self):
        self.dir = os.path.join(resource_base(), "assets", "icons")
        self.cache = {}

    def get(self, name):
        if not name:
            return None
        if name in self.cache:
            return self.cache[name]
        # handle legacy typo: trybrid.png vs tribrid.png
        candidates = [name]
        if name == "tribrid":
            candidates.append("trybrid")
        elif name == "trybrid":
            candidates.append("tribrid")
        path = None
        for cand in candidates:
            p = os.path.join(self.dir, "{}.png".format(cand))
            if os.path.isfile(p):
                path = p
                break
        if not path:
            self.cache[name] = None
            return None
        try:
            img = tk.PhotoImage(file=path)
            # keep icons reasonably small in the UI
            w, h = img.width(), img.height()
            target = 20
            if w > target * 2:
                factor = max(1, w // target)
                img = img.subsample(factor, factor)
            self.cache[name] = img
            return img
        except Exception:
            self.cache[name] = None
            return None


ICONS = IconManager()

# Bundled colored-emoji PNGs (Twemoji) for tags. Tk 8.6 renders emoji FONTS
# as monochrome outlines on Windows (GDI has no color glyphs), so real color
# requires actual images -- same approach as the driver/connector icons.
_TAG_ICON_CACHE = {}


def tag_icon(tag):
    """Cached PhotoImage of the tag's colored emoji PNG, or None."""
    if tag in _TAG_ICON_CACHE:
        return _TAG_ICON_CACHE[tag]
    path = os.path.join(resource_base(), "assets", "icons", "tags",
                        "{}.png".format(tag))
    img = None
    if os.path.isfile(path):
        try:
            img = tk.PhotoImage(file=path)
            factor = max(1, img.width() // 16)
            if factor > 1:
                img = img.subsample(factor, factor)
        except Exception:
            img = None
    _TAG_ICON_CACHE[tag] = img
    return img


def setup_styles(root):
    font_family = pick_font_family()
    root.option_add("*Font", "{{{}}} 10".format(font_family))
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=BG_MAIN, foreground=TEXT_MAIN,
                    fieldbackground=BG_INPUT, bordercolor=BORDER,
                    darkcolor=BG_PANEL, lightcolor=BG_PANEL, font=(font_family, 10))
    style.configure("TFrame", background=BG_MAIN)
    style.configure("Panel.TFrame", background=BG_PANEL)
    style.configure("Card.TFrame", background=BG_CARD, relief="solid", borderwidth=1)
    style.configure("TLabel", background=BG_MAIN, foreground=TEXT_MAIN, font=(font_family, 10))
    style.configure("Panel.TLabel", background=BG_PANEL, foreground=TEXT_MAIN)
    style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_MAIN)
    style.configure("Dim.TLabel", background=BG_MAIN, foreground=TEXT_DIM)
    style.configure("Header.TLabel", background=BG_MAIN, foreground=ACCENT_ORANGE,
                     font=(font_family, 13, "bold"))
    style.configure("CardHeader.TLabel", background=BG_CARD, foreground=ACCENT_BLUE,
                     font=(font_family, 10, "bold"))
    style.configure("Status.TLabel", background=BG_PANEL, foreground=TEXT_DIM, font=(font_family, 9))

    style.configure("TButton", background=BG_CARD, foreground=TEXT_MAIN,
                     bordercolor=BORDER_LIGHT, focusthickness=1, padding=6)
    style.map("TButton", background=[("active", BORDER_LIGHT)])

    style.configure("Accent.TButton", background=ACCENT_ORANGE, foreground="#1a1a1a",
                     bordercolor=ACCENT_ORANGE, padding=6, font=(font_family, 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#f2a75a")])

    style.configure("Danger.TButton", background=ACCENT_RED, foreground="#1a1a1a", padding=6)
    style.map("Danger.TButton", background=[("active", "#ea7d76")])

    style.configure("Blue.TButton", background=ACCENT_BLUE, foreground="#0c1a2a", padding=6)
    style.map("Blue.TButton", background=[("active", "#7bb2e6")])

    style.configure("TEntry", fieldbackground=BG_INPUT, foreground=TEXT_MAIN,
                     bordercolor=BORDER_LIGHT, insertcolor=TEXT_MAIN)
    style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=TEXT_MAIN,
                     background=BG_INPUT, arrowcolor=TEXT_MAIN)
    style.map("TCombobox", fieldbackground=[("readonly", BG_INPUT)],
              foreground=[("readonly", TEXT_MAIN)])

    style.configure("TCheckbutton", background=BG_CARD, foreground=TEXT_MAIN)
    style.map("TCheckbutton", background=[("active", BG_CARD)])
    style.configure("Panel.TCheckbutton", background=BG_PANEL, foreground=TEXT_MAIN)

    style.configure("Treeview", background=BG_INPUT, fieldbackground=BG_INPUT,
                     foreground=TEXT_MAIN, bordercolor=BORDER, rowheight=22)
    style.configure("Treeview.Heading", background=BG_CARD, foreground=ACCENT_BLUE,
                     font=(font_family, 10, "bold"))
    style.map("Treeview", background=[("selected", ACCENT_BLUE)],
              foreground=[("selected", "#0c1a2a")])

    style.configure("TNotebook", background=BG_MAIN, bordercolor=BORDER)
    style.configure("TNotebook.Tab", background=BG_CARD, foreground=TEXT_MAIN, padding=(12, 6))
    style.map("TNotebook.Tab", background=[("selected", ACCENT_BLUE)],
              foreground=[("selected", "#0c1a2a")])

    style.configure("TPanedwindow", background=BG_MAIN)
    style.configure("Vertical.TScrollbar", background=BG_CARD, troughcolor=BG_MAIN,
                     bordercolor=BORDER, arrowcolor=TEXT_MAIN)
    style.configure("Horizontal.TScrollbar", background=BG_CARD, troughcolor=BG_MAIN,
                     bordercolor=BORDER, arrowcolor=TEXT_MAIN)
    style.configure("TSpinbox", fieldbackground=BG_INPUT, foreground=TEXT_MAIN,
                     bordercolor=BORDER_LIGHT, arrowcolor=TEXT_MAIN)

    # menubutton-based dropdown pickers must stay dark on hover/press too
    # (clam's default active state is near-white)
    style.configure("TMenubutton", background=BG_CARD, foreground=TEXT_MAIN,
                     arrowcolor=TEXT_MAIN, bordercolor=BORDER_LIGHT,
                     relief="flat", padding=(8, 4))
    style.map("TMenubutton",
              background=[("pressed", BG_INPUT), ("active", BORDER_LIGHT)],
              foreground=[("pressed", TEXT_MAIN), ("active", TEXT_MAIN)],
              arrowcolor=[("pressed", TEXT_MAIN), ("active", TEXT_MAIN)])
    return font_family


# ---------------------------------------------------------------------------
# AUTOCOMPLETE ENTRY WIDGET
# ---------------------------------------------------------------------------
ENTRY_TEXT_PAD_X = 8  # approx. left inner padding of a clam ttk.Entry (px)


class AutocompleteEntry(ttk.Frame):
    """A ttk.Entry with a filtered dropdown suggestion popup.

    When constructed with a `spell_checker`, it also performs live offline
    spellchecking on its contents: misspelled words get a thin red bar drawn
    directly beneath them, and right-clicking offers correction suggestions
    at the top of the context menu. Checks are debounced so typing stays
    responsive; the checker's dynamic vocabulary keeps known product names
    from ever being flagged."""

    SPELL_DEBOUNCE_MS = 350

    def __init__(self, parent, suggestions_provider, on_change=None,
                 spell_checker=None, **kwargs):
        super().__init__(parent, style="Card.TFrame")
        self.suggestions_provider = suggestions_provider  # callable(text) -> list[str]
        self.on_change = on_change
        self.spell_checker = spell_checker
        self.var = tk.StringVar()
        font_family = pick_font_family()
        kwargs.setdefault("font", (font_family, 10))
        self.entry = ttk.Entry(self, textvariable=self.var, **kwargs)
        self.entry.pack(fill="x")
        # Thin canvas directly under the entry used to draw red bars beneath
        # flagged words (monospace font => exact per-character pixel math).
        self.underline = tk.Canvas(self, height=3, background=BG_CARD,
                                   highlightthickness=0)
        self.underline.pack(fill="x")
        self._flags = []          # [(start, end, word)] currently flagged spans
        self._spell_after = None

        self.popup = None
        self.listbox = None
        self._suppress = False

        self.var.trace_add("write", self._on_var_write)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Escape>", lambda e: self._hide_popup())
        self.entry.bind("<Down>", self._focus_listbox)
        self.entry.bind("<Return>", self._on_return)
        attach_entry_context_menu(self.entry, extra_items=self._spell_menu_items)

        # keep the underbars aligned when the widget resizes / text scrolls
        self.entry.bind("<Configure>", lambda e: self._draw_underlines())
        self.entry.bind("<ButtonRelease-1>", lambda e: self._draw_underlines())
        self.entry.bind("<KeyRelease-Left>", lambda e: self._draw_underlines())
        self.entry.bind("<KeyRelease-Right>", lambda e: self._draw_underlines())

    def get(self):
        return self.var.get()

    def set(self, value):
        self._suppress = True
        self.var.set(value or "")
        self._suppress = False
        self._schedule_spell()

    # -- spellcheck ------------------------------------------------------
    def _schedule_spell(self):
        """Debounced spellcheck run."""
        if not self.spell_checker:
            return
        if self._spell_after:
            try:
                self.after_cancel(self._spell_after)
            except Exception:
                pass
            self._spell_after = None
        self._spell_after = self.after(self.SPELL_DEBOUNCE_MS, self._run_spell)

    def _run_spell(self):
        # cancel any queued run first so stale timers can't re-fire later
        if self._spell_after:
            try:
                self.after_cancel(self._spell_after)
            except Exception:
                pass
            self._spell_after = None
        sc = self.spell_checker
        if not sc or not sc.ready:
            return
        try:
            self._flags = sc.check_text(self.var.get())
        except Exception:
            self._flags = []
        self._draw_underlines()

    def _char_metrics(self):
        """(char_width_px, leftmost_visible_index) for the monospace font."""
        import tkinter.font as tkfont
        try:
            f = tkfont.Font(font=self.entry.cget("font"))
            cw = max(1, f.measure("n"))
        except Exception:
            cw = 9
        try:
            left_idx = self.entry.index("@0")
        except Exception:
            left_idx = 0
        return cw, left_idx

    def _draw_underlines(self):
        canvas = self.underline
        canvas.delete("all")
        if not self._flags:
            return
        width = self.entry.winfo_width()
        if width <= 1:
            return
        cw, left_idx = self._char_metrics()
        for start, end, _word in self._flags:
            x1 = ENTRY_TEXT_PAD_X + (start - left_idx) * cw
            x2 = ENTRY_TEXT_PAD_X + (end - left_idx) * cw
            if x2 <= 0 or x1 >= width:
                continue  # scrolled off-screen
            canvas.create_rectangle(max(0, x1), 0, min(width - 1, x2), 2,
                                    fill=ACCENT_RED, width=0)

    def _flag_at_column(self, col):
        """Flagged span containing character column `col` (or None)."""
        for start, end, word in self._flags:
            if start <= col < end:
                return (start, end, word)
        return None

    @staticmethod
    def _match_case(suggestion, original):
        if original.isupper():
            return suggestion.upper()
        if original[:1].isupper():
            return suggestion[:1].upper() + suggestion[1:]
        return suggestion

    def _replace_span(self, start, end, new_text):
        value = self.var.get()
        replaced = value[:start] + new_text + value[end:]
        self.var.set(replaced)
        try:
            self.entry.icursor(start + len(new_text))
            self.entry.focus_set()
        except Exception:
            pass
        self._hide_popup()

    def _spell_menu_items(self, event, menu):
        """Context-menu hook: correction suggestions for the word that was
        right-clicked, inserted above Cut/Copy/Paste."""
        sc = self.spell_checker
        if not sc or not sc.ready or not self._flags:
            return
        cw, left_idx = self._char_metrics()
        col = left_idx + int(round((event.x - ENTRY_TEXT_PAD_X) / float(cw)))
        hit = self._flag_at_column(col)
        if not hit:
            # small slop so clicking just beside a flagged word still resolves
            for start, end, word in self._flags:
                if col < start and (start - col) * cw <= 14:
                    hit = (start, end, word)
                    break
                if col >= end and (col - end) * cw <= 14:
                    hit = (start, end, word)
                    break
        if not hit:
            return
        start, end, word = hit
        suggs = sc.suggest(word, limit=5)
        if not suggs:
            menu.add_command(label="No suggestions for \u201c{}\u201d".format(word),
                             state="disabled")
        else:
            for s in suggs:
                fixed = self._match_case(s, word)
                menu.add_command(
                    label="\u27f2 {}".format(fixed),
                    background=BORDER, foreground="#ffd9a0",
                    command=lambda st=start, en=end, fx=fixed: self._replace_span(st, en, fx))
        menu.add_separator()

    def _on_var_write(self, *_):
        if self._suppress:
            return
        if self.on_change:
            self.on_change(self.var.get())
        self._update_popup()
        self._schedule_spell()

    def _update_popup(self):
        text = self.var.get().strip()
        if not text:
            self._hide_popup()
            return
        items = self.suggestions_provider(text)
        items = [i for i in items if i and i.lower() != text.lower()][:12]
        if not items:
            self._hide_popup()
            return
        self._show_popup(items)

    def _show_popup(self, items):
        if self.popup is None:
            self.popup = tk.Toplevel(self)
            self.popup.wm_overrideredirect(True)
            self.popup.attributes("-topmost", True)
            self.listbox = tk.Listbox(self.popup, background=BG_INPUT, foreground=TEXT_MAIN,
                                       selectbackground=ACCENT_BLUE, selectforeground="#0c1a2a",
                                       highlightthickness=1, highlightbackground=BORDER_LIGHT,
                                       activestyle="none", height=min(8, len(items)))
            self.listbox.pack(fill="both", expand=True)
            self.listbox.bind("<<ListboxSelect>>", self._on_select)
            self.listbox.bind("<Return>", self._on_select)
            self.listbox.bind("<Escape>", lambda e: self._hide_popup())
        self.listbox.delete(0, tk.END)
        for it in items:
            self.listbox.insert(tk.END, it)
        self.listbox.configure(height=min(8, len(items)))
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w = max(self.entry.winfo_width(), 160)
        self.popup.geometry("{}x{}+{}+{}".format(w, min(8, len(items)) * 20, x, y))
        self.popup.deiconify()

    def _hide_popup(self):
        if self.popup is not None:
            self.popup.withdraw()

    def _focus_listbox(self, _event=None):
        if self.popup and self.popup.winfo_viewable():
            self.listbox.focus_set()
            if self.listbox.size() > 0:
                self.listbox.selection_set(0)
        return "break"

    def _on_select(self, _event=None):
        if not self.listbox.curselection():
            return
        value = self.listbox.get(self.listbox.curselection()[0])
        self.set(value)
        if self.on_change:
            self.on_change(value)
        self._hide_popup()
        self.entry.focus_set()
        self.entry.icursor(tk.END)
        return "break"

    def _on_return(self, _event=None):
        if self.popup and self.popup.winfo_viewable() and self.listbox.size() > 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self._on_select()
            return "break"

    def _on_focus_out(self, _event=None):
        self.after(150, self._hide_popup)


# ---------------------------------------------------------------------------
# DRIVER CONFIG PANEL
# ---------------------------------------------------------------------------
class DriverConfigPanel(ttk.Frame):
    def __init__(self, parent, on_change=None):
        super().__init__(parent, style="Card.TFrame")
        self.on_change = on_change
        self.vars = {}
        self.counts = {}
        self.count_widgets = {}

        ttk.Label(self, text="DRIVER CONFIGURATION", style="CardHeader.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4))
        ttk.Label(self, text="Check each driver technology used and enter its count.\n"
                              "The type (DD / Hybrid / Tribrid / etc.) is derived automatically.",
                  style="Card.TLabel", foreground=TEXT_DIM).grid(
            row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 6))

        row = 2
        col = 0
        for tech in L.DRIVER_TECH_ORDER:
            frame = ttk.Frame(self, style="Card.TFrame")
            frame.grid(row=row, column=col, sticky="w", padx=8, pady=3)
            var = tk.BooleanVar(value=False)
            self.vars[tech] = var
            icon = ICONS.get(L.DRIVER_TYPE_ICON.get(tech, tech.lower()))
            cb = ttk.Checkbutton(frame, text=L.DRIVER_TECH_LABELS[tech], variable=var, image=icon,
                                  compound="left" if icon else "none",
                                  command=lambda t=tech: self._toggle(t))
            cb.image = icon
            cb.pack(side="left")
            count_var = tk.StringVar(value="1")
            self.counts[tech] = count_var
            spin = ttk.Spinbox(frame, from_=1, to=16, width=4, textvariable=count_var,
                                state="disabled", command=self._recompute)
            spin.pack(side="left", padx=(6, 0))
            count_var.trace_add("write", lambda *a: self._recompute())
            self.count_widgets[tech] = spin
            col += 1
            if col >= 2:
                col = 0
                row += 1
        row += 1

        self.result_label = ttk.Label(self, text="Driver Type: (none)      Config: (none)",
                                       style="Card.TLabel", foreground=ACCENT_GREEN,
                                       font=(pick_font_family(), 10, "bold"))
        self.result_label.grid(row=row, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 8))

    def _toggle(self, tech):
        state = "normal" if self.vars[tech].get() else "disabled"
        self.count_widgets[tech].configure(state=state)
        self._recompute()

    def _recompute(self):
        components = {}
        for tech, var in self.vars.items():
            if var.get():
                try:
                    c = int(self.counts[tech].get())
                    if c < 1:
                        c = 1
                except (TypeError, ValueError):
                    c = 1
                components[tech] = c
        dtype, dconfig = L.classify_driver(components)
        label = "Driver Type: {}      Config: {}".format(dtype or "(unknown/unverified)",
                                                          dconfig or "(none)")
        self.result_label.configure(text=label)
        if self.on_change:
            self.on_change(dtype, dconfig)

    def get(self):
        components = {}
        for tech, var in self.vars.items():
            if var.get():
                try:
                    c = int(self.counts[tech].get())
                except (TypeError, ValueError):
                    c = 1
                components[tech] = max(1, c)
        return L.classify_driver(components)

    def set(self, driver_type, driver_config):
        parsed = L.parse_driver_config(driver_config)
        for tech, var in self.vars.items():
            if tech in parsed:
                var.set(True)
                self.counts[tech].set(str(parsed[tech]))
                self.count_widgets[tech].configure(state="normal")
            else:
                var.set(False)
                self.counts[tech].set("1")
                self.count_widgets[tech].configure(state="disabled")
        self._recompute()

    def clear(self):
        self.set("", "")


# ---------------------------------------------------------------------------
# TAG SELECTOR PANEL
# ---------------------------------------------------------------------------
class TagSelectorPanel(ttk.Frame):
    def __init__(self, parent, on_change=None, fr_provider=None):
        super().__init__(parent, style="Card.TFrame")
        self.on_change = on_change
        self.fr_provider = fr_provider   # callable -> (suggestions, info_text)
        self.vars = {tag: tk.BooleanVar(value=False) for tag in L.APPROVED_TAGS}
        self.current_price = 0
        self._auto_tier_tag = "Budget"
        self._suggestions = []

        ttk.Label(self, text="TAGS  (pick 4–12 total)", style="CardHeader.TLabel").grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        self.count_label = ttk.Label(self, text="0 / 12 selected", style="Card.TLabel",
                                      foreground=TEXT_DIM)
        self.count_label.grid(row=0, column=1, sticky="e", padx=8)

        self.suggest_btn = ttk.Button(
            self, text="\u26a1 Suggest from FR Data",
            command=self._run_fr_suggestions,
            style="Blue.TButton")
        if fr_provider is None:
            self.suggest_btn.configure(state="disabled")
        self.suggest_btn.grid(row=1, column=0, sticky="w", padx=8, pady=(2, 4))

        self.emoji_font = pick_emoji_font()

        # groups start below the suggestion button row
        r = 2
        for group_name, tags in L.TAG_GROUPS.items():
            ttk.Label(self, text=group_name, style="Card.TLabel", foreground=ACCENT_BLUE,
                      font=(pick_font_family(), 9, "bold")).grid(
                row=r, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 2))
            r += 1
            if group_name.startswith("Price Tier"):
                self.tier_label = ttk.Label(self, text="Auto: Budget ($0-99)",
                                             style="Card.TLabel", foreground=ACCENT_ORANGE)
                self.tier_label.grid(row=r, column=0, columnspan=2, sticky="w", padx=16)
                r += 1
                continue
            col_frame = ttk.Frame(self, style="Card.TFrame")
            col_frame.grid(row=r, column=0, columnspan=2, sticky="w", padx=12)
            r += 1
            # alphabetical within each group for faster scanning
            for i, tag in enumerate(sorted(tags)):
                cell = ttk.Frame(col_frame, style="Card.TFrame")
                cell.grid(row=i // 3, column=i % 3, sticky="w", padx=4, pady=2)
                e_label = None
                icon = tag_icon(tag)          # colored PNG (preferred)
                if icon is not None:
                    e_label = ttk.Label(cell, image=icon,
                                         background=BG_CARD, cursor="hand2")
                    e_label.image = icon
                else:
                    emoji = TAG_EMOJI.get(tag)
                    if emoji and self.emoji_font:
                        e_label = ttk.Label(cell, text=emoji,
                                             font=(self.emoji_font, 10),
                                             background=BG_CARD, cursor="hand2")
                if e_label is not None:
                    e_label.pack(side="left")
                cb = ttk.Checkbutton(cell, text=tag, variable=self.vars[tag],
                                      command=lambda t=tag: self._on_toggle(t))
                cb.pack(side="left")
                if e_label is not None:
                    # clicking the emoji toggles the checkbox too
                    e_label.bind("<Button-1>", lambda _e, c=cb: c.invoke())

        # FR-analysis suggestion strip (populated by "Suggest from FR Data")
        r += 1
        self.fr_status = ttk.Label(self, text="", style="Card.TLabel",
                                    foreground=TEXT_DIM, wraplength=0,
                                    justify="left")
        self.fr_status.grid(row=r, column=0, columnspan=2, sticky="w", padx=8)
        r += 1
        self.fr_chips = ttk.Frame(self, style="Card.TFrame")
        self.fr_chips.grid(row=r, column=0, columnspan=2, sticky="w", padx=12,
                            pady=(2, 8))

    # -- FR suggestions ---------------------------------------------------
    def _run_fr_suggestions(self):
        if not self.fr_provider:
            return
        self.configure(cursor="watch")
        try:
            suggs, info = self.fr_provider()
        except ValueError as e:
            self.set_suggestions([], str(e))
            return
        except Exception as e:
            self.set_suggestions([], "FR analysis failed: {}".format(e))
            return
        finally:
            self.configure(cursor="")
        self.set_suggestions(suggs, info)

    def set_suggestions(self, suggestions, info_text):
        """Render clickable '+ Tag' chips for suggested tags not already
        selected. Chips respect all picker guardrails when applied."""
        self._suggestions = list(suggestions or [])
        for w in self.fr_chips.winfo_children():
            w.destroy()
        self.fr_status.configure(text=info_text)
        if not self._suggestions:
            return
        selected = self._selected_set()
        shown = 0
        base_text = info_text
        for s in self._suggestions:
            tag = s["tag"] if isinstance(s, dict) else s
            reason = s.get("reason", "") if isinstance(s, dict) else ""
            if tag in selected:
                continue
            icon = tag_icon(tag)
            kwargs = dict(text="+ {}".format(tag), cursor="hand2")
            if icon is not None:
                kwargs["image"] = icon
                kwargs["compound"] = "left"
            chip = ttk.Button(self.fr_chips, **kwargs)
            if icon is not None:
                chip.image = icon

            def _apply(t=tag):
                var = self.vars.get(t)
                if var is None:
                    return
                if not var.get():
                    var.set(True)
                    self._on_toggle(t)   # runs conflict/count guards
                self.set_suggestions(self._suggestions,
                                     self.fr_status.cget("text"))

            def _hover(_e, t=tag, r=reason):
                # keep it to one simple line
                self.fr_status.configure(
                    text="{} {}".format(t, "-- " + r if r else ""))

            def _leave(_e):
                self.fr_status.configure(text=base_text)

            chip.configure(command=_apply)
            chip.pack(side="left", padx=(0, 6), pady=2)
            chip.bind("<Enter>", _hover)
            chip.bind("<Leave>", _leave)
            shown += 1
        if shown == 0 and self._suggestions:
            self.fr_status.configure(
                text="{} -- all suggested tags already applied.".format(info_text))

    def clear_suggestions(self):
        self._suggestions = []
        for w in self.fr_chips.winfo_children():
            w.destroy()
        self.fr_status.configure(text="")

    def _on_toggle(self, tag):
        var = self.vars[tag]
        if var.get():
            # about to be checked -- validate
            selected = self._selected_set()
            selected.add(tag)
            # max count (tier tag added separately, doesn't count toward user cap issue much,
            # but count includes it since it's part of final tags -- reserve 1 slot for it)
            if len(selected) > L.MAX_TAGS - 1:
                var.set(False)
                messagebox.showwarning(
                    APP_TITLE,
                    "You can select at most {} tags (plus the automatic price tier tag).".format(
                        L.MAX_TAGS - 1))
                return
            conflicts = L.tag_conflicts(selected)
            if conflicts:
                var.set(False)
                other = [t for t in conflicts[0] if t != tag]
                messagebox.showwarning(
                    APP_TITLE,
                    "'{}' conflicts with '{}'. Uncheck the other tag first.".format(
                        tag, ", ".join(other) if other else "another selected tag"))
                return
        self._refresh_count()
        if self.on_change:
            self.on_change()

    def _selected_set(self):
        return {t for t, v in self.vars.items() if v.get()}

    def _refresh_count(self):
        n = len(self._selected_set()) + 1  # +1 for automatic price tier tag
        self.count_label.configure(text="{} / {} selected".format(n, L.MAX_TAGS))
        if n < L.MIN_TAGS:
            self.count_label.configure(foreground=ACCENT_RED)
        elif n > L.MAX_TAGS:
            self.count_label.configure(foreground=ACCENT_RED)
        else:
            self.count_label.configure(foreground=ACCENT_GREEN)

    def update_price(self, price_usd):
        self.current_price = price_usd
        tier = L.price_tier_for(price_usd)
        self._auto_tier_tag = tier
        ranges = {"Budget": "$0-99", "Mid-Tier": "$100-499",
                  "Premium": "$500-1499", "Flagship": "$1500+"}
        self.tier_label.configure(text="Auto: {} ({})".format(tier, ranges[tier]))
        self._refresh_count()

    def get_tags(self):
        tags = sorted(self._selected_set())
        tags.append(self._auto_tier_tag)
        return tags

    def set_tags(self, tags):
        tagset = set(tags or [])
        for tag, var in self.vars.items():
            var.set(tag in tagset and tag not in L.PRICE_TIER_TAGS)
        self._refresh_count()

    def clear(self):
        for var in self.vars.values():
            var.set(False)
        self._refresh_count()


# ---------------------------------------------------------------------------
# FILE LINKER PANEL
# ---------------------------------------------------------------------------
class FileLinkerPanel(ttk.Frame):
    def __init__(self, parent, get_data_root):
        super().__init__(parent, style="Card.TFrame")
        self.get_data_root = get_data_root
        self.linked = []
        self._all_files_cache = None
        self._cache_root = None

        ttk.Label(self, text="MEASUREMENT FILES (.txt)", style="CardHeader.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 4))

        ttk.Label(self, text="Available", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=8)
        ttk.Label(self, text="Linked to this entry", style="Card.TLabel").grid(row=1, column=2, sticky="w", padx=8)

        self.search_var = tk.StringVar()
        search = ttk.Entry(self, textvariable=self.search_var)
        search.grid(row=2, column=0, sticky="ew", padx=8)
        attach_entry_context_menu(search)
        self._search_debounce = None
        def _on_search_change(*a):
            if self._search_debounce:
                try:
                    self.after_cancel(self._search_debounce)
                except Exception:
                    pass
            self._search_debounce = self.after(150, self._refresh_available)
        self.search_var.trace_add("write", _on_search_change)

        avail_frame = ttk.Frame(self, style="Card.TFrame")
        avail_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=4)
        avail_frame.rowconfigure(0, weight=1)
        avail_frame.columnconfigure(0, weight=1)
        self.available_list = tk.Listbox(avail_frame, background=BG_INPUT, foreground=TEXT_MAIN,
                                          selectbackground=ACCENT_BLUE, selectmode="extended",
                                          height=6, exportselection=False)
        self.available_list.grid(row=0, column=0, sticky="nsew")
        avail_scroll = ttk.Scrollbar(avail_frame, orient="vertical",
                                      command=self.available_list.yview)
        avail_scroll.grid(row=0, column=1, sticky="ns")
        self.available_list.configure(yscrollcommand=avail_scroll.set)
        # Mouse wheel scrolls the list even without clicking into it first.
        self.available_list.bind("<MouseWheel>", self._on_mousewheel_available)
        self.available_list.bind("<Button-4>", self._on_mousewheel_available)
        self.available_list.bind("<Button-5>", self._on_mousewheel_available)

        btns = ttk.Frame(self, style="Card.TFrame")
        btns.grid(row=3, column=1, sticky="ns")
        ttk.Button(btns, text="Add >>", command=self._add_selected, width=8).pack(pady=4)
        ttk.Button(btns, text="<< Remove", command=self._remove_selected, width=8).pack(pady=4)
        ttk.Button(btns, text="Refresh", command=self._invalidate_cache, width=8).pack(pady=4)

        linked_frame = ttk.Frame(self, style="Card.TFrame")
        linked_frame.grid(row=3, column=2, sticky="nsew", padx=8, pady=4)
        linked_frame.rowconfigure(0, weight=1)
        linked_frame.columnconfigure(0, weight=1)
        self.linked_list = tk.Listbox(linked_frame, background=BG_INPUT, foreground=TEXT_MAIN,
                                       selectbackground=ACCENT_BLUE, selectmode="extended",
                                       height=6, exportselection=False)
        self.linked_list.grid(row=0, column=0, sticky="nsew")
        linked_scroll = ttk.Scrollbar(linked_frame, orient="vertical",
                                       command=self.linked_list.yview)
        linked_scroll.grid(row=0, column=1, sticky="ns")
        self.linked_list.configure(yscrollcommand=linked_scroll.set)
        self.linked_list.bind("<MouseWheel>", self._on_mousewheel_linked)
        self.linked_list.bind("<Button-4>", self._on_mousewheel_linked)
        self.linked_list.bind("<Button-5>", self._on_mousewheel_linked)

        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(2, weight=1)

        self.hint = ttk.Label(self, text="", style="Card.TLabel", foreground=TEXT_DIM,
                               wraplength=380)
        self.hint.grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))

    def _invalidate_cache(self):
        self._all_files_cache = None
        self._cache_root = None
        self._refresh_available()

    @staticmethod
    def _scroll_amount(event):
        # Windows/macOS send <MouseWheel> with event.delta (+/-120 per notch);
        # X11/Linux send <Button-4> (up) / <Button-5> (down) instead.
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        delta = getattr(event, "delta", 0)
        return -1 if delta > 0 else 1

    def _on_mousewheel_available(self, event):
        self.available_list.yview_scroll(self._scroll_amount(event), "units")
        return "break"

    def _on_mousewheel_linked(self, event):
        self.linked_list.yview_scroll(self._scroll_amount(event), "units")
        return "break"

    def _all_files(self):
        root = self.get_data_root()
        if not root:
            self.hint.configure(text="No data folder set. Use File > Set Data Folder... to browse for .txt measurement files.")
            return []
        if self._all_files_cache is not None and self._cache_root == root:
            return self._all_files_cache
        # If user selected the data folder itself, use it directly
        if os.path.basename(os.path.normpath(root)).lower() == "data" and os.path.isdir(root):
            data_dir = root
            base_root = os.path.dirname(root)
            # need to compute rel against base_root so paths stay data/...
            results = []
            for r, _, files in os.walk(data_dir):
                for fn in files:
                    if fn.lower().endswith(".txt"):
                        full = os.path.join(r, fn)
                        try:
                            rel = os.path.relpath(full, base_root).replace("\\", "/")
                        except ValueError:
                            rel = os.path.join("data", os.path.relpath(full, data_dir)).replace("\\", "/")
                        results.append(rel)
            results.sort()
            self._all_files_cache = results
            self._cache_root = root
            self.hint.configure(text="{} .txt files found under {} (selected data folder directly)".format(len(results), data_dir))
            return results
        data_dir = os.path.join(root, "data")
        results = []
        if os.path.isdir(data_dir):
            for r, _, files in os.walk(data_dir):
                for fn in files:
                    if fn.lower().endswith(".txt"):
                        full = os.path.join(r, fn)
                        try:
                            rel = os.path.relpath(full, root).replace("\\", "/")
                        except ValueError:
                            continue
                        results.append(rel)
        else:
            # hint if data subfolder missing
            self.hint.configure(text="No 'data' subfolder found under {}. Use File > Set Data Folder...".format(root))
            self._all_files_cache = []
            self._cache_root = root
            return []
        results.sort()
        self._all_files_cache = results
        self._cache_root = root
        self.hint.configure(text="{} .txt files found under {}".format(len(results), data_dir))
        return results

    def _refresh_available(self):
        query = self.search_var.get().strip().lower()
        self.available_list.delete(0, tk.END)
        linked_set = set(self.linked)
        all_files = self._all_files()
        # avoid re-fetch inside loop
        for rel in all_files:
            if rel in linked_set:
                continue
            if query and query not in rel.lower():
                continue
            self.available_list.insert(tk.END, rel)

    def _refresh_linked(self):
        self.linked_list.delete(0, tk.END)
        for rel in self.linked:
            self.linked_list.insert(tk.END, rel)

    def _add_selected(self):
        for i in self.available_list.curselection():
            rel = self.available_list.get(i)
            if rel not in self.linked:
                self.linked.append(rel)
        self._refresh_linked()
        self._refresh_available()

    def _remove_selected(self):
        for i in reversed(self.linked_list.curselection()):
            del self.linked[i]
        self._refresh_linked()
        self._refresh_available()

    def get_files(self):
        return list(self.linked)

    def set_files(self, files):
        self.linked = list(files or [])
        self._refresh_linked()
        self._refresh_available()

    def clear(self):
        self.set_files([])

    def refresh_root_changed(self):
        self._invalidate_cache()


# ---------------------------------------------------------------------------
# ICON DROPDOWN (readonly combobox replacement with images)
# ---------------------------------------------------------------------------
class IconCombobox(ttk.Frame):
    """A readonly dropdown that shows an icon next to every option.
    ttk.Combobox cannot render images, so this wraps a ttk.Menubutton whose
    menu entries use image+compound (tk menus support that natively).
    Behaves like the combobox it replaces: shares a StringVar, supports
    dynamic value lists and lock/disable."""

    def __init__(self, parent, values, icon_for, textvariable,
                 on_change=None, width=22, **kw):
        super().__init__(parent, style="Card.TFrame")
        self.icon_for = icon_for            # callable(value) -> PhotoImage|None
        self.textvariable = textvariable
        self.on_change = on_change
        self.values = []
        self._locked = False
        self.button = ttk.Menubutton(self, textvariable=textvariable,
                                      direction="flush", width=width)
        self.button.pack(fill="x")
        self.menu = tk.Menu(self.button, tearoff=0,
                            background=BG_CARD, foreground=TEXT_MAIN,
                            activebackground=BORDER_LIGHT,
                            activeforeground=TEXT_MAIN,
                            font=(pick_font_family(), 10))
        self.button.configure(menu=self.menu)
        self.set_values(values)

    def set_values(self, values):
        """Rebuild the dropdown list (keeps current selection if still valid)."""
        self.values = list(values)
        self.menu.delete(0, "end")
        for v in self.values:
            icon = self.icon_for(v)
            kwargs = dict(label=v, compound="left",
                          command=lambda vv=v: self._choose(vv))
            if icon is not None:
                kwargs["image"] = icon
            self.menu.add_command(**kwargs)
        if self.textvariable.get() not in self.values:
            self.textvariable.set(self.values[0] if self.values else "")

    def _choose(self, value):
        if self._locked:
            return
        if value != self.textvariable.get():
            self.textvariable.set(value)
            if self.on_change:
                self.on_change()

    def get(self):
        return self.textvariable.get()

    def set(self, value):
        if value in self.values:
            self.textvariable.set(value)

    def set_locked(self, locked):
        """Locked = selection visible but changing it is disallowed."""
        self._locked = locked
        state = "disabled" if locked else "normal"
        self.button.configure(state=state)

    def is_locked(self):
        return self._locked


# ---------------------------------------------------------------------------
# ENTRY EDITOR
# ---------------------------------------------------------------------------
class EntryEditor(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame")
        self.app = app
        self.original_id = None  # id of the entry currently loaded, for update-in-place
        self._build()

    def _build(self):
        font_family = pick_font_family()
        canvas = tk.Canvas(self, background=BG_MAIN, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        inner = ttk.Frame(canvas, style="TFrame")
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")

        def on_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure("inner", width=canvas.winfo_width())
        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_configure)

        def _wheel(event):
            # Only scroll editor canvas when event is on canvas
            # Use canvas binding instead of bind_all to avoid double-scroll
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
        canvas.bind("<MouseWheel>", _wheel)
        # Linux scroll
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        pad = dict(padx=10, pady=4)

        # ---- identity row ----
        card = ttk.Frame(inner, style="Card.TFrame")
        card.pack(fill="x", padx=10, pady=8)
        ttk.Label(card, text="IDENTITY", style="CardHeader.TLabel").grid(
            row=0, column=0, columnspan=6, sticky="w", padx=8, pady=(8, 4))

        ttk.Label(card, text="Brand*", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=8)
        self.brand_entry = AutocompleteEntry(card, self.app.brand_suggestions,
                                              on_change=self._on_identity_change,
                                              spell_checker=self.app.speller)
        self.brand_entry.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))

        ttk.Label(card, text="Model*", style="Card.TLabel").grid(row=1, column=1, sticky="w", padx=8)
        self.model_entry = AutocompleteEntry(card, self.app.model_suggestions,
                                              on_change=self._on_identity_change,
                                              spell_checker=self.app.speller)
        self.model_entry.grid(row=2, column=1, sticky="ew", padx=8, pady=(0, 6))

        ttk.Label(card, text="Variant", style="Card.TLabel").grid(row=1, column=2, sticky="w", padx=8)
        self.variant_entry = AutocompleteEntry(card, self.app.variant_suggestions,
                                                on_change=self._on_identity_change,
                                                spell_checker=self.app.speller)
        self.variant_entry.grid(row=2, column=2, sticky="ew", padx=8, pady=(0, 6))

        for c in range(3):
            card.columnconfigure(c, weight=1)

        ttk.Label(card, text="Auto-generated ID:", style="Card.TLabel", foreground=TEXT_DIM).grid(
            row=3, column=0, sticky="w", padx=8)
        self.id_var = tk.StringVar(value="")
        id_label = ttk.Label(card, textvariable=self.id_var, style="Card.TLabel",
                              foreground=ACCENT_GREEN, font=(font_family, 10, "bold"))
        id_label.grid(row=3, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        # ---- specs row ----
        specs = ttk.Frame(inner, style="Card.TFrame")
        specs.pack(fill="x", padx=10, pady=8)
        ttk.Label(specs, text="SPECIFICATIONS", style="CardHeader.TLabel").grid(
            row=0, column=0, columnspan=6, sticky="w", padx=8, pady=(8, 4))

        ttk.Label(specs, text="Year (0 = unknown)", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=8)
        self.year_var = tk.StringVar(value="0")
        year_entry = ttk.Entry(specs, textvariable=self.year_var, width=10)
        year_entry.grid(row=2, column=0, sticky="w", padx=8, pady=(0, 6))
        year_entry.bind("<FocusOut>", self._validate_year)
        attach_entry_context_menu(year_entry)

        ttk.Label(specs, text="Price (USD)", style="Card.TLabel").grid(row=1, column=1, sticky="w", padx=8)
        self.price_var = tk.StringVar(value="0")
        price_entry = ttk.Entry(specs, textvariable=self.price_var, width=10)
        price_entry.grid(row=2, column=1, sticky="w", padx=8, pady=(0, 6))
        price_entry.bind("<FocusOut>", self._validate_price)
        attach_entry_context_menu(price_entry)

        ttk.Label(specs, text="Impedance (Ω)", style="Card.TLabel").grid(row=1, column=2, sticky="w", padx=8)
        self.impedance_var = tk.StringVar(value="0")
        self.impedance_entry = ttk.Entry(specs, textvariable=self.impedance_var, width=10)
        self.impedance_entry.grid(row=2, column=2, sticky="w", padx=8, pady=(0, 6))
        attach_entry_context_menu(self.impedance_entry)

        ttk.Label(specs, text="Sensitivity (dB/mW)", style="Card.TLabel").grid(row=1, column=3, sticky="w", padx=8)
        self.sensitivity_var = tk.StringVar(value="0")
        self.sensitivity_entry = ttk.Entry(specs, textvariable=self.sensitivity_var, width=10)
        self.sensitivity_entry.grid(row=2, column=3, sticky="w", padx=8, pady=(0, 6))
        attach_entry_context_menu(self.sensitivity_entry)

        ttk.Label(specs, text="Form Factor", style="Card.TLabel").grid(row=1, column=4, sticky="w", padx=8)
        self.form_var = tk.StringVar(value=L.FORM_FACTORS[0])
        self.form_picker = IconCombobox(
            specs, L.FORM_FACTORS,
            lambda v: ICONS.get(L.FORM_FACTOR_ICON.get(v, "")),
            self.form_var, on_change=self._on_form_change, width=26)
        self.form_picker.grid(row=2, column=4, sticky="w", padx=8, pady=(0, 6))

        ttk.Label(specs, text="Connector", style="Card.TLabel").grid(row=1, column=5, sticky="w", padx=8)
        self.connector_var = tk.StringVar(value="")
        self.connector_picker = IconCombobox(
            specs, L.FORM_CONNECTOR_MAP[L.FORM_FACTORS[0]],
            lambda v: ICONS.get(L.CONNECTOR_ICON.get(v, "")),
            self.connector_var, width=16)
        self.connector_picker.grid(row=2, column=5, sticky="w", padx=8, pady=(0, 6))

        self.price_hint = ttk.Label(specs, text="", style="Card.TLabel", foreground=ACCENT_ORANGE)
        self.price_hint.grid(row=3, column=1, sticky="w", padx=8, pady=(0, 6))
        self.year_hint = ttk.Label(specs, text="", style="Card.TLabel", foreground=ACCENT_RED)
        self.year_hint.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 6))
        self.spec_hint = ttk.Label(specs, text="", style="Card.TLabel", foreground=ACCENT_ORANGE)
        self.spec_hint.grid(row=3, column=2, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        # ---- driver config ----
        self.driver_panel = DriverConfigPanel(inner)
        self.driver_panel.pack(fill="x", padx=10, pady=8)

        # ---- tags ----
        self.tag_panel = TagSelectorPanel(inner, fr_provider=self._fr_suggestions)
        self.tag_panel.pack(fill="x", padx=10, pady=8)

        # ---- files ----
        self.file_panel = FileLinkerPanel(inner, self.app.get_data_root)
        self.file_panel.pack(fill="x", padx=10, pady=8)

        # ---- action buttons ----
        actions = ttk.Frame(inner, style="TFrame")
        actions.pack(fill="x", padx=10, pady=(4, 20))
        ttk.Button(actions, text="Save Entry", style="Accent.TButton",
                   command=self._on_save).pack(side="left", padx=4)
        ttk.Button(actions, text="Clear / New", command=self.new_entry).pack(side="left", padx=4)
        self.validation_label = ttk.Label(actions, text="", style="TLabel", foreground=ACCENT_RED,
                                           wraplength=600)
        self.validation_label.pack(side="left", padx=12)

        self._on_form_change()

    # -- helpers -------------------------------------------------------
    def _on_identity_change(self, _value=None):
        brand = self.brand_entry.get()
        model = self.model_entry.get()
        variant = self.variant_entry.get()
        self.id_var.set(L.build_id(brand, model, variant) or "(fill in brand & model)")

    def _on_form_change(self, _event=None):
        ff = self.form_var.get()
        allowed = L.FORM_CONNECTOR_MAP.get(ff, L.CONNECTORS_ALL)
        self.connector_picker.set_values(allowed)
        if len(allowed) == 1:
            self.connector_var.set(allowed[0])
            self.connector_picker.set_locked(True)
        else:
            self.connector_picker.set_locked(False)
            if self.connector_var.get() not in allowed:
                self.connector_var.set("")
        # TWS lock note unchanged from feature #3 (below)
        # TWS entries carry no amp/DAC chain -> impedance/sensitivity are
        # meaningless and must be 0; lock the fields so a conflict can't
        # even be typed (mirrors the audit's "TWS Specs" rule).
        if ff == L.TWS_FORM_FACTOR:
            self.impedance_var.set("0")
            self.sensitivity_var.set("0")
            self.impedance_entry.configure(state="disabled")
            self.sensitivity_entry.configure(state="disabled")
            self.spec_hint.configure(
                text="Locked to 0: TWS earbuds have no wired out path.")
        else:
            self.impedance_entry.configure(state="normal")
            self.sensitivity_entry.configure(state="normal")
            self.spec_hint.configure(text="")

    def _validate_year(self, _event=None):
        raw = self.year_var.get().strip()
        if raw == "":
            raw = "0"
            self.year_var.set(raw)
        try:
            y = int(raw)
        except ValueError:
            self.year_hint.configure(text="Enter a valid 4-digit year (1950-{}) or 0 if unknown."
                                      .format(L.CURRENT_YEAR + 1))
            return
        if not L.is_valid_year(y):
            self.year_hint.configure(text="Enter a valid 4-digit year (1950-{}) or 0 if unknown."
                                      .format(L.CURRENT_YEAR + 1))
        else:
            self.year_hint.configure(text="")

    def _validate_price(self, _event=None):
        raw = self.price_var.get().strip()
        if raw == "":
            raw = "0"
        try:
            p = int(raw)
        except ValueError:
            self.price_hint.configure(text="Price must be a whole number.")
            return
        if p < 0:
            p = 0
        rounded = L.round_price_to_5(p)
        if rounded != p:
            self.price_var.set(str(rounded))
            self.price_hint.configure(text="Rounded to nearest $5: ${}".format(rounded))
        else:
            self.price_hint.configure(text="")
        self.tag_panel.update_price(rounded)

    # -- FR tag suggestions -------------------------------------------------
    def _fr_suggestions(self):
        """Analyze every linked measurement file and merge the results into
        voted tag suggestions + a one-line metrics summary. Raises ValueError
        with a friendly message when nothing usable is linked."""
        import fr_analysis as FA
        data_root = self.app.get_data_root()
        rel_files = self.file_panel.get_files()
        if not rel_files:
            raise ValueError("No measurement files linked to this entry yet.")
        if not data_root:
            raise ValueError("Set the data folder first (File > Set Data Folder).")

        votes = {}          # tag -> [votes, first_rank]
        metric_sums = {}
        ok_count = err_count = 0
        errors = []
        for i, rel in enumerate(rel_files):
            full = os.path.join(data_root, rel.replace("/", os.sep))
            try:
                pts = FA.parse_fr_file(full)
                res = FA.analyze_points(pts)
            except OSError:
                res = {"ok": False, "error": "file not found"}
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            if not res.get("ok"):
                err_count += 1
                errors.append("{} ({})".format(rel, res.get("error", "unreadable")))
                continue
            ok_count += 1
            for rank, s in enumerate(res["suggestions"]):
                tag = s["tag"]
                if tag in L.APPROVED_TAGS:      # never suggest unapproved tags
                    votes.setdefault(tag, [0, 100])
                    votes[tag][0] += 1
                    votes[tag][1] = min(votes[tag][1], rank)
            for k, v in res.get("metrics", {}).items():
                metric_sums.setdefault(k, []).append(v)

        if ok_count == 0:
            msg = "Could not analyze any linked file."
            if errors:
                msg += "\n" + "\n".join(errors[:4])
            raise ValueError(msg)

        need = max(1, math.ceil(ok_count / 2.0))
        ordered = sorted(votes.items(), key=lambda kv: (-kv[1][0], kv[1][1]))
        suggs = [{"tag": t, "reason": "voted by {}/{} file(s)".format(n, ok_count)}
                 for t, (n, _r) in ordered if n >= need]

        avg = {k: round(sum(vals) / len(vals), 1) for k, vals in metric_sums.items()}
        info = "FR vs 1 kHz:  {}   \u00b7   {} file(s) used".format(
            FA.summarize_metrics(avg), ok_count)
        if err_count:
            info += "   \u00b7   {} unreadable".format(err_count)
        return suggs, info

    # -- public API ------------------------------------------------------
    def new_entry(self):
        self.original_id = None
        self.brand_entry.set("")
        self.model_entry.set("")
        self.variant_entry.set("")
        self.id_var.set("(fill in brand & model)")
        self.year_var.set("0")
        self.price_var.set("0")
        self.impedance_var.set("0")
        self.sensitivity_var.set("0")
        self.form_var.set(L.FORM_FACTORS[0])
        self._on_form_change()
        self.driver_panel.clear()
        self.tag_panel.clear()
        self.tag_panel.update_price(0)
        self.file_panel.clear()
        self.tag_panel.clear_suggestions()
        self.validation_label.configure(text="")
        self.year_hint.configure(text="")
        self.price_hint.configure(text="")

    def load_entry(self, entry):
        self.original_id = entry.get("id")
        self.brand_entry.set(entry.get("brand", ""))
        self.model_entry.set(entry.get("model", ""))
        self.variant_entry.set(entry.get("variant", ""))
        self._on_identity_change()
        self.year_var.set(str(entry.get("year", 0)))
        self.price_var.set(str(entry.get("price_usd", 0)))
        self.impedance_var.set(str(entry.get("impedance", 0)))
        self.sensitivity_var.set(str(entry.get("sensitivity", 0)))
        ff = entry.get("form_factor") or L.FORM_FACTORS[0]
        self.form_var.set(ff)
        self._on_form_change()
        self.connector_var.set(entry.get("connector", ""))
        self.driver_panel.set(entry.get("driver_type", ""), entry.get("driver_config", ""))
        self.tag_panel.set_tags(entry.get("tags", []))
        self.tag_panel.update_price(entry.get("price_usd", 0))
        self.file_panel.set_files(entry.get("files", []))
        self.tag_panel.clear_suggestions()
        self.validation_label.configure(text="")
        self.year_hint.configure(text="")
        self.price_hint.configure(text="")

        # legacy-conflict warning: TWS entry still carrying non-zero specs.
        # The fields are locked & zeroed by _on_form_change above; saving the
        # entry (or running the audit's "TWS Specs" fix) clears it permanently.
        if entry.get("form_factor") == L.TWS_FORM_FACTOR:
            try:
                bad = [f for f, v in (("Impedance", entry.get("impedance", 0)),
                                      ("Sensitivity", entry.get("sensitivity", 0)))
                       if int(float(v or 0)) != 0]
            except (TypeError, ValueError):
                bad = ["Impedance/Sensitivity"]
            if bad:
                messagebox.showwarning(
                    APP_TITLE,
                    "{}: this TWS entry has {} set to a non-zero value.\n\n"
                    "Wireless earbuds have no wired out path (no DAC/amp chain), "
                    "so these must be 0. The fields have been locked and zeroed -- "
                    "click 'Save Entry' to fix it, or use Audit > Fix All "
                    "Auto-Fixable.".format(entry.get("id"), " and ".join(bad)))

    def build_entry_dict(self):
        try:
            year = int(self.year_var.get() or 0)
        except ValueError:
            year = -1
        try:
            price = int(self.price_var.get() or 0)
        except ValueError:
            price = -1
        try:
            impedance = int(self.impedance_var.get() or 0)
        except ValueError:
            impedance = -1
        try:
            sensitivity = int(self.sensitivity_var.get() or 0)
        except ValueError:
            sensitivity = -1
        dtype, dconfig = self.driver_panel.get()
        brand = self.brand_entry.get().strip()
        model = self.model_entry.get().strip()
        variant = self.variant_entry.get().strip()
        entry = {
            "id": L.build_id(brand, model, variant),
            "brand": brand,
            "model": model,
            "variant": variant,
            "year": year,
            "price_usd": price,
            "driver_type": dtype,
            "driver_config": dconfig,
            "impedance": impedance,
            "sensitivity": sensitivity,
            "connector": self.connector_var.get(),
            "form_factor": self.form_var.get(),
            "tags": self.tag_panel.get_tags(),
            "files": self.file_panel.get_files(),
        }
        return entry

    def _on_save(self):
        self._validate_year()
        self._validate_price()
        entry = self.build_entry_dict()
        errors = self.app.validate_and_commit(entry, self.original_id)
        if errors:
            self.validation_label.configure(text="Cannot save:\n- " + "\n- ".join(errors))
        else:
            self.validation_label.configure(text="")
            self.original_id = entry["id"]


# ---------------------------------------------------------------------------
# AUDIT PANEL
# ---------------------------------------------------------------------------
class AuditPanel(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame")
        self.app = app
        self.issues = []

        top = ttk.Frame(self, style="TFrame")
        top.pack(fill="x", padx=10, pady=8)
        ttk.Button(top, text="Run Full Audit", style="Accent.TButton",
                   command=self.app.run_audit).pack(side="left", padx=4)
        ttk.Button(top, text="Fix Selected", command=self._fix_selected).pack(side="left", padx=4)
        ttk.Button(top, text="Fix All Auto-Fixable", style="Blue.TButton",
                   command=self._fix_all).pack(side="left", padx=4)
        ttk.Button(top, text="Export Report...", command=self._export).pack(side="left", padx=4)
        self.summary_label = ttk.Label(top, text="No audit run yet.", style="TLabel")
        self.summary_label.pack(side="left", padx=16)

        columns = ("category", "entry", "message", "fixable")
        tree_frame = ttk.Frame(self, style="TFrame")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("category", text="Category")
        self.tree.heading("entry", text="Entry")
        self.tree.heading("message", text="Issue")
        self.tree.heading("fixable", text="Auto-fixable")
        self.tree.column("category", width=140, anchor="w")
        self.tree.column("entry", width=180, anchor="w")
        self.tree.column("message", width=520, anchor="w")
        self.tree.column("fixable", width=90, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        # Mouse wheel scrolls the audit list even without clicking into it first.
        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        self.tree.bind("<Button-4>", self._on_mousewheel)
        self.tree.bind("<Button-5>", self._on_mousewheel)

        self.tree.tag_configure("error", foreground=ACCENT_RED)
        self.tree.tag_configure("warning", foreground=ACCENT_ORANGE)
        self.tree.tag_configure("info", foreground=TEXT_DIM)

    def _on_mousewheel(self, event):
        # Windows/macOS send <MouseWheel> with event.delta (+/-120 per notch);
        # X11/Linux send <Button-4> (up) / <Button-5> (down) instead.
        if getattr(event, "num", None) == 4:
            amount = -1
        elif getattr(event, "num", None) == 5:
            amount = 1
        else:
            amount = -1 if getattr(event, "delta", 0) > 0 else 1
        self.tree.yview_scroll(amount, "units")
        return "break"

    def show_issues(self, issues):
        self.issues = issues
        self.tree.delete(*self.tree.get_children())
        for i, issue in enumerate(issues):
            self.tree.insert("", "end", iid=str(i), values=(
                issue.category, issue.entry_id, issue.message,
                "Yes" if issue.fix else "No"), tags=(issue.severity,))
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        infos = sum(1 for i in issues if i.severity == "info")
        self.summary_label.configure(
            text="{} issues found  ({} errors, {} warnings, {} info)".format(
                len(issues), errors, warnings, infos))

    def _fix_selected(self):
        sel = self.tree.selection()
        idxs = [int(s) for s in sel]
        self.app.apply_fixes([self.issues[i] for i in idxs if self.issues[i].fix])
        self.app.run_audit()

    def _fix_all(self):
        fixable = [i for i in self.issues if i.fix]
        if not fixable:
            messagebox.showinfo(APP_TITLE, "No auto-fixable issues found.")
            return
        if not messagebox.askyesno(APP_TITLE, "Apply {} automatic fixes?".format(len(fixable))):
            return
        self.app.apply_fixes(fixable)
        self.app.run_audit()

    def _export(self):
        if not self.issues:
            messagebox.showinfo(APP_TITLE, "Nothing to export. Run an audit first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text file", "*.txt")],
                                             initialfile="audit_report.txt")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write("IEM Database Audit Report - {}\n".format(datetime.datetime.now()))
            f.write("=" * 70 + "\n")
            for issue in self.issues:
                f.write("[{}] {} :: {} :: {}\n".format(
                    issue.severity.upper(), issue.category, issue.entry_id, issue.message))
        messagebox.showinfo(APP_TITLE, "Report saved to:\n{}".format(path))


# ---------------------------------------------------------------------------
# HISTORY PANEL (undo / redo)
# ---------------------------------------------------------------------------
class HistoryPanel(ttk.Frame):
    """Lists every tracked change newest-first with plain-language
    descriptions. Select any number of rows to undo or redo them."""

    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame")
        self.app = app

        top = ttk.Frame(self, style="TFrame")
        top.pack(fill="x", padx=10, pady=8)
        ttk.Button(top, text="Undo Selected", style="Accent.TButton",
                   command=self._undo_selected).pack(side="left", padx=4)
        ttk.Button(top, text="Redo Selected", style="Blue.TButton",
                   command=self._redo_selected).pack(side="left", padx=4)
        ttk.Button(top, text="Clear History",
                   command=self._clear).pack(side="left", padx=4)
        self.summary_label = ttk.Label(top, text="", style="TLabel", foreground=TEXT_DIM)
        self.summary_label.pack(side="left", padx=16)

        columns = ("time", "action", "details")
        frame = ttk.Frame(self, style="TFrame")
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = ttk.Treeview(frame, columns=columns, show="tree headings",
                                  selectmode="extended")
        self.tree.heading("#0", text="#")
        self.tree.column("#0", width=50, anchor="center", stretch=False)
        self.tree.heading("time", text="Time")
        self.tree.column("time", width=90, anchor="w", stretch=False)
        self.tree.heading("action", text="Action")
        self.tree.column("action", width=520, anchor="w")
        self.tree.heading("details", text="")
        self.tree.column("details", width=60, anchor="center", stretch=False)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        self.tree.bind("<Button-4>", self._on_mousewheel)
        self.tree.bind("<Button-5>", self._on_mousewheel)

        self.tree.tag_configure("section", background=BG_CARD,
                                 foreground=ACCENT_ORANGE,
                                 font=(pick_font_family(), 9, "bold"))
        self.tree.tag_configure("op", foreground=TEXT_MAIN)
        self.tree.tag_configure("redoable", foreground=ACCENT_BLUE)

    def _on_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            amount = -1
        elif getattr(event, "num", None) == 5:
            amount = 1
        else:
            amount = -1 if getattr(event, "delta", 0) > 0 else 1
        self.tree.yview_scroll(amount, "units")
        return "break"

    KIND_VERB = {"edit": "Edited entry", "add": "Added entry",
                 "delete": "Deleted entry", "fixes": "Audit fixes"}

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        app = self.app
        n_undo = len(app.history)
        n_redo = len(app.redo_stack)
        self.summary_label.configure(
            text="{} undoable operation(s), {} redoable".format(n_undo, n_redo))
        if not n_undo and not n_redo:
            self.tree.insert("", "end", iid="sec:none", text="",
                             values=(" ", "No changes yet this session.", ""),
                             tags=("section",))
            return
        # undoable ops, newest at the top
        self.tree.insert("", "end", iid="sec:undo", text="",
                         values=(" ", "UNDOABLE  (most recent first)", ""),
                         tags=("section",))
        for display_no, i in enumerate(range(len(app.history) - 1, -1, -1)):
            op = app.history[i]
            self.tree.insert("", "end", iid="h:{}".format(i),
                             text=str(display_no + 1),
                             values=(op["when"], op["desc"], "undo"),
                             tags=("op",))
        if n_redo:
            self.tree.insert("", "end", iid="sec:redo", text="",
                             values=(" ", "REDOABLE  (undone operations)", ""),
                             tags=("section",))
            for j, op in enumerate(app.redo_stack):
                self.tree.insert("", "end", iid="r:{}".format(j),
                                 text="-", values=(op["when"], op["desc"], "redo"),
                                 tags=("redoable",))

    def _selected_ops(self):
        """Returns (undo_ops_in_application_order, redo_ops_in_order)."""
        undo_idx, redo_idx = [], []
        for iid in self.tree.selection():
            if iid.startswith("h:"):
                undo_idx.append(int(iid.split(":", 1)[1]))
            elif iid.startswith("r:"):
                redo_idx.append(int(iid.split(":", 1)[1]))
        # undo applies newest-first; redo applies oldest-first
        undo_idx.sort(reverse=True)
        redo_idx.sort()
        hist = self.app.history
        red = self.app.redo_stack
        return ([hist[i] for i in undo_idx if 0 <= i < len(hist)],
                [red[i] for i in redo_idx if 0 <= i < len(red)])

    def _undo_selected(self):
        undo_ops, redo_ops = self._selected_ops()
        if redo_ops and not undo_ops:
            messagebox.showinfo(APP_TITLE, "Those rows are already undone -- "
                                            "use 'Redo Selected' instead.")
            return
        if not undo_ops:
            messagebox.showinfo(APP_TITLE, "Select one or more operations to undo.")
            return
        self.app.apply_history_ops(undo_ops, redo=False)
        self.refresh()

    def _redo_selected(self):
        undo_ops, redo_ops = self._selected_ops()
        if undo_ops and not redo_ops:
            messagebox.showinfo(APP_TITLE, "Those rows are not undone -- "
                                            "use 'Undo Selected' instead.")
            return
        if not redo_ops:
            messagebox.showinfo(APP_TITLE, "Select one or more undone "
                                           "operations to redo them.")
            return
        self.app.apply_history_ops(redo_ops, redo=True)
        self.refresh()

    def _clear(self):
        if not self.app.history and not self.app.redo_stack:
            return
        if messagebox.askyesno(APP_TITLE,
                               "Forget all recorded history?\n\nYour database "
                               "entries are NOT affected -- this only clears "
                               "the undo/redo list."):
            self.app.history.clear()
            self.app.redo_stack.clear()
            self.refresh()


# ---------------------------------------------------------------------------
# MAIN APPLICATION
# ---------------------------------------------------------------------------
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("{}  v{}".format(APP_TITLE, APP_VERSION))
        self._set_window_icon()
        self.geometry("1400x860")
        self.configure(background=BG_MAIN)
        setup_styles(self)

        self.entries = []
        self.db_path = None
        self.data_root = None
        self.dirty = False
        self.editing_index = None  # index into self.entries currently loaded in editor, or None for "new"

        # undo/redo history (chronological ops; redo holds undone ops)
        self.history = []          # applied ops, oldest first
        self.redo_stack = []       # undone ops, in undo order
        self.HISTORY_MAX = 200     # cap so memory stays bounded

        # offline spellchecker for the identity fields; dictionaries load in
        # a background thread so startup is never blocked
        self.speller = SP.SpellChecker(resource_base)
        self.speller.load_async()

        self._build_menu()
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._try_auto_load()

    def refresh_spell_vocab(self):
        """Feed every Brand/Model/Variant in the loaded database to the
        spellchecker so product names are never flagged as typos."""
        texts = []
        for e in self.entries:
            texts.extend([e.get("brand", ""), e.get("model", ""), e.get("variant", "")])
        self.speller.replace_dynamic_vocab(texts)

    def _autosave(self):
        """Write a crash-recovery snapshot next to the database. Never
        blocks or interrupts editing -- failures are printed and ignored."""
        if not self.entries or not self.db_path:
            return
        try:
            L.write_autosave(self.db_path, self.entries)
        except Exception as e:
            print("Autosave failed: {}".format(e))

    # ------------------------------------------------------------------
    # HISTORY / UNDO / REDO
    # ------------------------------------------------------------------
    @staticmethod
    def _deepcopy(entry):
        import copy
        return copy.deepcopy(entry) if entry is not None else None

    def _record_op(self, kind, desc, changes):
        """Store one completed mutation for the History tab.
        changes: list of {pos_hint, ref_before, copy_before,
                          ref_after,  copy_after} dicts (see _apply_history_op).
        """
        op = {
            "kind": kind,
            "desc": desc,
            "when": datetime.datetime.now().strftime("%H:%M:%S"),
            "changes": changes,
        }
        self.history.append(op)
        if len(self.history) > self.HISTORY_MAX:
            self.history = self.history[-self.HISTORY_MAX:]
        self.redo_stack.clear()   # new work invalidates the redo branch
        if self.history_panel is not None:
            self.history_panel.refresh()

    def _find_slot(self, target_ref, target_copy):
        """Locate an entry's current list position: object identity first,
        then id-field equality as a fallback (survives sorting)."""
        if target_ref is not None:
            for i, e in enumerate(self.entries):
                if e is target_ref:
                    return i
        tid = (target_copy or {}).get("id")
        if tid:
            for i, e in enumerate(self.entries):
                if e.get("id") == tid:
                    return i
        return -1

    def _apply_history_changes(self, op, redo):
        """Apply (or revert) every sub-change of `op` in place.

        Each change stores the transition ref_before -> ref_after (either
        side may be None for add/delete). Undoing walks it backwards,
        redoing forwards:
          - transition INTO nothing  -> remove the located entry
          - transition OUT of nothing-> insert a fresh copy
          - otherwise                -> replace content at its position
        Returns the set of affected list positions. Unresolvable
        sub-changes are skipped (history is convenience, not a ledger)."""
        affected = set()
        changes = op["changes"]
        # within one batch, invert order when reverting
        for ch in (changes if redo else reversed(changes)):
            pos_hint = ch["pos_hint"]
            if redo:
                out_of, into, insert_copy = ch["ref_before"], ch["ref_after"], ch["copy_after"]
            else:
                out_of, into, insert_copy = ch["ref_after"], ch["ref_before"], ch["copy_before"]

            if into is None:
                # ends without an entry -> removal
                pos = self._find_slot(out_of, ch["copy_before" if redo else "copy_after"])
                if 0 <= pos < len(self.entries):
                    del self.entries[pos]
                    affected.add(pos)
            elif out_of is None:
                # starts from nothing -> insertion
                pos = max(0, min(pos_hint, len(self.entries)))
                self.entries.insert(pos, self._deepcopy(insert_copy))
                affected.add(pos)
            else:
                # content replacement
                pos = self._find_slot(out_of, ch["copy_before" if redo else "copy_after"])
                if pos >= 0:
                    self.entries[pos] = self._deepcopy(insert_copy)
                    affected.add(pos)
        return affected

    def apply_history_ops(self, ops, redo):
        """Undo (redo=False) or redo (redo=True) a list of ops. Ops must be
        given in application order: newest-first for undo, oldest-first
        for redo."""
        # remember which entry the editor is holding so we can re-locate it
        # after index shifts caused by insertions/deletions
        prev_ref = None
        if self.editing_index is not None and 0 <= self.editing_index < len(self.entries):
            prev_ref = self.entries[self.editing_index]

        all_affected = set()
        for op in ops:
            try:
                all_affected |= self._apply_history_changes(op, redo)
            except Exception as e:
                print("History {} failed: {}".format("redo" if redo else "undo", e))
            if redo:
                self.redo_stack.remove(op)
                self.history.append(op)
            else:
                self.history.remove(op)
                self.redo_stack.append(op)
        if all_affected:
            self.dirty = True
            self.populate_tree()
            new_idx = self._find_slot(prev_ref, prev_ref) if prev_ref is not None else -1
            if prev_ref is not None and new_idx >= 0:
                self.editing_index = new_idx
                self.editor.load_entry(self.entries[new_idx])
            else:
                self.editing_index = None
                self.editor.new_entry()
            self.editor.file_panel._refresh_available()
            self._autosave()
        verb = "Redid" if redo else "Undid"
        self.status_var.set("{} {} operation(s).".format(verb, len(ops)))
        if self.history_panel is not None:
            self.history_panel.refresh()

    def undo_last(self):
        if not self.history:
            messagebox.showinfo(APP_TITLE, "Nothing to undo yet.")
            return
        self.apply_history_ops([self.history[-1]], redo=False)

    def redo_last(self):
        if not self.redo_stack:
            messagebox.showinfo(APP_TITLE, "Nothing to redo.")
            return
        self.apply_history_ops([self.redo_stack[-1]], redo=True)

    # ------------------------------------------------------------------
    def _set_window_icon(self):
        """Use assets/icon.ico for the window/taskbar icon if present.
        This only affects the icon while the app is running from source
        or from a PyInstaller-built exe that wasn't given --icon; when
        built with --icon=assets/icon.ico (see README), Windows also
        uses it for the .exe file icon itself."""
        ico_path = os.path.join(resource_base(), "assets", "icon.ico")
        if os.path.isfile(ico_path):
            try:
                self.iconbitmap(default=ico_path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open Database...", command=self.open_database)
        filemenu.add_command(label="Set Data Folder...", command=self.set_data_folder)
        filemenu.add_separator()
        filemenu.add_command(label="Save As...", command=self.save_as)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = tk.Menu(menubar, tearoff=0)
        editmenu.add_command(label="Add New Entry", command=self.add_entry)
        editmenu.add_command(label="Delete Selected Entry", command=self.delete_entry)
        editmenu.add_separator()
        editmenu.add_command(label="Undo Last Action", command=self.undo_last)
        editmenu.add_command(label="Redo Last Undone Action", command=self.redo_last)
        menubar.add_cascade(label="Edit", menu=editmenu)

        auditmenu = tk.Menu(menubar, tearoff=0)
        auditmenu.add_command(label="Run Full Audit", command=self.run_audit)
        menubar.add_cascade(label="Audit", menu=auditmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)
        self.config(menu=menubar)

    def _build_layout(self):
        toolbar = ttk.Frame(self, style="Panel.TFrame")
        toolbar.pack(fill="x", side="top")
        ttk.Button(toolbar, text="Open Database", command=self.open_database).pack(side="left", padx=4, pady=6)
        ttk.Button(toolbar, text="Save As...", style="Accent.TButton", command=self.save_as).pack(side="left", padx=4, pady=6)
        ttk.Button(toolbar, text="Add Entry", command=self.add_entry).pack(side="left", padx=4, pady=6)
        ttk.Button(toolbar, text="Delete Entry", style="Danger.TButton", command=self.delete_entry).pack(side="left", padx=4, pady=6)
        ttk.Button(toolbar, text="Run Audit", style="Blue.TButton", command=self.run_audit).pack(side="left", padx=4, pady=6)

        ttk.Label(toolbar, text="Search:", style="Panel.TLabel").pack(side="left", padx=(20, 4))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=4)
        attach_entry_context_menu(search_entry)
        self._search_debounce_id = None
        def _on_search_change(*a):
            if self._search_debounce_id:
                try:
                    self.after_cancel(self._search_debounce_id)
                except Exception:
                    pass
            self._search_debounce_id = self.after(150, self.populate_tree)
        self.search_var.trace_add("write", _on_search_change)

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, style="Panel.TFrame")
        paned.add(left, weight=1)

        ttk.Label(left, text="DATABASE ENTRIES", style="Header.TLabel").pack(anchor="w", padx=8, pady=(8, 4))
        tree_frame = ttk.Frame(left, style="Panel.TFrame")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(paned, style="TFrame")
        paned.add(right, weight=3)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self.editor = EntryEditor(self.notebook, self)
        self.notebook.add(self.editor, text="  Editor  ")

        self.audit_panel = AuditPanel(self.notebook, self)
        self.notebook.add(self.audit_panel, text="  Audit  ")

        self.history_panel = None   # created just below, before any op recording
        self.history_panel = HistoryPanel(self.notebook, self)
        self.notebook.add(self.history_panel, text="  History  ")

        status = ttk.Frame(self, style="Panel.TFrame")
        status.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="No database loaded.")
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").pack(side="left", padx=8, pady=4)

    def _show_about(self):
        messagebox.showinfo(
            APP_TITLE,
            "{} v{}\n\nA standalone editor/auditor for the IEM & headphone "
            "measurement database.\nEntries are never saved over the original "
            "file -- always as a new file.".format(APP_TITLE, APP_VERSION))

    def _on_close(self):
        if self.dirty:
            resp = messagebox.askyesnocancel(
                APP_TITLE,
                "You have unsaved changes. Save before exiting?\n\nYes = Save As..., No = Exit without saving, Cancel = Stay.")
            if resp is None:
                return
            if resp:
                self.save_as()
                # if still dirty after save attempt, stay
                if self.dirty:
                    return
        self.destroy()

    # ------------------------------------------------------------------
    # LOADING / SAVING
    # ------------------------------------------------------------------
    def _try_auto_load(self):
        # Try multiple candidate locations: next to exe/script, parent folder, cwd
        candidates = [
            os.path.join(script_folder(), "database.json"),
            os.path.join(os.path.dirname(script_folder()), "database.json"),
            os.path.join(os.getcwd(), "database.json"),
        ]
        seen = set()
        for candidate in candidates:
            norm = os.path.normpath(candidate)
            if norm in seen:
                continue
            seen.add(norm)
            if os.path.isfile(candidate):
                self._load_from_path(candidate)
                return

    def open_database(self):
        path = filedialog.askopenfilename(
            title="Select database.json",
            filetypes=[("JSON database", "*.json"), ("All files", "*.*")])
        if not path:
            return
        self._load_from_path(path)

    def _load_from_path(self, path):
        # crash-recovery: offer the newest unseen autosave snapshot first
        load_from = path
        restored = False
        recovery = L.unseen_autosave(path)
        if recovery:
            try:
                stamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(recovery)).strftime("%Y-%m-%d %H:%M:%S")
            except OSError:
                stamp = "unknown time"
            resp = messagebox.askyesnocancel(
                APP_TITLE,
                "A more recent autosaved recovery file was found:\n\n"
                "{}\n(saved {})\n\n"
                "Yes = Load the recovery file\n"
                "No = Continue with the selected database\n"
                "Cancel = Don't ask again about this backup".format(
                    os.path.basename(recovery), stamp))
            L.mark_autosave_seen(path)
            if resp:
                load_from = recovery
                restored = True
        try:
            entries, notes = L.load_database(load_from)
        except L.DatabaseLoadError as e:
            messagebox.showerror(APP_TITLE, "Failed to load database:\n\n{}".format(e))
            return
        except Exception as e:
            messagebox.showerror(APP_TITLE, "Unexpected error loading database:\n\n{}".format(e))
            return
        self.entries = entries
        self.db_path = path
        self.data_root = os.path.dirname(os.path.abspath(path))
        self.dirty = False
        self.editing_index = None
        self.editor.new_entry()
        self.refresh_spell_vocab()
        self.file_panel_root_changed()
        self.populate_tree()
        msg = "Loaded {} entries from {}{}".format(
            len(entries), path,
            "  (RECOVERED from autosave backup -- use Save As to keep it)" if restored else "")
        if notes:
            msg += "  ({} note(s))".format(len(notes))
            for n in notes:
                print(n)
            # show first few notes in dialog
            preview = "\n".join(notes[:10])
            if len(notes) > 10:
                preview += "\n... and {} more (see console)".format(len(notes)-10)
            messagebox.showwarning(APP_TITLE, "Notes while loading:\n\n" + preview)
        self.status_var.set(msg)
        # run audit (may be heavy) without blocking
        try:
            issues = L.run_full_audit(self.entries, self.data_root)
        except Exception as e:
            messagebox.showwarning(APP_TITLE, "Audit failed:\n{}".format(e))
            issues = []
        self.audit_panel.show_issues(issues)
        if issues:
            messagebox.showinfo(
                APP_TITLE,
                "Database loaded.\n\nThe automatic audit found {} item(s) to review "
                "in the Audit tab.".format(len(issues)))

    def set_data_folder(self):
        path = filedialog.askdirectory(title="Select the folder that contains the 'data' subfolder")
        if not path:
            return
        # Validate: allow either the parent of data/ or data/ itself
        norm = os.path.normpath(path)
        base = os.path.basename(norm).lower()
        data_candidate = os.path.join(path, "data") if base != "data" else path
        if not os.path.isdir(data_candidate):
            # try parent case where user selected data folder directly - already handled
            # otherwise warn
            if base != "data":
                resp = messagebox.askyesno(APP_TITLE,
                    "No 'data' subfolder found under:\n{}\n\nUse this folder anyway?".format(path))
                if not resp:
                    return
        # If user selected .../data, normalize to parent so audit uses parent as root
        if base == "data":
            # store parent as data_root so relative paths stay data/...
            self.data_root = os.path.dirname(norm)
        else:
            self.data_root = path
        self.file_panel_root_changed()
        self.status_var.set("Data folder set to: {}".format(self.data_root))

    def file_panel_root_changed(self):
        self.editor.file_panel.refresh_root_changed()

    def get_data_root(self):
        return self.data_root

    def save_as(self):
        if not self.entries:
            messagebox.showwarning(APP_TITLE, "Nothing to save -- no database loaded.")
            return
        try:
            issues = L.run_full_audit(self.entries, self.data_root)
        except Exception as e:
            messagebox.showwarning(APP_TITLE, "Audit failed before save:\n{}".format(e))
            issues = []
        blocking = [i for i in issues if i.severity == "error"]
        dup_ids = {}
        for idx, e in enumerate(self.entries):
            dup_ids.setdefault(e.get("id"), []).append(idx)
        dup_msgs = ["Duplicate ID '{}' used {} times.".format(k, len(v))
                    for k, v in dup_ids.items() if len(v) > 1]
        if dup_msgs:
            messagebox.showerror(APP_TITLE, "Cannot save -- fix these first:\n\n" + "\n".join(dup_msgs))
            return
        if blocking:
            proceed = messagebox.askyesno(
                APP_TITLE,
                "The audit found {} error-level issue(s) (see Audit tab).\n"
                "Save anyway?".format(len(blocking)))
            if not proceed:
                return
        initial = "database_edited.json"
        if self.db_path:
            base = os.path.splitext(os.path.basename(self.db_path))[0]
            initial = "{}_edited.json".format(base)
        path = filedialog.asksaveasfilename(
            title="Save database as...", defaultextension=".json",
            filetypes=[("JSON database", "*.json")], initialfile=initial,
            initialdir=self.data_root or ".")
        if not path:
            return
        # case-insensitive compare on Windows, normalize path
        if self.db_path and os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(self.db_path)):
            messagebox.showerror(
                APP_TITLE,
                "For safety, you cannot overwrite the original database file.\n"
                "Please choose a different file name.")
            return
        try:
            # Remember currently edited id to restore selection after sort
            current_id = None
            if self.editing_index is not None and 0 <= self.editing_index < len(self.entries):
                current_id = self.entries[self.editing_index].get("id")
            ordered = L.save_database(path, self.entries)
        except OSError as e:
            messagebox.showerror(APP_TITLE, "Failed to save:\n{}".format(e))
            return
        except Exception as e:
            messagebox.showerror(APP_TITLE, "Unexpected error while saving:\n{}".format(e))
            return
        self.entries = ordered
        self.dirty = False
        # re-map editing_index to new sorted position
        if current_id:
            for i, e in enumerate(self.entries):
                if e.get("id") == current_id:
                    self.editing_index = i
                    break
            else:
                self.editing_index = None
        self.populate_tree()
        # re-select after sort
        if self.editing_index is not None:
            iid = "entry:{}".format(self.editing_index)
            try:
                self.tree.selection_set(iid)
                self.tree.see(iid)
            except Exception:
                pass
        self.status_var.set("Saved {} entries to {}".format(len(ordered), path))
        messagebox.showinfo(APP_TITLE, "Saved as:\n{}".format(path))

    # ------------------------------------------------------------------
    # TREE / SELECTION
    # ------------------------------------------------------------------
    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        query = self.search_var.get().strip().lower()
        by_brand = {}
        for idx, e in enumerate(self.entries):
            hay = " ".join([e.get("brand", ""), e.get("model", ""), e.get("variant", ""), e.get("id", "")]).lower()
            if query and query not in hay:
                continue
            by_brand.setdefault(e.get("brand", "(no brand)"), []).append(idx)
        for brand in sorted(by_brand.keys(), key=str.lower):
            idxs = by_brand[brand]
            node = self.tree.insert("", "end", iid="brand:{}".format(brand),
                                     text="{}  ({})".format(brand, len(idxs)), open=bool(query))
            for idx in sorted(idxs, key=lambda i: L.sort_key(self.entries[i])):
                e = self.entries[idx]
                label = e.get("model", "")
                if e.get("variant"):
                    label += "  [{}]".format(e["variant"])
                label += "   -- {}".format(e.get("id", ""))
                self.tree.insert(node, "end", iid="entry:{}".format(idx), text=label)

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("entry:"):
            idx = int(iid.split(":", 1)[1])
            self.editing_index = idx
            self.editor.load_entry(self.entries[idx])
            self.notebook.select(self.editor)

    # ------------------------------------------------------------------
    # ADD / DELETE / COMMIT
    # ------------------------------------------------------------------
    def add_entry(self):
        self.editing_index = None
        self.editor.new_entry()
        self.notebook.select(self.editor)
        self.tree.selection_remove(self.tree.selection())

    def delete_entry(self):
        sel = self.tree.selection()
        if not sel or not sel[0].startswith("entry:"):
            messagebox.showinfo(APP_TITLE, "Select an entry in the tree to delete.")
            return
        idx = int(sel[0].split(":", 1)[1])
        e = self.entries[idx]
        if not messagebox.askyesno(APP_TITLE, "Delete entry '{}'?".format(e.get("id"))):
            return
        del self.entries[idx]
        self.dirty = True
        self.editing_index = None
        self.editor.new_entry()
        self.populate_tree()
        self.status_var.set("Deleted entry '{}'. {} entries remain (unsaved).".format(e.get("id"), len(self.entries)))
        self._record_op("delete", "Deleted entry '{}' ({} {})".format(
            e.get("id"), e.get("brand", ""), e.get("model", "")), [{
            "pos_hint": idx,
            "ref_before": e, "copy_before": self._deepcopy(e),
            "ref_after": None, "copy_after": None,
        }])
        self._autosave()

    def validate_and_commit(self, entry, original_id):
        existing_ids = {e.get("id") for i, e in enumerate(self.entries)
                         if self.editing_index is None or i != self.editing_index}
        errors = L.validate_entry(entry, existing_ids=existing_ids, exclude_id=None)
        if errors:
            return errors
        clean = L.build_clean_entry(entry)
        if self.editing_index is not None:
            idx = self.editing_index
            old_obj = self.entries[idx]
            old_copy = self._deepcopy(old_obj)
            self.entries[idx] = clean
            detail = L.describe_entry_change(old_copy, clean)
            desc = "Edited '{}'{}".format(clean["id"],
                                          " -- {}".format(detail) if detail else "")
            self._record_op("edit", desc, [{
                "pos_hint": idx,
                "ref_before": old_obj, "copy_before": old_copy,
                "ref_after": clean, "copy_after": self._deepcopy(clean),
            }])
        else:
            self.entries.append(clean)
            self.editing_index = len(self.entries) - 1
            self._record_op("add", "Added entry '{}' ({} {})".format(
                clean["id"], clean.get("brand", ""), clean.get("model", "")), [{
                "pos_hint": self.editing_index,
                "ref_before": None, "copy_before": None,
                "ref_after": clean, "copy_after": self._deepcopy(clean),
            }])
        # newly saved names become known vocabulary immediately
        for key in ("brand", "model", "variant"):
            if clean.get(key):
                self.speller.add_vocab(clean[key])
        self.dirty = True
        self.populate_tree()
        self.status_var.set("Saved entry '{}' ({} total entries, unsaved changes).".format(
            clean["id"], len(self.entries)))
        self._autosave()
        # re-select it in the tree
        iid = "entry:{}".format(self.editing_index)
        try:
            self.tree.selection_set(iid)
            self.tree.see(iid)
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------
    def run_audit(self):
        if not self.entries:
            messagebox.showinfo(APP_TITLE, "No database loaded.")
            return
        # For small DBs run synchronously to keep simple; for large DBs use thread
        # Threshold ~2000 entries or when data_root has many files
        if len(self.entries) < 5000 and not self.data_root:
            issues = L.run_full_audit(self.entries, self.data_root)
            self.audit_panel.show_issues(issues)
            self.notebook.select(self.audit_panel)
            return
        # threaded audit to avoid freezing UI
        self.status_var.set("Running audit...")
        self.notebook.select(self.audit_panel)
        def _do():
            try:
                issues = L.run_full_audit(self.entries, self.data_root)
            except Exception as e:
                issues = []
                err_msg = str(e)
                def _err():
                    messagebox.showwarning(APP_TITLE, "Audit failed:\n{}".format(err_msg))
                self.after(0, _err)
            def _done():
                self.audit_panel.show_issues(issues)
                self.status_var.set("Audit complete: {} issues".format(len(issues)))
            self.after(0, _done)
        threading.Thread(target=_do, daemon=True).start()

    def apply_fixes(self, issues):
        fixable = [i for i in issues if i.fix]
        if not fixable:
            return
        # capture every entry about to be mutated so the batch is undoable
        idxs = sorted({i.entry_index for i in fixable
                       if isinstance(i.entry_index, int)
                       and 0 <= i.entry_index < len(self.entries)})
        before_copies = {i: self._deepcopy(self.entries[i]) for i in idxs}
        for issue in fixable:
            issue.fix(self.entries)
        changes = []
        for i in idxs:
            obj = self.entries[i]   # same object -- fixes mutate in place
            changes.append({
                "pos_hint": i,
                "ref_before": obj, "copy_before": before_copies[i],
                "ref_after": obj, "copy_after": self._deepcopy(obj),
            })
        n_entries = len(idxs)
        desc = "Applied {} audit fix(es) across {} entr{}".format(
            len(fixable), n_entries, "y" if n_entries == 1 else "ies")
        self._record_op("fixes", desc, changes)
        self.dirty = True
        self.populate_tree()
        self.status_var.set("Applied {} fix(es). Remember to Save As to keep them.".format(len(fixable)))
        self._autosave()

    # ------------------------------------------------------------------
    # AUTOCOMPLETE SUGGESTION PROVIDERS
    # ------------------------------------------------------------------
    def brand_suggestions(self, text):
        text = text.lower()
        seen = []
        for e in self.entries:
            b = e.get("brand", "")
            if b and text in b.lower() and b not in seen:
                seen.append(b)
        return sorted(seen, key=str.lower)

    def model_suggestions(self, text):
        text = text.lower()
        brand = self.editor.brand_entry.get().strip().lower() if hasattr(self, "editor") else ""
        matches, all_matches = [], []
        for e in self.entries:
            m = e.get("model", "")
            if not m:
                continue
            if text in m.lower():
                all_matches.append(m)
                if brand and e.get("brand", "").lower() == brand:
                    matches.append(m)
        pool = matches if matches else all_matches
        seen = sorted(set(pool), key=str.lower)
        return seen

    def variant_suggestions(self, text):
        text = text.lower()
        seen = set()
        for e in self.entries:
            v = e.get("variant", "")
            if v and text in v.lower():
                seen.add(v)
        return sorted(seen, key=str.lower)


def main():
    app = MainApp()
    app.mainloop()


if __name__ == "__main__":
    main()
