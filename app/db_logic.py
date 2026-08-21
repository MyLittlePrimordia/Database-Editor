"""
db_logic.py
Core data model, validation, normalization and audit logic for the
IEM/Headphone Database Editor.

This module has NO tkinter dependency so it can be unit-tested / reused
independently of the GUI.
"""

import os
import re
import json
import math
import datetime
import unicodedata

CURRENT_YEAR = datetime.datetime.now().year

# --------------------------------------------------------------------------
# SCHEMA
# --------------------------------------------------------------------------
SCHEMA_FIELDS = [
    "id", "brand", "model", "variant", "year", "price_usd",
    "driver_type", "driver_config", "impedance", "sensitivity",
    "connector", "form_factor", "tags", "files",
]

SCHEMA_STR_FIELDS = ["id", "brand", "model", "variant", "driver_type",
                     "driver_config", "connector", "form_factor"]
SCHEMA_INT_FIELDS = ["year", "price_usd", "impedance", "sensitivity"]
SCHEMA_LIST_FIELDS = ["tags", "files"]

BLANK_ENTRY = {
    "id": "", "brand": "", "model": "", "variant": "", "year": 0,
    "price_usd": 0, "driver_type": "", "driver_config": "", "impedance": 0,
    "sensitivity": 0, "connector": "", "form_factor": "", "tags": [], "files": [],
}

# --------------------------------------------------------------------------
# DRIVERS
# --------------------------------------------------------------------------
DRIVER_TECH_ORDER = ["DD", "Planar", "BA", "BC", "PZT", "MEMS", "EST"]
DRIVER_TECH_LABELS = {
    "DD": "Dynamic Driver (DD)",
    "Planar": "Planar",
    "BA": "Balanced Armature (BA)",
    "BC": "Bone Conduction (BC)",
    "PZT": "Piezoelectric (PZT)",
    "MEMS": "MEMS",
    "EST": "Electrostatic (EST)",
}
ALLOWED_DRIVER_TYPES = ["", "DD", "BA", "BC", "Planar", "Hybrid", "Tribrid", "EST", "MEMS", "PZT"]

# --------------------------------------------------------------------------
# FORM FACTOR / CONNECTOR MATRIX
# --------------------------------------------------------------------------
FORM_FACTORS = [
    "IEM",
    "Wireless Earbuds (TWS)",
    "Earbuds (Wired)",
    "Wireless Over-Ear Headphones",
    "Over-Ear Headphones (Wired)",
]

CONNECTORS_ALL = [
    "Bluetooth", "2-pin", "QDC", "MMCX", "A2DC",
    "Fixed Cable", "Detachable Cable", "Proprietary", "Electrostatic",
]

FORM_CONNECTOR_MAP = {
    "IEM": ["2-pin", "QDC", "MMCX", "A2DC", "Fixed Cable", "Proprietary"],
    "Earbuds (Wired)": ["2-pin", "QDC", "MMCX", "A2DC", "Fixed Cable", "Proprietary"],
    "Wireless Earbuds (TWS)": ["Bluetooth"],
    "Wireless Over-Ear Headphones": ["Bluetooth"],
    "Over-Ear Headphones (Wired)": ["Detachable Cable", "Fixed Cable", "Electrostatic"],
}

# icon keys used by the GUI for each form factor / connector / driver tech
FORM_FACTOR_ICON = {
    "IEM": "iem",
    "Wireless Earbuds (TWS)": "tws",
    "Earbuds (Wired)": "earbud",
    "Wireless Over-Ear Headphones": "headset",
    "Over-Ear Headphones (Wired)": "headphone",
}
CONNECTOR_ICON = {
    "Bluetooth": "bluetooth", "2-pin": "2pin", "QDC": "qdc", "MMCX": "mmcx",
    "A2DC": "a2dc", "Fixed Cable": "fixed", "Detachable Cable": "detach",
    "Proprietary": "proprietary", "Electrostatic": "electro",
}
DRIVER_TYPE_ICON = {
    "DD": "dd", "BA": "ba", "BC": "bc", "Planar": "planar", "EST": "est",
    "MEMS": "mems", "PZT": "pzt", "Hybrid": "hybrid", "Tribrid": "tribrid",
}

