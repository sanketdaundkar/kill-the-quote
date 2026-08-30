# Kill the Quote Spreadsheet - Aerchain Take-Home

An AI-powered RFx co-pilot + vendor response extraction + analyst chat, built for the Aerchain
"Kill the Quote Spreadsheet" assignment.

See `decisions.md` for what was built and why.

## Structure
```
streamlit_app.py              # main app (4 tabs: draft RFx, vendor responses, comparison, analyst chat)
app/generation/rfx_copilot.py # conversational RFx drafting
app/extraction/               # file readers + Claude-powered extraction into structured quotes
app/comparison/normalize.py   # currency/unit normalization, gap-fill, comparison table
app/chat/analyst.py           # natural-language analyst chat with a sandboxed pandas tool
data/rfx/rfx_spec.json        # the demo RFx (IT hardware, 30 lines, 5 vendors invited)
data/vendor_responses/        # 5 fabricated vendor responses (xlsx/pdf/docx/jpg/txt)
data/extractions/             # extraction results land here (JSON, one per vendor) once you run it
scripts/                      # generators used to fabricate the demo dataset (for reference)
```

## Run it locally
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # or paste it into the sidebar once the app is running
streamlit run streamlit_app.py
```
Then in the app: Tab 1 -> "Use the pre-loaded demo RFx" -> Tab 2 -> "Run extraction on all
vendor responses" -> Tab 3 for the comparison table -> Tab 4 to ask it questions.

### Getting vendor files into the system
Tab 2 has a real `st.file_uploader` - drop in Excel/PDF/Word/image/txt/email files and they're
saved to `data/uploaded_vendor_responses/` and added to the working set alongside the 5 demo
fixtures. Extraction runs over whatever's in the working set (demo + uploaded) at click time.
This is the "buyer gets vendor responses into the system" path stood in for actual inbound
email parsing, which is stubbed per the brief's "fake the SMTP server if you like."

## Deploy (for the live link)
Easiest path is Streamlit Community Cloud:
1. Push this folder to a GitHub repo.
2. https://share.streamlit.io -> New app -> point at `streamlit_app.py`.
3. Add `ANTHROPIC_API_KEY` under the app's Secrets.
4. Deploy - you'll get a public `*.streamlit.app` link.

`packages.txt` (poppler-utils) is already included so Streamlit Cloud installs it automatically -
that's what renders actual PDF pages as images in the vendor preview, not just extracted text.

## Notes
- All AI loops are real (extraction, RFx drafting, analyst chat all call the Anthropic API
  live) - nothing is hardcoded or replayed. Vendor *outreach* (actually emailing RFxs and
  receiving responses) is stubbed per the brief; the 5 vendor files are pre-loaded fixtures.
- Extraction results are cached to `data/extractions/*.json` so you don't burn API calls
  re-running the demo repeatedly - delete them (or click "Run extraction" again) to refresh.
