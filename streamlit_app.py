import json
import os
import re
import subprocess
import sys
import tempfile
import traceback

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from app.extraction.extract import extract_vendor_response
from app.extraction.file_readers import read_docx, read_pdf
from app.extraction.url_fetch import fetch_vendor_file_from_url, FetchError
from app.comparison.normalize import build_comparison_table, coverage_summary, load_rfx_spec
from app.chat.analyst import ask_analyst
from app.generation.rfx_copilot import copilot_turn
from app.generation.rfx_docx import build_rfx_docx_bytes

st.set_page_config(page_title="Aerchain - RFx Copilot", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
VENDOR_DIR = os.path.join(DATA_DIR, "vendor_responses")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploaded_vendor_responses")
EXTRACTION_DIR = os.path.join(DATA_DIR, "extractions")
RFX_SPEC_PATH = os.path.join(DATA_DIR, "rfx", "rfx_spec.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)

VENDOR_FILES = {
    "vendor_a_techsource.xlsx": "TechSource Distributors - Excel, their own template",
    "vendor_b_globalit.pdf": "Global IT Solutions - PDF letterhead, USD, discount in footnote",
    "vendor_c_primehardware.docx": "Prime Hardware Co - Word doc, per-box pricing for accessories",
    "vendor_d_quicksupply_ratecard.jpg": "QuickSupply Traders - photographed rate card, angled",
    "vendor_e_apex_email.txt": "Apex Systems - plain email, 'rest same as last year'",
}

ALLOWED_UPLOAD_TYPES = ["xlsx", "pdf", "docx", "jpg", "jpeg", "png", "txt", "eml"]


def _plain_payment_terms(value: str) -> str:
    """Rewrites a payment-terms string in plain language for display - 'Net 45'
    becomes 'Invoice is due 45 days after the invoice date', etc. If the value
    doesn't match a known pattern, show it as-is rather than forcing an
    awkward paraphrase."""
    match = re.search(r"net[\s-]*(\d+)", value, re.IGNORECASE)
    if match:
        days = match.group(1)
        basis = "delivery" if "delivery" in value.lower() else "the invoice date"
        return f"Invoice is due {days} days after {basis}"
    return value


def list_uploaded_files():
    if not os.path.exists(UPLOAD_DIR):
        return []
    return sorted(f for f in os.listdir(UPLOAD_DIR) if not f.startswith("."))


def all_vendor_sources():
    """Returns {filename: (full_path, is_uploaded)} for demo fixtures + anything uploaded.
    Demo fixtures the user has hidden this session are excluded."""
    hidden = st.session_state.get("hidden_demo_files", set())
    sources = {
        fname: (os.path.join(VENDOR_DIR, fname), False)
        for fname in VENDOR_FILES if fname not in hidden
    }
    for fname in list_uploaded_files():
        sources[fname] = (os.path.join(UPLOAD_DIR, fname), True)
    return sources


def hide_demo_file(fname: str):
    """Removes a bundled demo vendor from the working set for this session
    (not deleted from disk - it's a shared fixture, not the user's file) and
    clears any cached extraction for it so it doesn't linger in comparisons."""
    hidden = st.session_state.setdefault("hidden_demo_files", set())
    hidden.add(fname)
    extraction_path = os.path.join(EXTRACTION_DIR, os.path.splitext(fname)[0] + ".json")
    if os.path.exists(extraction_path):
        os.remove(extraction_path)


def render_api_key_sidebar():
    """Renders the sidebar API key widget exactly once per run - call this
    only from main(). Everywhere else, use has_api_key() to just check.

    If a key is already available (e.g. via Streamlit Cloud secrets, which
    are exposed as env vars automatically), this renders nothing at all -
    no point showing an API key box to someone who isn't meant to touch it.
    Only falls back to an input field for local dev without secrets set."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return
    with st.sidebar:
        st.markdown("### Anthropic API key")
        entered = st.text_input("ANTHROPIC_API_KEY", value="", type="password",
                                 key="anthropic_api_key_input",
                                 help="Needed for extraction, RFx co-pilot, and the analyst chat.")
        if entered:
            os.environ["ANTHROPIC_API_KEY"] = entered


def has_api_key():
    """Read-only check - safe to call from anywhere, never renders a widget."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", ""))


