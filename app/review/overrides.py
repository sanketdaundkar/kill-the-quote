"""
Buyer review decisions on flagged extraction lines - approvals, corrected
values, and a full audit trail. Stored as plain JSON keyed by vendor+item,
so a correction survives a re-extraction and actually flows into the
comparison table and analyst chat - not just recorded and ignored.

Nothing here overwrites what the vendor originally sent. The extraction
JSON stays untouched; an approval is a separate, layered decision that
gets applied on top when the comparison table is built, and every action
(approve, edit, revoke) is appended to that line's history rather than
replacing it - so "what did we decide and when" is always answerable.
"""
import json
import os
from datetime import datetime, timezone

OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "review", "overrides.json")


def _key(vendor_name: str, item_code: str) -> str:
    return f"{vendor_name}::{item_code}"


def load_overrides() -> dict:
    if not os.path.exists(OVERRIDES_PATH):
        return {}
    try:
        with open(OVERRIDES_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(overrides: dict):
    os.makedirs(os.path.dirname(OVERRIDES_PATH), exist_ok=True)
    with open(OVERRIDES_PATH, "w") as f:
        json.dump(overrides, f, indent=2)


def approve_line(vendor_name: str, item_code: str, original_unit_price_inr, new_unit_price_inr, note: str = "") -> dict:
    """Records an approval - with or without a price correction. `edited`
    is computed, not asserted, so it's never wrong even if the buyer
    re-types the same number the vendor originally gave."""
    overrides = load_overrides()
    key = _key(vendor_name, item_code)
    entry = overrides.get(key) or {"vendor_name": vendor_name, "item_code": item_code, "history": []}

    edited = (
        new_unit_price_inr is not None and original_unit_price_inr is not None
        and round(float(new_unit_price_inr), 2) != round(float(original_unit_price_inr), 2)
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    entry["approved"] = True
    entry["approved_at"] = now
    entry["note"] = note
    entry["original_unit_price_inr"] = original_unit_price_inr
    entry["override_unit_price_inr"] = new_unit_price_inr
    entry["edited"] = edited
    entry.setdefault("history", []).append({
        "action": "approved", "at": now,
        "unit_price_inr": new_unit_price_inr, "edited": edited, "note": note,
    })
    overrides[key] = entry
    _save(overrides)
    return entry


def revoke_approval(vendor_name: str, item_code: str, note: str = "") -> dict | None:
    """Puts a line back into the open/flagged state. Still recorded in the
    audit trail as a 'revoked' action - never deleted outright."""
    overrides = load_overrides()
    key = _key(vendor_name, item_code)
    entry = overrides.get(key)
    if not entry:
        return None
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry["approved"] = False
    entry.setdefault("history", []).append({"action": "revoked", "at": now, "note": note})
    overrides[key] = entry
    _save(overrides)
    return entry


def get_override(overrides: dict, vendor_name: str, item_code: str) -> dict | None:
    return overrides.get(_key(vendor_name, item_code))