# --------------------------------------------------------------------------
# TAGS
# --------------------------------------------------------------------------
TAG_GROUPS = {
    "Tonal Profiles & Sound Signature": [
        "Basshead", "Sub-Bass", "Punchy Bass", "Warm", "Neutral", "V-Shaped",
        "U-Shaped", "Balanced", "Bright", "Treblehead", "Dark", "Vocal-Focused",
    ],
    "Technicalities & Presentation": [
        "Detailed", "Resolving", "Technical", "Wide-Stage", "Good-Imaging",
        "Smooth", "Reference", "Analytical", "Fun", "Relaxed",
    ],
    "Use Cases": ["Gaming", "Competitive-Gaming", "Studio-Monitoring"],
    "Price Tier (auto-assigned)": ["Budget", "Mid-Tier", "Premium", "Flagship"],
    "Release Types": ["Collab", "Limited-Edition"],
}
APPROVED_TAGS = [t for grp in TAG_GROUPS.values() for t in grp]
PRICE_TIER_TAGS = TAG_GROUPS["Price Tier (auto-assigned)"]

# tags that cannot ever be combined
TAG_CONFLICT_PAIRS = [
    frozenset(["V-Shaped", "U-Shaped"]),
    frozenset(["Neutral", "V-Shaped"]),
    frozenset(["V-Shaped", "Vocal-Focused"]),
    frozenset(["Dark", "Bright"]),
    frozenset(["Dark", "Treblehead"]),
    frozenset(["Warm", "Bright"]),
    frozenset(["Warm", "Analytical"]),
    frozenset(["Basshead", "Treblehead"]),
]

# only one of these primary-tonality descriptors may be present at once
PRIMARY_TONALITY_GROUP = {"Neutral", "Balanced", "V-Shaped", "U-Shaped"}

MIN_TAGS = 4
MAX_TAGS = 12

# --------------------------------------------------------------------------
# NORMALIZATION HELPERS
# --------------------------------------------------------------------------

def normalize_component(text):
    """Lowercase, strip symbols/punctuation, collapse whitespace to underscore.

    Special case: '+' is preserved as the literal word 'plus' rather than
    being silently collapsed like any other separator. Without this,
    "V3" and "V3+" both normalize to "v3" -- a real id collision for any
    "+" naming (Studio Buds+, Galaxy Buds+, Arctis 7+, Chu II+, etc.),
    which is common in this space. This matches the "_plus" convention
    already used throughout the existing database ids.

    Unicode accents are stripped via NFKD (Cafe -> cafe) to avoid
    collisions/loss.
    """
    if text is None:
        return ""
    # Decompose unicode and strip accents, keep ASCII only
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = text.replace("+", "_plus_")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def build_id(brand, model, variant):
    comps = [normalize_component(brand), normalize_component(model)]
    if variant and variant.strip():
        comps.append(normalize_component(variant))
    idstr = "_".join(c for c in comps if c)
    idstr = re.sub(r"_+", "_", idstr).strip("_")
    return idstr


def price_tier_for(price_usd):
    try:
        p = int(float(price_usd))
    except (TypeError, ValueError):
        p = 0
    if p >= 1500:
        return "Flagship"
    if p >= 500:
        return "Premium"
    if p >= 100:
        return "Mid-Tier"
    return "Budget"


def round_price_to_5(price_usd):
    """Round to nearest $5 using half-up (2.5 -> 5, not bankers)."""
    try:
        p = float(price_usd)
    except (TypeError, ValueError):
        return 0
    # half-up: floor((p+2.5)/5)*5 ; handle negative correctly
    if p < 0:
        return int(math.floor((p + 2.5) / 5.0) * 5) if p != 0 else 0
    return int(math.floor((p + 2.5) / 5.0) * 5)


