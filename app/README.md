# Database Editor

A standalone desktop GUI for maintaining `database.json` — the audio
database used by your offline IEM/headphone discovery app. Built with
Python's built-in `tkinter`, so it has **zero third-party dependencies**
and packages into a single `.exe` cleanly.

It implements the rules from your `ADD ENTRY PROMPT.txt` and
`AUDIT DATABASE PROMPT.txt` as live GUI guardrails, so most mistakes
are simply impossible to make instead of needing to be caught later.

---

## Features

- **Never overwrites your original file.** "Save As..." always writes a
  new `.json` file; it explicitly refuses to save over the file you loaded.
- **Brand-grouped tree view** of every entry ("Brand (count)" ▸ Model
  [Variant] — id), with a live search box.
- **Add / Edit / Delete** entries through one form — no manual JSON editing.
- **Smart autofill** — Brand/Model/Variant are the only free-typed
  fields, and each shows a filtered dropdown of matching values already
  in your database as you type (Model suggestions prefer the currently
  typed Brand).
- **Auto-generated, normalized ID** — you never type an id; it's built
  live from Brand/Model/Variant using your normalization rules (lowercase,
  underscores only, no trailing underscore) and blocks saving if it would
  collide with an existing id. `+` in a name (Studio Buds+, Galaxy Buds+,
  Arctis 7+, "V3+", etc.) is preserved as the word `plus` rather than
  being silently dropped — earlier versions of the normalizer treated
  `+` like any other separator, which caused it to disappear entirely
  and made e.g. "V3" and "V3+" collide on the same id.
- **Guardrailed price & year fields:**
  - Price is auto-rounded to the nearest $5 the moment you tab out
    (e.g. `499` → `500`), with a note shown explaining the change.
  - Year must be a real 4-digit year (1950–next year) or `0` for
    "unknown/unverifiable" — anything else is rejected with a clear message.
- **Driver configuration builder** — check off which driver technologies
  are used (DD, BA, Planar, BC, PZT, MEMS, EST) and enter a count for
  each; `driver_type` (DD / Hybrid / Tribrid / etc.) and the
  `driver_config` string (e.g. `1DD+4BA+2EST`, no spaces) are computed
  for you — you can never mismatch them.
- **Form factor ⇄ connector matrix enforcement** — the Connector dropdown
  only ever shows values that are legal for the selected Form Factor
  (e.g. picking "Wireless Earbuds (TWS)" locks the connector to
  "Bluetooth"; picking "IEM" removes Bluetooth/Detachable/Electrostatic
  from the list entirely).
- **Tag picker with conflict guardrails** — all 31 approved tags,
  grouped exactly like the prompts, each with a quick-scan emoji next
  to its name. You physically cannot check two tags that conflict
  (V-Shaped+U-Shaped, Warm+Bright, Dark+Treblehead, etc.), and only
  one "primary tonality" tag (Neutral/Balanced/V-Shaped/U-Shaped) may
  be active at a time. The count must stay between 4 and 12. The
  price-tier tag (Budget/Mid-Tier/Premium/Flagship) is fully automatic
  based on the price you entered — you don't pick it, and it can
  never drift out of sync. (The emojis are display-only — the tag
  strings saved to `database.json` are unchanged.)
- **Measurement file linker** — browse/search the `.txt` files under
  your `data/` folder and attach them to an entry with two clicks
  (no manual path typing). Both the Available and Linked lists have a
  scrollbar and support mouse-wheel scrolling. Paths are always stored
  as forward-slash relative paths (e.g. `data/ADEN/NOBLE ONYX.txt`),
  never as Windows backslash or absolute paths, regardless of what OS
  you run the app on.