def load_or_init_rfx():
    if "rfx_spec" not in st.session_state:
        st.session_state.rfx_spec = load_rfx_spec()
    return st.session_state.rfx_spec


def page_rfx_copilot():
    st.header("1. Draft the RFx")
    st.caption("Chat with the assistant on the left to build your own request for quote, or "
               "click the button on the right to load a ready-made example and skip ahead.")

    rfx = load_or_init_rfx()

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Co-pilot chat")
        if "copilot_history" not in st.session_state:
            st.session_state.copilot_history = []
            st.session_state.copilot_draft = None

        for turn in st.session_state.copilot_history:
            if turn["role"] == "user" and isinstance(turn["content"], str):
                with st.chat_message("user"):
                    st.write(turn["content"])
            elif turn["role"] == "assistant":
                text = "".join(b.text for b in turn["content"] if getattr(b, "type", None) == "text") \
                    if not isinstance(turn["content"], str) else turn["content"]
                if text:
                    with st.chat_message("assistant"):
                        st.write(text)

        prompt = st.chat_input("e.g. 'I need to refresh IT hardware for a 400-seat office'")
        if prompt:
            if not has_api_key():
                st.error("Add your ANTHROPIC_API_KEY in the sidebar first.")
            else:
                with st.spinner("Thinking..."):
                    try:
                        reply, draft, history = copilot_turn(
                            prompt, st.session_state.copilot_history, st.session_state.copilot_draft
                        )
                        st.session_state.copilot_history = history
                        if draft:
                            st.session_state.copilot_draft = draft
                        st.rerun()
                    except Exception as e:
                        st.error(f"Co-pilot error: {e}")

    with col2:
        st.subheader("Current draft")
        draft_to_show = st.session_state.get("copilot_draft") or rfx
        st.markdown(f"**{draft_to_show.get('title', rfx.get('title'))}**")
        category = draft_to_show.get("category")
        currency = draft_to_show.get("currency_base") or rfx.get("currency_base")
        meta_bits = [b for b in [category, currency] if b]
        if meta_bits:
            st.caption(" · ".join(meta_bits))
        st.write(draft_to_show.get("scope", rfx.get("scope")))

        li = draft_to_show.get("line_items", rfx.get("line_items"))
        st.markdown(f"**Line items** ({len(li)})")
        st.dataframe(pd.DataFrame(li), use_container_width=True, height=300)

        terms = draft_to_show.get("commercial_terms") or rfx.get("commercial_terms") or {}
        if any(terms.values()):
            st.markdown("**Commercial terms**")
            display_values = {
                "payment_terms": _plain_payment_terms(terms.get("payment_terms", "")),
                "delivery_location": terms.get("delivery_location"),
                "delivery_window": terms.get("delivery_window"),
                "warranty_minimum": terms.get("warranty_minimum"),
            }
            labels = {
                "payment_terms": "Payment terms",
                "delivery_location": "Delivery location",
                "delivery_window": "Delivery window",
                "warranty_minimum": "Minimum warranty",
            }
            for key, label in labels.items():
                if terms.get(key):
                    st.write(f"- {label}: {display_values[key]}")

        questionnaire = draft_to_show.get("questionnaire") or rfx.get("questionnaire") or []
        if questionnaire:
            st.markdown(f"**Vendor questionnaire** ({len(questionnaire)})")
            for q in questionnaire:
                qid = q.get("q_id", "")
                qtext = q.get("question", "")
                st.write(f"{qid}. {qtext}" if qid else f"- {qtext}")

        if st.button("Use the pre-loaded demo RFx for this walkthrough", type="primary"):
            st.session_state.rfx_spec = load_rfx_spec()
            st.session_state.copilot_draft = None
            st.success("Loaded the demo RFx: IT Hardware Refresh, 30 lines, 5 vendors invited.")

        st.divider()
        try:
            docx_bytes = build_rfx_docx_bytes(draft_to_show)
            docx_title = (draft_to_show.get("title") or "RFx").replace(" ", "_")
            st.download_button(
                "Download RFx as Word doc (.docx)",
                data=docx_bytes,
                file_name=f"{docx_title}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.warning(f"Couldn't build the Word doc yet: {e}")


MIME_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".txt": "text/plain", ".eml": "message/rfc822",
}