def is_valid_year(year):
    """0 means 'unknown / unverifiable' and is allowed as a safe fallback."""
    try:
        # allow float-like strings "2020.0" -> int via float first
        if isinstance(year, float):
            year = int(year)
        elif isinstance(year, str) and "." in year:
            year = int(float(year))
        else:
            year = int(year)
    except (TypeError, ValueError):
        return False
    if year == 0:
        return True
    return 1950 <= year <= CURRENT_YEAR + 1


def classify_driver(components):
    """
    components: dict {tech: count} for techs with count > 0
    returns (driver_type, driver_config)
    """
    techs = [t for t, c in components.items() if c and c > 0]
    ordered = [t for t in DRIVER_TECH_ORDER if t in techs]
    if not ordered:
        return "", ""
    config = "+".join("{}{}".format(components[t], t) for t in ordered)
    if len(ordered) == 1:
        return ordered[0], config
    if len(ordered) == 2:
        return "Hybrid", config
    return "Tribrid", config


def parse_driver_config(config_str):
    """Parse a driver_config string like '1DD+4BA+2EST' back into a
    {tech: count} dict. Unknown tokens are ignored."""
    result = {}
    if not config_str:
        return result
    parts = config_str.replace(" ", "").split("+")
    for part in parts:
        if not part:
            continue
        m = re.match(r"^(\d+)([A-Za-z]+)$", part)
        if not m:
            continue
        count, tech = m.groups()
        if tech in DRIVER_TECH_ORDER:
            try:
                c = int(count)
                if c > 0:
                    result[tech] = c
            except ValueError:
                continue
    return result


def tag_conflicts(tag_set):
    """Return list of conflicting pairs present in tag_set (deduplicated)."""
    seen = set()
    conflicts = []
    for pair in TAG_CONFLICT_PAIRS:
        if pair.issubset(tag_set):
            key = tuple(sorted(pair))
            if key not in seen:
                seen.add(key)
                conflicts.append(key)
    present_primary = [t for t in tag_set if t in PRIMARY_TONALITY_GROUP]
    if len(present_primary) > 1:
        key = tuple(sorted(present_primary))
        if key not in seen:
            seen.add(key)
            conflicts.append(key)
    return conflicts


