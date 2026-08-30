"""
Turns N raw per-vendor extraction JSONs into one normalized comparison table.

Deliberately conservative: nothing here invents a number the vendor (or a
documented historical record) didn't provide. Anything the system had to
infer, convert, or fill in gets a flag so the buyer can see exactly where
their trust is resting on an assumption rather than a vendor's own word.
"""
import json
import os
import pandas as pd

FX_RATES_TO_INR = {"INR": 1.0, "USD": 87.0}  # documented assumption, see decisions.md

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "rfx")


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def load_rfx_spec():
    return _load_json(os.path.join(DATA_DIR, "rfx_spec.json"))


def load_historical_prices(vendor_name: str):
    """Look for a vendor-specific 'last cycle' price file. Only Apex has one
    fabricated for this demo, representing an existing-vendor price history
    the buyer's system would realistically already hold."""
    if "apex" in vendor_name.lower():
        path = os.path.join(DATA_DIR, "apex_last_year_prices.json")
        if os.path.exists(path):
            return _load_json(path)
    return None


def convert_to_inr(amount, currency):
    if amount is None:
        return None
    rate = FX_RATES_TO_INR.get(currency.upper(), None)
    if rate is None:
        return None
    return amount * rate


def normalize_line(vendor_name, li, rfx_by_code):
    """Returns a flat dict for one normalized comparison row."""
    code = li.get("matched_item_code")
    unit_price = li.get("unit_price")
    basis = li.get("unit_basis", "unknown")
    box_size = li.get("box_size")
    currency = (li.get("currency") or "INR").upper()

    per_unit_native = None
    if unit_price is not None:
        if basis == "per_unit":
            per_unit_native = unit_price
        elif basis == "per_box" and box_size:
            per_unit_native = unit_price / box_size
        # basis == "unknown" -> leave None, force review

    per_unit_inr = convert_to_inr(per_unit_native, currency)

    rfx_item = rfx_by_code.get(code) if code else None
    qty_gap = None
    if rfx_item and li.get("qty_quoted") is not None:
        qty_gap = li["qty_quoted"] - rfx_item["qty"]

    return {
        "vendor_name": vendor_name,
        "item_code": code,
        "rfx_description": rfx_item["description"] if rfx_item else None,
        "qty_requested": rfx_item["qty"] if rfx_item else None,
        "qty_quoted": li.get("qty_quoted"),
        "qty_gap": qty_gap,
        "vendor_line_ref": li.get("vendor_line_ref"),
        "description_as_quoted": li.get("description_as_quoted"),
        "unit_price_native": unit_price,
        "currency_native": currency,
        "unit_basis": basis,
        "box_size": box_size,
        "unit_price_inr": round(per_unit_inr, 2) if per_unit_inr is not None else None,
        "match_confidence": li.get("match_confidence"),
        "needs_buyer_review": li.get("needs_buyer_review", False),
        "review_reason": li.get("review_reason", ""),
        "carried_forward": False,
        "notes": li.get("notes", ""),
    }


def gap_fill_carried_forward(vendor_name, rows, rfx_spec, extraction):
    """If a vendor explicitly said 'rest same as last year' (visible in
    extraction_warnings or notes) and we have a historical price file for
    them, fill remaining unmatched RFx lines from that record - flagged,
    never silently."""
    hist = load_historical_prices(vendor_name)
    if not hist:
        return rows

    warnings_text = " ".join(extraction.get("extraction_warnings", [])).lower()
    any_note_text = " ".join(li.get("notes", "") for li in extraction.get("line_items", [])).lower()
    mentions_carry_forward = "last year" in warnings_text or "last year" in any_note_text or \
        any("last year" in (li.get("description_as_quoted") or "").lower() for li in extraction.get("line_items", []))

    if not mentions_carry_forward:
        return rows

    matched_codes = {r["item_code"] for r in rows if r["item_code"]}
    for li in rfx_spec["line_items"]:
        code = li["item_code"]
        if code in matched_codes or code not in hist:
            continue
        rows.append({
            "vendor_name": vendor_name,
            "item_code": code,
            "rfx_description": li["description"],
            "qty_requested": li["qty"],
            "qty_quoted": li["qty"],
            "qty_gap": 0,
            "vendor_line_ref": "(carried forward, not itemized in this response)",
            "description_as_quoted": "(vendor stated: 'rest same as last year')",
            "unit_price_native": hist[code],
            "currency_native": "INR",
            "unit_basis": "per_unit",
            "box_size": None,
            "unit_price_inr": hist[code],
            "match_confidence": 0.5,
            "needs_buyer_review": True,
            "review_reason": "Price carried forward from prior cycle's record, not independently re-quoted "
                              "by the vendor in this response. Confirm before award.",
            "carried_forward": True,
            "notes": "Filled from historical price file per vendor's 'same as last year' reference.",
        })
    return rows