- **Built-in Audit tab** — on load (and any time via "Run Full Audit")
  it checks the *whole* database for:
  - JSON syntax errors (reported with line/column on load)
  - duplicate / malformed IDs
  - price-tier tag mismatches
  - prices not rounded to $5
  - invalid years
  - `driver_config` whitespace and `driver_type` mismatches
  - form factor / connector matrix violations
  - tag conflicts and tag count violations
  - unapproved tags
  - **missing files** (referenced in the JSON but not found on disk)
  - **unlinked files** (`.txt` files on disk that no entry references)

  Each row shows whether it's auto-fixable. "Fix Selected" or "Fix All
  Auto-Fixable" apply the safe, mechanical corrections (id normalization,
  driver_config whitespace, price rounding, price-tier tag correction) —
  the changes stay in memory until you explicitly "Save As...". The
  Audit tab's list has a scrollbar and supports mouse-wheel scrolling
  (an earlier version created the scrollbar but never actually placed
  it in the layout, so it silently didn't render).
- **Alphabetical, clean output** — on save, every entry is rebuilt with
  exactly the 14 schema fields in the original order, sorted by
  Brand → Model → Variant, with 2-space JSON indentation.
- Retro dark / pixel-adjacent theme to loosely match your other app,
  using your custom icons if the `assets/icons` folder is present next
  to the script/exe (falls back gracefully to plain labels if not).

## Files in this folder

```
main.py           <- run this
db_logic.py       <- all data/validation/audit logic (no GUI code)
assets/icons/*.png <- your custom driver/connector icons (optional)
assets/icon.ico   <- app/window icon (optional — used if present)
README.md         <- this file
```

## Running it

Requires Python 3.8+ (tkinter ships with the standard Windows/macOS
installers; on Linux you may need `sudo apt install python3-tk`).

```
python main.py
```

### Loading your database

- If `database.json` sits in the **same folder** as `main.py` (or the
  built `.exe`), it auto-loads on startup.
- Otherwise use **File ▸ Open Database...** and pick the file. The
  folder that file is in is assumed to also contain your `data/`
  subfolder (matching your existing layout). If your `data/` folder
  lives somewhere else, use **File ▸ Set Data Folder...** to point at
  it separately — this is used for the measurement-file linker and the
  missing/unlinked-file audit checks.

### Saving

**File ▸ Save As...** — always. The app will refuse to write over the
file you loaded, by design, so your source database is never at risk.

---

## Building a standalone .exe with PyInstaller

1. Install PyInstaller (only needed on your build machine, not for
   running the app):
   ```
   pip install pyinstaller
   ```

2. From this folder, run:
   ```
   pyinstaller --onefile --windowed --name "Database Editor" ^
       --icon "assets/icon.ico" --add-data "assets;assets" main.py
   ```
   (On macOS/Linux use `--add-data "assets:assets"` — colon instead of
   semicolon — and drop `--icon`, since `.ico` files are Windows-only;
   macOS uses `.icns` instead.)

3. Your `.exe` will be in `dist/Database Editor.exe`.

   - `--icon "assets/icon.ico"` makes Windows use `assets/icon.ico` as
     the icon **on the .exe file itself** (in Explorer, the taskbar
     pinned shortcut, etc.).
   - The app also loads `assets/icon.ico` itself at startup and sets it
     as the **window/taskbar icon while running** — this happens
     automatically the moment `icon.ico` exists in the `assets` folder,
     so it works whether you run `main.py` directly or the built exe.
   - The `--add-data` flag bundles the whole `assets` folder (icons +
     `icon.ico`) inside the exe automatically — no extra steps needed.
   - If you'd rather NOT bundle assets into the exe (smaller file, and
     lets you swap icons later without rebuilding), just drop the
     `--add-data` flag and instead copy the `assets` folder next to
     the built `.exe` — the app checks there first.

That's it — `dist/Database Editor.exe` is a single portable file.
Drop it next to your `database.json` and `data/` folder (or point the
app at them from the menus) and you're good to go.

---

## Building a .dmg (macOS) or .AppImage (Linux)