def validate_entry(entry, existing_ids=None, exclude_id=None):
    """
    Full validation of a single entry dict.
    Returns list of human-readable error strings (empty list == valid).
    `existing_ids` is a set of ids already in the database (for duplicate
    checking); `exclude_id` is the entry's own original id (skip self-match).
    """
    errors = []
    existing_ids = existing_ids or set()

    brand = (entry.get("brand") or "").strip()
    model = (entry.get("model") or "").strip()
    variant = (entry.get("variant") or "").strip()
    if not brand:
        errors.append("Brand is required.")
    if not model:
        errors.append("Model is required.")

    expected_id = build_id(brand, model, variant)
    if not expected_id:
        errors.append("Could not build a valid ID from Brand/Model/Variant.")
    elif entry.get("id") != expected_id:
        errors.append(
            "ID does not match normalized Brand/Model/Variant "
            "(expected '{}').".format(expected_id)
        )
    if expected_id and expected_id in existing_ids and expected_id != exclude_id:
        errors.append("An entry with ID '{}' already exists.".format(expected_id))

    if not is_valid_year(entry.get("year", 0)):
        errors.append(
            "Year must be a 4-digit year between 1950 and {} (or 0 if unknown).".format(
                CURRENT_YEAR + 1
            )
        )

    try:
        price_raw = entry.get("price_usd", 0)
        if isinstance(price_raw, str) and "." in price_raw:
            price = int(float(price_raw))
            errors.append("Price must be a whole number (got '{}').".format(price_raw))
        else:
            price = int(price_raw)
        if price < 0:
            errors.append("Price cannot be negative.")
        elif price % 5 != 0:
            errors.append(
                "Price must be rounded to the nearest $5 (got ${}).".format(price)
            )
    except (TypeError, ValueError):
        errors.append("Price must be a whole number.")

    form_factor = (entry.get("form_factor") or "").strip()
    connector = (entry.get("connector") or "").strip()
    if not form_factor:
        errors.append("Form factor is required (must be one of: {}).".format(", ".join(FORM_FACTORS)))
    elif form_factor not in FORM_FACTORS:
        errors.append("Form factor '{}' is not one of the 5 approved values.".format(form_factor))

    if not connector:
        errors.append("Connector is required (must be one of: {}).".format(", ".join(CONNECTORS_ALL)))
    elif connector not in CONNECTORS_ALL:
        errors.append("Connector '{}' is not one of the 9 approved values.".format(connector))
    elif form_factor and form_factor in FORM_CONNECTOR_MAP and connector not in FORM_CONNECTOR_MAP[form_factor]:
        errors.append(
            "Connector '{}' is not valid for form factor '{}'.".format(connector, form_factor)
        )

    driver_type = (entry.get("driver_type") or "").strip()
    driver_config = (entry.get("driver_config") or "").strip()
    if driver_type and driver_type not in ALLOWED_DRIVER_TYPES:
        errors.append("Driver type '{}' is not an approved value.".format(driver_type))
    if driver_config and re.search(r"\s", driver_config):
        errors.append("Driver config must not contain whitespace (got '{}').".format(driver_config))
    if driver_type and not driver_config:
        errors.append("Driver type '{}' present but driver_config is empty.".format(driver_type))
    if driver_config and not driver_type:
        parsed_tmp = parse_driver_config(driver_config)
        if parsed_tmp:
            errors.append("Driver config '{}' present but driver_type is empty.".format(driver_config))
    if driver_config:
        parsed = parse_driver_config(driver_config)
        if not parsed and driver_config:
            errors.append("Driver config '{}' is malformed or contains unknown tech.".format(driver_config))
        else:
            expected_type, expected_config = classify_driver(parsed)
            if expected_type != driver_type:
                errors.append(
                    "Driver type '{}' does not match configuration '{}' "
                    "(expected '{}').".format(driver_type, driver_config, expected_type)
                )

    for f in ("impedance", "sensitivity"):
        raw = entry.get(f, 0)
        try:
            if isinstance(raw, str) and "." in raw:
                errors.append("{} must be a whole number (got '{}').".format(f.capitalize(), raw))
                v = int(float(raw))
            else:
                v = int(raw)
            if v < 0:
                errors.append("{} cannot be negative.".format(f.capitalize()))
        except (TypeError, ValueError):
            errors.append("{} must be a whole number.".format(f.capitalize()))

    tags = entry.get("tags", []) or []
    if len(tags) != len(set(tags)):
        dup = [t for t in set(tags) if tags.count(t) > 1]
        errors.append("Duplicate tag(s): {}".format(", ".join(dup)))
    unapproved = [t for t in tags if t not in APPROVED_TAGS]
    if unapproved:
        errors.append("Unapproved tag(s): {}".format(", ".join(unapproved)))
    if len(tags) < MIN_TAGS:
        errors.append("At least {} tags are required (has {}).".format(MIN_TAGS, len(tags)))
    if len(tags) > MAX_TAGS:
        errors.append("At most {} tags are allowed (has {}).".format(MAX_TAGS, len(tags)))
    conflicts = tag_conflicts(set(tags))
    for pair in conflicts:
        errors.append("Conflicting tags present: {}".format(" + ".join(pair)))
    tier_tags_present = [t for t in tags if t in PRICE_TIER_TAGS]
    if len(tier_tags_present) != 1:
        errors.append("Exactly one price-tier tag is required (Budget/Mid-Tier/Premium/Flagship).")
    else:
        expected_tier = price_tier_for(entry.get("price_usd", 0))
        if tier_tags_present[0] != expected_tier:
            errors.append(
                "Price-tier tag '{}' does not match price ${} (expected '{}').".format(
                    tier_tags_present[0], entry.get("price_usd", 0), expected_tier
                )
            )

    return errors


