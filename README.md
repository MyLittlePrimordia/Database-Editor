# Database Editor

A standalone desktop GUI for maintaining and auditing `database.json` — the catalog database used by **IEM Tool**.

Built entirely with Python and standard `tkinter`. It requires zero third-party packages to run and builds into a single, self-contained executable.

<p align="center">
  <img src="preview.png" width="900" alt="Database Editor Screenshot">
</p>

---

## Features

### Smart Entry Form & Validation
- **Searchable tree view:** Entries are grouped by brand (`Brand (count) ▸ Model [Variant] — id`) with real-time text filtering.
- **Autofill suggestions:** Brand, Model, and Variant suggest existing values as you type.
- **Auto-generated IDs:** Normalizes Brand/Model/Variant (lowercase, underscores). Preserves `+` as `plus` (e.g., `Studio Buds+` → `studio_buds_plus`) to avoid ID collisions.
- **Input guardrails:**
  - Auto-rounds prices to the nearest $5 on focus lost.
  - Driver configuration builder computes `driver_type` and `driver_config` (e.g., `1DD+4BA+2EST`) automatically from selected driver counts.
  - Form Factor selection dynamically filters the Connector dropdown to prevent invalid pairings.
  - Tag selector enforces the 31 approved tags, blocks conflicting tonality tags, and assigns price-tier tags automatically.

### Database Audit & Repair
- **Full database health check:** Scans on load (and on demand) for syntax errors, duplicate/malformed IDs, missing fields, invalid year formats, and tag rule violations.
- **File integrity checks:** Identifies missing measurement `.txt` files referenced in the JSON, as well as unlinked `.txt` files in your `data/` directory.
- **One-click repairs:** Safely batch-fixes ID normalization, whitespace, price rounding, and tier tags in memory.

### Safe File Handling
- **Non-destructive saving:** `Save As...` enforces saving to a new file and intentionally refuses to overwrite the loaded source file.
- **Strict schema export:** Formats JSON with 2-space indentation, sorting entries by `Brand → Model → Variant` with schema fields in fixed order.
- **Cross-platform paths:** Stores all measurement file references as forward-slash relative paths (`data/BRAND/file.txt`).

---

## Running from Source

Requires Python 3.8+. `tkinter` is included with standard Python installations on Windows and macOS. On Debian/Ubuntu Linux, install it via `sudo apt install python3-tk`.

```bash
python app/main.py
```

- If `database.json` and the `data/` directory are in the same folder as the script/executable, they load automatically.
- Use **File → Open Database...** or **File → Set Data Folder...** to point to custom locations.

---

## Building Executables

### Windows (`.exe`)
```bash
cd app
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "Database Editor" --icon="assets/icon.ico" --add-data "assets;assets" main.py
```

### macOS (`.dmg`) & Linux (`.AppImage`)
Platform-specific build scripts are located inside the `app/` folder:

```bash
# macOS (creates dist/Database Editor.dmg)
chmod +x build_macos.sh && ./build_macos.sh

# Linux (creates dist/Database_Editor-x86_64.AppImage)
chmod +x build_linux_appimage.sh && ./build_linux_appimage.sh
```

*(You can also build all three targets simultaneously using the included GitHub Actions workflow in `.github/workflows/build.yml`.)*

---

## Related Utilities

This editor is part of the companion tool suite for [IEM Tool](https://github.com/your-org/iem-tool):

| Utility | Description |
| :--- | :--- |
| **Database Editor** | GUI for editing, validating, and auditing `database.json` |
| **Curve Converter** | Converts raw measurement `.txt`/`.csv` files into standard format |
| **Split Database** | Splits large JSON databases into chunks for LLM context windows |
| **Compress Database** | Gzips `database.json` into `database.json.gz` for faster loading |
