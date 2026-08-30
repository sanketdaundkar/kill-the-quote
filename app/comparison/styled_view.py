"""
Builds the styled "cards + grid" comparison view - vendor summary cards up
top (total on the lines every vendor actually has a price for, coverage,
questionnaire pass/fail with the specific reason), then a per-line pricing
grid with the cheapest vendor highlighted per row.

Every number here is computed from the real comparison DataFrame and
vendor_meta - nothing is templated or hardcoded per vendor. HTML is built
here as plain strings and handed to Streamlit via st.markdown(unsafe_allow_html=True)
by the caller, so this module stays testable without a running Streamlit app.
"""
import re

import pandas as pd

QUESTION_LABEL_PREFIXES = ("Do you ", "Can you ", "Are you ", "Will you ")


def short_question_label(qtext: str, max_len: int = 40) -> str:
    qtext = (qtext or "").rstrip("?").strip()
    for prefix in QUESTION_LABEL_PREFIXES:
        if qtext.startswith(prefix):
            qtext = qtext[len(prefix):]
            break
    return qtext if len(qtext) <= max_len else qtext[:max_len].rstrip() + "..."


def questionnaire_detail(qa: dict, rfx_questionnaire: dict) -> tuple[bool, str]:
    """Returns (passed, detail_text). detail_text names the SPECIFIC
    question that failed or is missing, not just a generic Pass/Fail -
    matching what a buyer actually needs to act on a flag."""
    if not qa:
        return False, "no answers"
    answered = {k: v for k, v in qa.items() if v}
    if not answered:
        return False, "no answers"
    for qid, ans in qa.items():
        if ans and re.search(r"(?<![a-z])no(?![a-z])", str(ans).lower()):
            return False, f"no {short_question_label(rfx_questionnaire.get(qid, qid))}"
    missing = [qid for qid, v in qa.items() if not v]
    if missing:
        return False, f"{short_question_label(rfx_questionnaire.get(missing[0], missing[0]))} not addressed"
    return True, "cleared the questionnaire"


def lead_time_display(text: str) -> str:
    if not text:
        return "lead time n/a"
    nums = re.findall(r"\d+", text)
    if len(nums) >= 2:
        return f"{nums[0]}\u2013{nums[1]} lead"
    if len(nums) == 1:
        return f"{nums[0]} lead"
    return (text[:15] + "...") if len(text) > 15 else text


def common_lines_totals(df: pd.DataFrame, vendors: list[str]):
    """Item codes priced by EVERY vendor in `vendors`, and each vendor's
    total over exactly that shared set - so the headline number on each
    card is comparing the same lines, not each vendor's own best-case
    subset."""
    priced = df[df["unit_price_inr"].notna() & df["vendor_name"].isin(vendors)]
    if priced.empty or not vendors:
        return [], {}
    counts = priced.groupby("item_code")["vendor_name"].nunique()
    common_codes = counts[counts == len(vendors)].index.tolist()
    if not common_codes:
        return [], {}
    sub = priced[priced["item_code"].isin(common_codes)]
    totals = (sub.assign(line_value=sub["unit_price_inr"] * sub["qty_requested"])
              .groupby("vendor_name")["line_value"].sum().to_dict())
    return common_codes, totals


def build_vendor_cards(df: pd.DataFrame, vendor_meta: dict, rfx: dict, vendors: list[str]) -> list[dict]:
    total_rfx_lines = len(rfx.get("line_items", []))
    rfx_questionnaire = {q["q_id"]: q["question"] for q in rfx.get("questionnaire", [])}
    common_codes, totals = common_lines_totals(df, vendors)

    cards = []
    for vendor in vendors:
        vdf = df[df["vendor_name"] == vendor]
        meta = vendor_meta.get(vendor) or {}
        qa = meta.get("questionnaire_answers") or {}
        passed, detail = questionnaire_detail(qa, rfx_questionnaire)
        cards.append({
            "vendor": vendor,
            "total_on_common_lines": totals.get(vendor),
            "common_line_count": len(common_codes),
            "coverage": vdf["item_code"].nunique(),
            "total_rfx_lines": total_rfx_lines,
            "questionnaire_passed": passed,
            "questionnaire_detail": detail,
        })
    return cards


def build_line_grid(df: pd.DataFrame, rfx: dict, vendors: list[str], excluded: set) -> list[dict]:
    """One row per RFx line item, with each vendor's price (or a reason
    there isn't one) and whether that vendor is the cheapest on this line
    among vendors who actually quoted it - excluded vendors' real quotes
    still count as data, they're just visually deprioritized."""
    rows = []
    for li in rfx.get("line_items", []):
        code = li["item_code"]
        line_df = df[df["item_code"] == code]
        priced = line_df[line_df["unit_price_inr"].notna()]
        lowest_vendor = priced.loc[priced["unit_price_inr"].idxmin(), "vendor_name"] if not priced.empty else None

        cells = {}
        for vendor in vendors:
            vrow = line_df[line_df["vendor_name"] == vendor]
            if vrow.empty or pd.isna(vrow.iloc[0]["unit_price_inr"]):
                cells[vendor] = {
                    "quoted": False,
                    "excluded": vendor in excluded,
                }
            else:
                r = vrow.iloc[0]
                cells[vendor] = {
                    "quoted": True,
                    "excluded": False,
                    "price_inr": r["unit_price_inr"],
                    "currency_native": r["currency_native"],
                    "price_native": r["unit_price_native"],
                    "is_lowest": vendor == lowest_vendor,
                }
        rows.append({
            "item_code": code,
            "description": li["description"],
            "unit": li.get("unit", "unit"),
            "qty": li["qty"],
            "cells": cells,
        })
    return rows