def build_clean_entry(source):
    """Return a new dict containing exactly SCHEMA_FIELDS, in canonical
    order, with best-effort type coercion. Never raises."""
    out = {}
    for f in SCHEMA_FIELDS:
        val = source.get(f, BLANK_ENTRY[f])
        if f in SCHEMA_INT_FIELDS:
            try:
                if isinstance(val, str):
                    val = val.strip()
                    if val == "":
                        val = 0
                    elif "." in val:
                        val = int(float(val))
                    else:
                        val = int(val)
                else:
                    val = int(val)
            except (TypeError, ValueError):
                val = 0
        elif f in SCHEMA_STR_FIELDS:
            val = "" if val is None else str(val).strip()
        elif f in SCHEMA_LIST_FIELDS:
            if not isinstance(val, list):
                val = []
            else:
                cleaned_list = []
                for x in val:
                    if x is None:
                        continue
                    s = str(x).strip()
                    if s:
                        cleaned_list.append(s)
                val = cleaned_list
        out[f] = val
    return out


def sort_key(entry):
    return (
        (entry.get("brand") or "").lower(),
        (entry.get("model") or "").lower(),
        (entry.get("variant") or "").lower(),
    )


# --------------------------------------------------------------------------
# LOAD / SAVE
# --------------------------------------------------------------------------

class DatabaseLoadError(Exception):
    pass