def render_pdf_pages(path: str, max_pages: int = 5):
    """Renders actual PDF pages as images (true visual preview, not just
    extracted text) via poppler's pdftoppm. Falls back silently if poppler
    isn't installed in this environment - text extraction still covers it."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            prefix = os.path.join(tmpdir, "page")
            subprocess.run(
                ["pdftoppm", "-jpeg", "-r", "110", "-l", str(max_pages), path, prefix],
                check=True, capture_output=True, timeout=30,
            )
            pages = sorted(f for f in os.listdir(tmpdir) if f.startswith("page"))
            for pg in pages:
                st.image(os.path.join(tmpdir, pg))
            return len(pages)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def render_vendor_preview(path: str, ext: str, fname: str, key_prefix: str = "main"):
    """Show the vendor file's actual content, not just a filename - the same
    raw text/tables/pixels the extraction model reads, so a buyer can
    sanity-check it themselves rather than trusting extraction blind.

    key_prefix disambiguates the download button's widget key when this same
    file is previewed from more than one tab in the same script run (e.g.
    Vendor Responses and Comparison both preview the same file) - Streamlit
    runs every tab's body every rerun regardless of which tab is visible, so
    without this two previews of the same fname would collide on one key."""
    with open(path, "rb") as f:
        raw_bytes = f.read()
    st.download_button(
        "Download original file", data=raw_bytes, file_name=fname,
        mime=MIME_TYPES.get(ext, "application/octet-stream"), key=f"dl_{key_prefix}_{fname}",
    )

    if ext in (".jpg", ".jpeg", ".png"):
        st.image(path)
    elif ext in (".txt", ".eml"):
        st.text(open(path, errors="ignore").read())
    elif ext == ".xlsx":
        try:
            sheets = pd.read_excel(path, sheet_name=None, header=None)
            for sheet_name, sheet_df in sheets.items():
                st.caption(f"Sheet: {sheet_name}")
                st.dataframe(sheet_df, use_container_width=True,
                             height=min(420, 36 * (len(sheet_df) + 1)))
        except Exception as e:
            st.warning(f"Couldn't render a spreadsheet preview ({e}). "
                       "Extraction can usually still read it - try running extraction below.")
    elif ext == ".docx":
        try:
            st.text(read_docx(path))
        except Exception as e:
            st.warning(f"Couldn't render a document preview ({e}). "
                       "Extraction can usually still read it - try running extraction below.")
    elif ext == ".pdf":
        n_rendered = render_pdf_pages(path)
        if n_rendered is None:
            st.caption("Visual page rendering unavailable in this environment - showing extracted text instead.")
            try:
                st.text(read_pdf(path))
            except Exception as e:
                st.warning(f"Couldn't render a PDF preview ({e}). "
                           "Extraction can usually still read it - try running extraction below.")
        else:
            with st.expander("Extracted text (what the extraction model actually reads)"):
                try:
                    st.text(read_pdf(path))
                except Exception as e:
                    st.warning(f"Couldn't extract text ({e}).")
    else:
        st.write(f"No preview available for {ext} files ({os.path.getsize(path)/1024:.0f} KB) - use the download button above.")


def remove_uploaded_file(fname: str):
    """Deletes an uploaded vendor file and any cached extraction result for it,
    so a removed vendor doesn't linger as stale data in the comparison table."""
    path = os.path.join(UPLOAD_DIR, fname)
    if os.path.exists(path):
        os.remove(path)
    extraction_path = os.path.join(EXTRACTION_DIR, os.path.splitext(fname)[0] + ".json")
    if os.path.exists(extraction_path):
        os.remove(extraction_path)


