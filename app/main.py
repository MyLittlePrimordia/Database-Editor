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
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import db_logic as L

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
    return font_family


# ---------------------------------------------------------------------------
# AUTOCOMPLETE ENTRY WIDGET
# ---------------------------------------------------------------------------
class AutocompleteEntry(ttk.Frame):
    """A ttk.Entry with a filtered dropdown suggestion popup."""

    def __init__(self, parent, suggestions_provider, on_change=None, **kwargs):
        super().__init__(parent, style="Card.TFrame")
        self.suggestions_provider = suggestions_provider  # callable(text) -> list[str]
        self.on_change = on_change
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, **kwargs)
        self.entry.pack(fill="x")
        self.popup = None
        self.listbox = None
        self._suppress = False

        self.var.trace_add("write", self._on_var_write)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Escape>", lambda e: self._hide_popup())
        self.entry.bind("<Down>", self._focus_listbox)
        self.entry.bind("<Return>", self._on_return)

    def get(self):
        return self.var.get()

    def set(self, value):
        self._suppress = True
        self.var.set(value or "")
        self._suppress = False

    def _on_var_write(self, *_):
        if self._suppress:
            return
        if self.on_change:
            self.on_change(self.var.get())
        self._update_popup()

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
    def __init__(self, parent, on_change=None):
        super().__init__(parent, style="Card.TFrame")
        self.on_change = on_change
        self.vars = {tag: tk.BooleanVar(value=False) for tag in L.APPROVED_TAGS}
        self.current_price = 0
        self._auto_tier_tag = "Budget"

        ttk.Label(self, text="TAGS  (pick 4–12 total)", style="CardHeader.TLabel").grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        self.count_label = ttk.Label(self, text="0 / 12 selected", style="Card.TLabel",
                                      foreground=TEXT_DIM)
        self.count_label.grid(row=0, column=1, sticky="e", padx=8)

        r = 1
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
            for i, tag in enumerate(tags):
                cb = ttk.Checkbutton(col_frame, text=tag_label(tag), variable=self.vars[tag],
                                      command=lambda t=tag: self._on_toggle(t))
                cb.grid(row=i // 3, column=i % 3, sticky="w", padx=4, pady=2)

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
        self.brand_entry = AutocompleteEntry(card, self.app.brand_suggestions, on_change=self._on_identity_change)
        self.brand_entry.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))

        ttk.Label(card, text="Model*", style="Card.TLabel").grid(row=1, column=1, sticky="w", padx=8)
        self.model_entry = AutocompleteEntry(card, self.app.model_suggestions, on_change=self._on_identity_change)
        self.model_entry.grid(row=2, column=1, sticky="ew", padx=8, pady=(0, 6))

        ttk.Label(card, text="Variant", style="Card.TLabel").grid(row=1, column=2, sticky="w", padx=8)
        self.variant_entry = AutocompleteEntry(card, self.app.variant_suggestions, on_change=self._on_identity_change)
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

        ttk.Label(specs, text="Price (USD)", style="Card.TLabel").grid(row=1, column=1, sticky="w", padx=8)
        self.price_var = tk.StringVar(value="0")
        price_entry = ttk.Entry(specs, textvariable=self.price_var, width=10)
        price_entry.grid(row=2, column=1, sticky="w", padx=8, pady=(0, 6))
        price_entry.bind("<FocusOut>", self._validate_price)

        ttk.Label(specs, text="Impedance (Ω)", style="Card.TLabel").grid(row=1, column=2, sticky="w", padx=8)
        self.impedance_var = tk.StringVar(value="0")
        ttk.Entry(specs, textvariable=self.impedance_var, width=10).grid(row=2, column=2, sticky="w", padx=8, pady=(0, 6))

        ttk.Label(specs, text="Sensitivity (dB/mW)", style="Card.TLabel").grid(row=1, column=3, sticky="w", padx=8)
        self.sensitivity_var = tk.StringVar(value="0")
        ttk.Entry(specs, textvariable=self.sensitivity_var, width=10).grid(row=2, column=3, sticky="w", padx=8, pady=(0, 6))

        ttk.Label(specs, text="Form Factor", style="Card.TLabel").grid(row=1, column=4, sticky="w", padx=8)
        self.form_var = tk.StringVar(value=L.FORM_FACTORS[0])
        form_combo = ttk.Combobox(specs, textvariable=self.form_var, values=L.FORM_FACTORS,
                                   state="readonly", width=26)
        form_combo.grid(row=2, column=4, sticky="w", padx=8, pady=(0, 6))
        form_combo.bind("<<ComboboxSelected>>", self._on_form_change)

        ttk.Label(specs, text="Connector", style="Card.TLabel").grid(row=1, column=5, sticky="w", padx=8)
        self.connector_var = tk.StringVar(value="")
        self.connector_combo = ttk.Combobox(specs, textvariable=self.connector_var,
                                             values=L.FORM_CONNECTOR_MAP[L.FORM_FACTORS[0]],
                                             state="readonly", width=16)
        self.connector_combo.grid(row=2, column=5, sticky="w", padx=8, pady=(0, 6))

        self.price_hint = ttk.Label(specs, text="", style="Card.TLabel", foreground=ACCENT_ORANGE)
        self.price_hint.grid(row=3, column=1, sticky="w", padx=8, pady=(0, 6))
        self.year_hint = ttk.Label(specs, text="", style="Card.TLabel", foreground=ACCENT_RED)
        self.year_hint.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 6))

        # ---- driver config ----
        self.driver_panel = DriverConfigPanel(inner)
        self.driver_panel.pack(fill="x", padx=10, pady=8)

        # ---- tags ----
        self.tag_panel = TagSelectorPanel(inner)
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
        self.connector_combo.configure(values=allowed)
        if len(allowed) == 1:
            self.connector_var.set(allowed[0])
            self.connector_combo.configure(state="disabled")
        else:
            self.connector_combo.configure(state="readonly")
            if self.connector_var.get() not in allowed:
                self.connector_var.set("")

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
        self.validation_label.configure(text="")
        self.year_hint.configure(text="")
        self.price_hint.configure(text="")

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

        self._build_menu()
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._try_auto_load()

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
        try:
            entries, notes = L.load_database(path)
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
        self.file_panel_root_changed()
        self.populate_tree()
        msg = "Loaded {} entries from {}".format(len(entries), path)
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

    def validate_and_commit(self, entry, original_id):
        existing_ids = {e.get("id") for i, e in enumerate(self.entries)
                         if self.editing_index is None or i != self.editing_index}
        errors = L.validate_entry(entry, existing_ids=existing_ids, exclude_id=None)
        if errors:
            return errors
        clean = L.build_clean_entry(entry)
        if self.editing_index is not None:
            self.entries[self.editing_index] = clean
        else:
            self.entries.append(clean)
            self.editing_index = len(self.entries) - 1
        self.dirty = True
        self.populate_tree()
        self.status_var.set("Saved entry '{}' ({} total entries, unsaved changes).".format(
            clean["id"], len(self.entries)))
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
        for issue in issues:
            if issue.fix:
                issue.fix(self.entries)
        if issues:
            self.dirty = True
            self.populate_tree()
            self.status_var.set("Applied {} fix(es). Remember to Save As to keep them.".format(len(issues)))

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
