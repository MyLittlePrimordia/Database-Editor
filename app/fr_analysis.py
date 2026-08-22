"""
fr_analysis.py
Frequency-response (.txt) acoustic analysis for tonal tag suggestions.
Pure logic, no tkinter dependency.

Implements the measurement-band thresholds defined in ADD ENTRY PROMPT.txt /
AUDIT DATABASE PROMPT.txt, using the 1 kHz region as the reference:

  - Bass shelf (20-100 Hz)   vs 1 kHz
  - Midrange level (500-1500 Hz) vs 1 kHz, checked for scoops
  - Pinna gain (2.5-3.5 kHz) vs 1 kHz
  - Treble energy (6-15 kHz) vs 1 kHz and vs pinna gain

All bands degrade gracefully when the file simply doesn't cover them
(e.g. 20 Hz - 10 kHz sweeps): missing bands contribute nothing instead of
producing wrong numbers.
"""

import re

_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def parse_fr_file(path):
    """Parse 'frequency dB' pairs from a measurement .txt file.

    Tolerant of headers, comments (# // ;), tabs, commas and semicolons.
    Returns a frequency-sorted list of (freq_hz, db) float tuples.
    Raises IOError on unreadable files; returns [] if no data rows found.
    """
    points = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            nums = _NUM_RE.findall(line.replace(";", ",").replace("\t", ","))
            # comma decimal separator: "20,15" would wrongly split into two;
            # treat single-comma lines with exactly 2 numeric parts as one pair
            parts = [p for p in re.split(r"[,\s]+", line) if p]
            vals = None
            if len(parts) == 2 and len(_NUM_RE.findall(parts[0])) == 1 \
                    and len(_NUM_RE.findall(parts[1])) == 1:
                try:
                    vals = (float(parts[0].replace(",", ".")),
                            float(parts[1].replace(",", ".")))
                except ValueError:
                    vals = None
            if vals is None:
                nums = [_to_float(n) for n in nums]
                nums = [n for n in nums if n is not None]
                if len(nums) >= 2:
                    vals = (nums[0], nums[1])
            if vals is None:
                continue
            freq, db = vals
            if 2.0 <= freq <= 100000.0 and -120.0 <= db <= 140.0:
                points.append((freq, db))
    points.sort(key=lambda p: p[0])
    return points


def _to_float(token):
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return None


def _band(points, lo, hi):
    """Mean dB within [lo, hi] Hz, plus whether any samples exist there."""
    vals = [db for f, db in points if lo <= f <= hi]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _band_peak(points, lo, hi):
    """Peak (max) dB within [lo, hi] Hz, or None."""
    vals = [db for f, db in points if lo <= f <= hi]
    return max(vals) if vals else None


