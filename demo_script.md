# Demo Video Script - "Kill the Quote Spreadsheet"

Target length: 6-9 minutes. Record with the Streamlit app running locally
(`streamlit run streamlit_app.py`) or against the deployed link.

---

## 0. Cold open (30 sec) - don't screen-share yet

Say this to camera, no screen:

> "Aerchain's brief was to kill the week a category buyer loses to five vendors quoting
> in five different formats. I built the full flow - RFx co-pilot, extraction, comparison,
> and an analyst chat - for one category: an IT hardware refresh, 30 line items, 5 vendors.
> Everything you're about to see is a live call to Claude, not a script replaying a
> recorded answer. Let me walk through it."

## 1. The RFx (45 sec) - Tab 1

Screen-share now. Click "Use the pre-loaded demo RFx."

> "This is the RFx - IT hardware refresh, 30 line items, a 5-question vendor
> questionnaire, and commercial terms. In a real session a buyer would talk this into
> existence with the co-pilot instead of filling a form - [type one line into the chat
> input, e.g. 'add a line for 10 conference room speakerphones'] - and watch the draft
> update live on the right."

Keep this short - the interesting work is downstream.

## 2. The five vendors (90 sec) - Tab 2

Open each expander briefly, in this order, narrating what makes each one nasty:

1. **TechSource (Excel)** - "Their own column layout, their own item descriptions, no
   shared item codes. This is a matching problem, not a parsing problem."
2. **Global IT Solutions (PDF)** - "Priced in USD, missing two line items outright, and
   there's a 6% discount sitting in an 8-point footnote at the bottom - easy for a human
   to miss entirely."
3. **Prime Hardware (Word)** - "Commercial terms are written in prose, and small
   accessories are priced per box, not per unit."
4. **QuickSupply (photo)** - "This is a real photographed rate card - angled, slightly
   blurred - and it uses a *different* box size than Prime Hardware for the same item.
   Two vendors, two box sizes, same accessory."
5. **Apex Systems (email)** - "This is the '₹42/kg for the 5-ply... rest same as last
   year' pattern from the brief, in hardware form - only 5 prices are called out
   explicitly, everything else points at a prior PO."

## 3. Run extraction (60 sec) - Tab 2

Click "Run extraction on all 5 vendor responses." While it runs:

> "Each of these is one real Claude call - vision for the photo, text for the rest -
> reading whatever's on the page and matching it back to our RFx line items by meaning,
> since none of these vendors used our item codes."

Open one raw extraction result (pick QuickSupply, the photo) and point at:
- `match_confidence` per line
- `needs_buyer_review` + `review_reason` on at least one line
- `unit_basis` / `box_size` fields

## 4. The comparison (2 min) - Tab 3

This is the core of the demo.

- Show the **coverage table** first: "TechSource covers all 30 lines, Global IT is
  missing 2, QuickSupply is missing 3 - visible immediately, not discovered on day 9."
- Check **"Show only lines flagged for buyer review"** - point at a few flagged rows:
  the ambiguous box size, a low-confidence match, an Apex carried-forward line.
- Scroll to **"Cheapest eligible vendor per line"** and the total value callout -
  explicitly call out: "This total mixes solid quotes with flagged ones - that's the
  ₹X sitting on lines I would NOT sign off on without a second look."
- Open **vendor questionnaire answers** - show Apex's informally-phrased answers
  extracted anyway ("yes to pretty much everything same as before").

## 5. Ask the analyst (2 min) - Tab 4

Type the VP's question live, unscripted reaction to whatever comes back:

> "What if we split it, cheapest per line, but only among vendors who cleared the
> quality questionnaire?"

While it's thinking:

> "There's no pre-written answer for this - it's running a real pandas query against
> the comparison table, and it has to decide for itself what 'cleared the quality
> questionnaire' means, since that's not a column in the data."

When the answer comes back, read the eligibility rule it applied out loud and react to
whether it's the rule you'd have picked. Ask one follow-up live, e.g.:

> "Which of those lines are you least confident in?"

## 6. Close (30 sec) - back to camera

> "The interesting problem here wasn't reading messy documents - models are already good
> at that. It was deciding what to do the moment you know a number is uncertain: fill it
> and flag it, leave it blank, or go back to the vendor. I wrote up the specific calls I
> made - the box-size mismatch, the carried-forward pricing, the FX assumption - in
> decisions.md. Thanks for reading this far into a take-home."

---

## Recording notes
- Do one full dry run before recording - the analyst chat's answer is genuinely
  non-deterministic, so know roughly what shape of answer to expect but don't fake
  surprise if it says something different.
- If a step is slow (extraction takes ~30-60s for 5 vendors), either cut in editing or
  talk over it live - don't sit in silence.
- Loom's "trim silence" feature works well here if you'd rather record raw and clean up.
