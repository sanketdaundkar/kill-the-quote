# Decisions - Kill the Quote Spreadsheet

## Compliance with the brief's one rule
The brief's rule is: stub the plumbing, but the AI loops must be real - don't fake extraction,
don't fake reasoning, don't hardcode answers to demo questions. Here's exactly where that line
sits in this build:

**Real (live Claude API calls, every time, no shortcuts):**
- **Extraction** (`app/extraction/extract.py`) - one live call per vendor file. Reads whatever
  raw text/table/image the file actually contains; nothing about the output is templated or
  keyed off filename. Vision is used for the photographed rate card, not OCR-then-fake.
- **RFx co-pilot** (`app/generation/rfx_copilot.py`) - drafts the RFx through genuine
  conversation via tool use; nothing is pre-written.
- **Analyst chat** (`app/chat/analyst.py`) - answers are computed by the model writing and
  running real pandas code against the actual comparison table on every question, including
  the brief's own example question ("cheapest per line, only among vendors who cleared the
  quality questionnaire") - there is no special-cased handler for that or any other question.
  Verified this isn't a coincidence: state persists across tool calls within a turn so the
  model can build up genuinely multi-step analysis rather than needing a canned path.

**Stubbed (exactly what the brief invites):**
- **Vendor outreach.** The brief explicitly says "fake the SMTP server if you like" - no RFx
  is actually emailed out, and no inbox is polled for replies. Vendor responses arrive via a
  file upload widget instead. This is the transport layer, not the intelligence layer.

Normalization (`app/comparison/normalize.py` - currency conversion, per-box math, matching)
is deterministic code, not an LLM call, and that's intentional: arithmetic shouldn't be left
to a model to (possibly) get right. The three loops above are where the actual reasoning work
happens, and those are the ones required to be real.

## Compliance with the "single side-by-side comparison" requirement
The brief specifies the comparison must land everything in one view - same lines, same units,
same currency - with questionnaire answers and attached docs alongside the numbers. Checked
each clause against the actual code, not just design intent:
- **Same lines**: matched via `matched_item_code`, not string equality - vendors never reuse
  our item codes, so this has to be semantic matching, not a join.
- **Same units**: per-box quotes are converted to per-unit using each vendor's own stated box
  size (`app/comparison/normalize.py`).
- **Same currency**: USD is converted to INR (`unit_price_inr`), FX rate hardcoded and
  disclosed rather than a live call - see below.
- **Questionnaire answers alongside the numbers**: rendered as a real per-question table (the
  actual question text, not just "Q1"), not a raw JSON dump - on the same Comparison tab as
  the numeric table, one expander per vendor.
- **Attached docs alongside the numbers**: added in an earlier pass (each vendor's expander on
  the Comparison tab included their actual original document), then removed at the user's
  request to keep that tab focused on the questionnaire/terms table - source documents remain
  fully viewable on the Vendor Responses tab instead.

## Compliance with "text answers, tables, charts, exports"
The brief's description of the analyst layer names four output forms explicitly. Checked each
against the code, found two that didn't exist at all and one that was faked:
- **Text answers**: real, always was.
- **Tables**: was faked - a DataFrame result got `.to_string()`'d into plain text that looked
  tabular but wasn't. Fixed: `run_pandas_query` results that are DataFrames now render as a
  real `st.dataframe` below the answer, with its own CSV export button.
- **Charts**: didn't exist - there was no way for the model to produce one, ever. Added a
  second tool, `render_chart`, that the model calls explicitly (bar or line) when a chart
  would help more than prose - never auto-triggered by keyword-matching the question, so it's
  the model's judgment call, not a heuristic guessing what "looks chart-worthy."
- **Exports**: didn't exist - fixed with a "Export full comparison to CSV" button plus a
  per-answer "Export this table to CSV" button whenever a query returns tabular data.

## What I built
An end-to-end flow for one category (IT hardware, 30 line items, 5 vendors, real messiness):
an RFx co-pilot that drafts scope/line items/questionnaire/terms through conversation, a
format-agnostic extraction step that reads Excel, PDF, Word, a photographed rate card, and a
plain email and turns each into structured quotes, a normalization engine that lands
everything in one comparable table, and an analyst chat that runs real pandas queries against
that table instead of canned answers.

## Category and demo data
IT hardware refresh, 400 seats, 30 line items, 5 vendors. I fabricated all five vendor
responses myself, deliberately mirroring the ugly edges named in the brief plus a couple of my
own:
- **TechSource** (Excel): own column layout, own item descriptions, no item codes reused - a
  real-world matching problem, not a parsing problem.
- **Global IT Solutions** (PDF): USD pricing, misses 2 line items outright, and a 6% volume
  discount sitting only in an 8pt footnote at the bottom of the page.
- **Prime Hardware** (Word): commercial terms in prose paragraphs, and small accessories priced
  per-box instead of per-unit.