def _ref_1k(points):
    """Median dB in 900-1100 Hz (robust against single-sample spikes)."""
    vals = sorted(db for f, db in points if 900 <= f <= 1100)
    if not vals:
        # widen the search before giving up
        vals = sorted(db for f, db in points if 700 <= f <= 1300)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def analyze_points(points):
    """Compute band metrics relative to 1 kHz and derive tag suggestions.

    Returns {ok, error?, metrics{...}, suggestions:[{tag, reason}]}.
    Suggestions follow the prompt thresholds and are ordered by strength;
    callers may further filter them (conflicts, counts).
    """
    out = {"ok": False, "metrics": {}, "suggestions": []}
    if not points or len(points) < 20:
        out["error"] = "Not enough data points."
        return out
    fmin, fmax = points[0][0], points[-1][0]
    ref = _ref_1k(points)
    if ref is None:
        out["error"] = "No samples near 1 kHz to reference against."
        return out

    m = {}
    bass = _band(points, 20, 100)
    if bass is not None:
        m["bass_shelf"] = round(bass - ref, 1)
    mid = _band(points, 500, 1500)
    if mid is not None:
        m["mid_level"] = round(mid - ref, 1)
    pinna_band = _band(points, 2500, 3500)
    pinna_peak = _band_peak(points, 2500, 3500)
    if pinna_band is not None:
        m["pinna_gain"] = round(pinna_band - ref, 1)
    if pinna_peak is not None:
        m["pinna_peak"] = round(pinna_peak - ref, 1)
    treb_avg = _band(points, 6000, min(15000, fmax))
    treb_peak = _band_peak(points, 6000, min(15000, fmax))
    if treb_avg is not None:
        m["treble_avg"] = round(treb_avg - ref, 1)
    if treb_peak is not None:
        m["treble_peak"] = round(treb_peak - ref, 1)

    sugg = []

    def add(tag, reason):
        sugg.append({"tag": tag, "reason": reason})

    # ---- bass shelf -----------------------------------------------------
    bs = m.get("bass_shelf")
    if bs is not None:
        if bs > 8:
            add("Basshead", "Bass shelf {:+.1f} dB above 1 kHz (>8)".format(bs))
            add("Sub-Bass", "Deep-bass elevated shelf")
            add("Punchy Bass", "Elevated low-end energy")
        elif bs >= 3:
            add("Warm", "Moderate bass shelf {:+.1f} dB (3-8)".format(bs))
            add("Balanced", "Bass present but controlled ({:+.1f} dB)".format(bs))
        elif bs >= 0:
            add("Neutral", "Flat bass shelf {:+.1f} dB vs 1 kHz".format(bs))
            add("Reference", "Near-linear low end")

    # ---- overall brightness verdict (prevents contradicting families) ---
    pg = m.get("pinna_gain", m.get("pinna_peak"))
    ta = m.get("treble_avg")
    tp = m.get("treble_peak")
    # Blend of pinna gain vs the Harman ~9 dB target and treble energy vs a
    # realistic ~-2 dB average for 6-15 kHz. Real sweeps roll off up top, so
    # the treble term is gentle; peaks only matter when far above ear gain.
    warm_bass = bs is not None and bs >= 3
    basshead_bass = bs is not None and bs > 8
    score = 0.0
    if pg is not None:
        score += (pg - 9.0) / 3.0
    if ta is not None:
        score += (ta + 2.0) / 6.0
    if tp is not None and pg is not None and tp - pg > 6:
        score += 0.4
    bright = score > 1.0 and not (warm_bass and score < 2.0)
    dark = score < -0.9

    if bright:
        add("Bright", "Forward upper range (brightness score {:+.1f})".format(score))
        if pg is not None and pg > 12:
            add("Vocal-Focused", "Pinna gain {:+.1f} dB (>12)".format(pg))
        if tp is not None and pg is not None and tp - pg > 6:
            add("Treblehead", "Sharp treble peak {:+.1f} dB over ear gain".format(tp))
        elif ta is not None and pg is not None and ta > pg:
            add("Analytical", "Treble energy at/above ear gain ({:+.1f} dB)".format(ta))
    elif dark:
        add("Smooth", "Receding highs (brightness score {:+.1f})".format(score))
        add("Dark", "Low high-frequency energy")
        if pg is not None and pg < 6:
            add("Relaxed", "Soft pinna gain {:+.1f} dB (<6)".format(pg))

    # ---- midrange character (needs bass+pinna context) ------------------
    # A scoop means the midrange sits clearly BELOW both neighbours once the
    # natural ~7 dB pinna rise is accounted for -- otherwise every normal
    # Harman-like tuning would look "scooped".
    ml = m.get("mid_level")
    if ml is not None and bs is not None and pg is not None:
        floor = min(bs, pg - 7.0)
        if ml + 3.0 < floor:
            shape = "V-Shaped" if bs >= 6 else "U-Shaped"
            add(shape, "Midrange sits {:.1f} dB below the bass/pinna shoulders".format(ml))
        elif abs(ml) <= 3 and pg is not None and 8 <= pg <= 12 and not bright and not dark:
            add("Balanced", "Linear midrange with Harman-like pinna gain")

    # ---- resolve: at most ONE primary tonality --------------------------
    primary_priority = ("V-Shaped", "U-Shaped", "Neutral", "Balanced")
    kept_primary = next((p for p in primary_priority
                         if any(s["tag"] == p for s in sugg)), None)
    if kept_primary is not None:
        sugg[:] = [s for s in sugg
                   if s["tag"] not in ("Neutral", "Balanced", "V-Shaped", "U-Shaped")
                   or s["tag"] == kept_primary]

    # ---- hard conflict guards from the tagging rules ---------------------
    tags_now = {s["tag"] for s in sugg}
    if "Basshead" in tags_now:
        sugg[:] = [s for s in sugg if s["tag"] != "Treblehead"]   # Basshead+Treblehead
    if kept_primary == "V-Shaped":
        sugg[:] = [s for s in sugg if s["tag"] != "Vocal-Focused"]  # V+VF

    # ---- dedupe, keep order ---------------------------------------------
    seen = set()
    uniq = []
    for s in sugg:
        if s["tag"] not in seen:
            seen.add(s["tag"])
            uniq.append(s)
    out["ok"] = True
    out["metrics"] = m
    out["suggestions"] = uniq
    out["coverage"] = "{:.0f}Hz - {:.0f}Hz".format(fmin, fmax)
    return out


def summarize_metrics(metrics):
    """Compact one-line summary for the UI, e.g.
    'Bass +8.2 | Mid -1.1 | Pinna +9.8 | Treble +2.3 dB'."""
    order = [("bass_shelf", "Bass"), ("mid_level", "Mid"),
             ("pinna_gain", "Pinna"), ("treble_avg", "Treble")]
    parts = ["{} {:+.1f}".format(lbl, metrics[k]) for k, lbl in order
             if k in metrics]
    return " | ".join(parts) + (" dB" if parts else "")