def page_vendor_responses():
    st.header("2. Vendor responses")
    st.caption("Vendors reply however they like - no shared template required. Upload real "
               "vendor files below (or paste a link) to add them to, or replace, the demo set.")

    st.subheader("Upload vendor responses")
    uploaded = st.file_uploader(
        "Drop vendor quote files here - Excel, PDF, Word, image, or plain text/email",
        type=ALLOWED_UPLOAD_TYPES, accept_multiple_files=True,
        help="Each file is treated as one vendor's response. Filename is used as the vendor label "
             "until extraction reads the vendor's actual name out of the document.",
    )
    if uploaded:
        for uf in uploaded:
            dest = os.path.join(UPLOAD_DIR, uf.name)
            with open(dest, "wb") as f:
                f.write(uf.getbuffer())
        st.success(f"Saved {len(uploaded)} file(s). They'll be included in extraction below.")

    with st.expander("Or add one via link (Google Doc/Sheet, or a direct file link)"):
        st.caption(
            "Works with public links only - no sign-in flow here. For a Google Doc/Sheet, set "
            "sharing to 'Anyone with the link can view' first. A private link, or one that needs "
            "you to be logged into an email account, won't work - download that file yourself "
            "and use the upload box above instead."
        )
        link_col, btn_col = st.columns([4, 1])
        with link_col:
            link_url = st.text_input(
                "Vendor response link", key="vendor_link_input", label_visibility="collapsed",
                placeholder="https://docs.google.com/document/d/... or a direct file link",
            )
        with btn_col:
            add_link_clicked = st.button("Add link")
        if add_link_clicked and link_url:
            with st.spinner("Fetching..."):
                try:
                    fname, content = fetch_vendor_file_from_url(link_url)
                    dest = os.path.join(UPLOAD_DIR, fname)
                    with open(dest, "wb") as f:
                        f.write(content)
                    st.success(f"Added {fname} from the link. It'll be included in extraction below.")
                except FetchError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Couldn't add that link: {e}")

    uploaded_existing = list_uploaded_files()
    if uploaded_existing:
        cols = st.columns([4, 1])
        with cols[0]:
            st.caption(f"{len(uploaded_existing)} uploaded file(s) currently in the working set - "
                       "remove individual ones below, or clear them all here.")
        with cols[1]:
            if st.button("Clear all uploads"):
                for fname in uploaded_existing:
                    remove_uploaded_file(fname)
                st.rerun()

    st.divider()
    st.subheader("Working set")
    st.caption("Preview shows the raw content exactly as extraction will read it - "
               "check it yourself before trusting the comparison.")

    hidden_demo = st.session_state.get("hidden_demo_files", set())
    if hidden_demo:
        cols = st.columns([4, 1])
        with cols[0]:
            st.caption(f"{len(hidden_demo)} demo vendor(s) removed from the working set this session.")
        with cols[1]:
            if st.button("Restore demo vendors"):
                st.session_state.hidden_demo_files = set()
                st.rerun()

    sources = all_vendor_sources()
    for fname, (path, is_uploaded) in sources.items():
        label = f"{fname}" + (" - uploaded" if is_uploaded else f" - {VENDOR_FILES.get(fname, '')}")
        with st.expander(label):
            if is_uploaded:
                if st.button("Remove this vendor response", key=f"remove_{fname}"):
                    remove_uploaded_file(fname)
                    st.rerun()
            else:
                if st.button("Remove from working set", key=f"hide_{fname}",
                              help="Removes this demo vendor for this session. It isn't deleted "
                                   "from disk - you can bring it back with 'Restore demo vendors' above."):
                    hide_demo_file(fname)
                    st.rerun()
            ext = os.path.splitext(fname)[1].lower()
            render_vendor_preview(path, ext, fname)

    st.divider()
    already_extracted = {
        fname for fname in sources
        if os.path.exists(os.path.join(EXTRACTION_DIR, os.path.splitext(fname)[0] + ".json"))
    }
    pending = [fname for fname in sources if fname not in already_extracted]

    col1, col2 = st.columns([2, 1])
    with col1:
        if pending:
            label = f"Run extraction on {len(pending)} pending vendor response(s)"
        else:
            label = f"Re-run extraction on all {len(sources)} vendor response(s)"
        run_clicked = st.button(label, type="primary")
    with col2:
        force_all = st.checkbox("Force re-run all", value=not pending,
                                 help="Off by default once some vendors have already succeeded, "
                                      "so a retry after a partial failure doesn't re-spend API calls "
                                      "on vendors that already extracted cleanly.")

    if run_clicked:
        if not has_api_key():
            st.error("Add your ANTHROPIC_API_KEY in the sidebar first.")
        else:
            rfx = load_or_init_rfx()
            to_run = list(sources.items()) if force_all else [
                (fname, val) for fname, val in sources.items() if fname not in already_extracted
            ]
            if not to_run:
                st.info("Nothing to extract - every vendor already has a cached result. "
                        "Check 'Force re-run all' to redo them anyway.")
            else:
                progress = st.progress(0.0, text="Starting extraction...")
                errors = []
                for i, (fname, (path, _)) in enumerate(to_run):
                    progress.progress(i / len(to_run), text=f"Extracting {fname}...")
                    try:
                        result = extract_vendor_response(path, rfx)
                        out_path = os.path.join(EXTRACTION_DIR, os.path.splitext(fname)[0] + ".json")
                        with open(out_path, "w") as f:
                            json.dump(result, f, indent=2)
                    except Exception as e:
                        errors.append((fname, str(e), traceback.format_exc()))
                progress.progress(1.0, text="Done.")
                if errors:
                    for fname, err, tb in errors:
                        st.error(f"{fname}: {err}")
                    ok_count = len(to_run) - len(errors)
                    if ok_count:
                        st.success(f"{ok_count} of {len(to_run)} succeeded. Re-click above to retry "
                                   "just the failed one(s) - already-succeeded vendors won't be re-run.")
                else:
                    st.success(f"Extraction complete for all {len(to_run)} vendor(s). See the Comparison tab.")

    existing = [f for f in os.listdir(EXTRACTION_DIR) if f.endswith(".json")] if os.path.exists(EXTRACTION_DIR) else []
    if existing:
        st.caption(f"{len(existing)} extraction result(s) cached on disk. Re-run above to refresh.")
        pick = st.selectbox("Inspect a raw extraction result", ["(none)"] + existing)
        if pick != "(none)":
            with open(os.path.join(EXTRACTION_DIR, pick)) as f:
                st.json(json.load(f))