def build_comparison_table(extraction_dir: str, rfx_spec: dict, overrides: dict = None) -> pd.DataFrame:
    """overrides, if given, is the dict from app.review.overrides.load_overrides() -
    an approved line's price correction (if any) is applied here, and its
    needs_buyer_review flag clears, so an approval actually changes what the
    rest of the app sees - the comparison totals, the analyst chat, all of
    it - not just what this one table displays."""
    rfx_by_code = {li["item_code"]: li for li in rfx_spec["line_items"]}
    overrides = overrides or {}
    all_rows = []
    vendor_meta = {}

    for fname in sorted(os.listdir(extraction_dir)):
        if not fname.endswith(".json"):
            continue
        try:
            extraction = _load_json(os.path.join(extraction_dir, fname))
        except (json.JSONDecodeError, OSError):
            # Corrupted or partially-written file from an earlier failed run -
            # skip it rather than take down the whole comparison table.
            continue
        vendor_name = extraction.get("vendor_name", fname)
        rows = [normalize_line(vendor_name, li, rfx_by_code) for li in extraction.get("line_items", [])]
        rows = gap_fill_carried_forward(vendor_name, rows, rfx_spec, extraction)

        for row in rows:
            override = overrides.get(f"{vendor_name}::{row['item_code']}")
            if override and override.get("approved"):
                if override.get("override_unit_price_inr") is not None:
                    row["unit_price_inr"] = override["override_unit_price_inr"]
                row["needs_buyer_review"] = False
                row["buyer_approved"] = True
                row["buyer_edited"] = bool(override.get("edited"))
                row["approval_note"] = override.get("note") or ""
            else:
                row["buyer_approved"] = False
                row["buyer_edited"] = False
                row["approval_note"] = ""

        all_rows.extend(rows)
        vendor_meta[vendor_name] = {
            "vendor_ref": extraction.get("vendor_ref"),
            "quote_date": extraction.get("quote_date"),
            "questionnaire_answers": extraction.get("questionnaire_answers", {}),
            "commercial_terms": extraction.get("commercial_terms", {}),
            "extraction_warnings": extraction.get("extraction_warnings", []),
            "source_file": extraction.get("_source_file"),
        }

    df = pd.DataFrame(all_rows)
    return df, vendor_meta


def coverage_summary(df: pd.DataFrame, rfx_spec: dict) -> pd.DataFrame:
    total_items = len(rfx_spec["line_items"])
    rows = []
    for vendor, g in df.groupby("vendor_name"):
        matched = g["item_code"].notna().sum()
        priced = g["unit_price_inr"].notna().sum()
        needs_review = g["needs_buyer_review"].sum()
        carried = g["carried_forward"].sum()
        rows.append({
            "vendor_name": vendor,
            "lines_matched": matched,
            "lines_total_rfx": total_items,
            "coverage_pct": round(100 * matched / total_items, 1),
            "lines_priced": priced,
            "lines_needing_review": int(needs_review),
            "lines_carried_forward": int(carried),
        })
    return pd.DataFrame(rows).sort_values("coverage_pct", ascending=False)
