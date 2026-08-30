"""
Vendor response -> structured quote extraction.

One real LLM call per vendor file. No hardcoding: the model reads whatever
raw text/table dump or image we hand it and has to figure out currency,
unit basis (per-unit vs per-box), which RFx line item each entry maps to,
and what to flag for buyer review. It is told about the RFx line items so
it can match by meaning, not just by code - vendors barely ever reuse our
codes.
"""
import json
import os
from .file_readers import read_vendor_file

import anthropic

MODEL = "claude-sonnet-5"

EXTRACTION_SYSTEM_PROMPT = """You are a procurement document extraction engine. You are given:
1. The buyer's RFx line items (code, description, quantity requested, unit).
2. The RFx questionnaire questions.
3. A raw dump of one vendor's response - this may be a spreadsheet dump, a Word doc dump,
   a PDF text dump, a plain email, or an image of a printed rate card.

Your job: extract every commercial line the vendor quoted, matching each to the closest RFx
line item by meaning (descriptions will rarely match verbatim - vendors reorder, rename,
abbreviate, and use their own catalog language). For each quoted line, determine:
- matched_item_code: the RFx item_code you believe this line corresponds to, or null if you
  genuinely cannot match it to anything in the RFx.
- match_confidence: 0.0-1.0, your honest confidence in that match.
- qty_quoted, unit_price (as a plain number, no currency symbols or commas), currency
  (ISO code, infer from symbols/context if not stated explicitly - e.g. "Rs" or "₹" = INR).
- unit_basis: "per_unit", "per_box", or "unknown". If per_box, also fill box_size (integer
  units per box) so downstream code can normalize to per-unit price. If the vendor's box
  size is ambiguous or not stated, set unit_basis to "unknown" and explain in notes - do not
  guess a box size.
- needs_buyer_review (boolean) and review_reason (string, ONE short sentence, under 20 words)
  whenever: the match confidence is below 0.75, unit_basis is unknown, the vendor's quantity
  quoted differs from what was requested, pricing language is vague (e.g. "same as last year"
  with no number given to you), or anything else a careful category buyer would want to
  double check before trusting this number in a ₹4 crore decision.

Also extract:
- vendor_name, vendor_ref (their quote/reference number if present), quote_date if present.
- questionnaire_answers: map of Q1-Q5 (as defined in the RFx questionnaire) to the vendor's
  answer if you can find it, even if phrased informally in prose - "yes to pretty much
  everything same as before" is a real answer, extract your best interpretation and mark low
  confidence rather than skipping it. Use null if genuinely not addressed at all. Keep each
  answer to a short phrase, not a full quote of the vendor's prose.
- commercial_terms: payment_terms, warranty, freight_terms, delivery_weeks - whatever is
  stated, as short free text (a few words each). Use null for anything not mentioned.
- extraction_warnings: a list of short strings (one short sentence each) for anything unusual
  you noticed reading this document (garbled/skewed text if it's a photo, items you could not
  read at all, footnotes that change the effective price, discounts buried away from the main
  table, etc). Keep this list to the genuinely notable items, not one entry per line.

Do not fabricate numbers. If something is illegible or absent, say so via needs_buyer_review
and a clear review_reason rather than inventing a plausible-looking value.

Keep every string field concise - this is a structured data extraction task, not a narrative.
The "notes" field on a line item should usually be empty ("") unless there's something
specific and useful to flag; when used, keep it to one short clause.

Respond with ONLY valid JSON matching this shape, no markdown fences, no commentary:
{
  "vendor_name": string,
  "vendor_ref": string or null,
  "quote_date": string or null,
  "line_items": [
    {
      "vendor_line_ref": string,
      "description_as_quoted": string,
      "matched_item_code": string or null,
      "match_confidence": number,
      "qty_quoted": number or null,
      "unit_price": number or null,
      "unit_basis": "per_unit" | "per_box" | "unknown",
      "box_size": number or null,
      "currency": string,
      "notes": string,
      "needs_buyer_review": boolean,
      "review_reason": string
    }
  ],
  "questionnaire_answers": {"Q1": string or null, "Q2": string or null, "Q3": string or null, "Q4": string or null, "Q5": string or null},
  "commercial_terms": {"payment_terms": string or null, "warranty": string or null, "freight_terms": string or null, "delivery_weeks": string or null},
  "extraction_warnings": [string]
}
"""


def _client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it before running extraction "
            "(see README.md)."
        )
    return anthropic.Anthropic(api_key=api_key)


def build_user_content(rfx_spec: dict, kind: str, payload):
    rfx_lines_desc = "\n".join(
        f"- {li['item_code']}: {li['description']} (qty requested: {li['qty']} {li['unit']})"
        for li in rfx_spec["line_items"]
    )
    questionnaire_desc = "\n".join(
        f"- {q['q_id']}: {q['question']}" for q in rfx_spec["questionnaire"]
    )
    header = (
        f"RFx Line Items:\n{rfx_lines_desc}\n\n"
        f"RFx Questionnaire:\n{questionnaire_desc}\n\n"
        f"Base currency for this RFx: {rfx_spec['currency_base']}\n\n"
        "Vendor response follows below. Extract per the system instructions."
    )
    if kind == "text":
        return [{"type": "text", "text": header + "\n\n--- VENDOR RESPONSE (raw text dump) ---\n" + payload}]
    elif kind == "image":
        return [
            {"type": "text", "text": header + "\n\nVendor response is the attached image (a photographed rate card - it may be angled/skewed, read it carefully)."},
            {"type": "image", "source": {"type": "base64", "media_type": payload["media_type"], "data": payload["data"]}},
        ]
    raise ValueError(kind)


def extract_vendor_response(file_path: str, rfx_spec: dict) -> dict:
    kind, payload = read_vendor_file(file_path)
    client = _client()
    content = build_user_content(rfx_spec, kind, payload)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text")
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Extraction for {file_path} was cut off before finishing (hit the token limit). "
            f"This usually means the vendor file has more line items or text than expected - "
            f"try again, or increase max_tokens in extract.py if it keeps happening."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Extraction for {file_path} did not return valid JSON: {e}\nRaw: {raw[:500]}")
    data["_source_file"] = os.path.basename(file_path)
    return data


if __name__ == "__main__":
    import sys
    with open("/home/claude/aerchain-rfx/data/rfx/rfx_spec.json") as f:
        rfx = json.load(f)
    result = extract_vendor_response(sys.argv[1], rfx)
    print(json.dumps(result, indent=2))