# --- HTML rendering -------------------------------------------------------

_CARD_CSS = """
<style>
.rfx-card-row { display: flex; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }
.rfx-card { background: #EDE6D6; border-radius: 10px; padding: 16px 18px; flex: 1 1 180px; min-width: 170px; }
.rfx-card.rfx-card-fail { background: #F2ECE0; opacity: 0.72; }
.rfx-card-name { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: #6b6558; margin-bottom: 6px; }
.rfx-card-total { font-size: 22px; font-weight: 700; color: #2a2620; margin-bottom: 4px; }
.rfx-card-meta { font-size: 12px; color: #6b6558; margin-bottom: 8px; }
.rfx-card-status-pass { font-size: 12px; color: #2f6f4f; }
.rfx-card-status-fail { font-size: 12px; color: #a13f3f; }
.rfx-grid-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.rfx-grid-table th { text-align: right; padding: 8px 10px; background: #EDE6D6; font-size: 11px;
  letter-spacing: 0.04em; text-transform: uppercase; color: #6b6558; }
.rfx-grid-table th.rfx-line-col { text-align: left; }
.rfx-grid-table td { padding: 10px; border-top: 1px solid #e5e1d6; text-align: right; vertical-align: top; }
.rfx-grid-table td.rfx-line-col { text-align: left; }
.rfx-line-desc { font-weight: 600; }
.rfx-line-meta { font-size: 11px; color: #8a8474; }
.rfx-cell-lowest { background: #E4EEE1; font-weight: 700; }
.rfx-cell-lowest-tag { font-size: 10px; color: #2f6f4f; display: block; }
.rfx-cell-usd { font-size: 11px; color: #8a8474; display: block; }
.rfx-cell-empty { color: #b3ada0; font-style: italic; background:
  repeating-linear-gradient(45deg, #f5f2ea, #f5f2ea 6px, #ece7da 6px, #ece7da 12px); }
.rfx-cell-excluded { color: #b3ada0; font-style: italic; }
</style>
"""


def render_cards_html(cards: list[dict]) -> str:
    parts = [_CARD_CSS, '<div class="rfx-card-row">']
    for c in cards:
        cls = "rfx-card" if c["questionnaire_passed"] else "rfx-card rfx-card-fail"
        total_display = f"Rs {c['total_on_common_lines']:,.0f}" if c["total_on_common_lines"] else "n/a"
        common_note = (f"on the {c['common_line_count']} common line(s)" if c["common_line_count"]
                        else "no lines common to all vendors")
        status_cls = "rfx-card-status-pass" if c["questionnaire_passed"] else "rfx-card-status-fail"
        status_icon = "&#10003;" if c["questionnaire_passed"] else "&#10007;"
        parts.append(
            f'<div class="{cls}">'
            f'<div class="rfx-card-name">{c["vendor"]}</div>'
            f'<div class="rfx-card-total">{total_display}</div>'
            f'<div class="rfx-card-meta">{common_note} &middot; {c["coverage"]}/{c["total_rfx_lines"]} priced</div>'
            f'<div class="{status_cls}">{status_icon} {c["questionnaire_detail"]}</div>'
            f'</div>'
        )
    parts.append('</div>')
    return "".join(parts)


def render_grid_html(rows: list[dict], vendors: list[str], vendor_headers: dict) -> str:
    parts = ['<table class="rfx-grid-table"><thead><tr><th class="rfx-line-col">Line</th><th>Qty</th>']
    for vendor in vendors:
        parts.append(f'<th>{vendor_headers.get(vendor, vendor)}</th>')
    parts.append('</tr></thead><tbody>')

    for row in rows:
        parts.append(
            '<tr><td class="rfx-line-col">'
            f'<div class="rfx-line-desc">{row["item_code"]} &middot; {row["description"]}</div>'
            f'<div class="rfx-line-meta">{row["unit"]}</div>'
            f'</td><td>{row["qty"]}</td>'
        )
        for vendor in vendors:
            cell = row["cells"][vendor]
            if not cell["quoted"]:
                if cell["excluded"]:
                    parts.append('<td class="rfx-cell-excluded">excluded by your call</td>')
                else:
                    parts.append('<td class="rfx-cell-empty">not quoted</td>')
                continue
            cls = "rfx-cell-lowest" if cell["is_lowest"] else ""
            usd_line = ""
            if cell["currency_native"] and cell["currency_native"] != "INR":
                usd_line = (f'<span class="rfx-cell-usd">{cell["currency_native"]} '
                            f'{cell["price_native"]:,.0f}</span>')
            lowest_tag = '<span class="rfx-cell-lowest-tag">lowest</span>' if cell["is_lowest"] else ""
            parts.append(
                f'<td class="{cls}">Rs {cell["price_inr"]:,.0f}{lowest_tag}{usd_line}</td>'
            )
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return "".join(parts)