def _questionnaire_badge(qa: dict) -> str:
    """Turns a vendor's questionnaire answers into a simple Pass/Partial/Fail
    read. Deliberately simple and stated plainly rather than buried - this
    is exactly the kind of judgment call a buyer should be able to
    override: Fail if any answer contains a clear 'no', Partial if
    anything's unanswered, Pass otherwise."""
    if not qa:
        return "No answers"
    answered = {k: v for k, v in qa.items() if v}
    if not answered:
        return "No answers"
    has_no = any(re.search(r"(?<![a-z])no(?![a-z])", str(v).lower()) for v in answered.values())
    if has_no:
        return "Fail"
    if len(answered) < len(qa):
        return "Partial"
    return "Pass"


def _freight_label(text: str) -> str:
    """Classifies freight terms into Included/Extra for the compact summary
    row. Falls back to the vendor's own words (truncated) when the phrasing
    doesn't clearly say either way, rather than forcing a guess."""
    if not text:
        return "-"
    t = text.lower()
    if "includ" in t:
        return "Included"
    if "extra" in t or "exclud" in t or "excl" in t:
        return "Extra"
    return text if len(text) <= 18 else text[:15] + "..."


def page_comparison():
    st.header("3. Side-by-side comparison")
    st.caption("Every vendor's response normalized to the same lines, same units, same "
               "currency - so 'cheapest' means something you can actually act on.")
    existing = [f for f in os.listdir(EXTRACTION_DIR) if f.endswith(".json")] if os.path.exists(EXTRACTION_DIR) else []
    if not existing:
        st.info("Run extraction on the Vendor Responses tab first.")
        return

    rfx = load_or_init_rfx()
    df, vendor_meta = build_comparison_table(EXTRACTION_DIR, rfx)
    if df.empty:
        st.warning("Extraction result(s) on disk don't have any usable line items yet - "
                   "re-run extraction on the Vendor Responses tab.")
        return
    st.session_state.comparison_df = df
    st.session_state.vendor_meta = vendor_meta

    st.subheader("Vendor summary")
    st.caption("Who should you even be looking at, before you scroll into the line-item detail.")

    vendors = sorted(df["vendor_name"].unique())
    total_rfx_lines = len(rfx["line_items"])
    summary = {}
    for vendor in vendors:
        vdf = df[df["vendor_name"] == vendor]
        meta = vendor_meta.get(vendor) or {}
        terms = meta.get("commercial_terms") or {}
        qa = meta.get("questionnaire_answers") or {}
        badge = _questionnaire_badge(qa)
        conf = vdf["match_confidence"].dropna()

        summary[vendor] = {
            "RFx lines quoted": f"{vdf['item_code'].nunique()}/{total_rfx_lines}",
            "Quality pass": "✅" if badge == "Pass" else "❌",
            "Lead time": terms.get("delivery_weeks") or "-",
            "Freight": _freight_label(terms.get("freight_terms")),
            "Quote validity": terms.get("quote_validity") or "-",
            "Avg. confidence": f"{conf.mean() * 100:.0f}%" if len(conf) else "-",
            "Review required": int((vdf["needs_buyer_review"] == True).sum()),
        }

    summary_df = pd.DataFrame(summary)  # rows = metrics, columns = vendors (already in this shape)
    summary_df = summary_df[vendors]
    st.dataframe(summary_df, use_container_width=True)
    st.caption("'Quality pass' is ✅ only if every questionnaire answer is in and none is a clear "
               "'no' - partial or unanswered questionnaires show as ❌ too, so nothing incomplete "
               "gets credit it hasn't earned. Override it yourself if you'd weigh it differently. "
               "'Lead time' and 'Quote validity' show '-' when a vendor didn't state one - that's "
               "a real gap in their response, not a missing feature here.")

    st.subheader("Coverage")
    st.caption("How much of the RFx each vendor actually quoted - a gap here is worth catching "
               "now, not on day nine when the VP asks why a vendor's total looks light.")
    st.dataframe(coverage_summary(df, rfx), use_container_width=True)

    st.subheader("Full line-item comparison")
    show_flagged_only = st.checkbox("Show only lines flagged for buyer review")
    view = df[df["needs_buyer_review"] == True] if show_flagged_only else df
    st.dataframe(
        view[["vendor_name", "item_code", "rfx_description", "qty_quoted", "unit_price_inr",
              "unit_basis", "carried_forward", "needs_buyer_review", "review_reason"]]
        .sort_values(["item_code", "vendor_name"]),
        use_container_width=True, height=500,
    )

    st.subheader("Cheapest eligible vendor per line")
    priced = df[df["unit_price_inr"].notna()]
    if not priced.empty:
        cheapest = priced.loc[priced.groupby("item_code")["unit_price_inr"].idxmin()]
        st.dataframe(
            cheapest[["item_code", "rfx_description", "vendor_name", "unit_price_inr", "needs_buyer_review"]]
            .sort_values("item_code"),
            use_container_width=True, height=400,
        )
        total = (cheapest["unit_price_inr"] * cheapest["qty_requested"]).sum()
        flagged_value = (cheapest[cheapest["needs_buyer_review"]]["unit_price_inr"] *
                          cheapest[cheapest["needs_buyer_review"]]["qty_requested"]).sum()
        st.metric("Total value if awarded cheapest-per-line (no eligibility filter)", f"Rs {total:,.0f}")
        if flagged_value:
            st.caption(f"Rs {flagged_value:,.0f} of that total sits on lines flagged for buyer review - "
                       "check the Ask the Analyst tab before treating this as final.")

    st.subheader("Vendor questionnaire, terms, and source documents")
    st.caption("Each vendor's answers and the original file they sent, right next to the numbers "
               "above - so you don't have to jump tabs to sanity-check where a figure came from.")
    sources = all_vendor_sources()
    rfx_questionnaire = {q["q_id"]: q["question"] for q in rfx.get("questionnaire", [])}

    for vendor, meta in vendor_meta.items():
        with st.expander(vendor):
            qa = meta.get("questionnaire_answers") or {}
            if any(qa.values()):
                qa_rows = [
                    {"Question": rfx_questionnaire.get(qid, qid), "Answer": ans or "(not addressed)"}
                    for qid, ans in qa.items()
                ]
                st.table(pd.DataFrame(qa_rows))
            else:
                st.caption("No questionnaire answers extracted for this vendor.")

            terms = meta.get("commercial_terms") or {}
            if any(terms.values()):
                st.markdown("**Commercial terms**")
                for k, v in terms.items():
                    if v:
                        st.write(f"- {k.replace('_', ' ').title()}: {v}")

            if meta.get("extraction_warnings"):
                st.markdown("**Extraction warnings**")
                for w in meta["extraction_warnings"]:
                    st.caption(f"⚠️ {w}")

            src_fname = meta.get("source_file")
            if src_fname and src_fname in sources:
                st.markdown("**Original document**")
                src_path, _ = sources[src_fname]
                ext = os.path.splitext(src_fname)[1].lower()
                render_vendor_preview(src_path, ext, src_fname, key_prefix="comparison")
            elif src_fname:
                st.caption(f"Original file ({src_fname}) is no longer in the working set - "
                           "it may have been removed or replaced since this extraction ran.")