**PyInstaller cannot cross-build.** A Windows machine can only produce
a `.exe`; you need to actually run the build ON a Mac for a `.dmg` and
ON Linux for an `.AppImage`. If you don't have that hardware, free CI
runners work fine (e.g. a GitHub Actions workflow using the
`macos-latest` and `ubuntu-latest` runners) — same commands below,
just run inside the CI job.

Two ready-to-run scripts are included for this:

- `build_macos.sh` — builds `Database Editor.app`, then wraps it in
  `Database_Editor.dmg` (uses `create-dmg` for a nicer drag-to-Applications
  layout if installed via `brew install create-dmg`, otherwise falls
  back to a plain `hdiutil` dmg).
- `build_linux_appimage.sh` — builds a onefile Linux binary, assembles
  the `AppDir` structure appimagetool expects, downloads `appimagetool`
  if it isn't already next to the script, and produces
  `Database_Editor.AppImage`.

Both use the icon files already in `assets/`: `icon.icns` for macOS,
`icon.png` for Linux (converted from your `icon.ico` — `.ico` itself
is Windows-only and isn't valid for either of these).

Run from this folder:
```
chmod +x build_macos.sh          # macOS
./build_macos.sh

chmod +x build_linux_appimage.sh # Linux
./build_linux_appimage.sh
```

Requirements per platform:
- **macOS:** Python 3 with tkinter (the python.org installer bundles
  it; `brew install python-tk` if you're on Homebrew Python),
  `pip install pyinstaller`.
- **Linux:** `sudo apt install python3-tk` (or your distro's
  equivalent) and `pip install pyinstaller`. `curl` is needed the
  first time to fetch `appimagetool`.

Both scripts reuse the same `--add-data` bundling approach as the
Windows build, so `resource_base()` in `main.py` (which already knows
how to find `assets/` next to a PyInstaller-frozen executable) works
unchanged on all three platforms — no code changes needed per OS.

### Building all three via GitHub Actions

`.github/workflows/build.yml` (at the repo root, one level above this
`app/` folder) runs all three builds for you — Windows `.exe`, macOS
`.dmg`, Linux `.AppImage` — as three parallel jobs on GitHub-hosted
runners, so you don't need to own a Mac or a Linux box.

- Push this repo to GitHub with the layout intact (`.github/` and
  `app/` as siblings at the repo root).
- Trigger it from the **Actions** tab → "Build Database Editor" →
  **Run workflow** (or push a tag like `v1.0` — the workflow also
  fires automatically on any tag starting with `v`).
- Each job uploads its result as a build artifact you can download
  from the finished run's summary page.

The macOS job is the one most likely to need attention over time: it
installs a Tk-enabled Python via Homebrew (`python-tk@3.12`) because
the plain `python3` on GitHub's macOS runners doesn't reliably include
tkinter. If Homebrew changes that formula's layout in the future and
the job fails to find `python3.12`, the fix is usually just bumping
the version pin in `build.yml` to whatever `brew install python-tk@X.Y`
currently resolves to.

---

## Notes on the design choices

- **Driver type is derived, not chosen.** Rather than picking "Hybrid"
  first and then trying to make the driver count match it (which is
  where mismatches like "Hybrid" + `"2DD"` sneak in), you build the
  actual driver list (e.g. 1× DD, 4× BA) and the app works out that
  this is a "Hybrid" for you. It is impossible to produce a
  `driver_type`/`driver_config` mismatch through the GUI.
- **The price-tier tag is not a checkbox.** Since it must always agree
  with `price_usd`, letting a user hand-pick it would just reintroduce
  the exact bug class the audit prompt exists to catch. It's computed
  and shown read-only, and included automatically in the saved tag list.
- **Tag conflicts block instead of silently resolving.** Rather than
  guessing which of two conflicting tags you "meant" (as the audit
  prompt has to do after the fact with no clear rule for some pairs),
  the live editor simply won't let the second one be checked, and
  tells you which tag to remove first.