- **QuickSupply** (photo): an actually skewed/rotated image of a printed rate card, missing 3
  line items they don't stock, and a *different* box size than Prime Hardware for overlapping
  items - so two vendors' "per box" doesn't mean the same box.
- **Apex Systems** (email): the "₹42/kg... rest same as last year" pattern from the brief,
  transposed to hardware - only the 5 items that changed price are stated; everything else
  points at a prior PO.

## Where the trust decisions are

**Never invent a number.** The extraction prompt is explicit: if unit basis, box size, or a
match is unclear, flag it (`needs_buyer_review` + a reason) rather than guess. This is the
single decision I'd defend hardest in a live demo - a fabricated-looking number is worse than
a visible gap.

**"Same as last year" is real, and I chose to resolve it, not just flag it.** Apex is treated
as an existing vendor with a price history on file (fabricated for the demo). When their
extraction shows a "rest is the same" reference, the comparison engine fills the remaining
lines from that history - but every filled line is tagged `carried_forward=True`, gets a
`needs_buyer_review` reason, and the analyst is instructed to always disclose that flag when
it's relevant to a question. The alternative (leave those 25 lines blank) makes Apex look
artificially incomplete and non-competitive, which is its own kind of misleading. Filling with
disclosure felt like the closer-to-real-life answer.

**Two vendors, two different box sizes, same accessory.** This is intentionally the nastiest
edge case in the dataset - Prime Hardware boxes mice at 20/box, QuickSupply at 12/box. Nothing
silently averages or reconciles this; the normalization step converts per-box to per-unit using
each vendor's *own* stated box size, so the two numbers become genuinely comparable rather than
coincidentally similar-looking.

**Currency conversion is a stated, hardcoded assumption**, not a live FX call (`FX_RATES_TO_INR`
in `normalize.py`). For a real system this is obviously a rates API; for the demo I wanted the
number visible and auditable rather than dependent on a live external call succeeding during
the interview.

**The analyst chat gets a real pandas tool, not a lookup table.** The VP's "cheapest per line,
split, only among vendors who passed the questionnaire" question is the whole point of the
brief - it can't be pre-baked. Claude gets `run_pandas_query` over the actual comparison
DataFrame and vendor questionnaire answers, has to define "passed the questionnaire" itself
when asked (and is instructed to say out loud what rule it applied, since that's a judgment
call the buyer should be able to overrule), and is told to surface `needs_buyer_review` /
`carried_forward` flags whenever they're relevant to the answer rather than let a shaky number
look identical to a solid one.

## What I deliberately left out
- **Live vendor outreach (SMTP/email sending).** Per the brief, plumbing is stubbed - vendor
  responses arrive via a file upload widget or a pasted link (Tab 2) rather than being actually
  emailed out and back. A buyer can drop in real Excel/PDF/Word/image/email files, or paste a
  link (a Google Doc/Sheet, or a direct file link - including one copied out of an email)
  alongside or instead of the 5 demo fixtures. The link path is intentionally scoped to public
  links only - there's no OAuth flow asking the buyer to sign into Google or their email
  provider. A Google Doc/Sheet needs "Anyone with the link can view" sharing; a private link
  fails with a clear message rather than silently doing nothing, and the buyer can fall back to
  downloading the file themselves. Every file - however it arrived - gets a genuine preview:
  actual rendered PDF pages (via poppler, not just extracted text), a real sheet-by-sheet table
  for Excel, extracted text for Word, the image itself for photos - plus a download button for
  the original file. Extraction and comparison both run over the full working set (demo +
  uploaded, by file or by link) automatically. What's stubbed is the transport (no inbox is
  actually polled, no Google/email account is ever connected), not the intake or visibility.
- **Multi-currency FX as a live service** - see above, hardcoded and disclosed instead.
- **Auth, multi-user, persistence beyond local JSON/session state.** This is a single-buyer demo
  prototype, not a multi-tenant product.
- **A generalized "any category" UI.** The RFx co-pilot can draft any category conversationally,
  but the demo dataset and box-size/carry-forward edge cases are hand-built for IT hardware
  specifically, since fabricating equally textured messiness for a second category in the time
  available would have thinned both.
- **OCR confidence scoring as a separate step.** I rely on the vision model's own stated
  `match_confidence` and its `extraction_warnings` for the photographed rate card rather than
  bolting on a second OCR-quality pass - given more time this is the first thing I'd add, since
  right now "the image was hard to read" and "the description was ambiguous" both surface
  through the same flag.

## If I'm honest about where the interesting problem actually was
Less in the extraction (models are already good at reading messy documents) and more in
**deciding what to do once you know something is uncertain** - fill it and flag it, or leave it
blank, or ask the buyer a clarifying question before showing them a number at all. I picked
"fill and flag, never silently" as the house rule and tried to apply it consistently across the
box-size mismatch, the carried-forward pricing, and the analyst's own eligibility judgment
calls. A buyer with ₹4 crore on the line should never have to guess which numbers on their
screen are solid.