def page_analyst():
    st.header("4. Ask the analyst")
    st.caption("Natural language over the whole comparison. Try: \"cheapest per line, but only "
               "among vendors who cleared the quality questionnaire\"")

    if "comparison_df" not in st.session_state:
        st.info("Build the comparison table on the Comparison tab first.")
        return

    if "analyst_history" not in st.session_state:
        st.session_state.analyst_history = []
        st.session_state.analyst_display = []

    for role, text in st.session_state.analyst_display:
        with st.chat_message(role):
            st.write(text)

    q = st.chat_input("Ask a question about the vendor comparison...")
    if q:
        if not has_api_key():
            st.error("Add your ANTHROPIC_API_KEY in the sidebar first.")
        else:
            st.session_state.analyst_display.append(("user", q))
            with st.spinner("Analyzing..."):
                try:
                    answer, history = ask_analyst(
                        q, st.session_state.comparison_df, st.session_state.vendor_meta,
                        st.session_state.analyst_history,
                    )
                    st.session_state.analyst_history = history
                    st.session_state.analyst_display.append(("assistant", answer))
                except Exception as e:
                    st.session_state.analyst_display.append(("assistant", f"Error: {e}"))
            st.rerun()


def main():
    st.title("RFx Copilot")
    render_api_key_sidebar()
    tabs = st.tabs(["1. Draft RFx", "2. Vendor Responses", "3. Comparison", "4. Ask the Analyst"])
    with tabs[0]:
        page_rfx_copilot()
    with tabs[1]:
        page_vendor_responses()
    with tabs[2]:
        page_comparison()
    with tabs[3]:
        page_analyst()


if __name__ == "__main__":
    main()