def load_database(path):
    """Load + syntax-check a database JSON file. Raises DatabaseLoadError
    with a friendly message on failure."""
    # guard against huge files (e.g., >100 MB)
    try:
        size = os.path.getsize(path)
        if size > 100 * 1024 * 1024:
            raise DatabaseLoadError("File too large ({} MB) - refusing to load.".format(size // (1024*1024)))
    except OSError:
        pass
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw_text = f.read()
    except OSError as e:
        raise DatabaseLoadError("Could not open file:\n{}".format(e))

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise DatabaseLoadError(
            "Invalid JSON syntax at line {}, column {}:\n{}".format(e.lineno, e.colno, e.msg)
        )

    if not isinstance(data, list):
        raise DatabaseLoadError("Database file must contain a JSON array of entries at the top level.")

    cleaned = []
    coercion_notes = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            coercion_notes.append("Entry #{} was not a JSON object and was skipped.".format(i))
            continue
        extra = set(item.keys()) - set(SCHEMA_FIELDS)
        if extra:
            coercion_notes.append("Entry #{} had extra field(s) {} - they will be dropped on save.".format(i, ", ".join(extra)))
        cleaned.append(build_clean_entry(item))
    return cleaned, coercion_notes


def save_database(path, entries):
    ordered = sorted((build_clean_entry(e) for e in entries), key=sort_key)
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return ordered


# --------------------------------------------------------------------------
# AUDIT ENGINE
# --------------------------------------------------------------------------

class AuditIssue:
    def __init__(self, category, entry_index, entry_id, message, fix=None, severity="warning"):
        self.category = category
        self.entry_index = entry_index
        self.entry_id = entry_id
        self.message = message
        self.fix = fix  # callable(entries) -> None, mutates entries in place; or None
        self.severity = severity  # "error" | "warning" | "info"

    def __repr__(self):
        return "<AuditIssue {} {} {}>".format(self.category, self.entry_id, self.message)


def run_full_audit(entries, data_root=None):
    """
    Returns list of AuditIssue.
    data_root: folder that CONTAINS the 'data' subfolder (and normally the
    database.json). If None, file-existence checks are skipped.
    """
    issues = []
    seen_ids = {}

    # Pre-compute file index once if data_root provided (single walk)
    on_disk_set = None
    referenced_map = {}  # rel -> [indices]
    # always build referenced_map for duplicate-file checks (no data_root needed)
    for idx, entry in enumerate(entries):
        for rel in entry.get("files", []) or []:
            norm = rel.replace("\\", "/")
            norm = re.sub(r"/+", "/", norm.strip())
            if norm:
                referenced_map.setdefault(norm, []).append(idx)
    if data_root:
        data_dir = os.path.join(data_root, "data")
        if os.path.isdir(data_dir):
            on_disk = []
            for root, _, files in os.walk(data_dir):
                for fn in files:
                    if fn.lower().endswith(".txt"):
                        full = os.path.join(root, fn)
                        try:
                            rel = os.path.relpath(full, data_root).replace("\\", "/")
                        except ValueError:
                            continue
                        rel = re.sub(r"/+", "/", rel)
                        on_disk.append(rel)
            on_disk_set = set(on_disk)

    # ---- per-entry checks -------------------------------------------------
    for idx, entry in enumerate(entries):
        eid = entry.get("id", "") or "(no id) #{}".format(idx)

        # duplicate id
        real_id = entry.get("id", "")
        if real_id:
            if real_id in seen_ids:
                first_idx = seen_ids[real_id]
                issues.append(AuditIssue(
                    "Duplicate ID", idx, eid,
                    "Duplicate id '{}' also used by entry #{}.".format(real_id, first_idx),
                    severity="error",
                ))
            else:
                seen_ids[real_id] = idx

        # id format / normalization - merged, no double report
        expected_id = build_id(entry.get("brand", ""), entry.get("model", ""), entry.get("variant", ""))
        has_leading_trailing = entry.get("id", "").startswith("_") or entry.get("id", "").endswith("_")
        if expected_id and entry.get("id") != expected_id:
            if has_leading_trailing:
                msg = "ID '{}' should be '{}' (has leading/trailing underscore).".format(entry.get("id"), expected_id)
            else:
                msg = "ID '{}' should be '{}'.".format(entry.get("id"), expected_id)
            def make_id_fix(i=idx, exp=expected_id):
                def fix(entries_list):
                    entries_list[i]["id"] = exp
                return fix
            issues.append(AuditIssue(
                "ID Format", idx, eid,
                msg,
                fix=make_id_fix(),
            ))
        elif has_leading_trailing:
            def make_id_fix2(i=idx, exp=expected_id):
                def fix(entries_list):
                    entries_list[i]["id"] = exp
                return fix
            issues.append(AuditIssue(
                "ID Format", idx, eid,
                "ID has a leading/trailing underscore.",
                fix=make_id_fix2(),
            ))

        # driver_config whitespace - any whitespace
        dc = entry.get("driver_config", "")
        has_ws = bool(dc and re.search(r"\s", dc))
        if has_ws:
            fixed_dc = re.sub(r"\s+", "", dc)
            def make_dc_fix(i=idx, val=fixed_dc):
                def fix(entries_list):
                    entries_list[i]["driver_config"] = val
                return fix
            issues.append(AuditIssue(
                "Driver Config", idx, eid,
                "driver_config '{}' contains whitespace.".format(dc),
                fix=make_dc_fix(),
            ))

        # driver_type / driver_config classification match + orphan
        parsed = parse_driver_config(entry.get("driver_config", ""))
        dt = (entry.get("driver_type") or "").strip()
        dc_stripped = (entry.get("driver_config") or "").strip()
        if dt and not dc_stripped:
            def make_clear_dt(i=idx):
                def fix(entries_list):
                    entries_list[i]["driver_type"] = ""
                return fix
            issues.append(AuditIssue(
                "Driver Type", idx, eid,
                "driver_type '{}' present but driver_config is empty.".format(dt),
                fix=make_clear_dt(),
                severity="error",
            ))
        elif dc_stripped and not dt:
            if parsed:
                expected_type, _ = classify_driver(parsed)
                def make_dt_fix(i=idx, val=expected_type):
                    def fix(entries_list):
                        entries_list[i]["driver_type"] = val
                    return fix
                issues.append(AuditIssue(
                    "Driver Type", idx, eid,
                    "driver_type missing but driver_config '{}' implies '{}'.".format(dc_stripped, expected_type),
                    fix=make_dt_fix(),
                    severity="error",
                ))
        elif parsed:
            expected_type, expected_config = classify_driver(parsed)
            if dt != expected_type:
                def make_type_fix(i=idx, val=expected_type):
                    def fix(entries_list):
                        entries_list[i]["driver_type"] = val
                    return fix
                issues.append(AuditIssue(
                    "Driver Type", idx, eid,
                    "driver_type '{}' does not match driver_config '{}' (expected '{}').".format(
                        dt, dc_stripped, expected_type),
                    fix=make_type_fix(),
                ))
            if not has_ws and dc_stripped != expected_config and parsed:
                def make_order_fix(i=idx, val=expected_config):
                    def fix(entries_list):
                        entries_list[i]["driver_config"] = val
                    return fix
                issues.append(AuditIssue(
                    "Driver Config", idx, eid,
                    "driver_config '{}' not in canonical order (expected '{}').".format(dc_stripped, expected_config),
                    fix=make_order_fix(),
                    severity="info",
                ))

        # form factor / connector matrix + required
        ff = (entry.get("form_factor") or "").strip()
        conn = (entry.get("connector") or "").strip()
        if not ff:
            issues.append(AuditIssue(
                "Form/Connector Mismatch", idx, eid,
                "Form factor is missing/empty.",
                severity="error",
            ))
        elif ff not in FORM_FACTORS:
            issues.append(AuditIssue(
                "Form/Connector Mismatch", idx, eid,
                "Form factor '{}' is not an approved value.".format(ff),
                severity="error",
            ))
        if not conn:
            issues.append(AuditIssue(
                "Form/Connector Mismatch", idx, eid,
                "Connector is missing/empty.",
                severity="error",
            ))
        elif conn not in CONNECTORS_ALL:
            issues.append(AuditIssue(
                "Form/Connector Mismatch", idx, eid,
                "Connector '{}' is not an approved value.".format(conn),
                severity="error",
            ))
        if ff in FORM_CONNECTOR_MAP and conn in CONNECTORS_ALL and conn not in FORM_CONNECTOR_MAP[ff]:
            issues.append(AuditIssue(
                "Form/Connector Mismatch", idx, eid,
                "Connector '{}' is not allowed for form factor '{}'. Allowed: {}".format(
                    conn, ff, ", ".join(FORM_CONNECTOR_MAP[ff])),
                severity="error",
            ))

        # price tier tag correction
        price = entry.get("price_usd", 0)
        expected_tier = price_tier_for(price)
        tags = entry.get("tags", []) or []
        present_tiers = [t for t in tags if t in PRICE_TIER_TAGS]

        def make_tier_fix(i=idx, expected=expected_tier):
            def fix(entries_list):
                cur_tags = [t for t in entries_list[i].get("tags", []) if t not in PRICE_TIER_TAGS]
                cur_tags.append(expected)
                entries_list[i]["tags"] = cur_tags
            return fix

        if present_tiers != [expected_tier]:
            issues.append(AuditIssue(
                "Price Tier Tag", idx, eid,
                "Price tier tag(s) {} do not match price ${} (expected '{}').".format(
                    present_tiers or "(none)", price, expected_tier),
                fix=make_tier_fix(),
            ))

        # price not multiple of 5 and negative
        try:
            p = int(float(price)) if isinstance(price, str) and "." in str(price) else int(price)
            if p < 0:
                issues.append(AuditIssue(
                    "Price Rounding", idx, eid,
                    "Price ${} cannot be negative.".format(p),
                    severity="error",
                ))
            elif p % 5 != 0:
                rounded = round_price_to_5(p)
                def make_price_fix(i=idx, val=rounded):
                    def fix(entries_list):
                        entries_list[i]["price_usd"] = val
                    return fix
                issues.append(AuditIssue(
                    "Price Rounding", idx, eid,
                    "Price ${} is not a multiple of $5 (should be ${}).".format(p, rounded),
                    fix=make_price_fix(),
                ))
        except (TypeError, ValueError):
            issues.append(AuditIssue(
                "Price Rounding", idx, eid,
                "Price '{}' is not a valid integer.".format(price),
                severity="error",
            ))

        # year validity
        if not is_valid_year(entry.get("year", 0)):
            issues.append(AuditIssue(
                "Year", idx, eid,
                "Year '{}' is not a valid 4-digit year.".format(entry.get("year")),
                severity="error",
            ))

        # tag conflicts (deduplicated)
        conflicts = tag_conflicts(set(tags))
        for pair in conflicts:
            issues.append(AuditIssue(
                "Tag Conflict", idx, eid,
                "Conflicting tags present: {}".format(" + ".join(pair)),
                severity="error",
            ))

        # tag count
        if len(tags) < MIN_TAGS:
            issues.append(AuditIssue(
                "Tag Count", idx, eid,
                "Only {} tag(s) (minimum {}).".format(len(tags), MIN_TAGS),
                severity="error",
            ))
        if len(tags) > MAX_TAGS:
            issues.append(AuditIssue(
                "Tag Count", idx, eid,
                "{} tags present (maximum {}).".format(len(tags), MAX_TAGS),
                severity="error",
            ))

        # duplicate tags
        if len(tags) != len(set(tags)):
            dup = [t for t in set(tags) if tags.count(t) > 1]
            issues.append(AuditIssue(
                "Duplicate Tag", idx, eid,
                "Duplicate tag(s): {}".format(", ".join(dup)),
                severity="error",
            ))

        # unapproved tags
        unapproved = [t for t in tags if t not in APPROVED_TAGS]
        if unapproved:
            issues.append(AuditIssue(
                "Unapproved Tag", idx, eid,
                "Unapproved tag(s): {}".format(", ".join(unapproved)),
                severity="error",
            ))

        # duplicate files within entry
        files = entry.get("files", []) or []
        if len(files) != len(set(files)):
            issues.append(AuditIssue(
                "Duplicate File", idx, eid,
                "Duplicate file path(s) within entry.",
                severity="error",
            ))
        for rel in files:
            if not isinstance(rel, str) or not rel.strip():
                issues.append(AuditIssue(
                    "File Path", idx, eid,
                    "File path is empty or not a string: '{}'.".format(rel),
                    severity="error",
                ))
            elif rel != rel.strip():
                issues.append(AuditIssue(
                    "File Path", idx, eid,
                    "File path has leading/trailing whitespace: '{}'.".format(rel),
                    severity="error",
                ))
            elif "\\" in rel:
                def make_slash_fix(i=idx, old=rel):
                    def fix(entries_list):
                        lst = entries_list[i].get("files", [])
                        entries_list[i]["files"] = [p.replace("\\", "/") if p == old else p for p in lst]
                    return fix
                issues.append(AuditIssue(
                    "File Path", idx, eid,
                    "File path uses backslashes (should be forward slashes): '{}'.".format(rel),
                    fix=make_slash_fix(),
                    severity="warning",
                ))
            if isinstance(rel, str) and ".." in rel.split("/"):
                issues.append(AuditIssue(
                    "File Path", idx, eid,
                    "File path contains '..' traversal: '{}'.".format(rel),
                    severity="error",
                ))

    # ---- duplicate file link check (always, no data_root needed) ----------
    for rel, idxs in referenced_map.items():
        if len(idxs) > 1:
            ids = [entries[i].get("id", "#{}".format(i)) for i in idxs]
            for idx in idxs:
                eid = entries[idx].get("id", "") or "(no id) #{}".format(idx)
                issues.append(AuditIssue(
                    "Duplicate File Link", idx, eid,
                    "File '{}' is linked to multiple entries: {}".format(rel, ", ".join(ids)),
                    severity="warning",
                ))

    # ---- file existence and unlinked checks (needs data_root) ----------
    if on_disk_set is not None:
        for rel, idxs in referenced_map.items():
            if rel not in on_disk_set:
                for idx in idxs:
                    eid = entries[idx].get("id", "") or "(no id) #{}".format(idx)
                    issues.append(AuditIssue(
                        "Missing File", idx, eid,
                        "Linked file not found on disk: {}".format(rel),
                        severity="error",
                    ))
        referenced_set = set(referenced_map.keys())
        unlinked = sorted(on_disk_set - referenced_set)
        for rel in unlinked:
            issues.append(AuditIssue(
                "Unlinked File", -1, "(none)",
                "File on disk is not linked to any entry: {}".format(rel),
                severity="info",
            ))

    return issues
