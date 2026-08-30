const pptxgen = require("pptxgenjs");

const NAVY = "1A2744";
const NAVY_DARK = "121B33";
const ICE = "E8EDF5";
const ORANGE = "E8542F";
const WHITE = "FFFFFF";
const GREY = "6B7688";

function newDeck() {
  const p = new pptxgen();
  p.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
  return p;
}

const pres = newDeck();

// ---------- Slide 1: Title ----------
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DARK };
  s.addText("KILL THE", {
    x: 0.8, y: 1.5, w: 11.7, h: 1.0, fontFace: "Calibri", fontSize: 20,
    color: ORANGE, bold: true, charSpacing: 4, isTextBox: true,
  });
  s.addText("Quote Spreadsheet", {
    x: 0.8, y: 2.0, w: 11.7, h: 1.4, fontFace: "Cambria", fontSize: 48,
    color: WHITE, bold: true, isTextBox: true,
  });
  s.addText("An AI-powered RFx co-pilot, response extraction, and analyst chat", {
    x: 0.8, y: 3.35, w: 10, h: 0.6, fontFace: "Calibri", fontSize: 18,
    color: ICE, isTextBox: true,
  });
  s.addShape(pres.ShapeType.line, { x: 0.8, y: 4.15, w: 2.2, h: 0, line: { color: ORANGE, width: 3 } });
  s.addText("Aerchain — Product Management Take-Home Assignment", {
    x: 0.8, y: 6.55, w: 8, h: 0.4, fontFace: "Calibri", fontSize: 13, color: GREY, isTextBox: true,
  });
  s.addText("Sanket Daundkar", {
    x: 0.8, y: 6.15, w: 8, h: 0.4, fontFace: "Calibri", fontSize: 15, color: WHITE, bold: true, isTextBox: true,
  });
}

// ---------- Slide 2: The problem ----------
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("The week I'm trying to delete", {
    x: 0.6, y: 0.5, w: 12, h: 0.7, fontFace: "Cambria", fontSize: 30, color: NAVY, bold: true, isTextBox: true,
  });
  const pain = [
    ["Day 1-2", "RFx goes out to 5 vendors. Everyone quotes however they like."],
    ["Day 3-9", "Excel that ignores the template. A PDF with the discount in a footnote. A Word doc with commercials in a paragraph. An angled phone photo. An email shorthand."],
    ["Day 10", "Buyer retypes everything into one sheet by hand. Three days gone."],
    ["Day 11", "VP asks one conditional question the sheet can't answer. There goes the fourth."],
  ];
  let y = 1.55;
  pain.forEach(([tag, text], i) => {
    s.addShape(pres.ShapeType.roundRect, {
      x: 0.6, y, w: 1.5, h: 0.55, rectRadius: 0.08,
      fill: { color: i === 3 ? ORANGE : NAVY }, line: { type: "none" },
    });
    s.addText(tag, {
      x: 0.6, y, w: 1.5, h: 0.55, fontFace: "Calibri", fontSize: 13, color: WHITE, bold: true,
      align: "center", valign: "middle", isTextBox: true,
    });
    s.addText(text, {
      x: 2.35, y: y - 0.05, w: 10.2, h: 0.7, fontFace: "Calibri", fontSize: 15,
      color: i === 3 ? ORANGE : NAVY, bold: i === 3, valign: "middle", isTextBox: true,
    });
    y += 1.15;
  });
  s.addText("This happens in every procurement team on earth. Nobody's built the thing that ends it — until now.", {
    x: 0.6, y: 6.55, w: 12, h: 0.5, fontFace: "Calibri", fontSize: 14, italic: true, color: GREY, isTextBox: true,
  });
}

// ---------- Slide 3: What I built - architecture ----------
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("One flow, end to end", {
    x: 0.6, y: 0.5, w: 12, h: 0.7, fontFace: "Cambria", fontSize: 30, color: NAVY, bold: true, isTextBox: true,
  });
  s.addText("Four real AI loops. No hardcoded answers, no replayed demo.", {
    x: 0.6, y: 1.15, w: 12, h: 0.4, fontFace: "Calibri", fontSize: 14, color: GREY, isTextBox: true,
  });

  const stages = [
    ["1", "RFx Co-pilot", "Buyer talks scope, line items, questionnaire, and terms into existence through conversation."],
    ["2", "Extraction", "Reads Excel, PDF, Word, a photographed rate card, and a plain email — turns each into structured quotes."],
    ["3", "Normalization", "Currency, per-unit vs per-box, matching to RFx lines — one comparable table, every assumption flagged."],
    ["4", "Analyst Chat", "Natural language over the whole comparison, backed by a real pandas query tool, not canned Q&A."],
  ];
  const boxW = 2.75, gap = 0.25, startX = 0.6, y0 = 2.1, boxH = 3.6;
  stages.forEach(([num, title, desc], i) => {
    const x = startX + i * (boxW + gap);
    s.addShape(pres.ShapeType.roundRect, {
      x, y: y0, w: boxW, h: boxH, rectRadius: 0.1,
      fill: { color: i % 2 === 0 ? NAVY : NAVY_DARK }, line: { type: "none" },
    });
    s.addText(num, {
      x: x + 0.2, y: y0 + 0.2, w: 1, h: 0.6, fontFace: "Cambria", fontSize: 30, color: ORANGE, bold: true, isTextBox: true,
    });
    s.addText(title, {
      x: x + 0.2, y: y0 + 0.85, w: boxW - 0.4, h: 0.7, fontFace: "Calibri", fontSize: 17, color: WHITE, bold: true, isTextBox: true,
    });
    s.addText(desc, {
      x: x + 0.2, y: y0 + 1.55, w: boxW - 0.4, h: 1.9, fontFace: "Calibri", fontSize: 12.5, color: ICE, isTextBox: true,
    });
    if (i < stages.length - 1) {
      s.addText("→", { x: x + boxW - 0.05, y: y0 + boxH / 2 - 0.3, w: 0.5, h: 0.6, fontFace: "Arial", fontSize: 22, color: ORANGE, bold: true, align: "center", isTextBox: true });
    }
  });
}

// ---------- Slide 4: Demo dataset ----------
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("5 vendors. 5 formats. Real messiness.", {
    x: 0.6, y: 0.5, w: 12, h: 0.7, fontFace: "Cambria", fontSize: 30, color: NAVY, bold: true, isTextBox: true,
  });
  s.addText("IT hardware refresh · 30 line items · 400 seats — all fabricated for the demo, textured on purpose", {
    x: 0.6, y: 1.15, w: 12, h: 0.4, fontFace: "Calibri", fontSize: 14, color: GREY, isTextBox: true,
  });

  const rows = [
    ["TechSource", "Excel", "Own column layout & item descriptions — no shared item codes. A matching problem, not a parsing one."],
    ["Global IT Solutions", "PDF", "USD pricing, misses 2 line items, 6% discount buried in an 8pt footnote."],
    ["Prime Hardware", "Word", "Commercials in prose paragraphs; small accessories priced per-box, not per-unit."],
    ["QuickSupply", "Photo", "Genuinely skewed/rotated rate-card photo; 3 unstocked items; a different box size than Prime Hardware."],
    ["Apex Systems", "Email", '"Rest same as last year" — only 5 changed prices stated, rest points at a prior PO.'],
  ];
  let y = 2.15;
  const rowH = 0.92;
  rows.forEach(([vendor, fmt, desc], i) => {
    if (i % 2 === 0) {
      s.addShape(pres.ShapeType.rect, { x: 0.6, y, w: 12.1, h: rowH, fill: { color: ICE }, line: { type: "none" } });
    }
    s.addText(vendor, { x: 0.8, y, w: 2.3, h: rowH, fontFace: "Calibri", fontSize: 14, bold: true, color: NAVY, valign: "middle", isTextBox: true });
    s.addShape(pres.ShapeType.roundRect, { x: 3.2, y: y + rowH / 2 - 0.2, w: 1.1, h: 0.4, rectRadius: 0.06, fill: { color: ORANGE }, line: { type: "none" } });
    s.addText(fmt, { x: 3.2, y: y + rowH / 2 - 0.2, w: 1.1, h: 0.4, fontFace: "Calibri", fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", isTextBox: true });
    s.addText(desc, { x: 4.55, y, w: 8.0, h: rowH, fontFace: "Calibri", fontSize: 12.5, color: NAVY, valign: "middle", isTextBox: true });
    y += rowH;
  });
}

// ---------- Slide 5: Trust decisions ----------
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DARK };
  s.addText("Would a buyer act on this with ₹4 crore on the line?", {
    x: 0.6, y: 0.5, w: 12, h: 0.9, fontFace: "Cambria", fontSize: 27, color: WHITE, bold: true, isTextBox: true,
  });
  const rules = [
    ["Never invent a number", "If unit basis, box size, or a match is unclear, the extraction flags it with a reason — it does not guess."],
    ["Two vendors, two box sizes, same item", "Per-box pricing is converted to per-unit using each vendor's own stated box size — never averaged or assumed equal."],
    ["FX rate is a visible, hardcoded assumption", "Not a live API call — the number is auditable and named in the code, not hidden behind a service call that might silently fail."],
  ];
  let y = 1.75;
  rules.forEach(([title, desc]) => {
    s.addShape(pres.ShapeType.roundRect, { x: 0.6, y, w: 0.12, h: 1.15, rectRadius: 0, fill: { color: ORANGE }, line: { type: "none" } });
    s.addText(title, { x: 0.95, y: y - 0.05, w: 11.5, h: 0.5, fontFace: "Calibri", fontSize: 18, bold: true, color: WHITE, isTextBox: true });
    s.addText(desc, { x: 0.95, y: y + 0.45, w: 11.5, h: 0.65, fontFace: "Calibri", fontSize: 14, color: ICE, isTextBox: true });
    y += 1.5;
  });
}

// ---------- Slide 6: "Same as last year" ----------
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText('The "rest, same as last year" problem', {
    x: 0.6, y: 0.5, w: 12, h: 0.7, fontFace: "Cambria", fontSize: 28, color: NAVY, bold: true, isTextBox: true,
  });
  s.addText("Apex's email states 5 changed prices and points at a prior PO for the other 25 lines. Leaving those blank makes an existing vendor look artificially incomplete.", {
    x: 0.6, y: 1.25, w: 11.8, h: 0.7, fontFace: "Calibri", fontSize: 14, color: GREY, isTextBox: true,
  });

  s.addText("My rule: fill it, and flag it — never silently.", {
    x: 0.6, y: 2.15, w: 11.8, h: 0.5, fontFace: "Calibri", fontSize: 18, bold: true, color: ORANGE, isTextBox: true,
  });

  const cols = [
    ["Historical record", "Apex is treated as an existing vendor with last cycle's price file on file — as a real system would have."],
    ["Gap-fill", "Unmatched RFx lines are filled from that record when the vendor references \"same as last year.\""],
    ["Always disclosed", "Every filled line is tagged carried_forward=True with a review reason — the analyst chat surfaces it whenever relevant."],
  ];
  const colW = 3.83, gap = 0.25;
  cols.forEach(([title, desc], i) => {
    const x = 0.6 + i * (colW + gap);
    s.addShape(pres.ShapeType.roundRect, { x, y: 2.95, w: colW, h: 2.9, rectRadius: 0.1, fill: { color: ICE }, line: { type: "none" } });
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.25, y: 3.2, w: 0.5, h: 0.5, rectRadius: 0.25, fill: { color: NAVY }, line: { type: "none" } });
    s.addText(String(i + 1), { x: x + 0.25, y: 3.2, w: 0.5, h: 0.5, fontFace: "Calibri", fontSize: 16, bold: true, color: WHITE, align: "center", valign: "middle", isTextBox: true });
    s.addText(title, { x: x + 0.25, y: 3.85, w: colW - 0.5, h: 0.5, fontFace: "Calibri", fontSize: 15, bold: true, color: NAVY, isTextBox: true });
    s.addText(desc, { x: x + 0.25, y: 4.35, w: colW - 0.5, h: 1.4, fontFace: "Calibri", fontSize: 12, color: NAVY, isTextBox: true });
  });
}

// ---------- Slide 7: Analyst chat ----------
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("Stop clicking. Start asking.", {
    x: 0.6, y: 0.5, w: 12, h: 0.7, fontFace: "Cambria", fontSize: 30, color: NAVY, bold: true, isTextBox: true,
  });
  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 1.4, w: 7.0, h: 2.2, rectRadius: 0.12, fill: { color: NAVY_DARK }, line: { type: "none" },
  });
  s.addText('"What if we split it, cheapest per line, but only among\nvendors who cleared the quality questionnaire?"', {
    x: 0.9, y: 1.65, w: 6.4, h: 1.0, fontFace: "Cambria", fontSize: 16, italic: true, color: WHITE, isTextBox: true,
  });
  s.addText("— the question that used to cost the buyer their 4th day", {
    x: 0.9, y: 2.75, w: 6.4, h: 0.5, fontFace: "Calibri", fontSize: 12, color: GREY, isTextBox: true,
  });

  const points = [
    "Claude gets a real run_pandas_query tool over the live comparison table — the question is never pre-baked.",
    "Eligibility rules like \"cleared the questionnaire\" aren't a schema column — the model derives them and states the rule it applied, since it's a judgment call the buyer can override.",
    "needs_buyer_review and carried_forward flags are surfaced in the answer whenever they're relevant — a shaky number never looks identical to a solid one.",
  ];
  let y = 4.0;
  points.forEach((pt) => {
    s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: y + 0.08, w: 0.16, h: 0.16, rectRadius: 0.08, fill: { color: ORANGE }, line: { type: "none" } });
    s.addText(pt, { x: 1.0, y, w: 11.6, h: 0.75, fontFace: "Calibri", fontSize: 14, color: NAVY, isTextBox: true });
    y += 0.95;
  });
}

// ---------- Slide 8: Left out / closing ----------
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DARK };
  s.addText("What I deliberately left out", {
    x: 0.6, y: 0.55, w: 12, h: 0.7, fontFace: "Cambria", fontSize: 28, color: WHITE, bold: true, isTextBox: true,
  });
  const left = [
    "Live vendor outreach (SMTP) — plumbing stubbed per the brief",
    "Live FX rates — hardcoded and disclosed instead",
    "Auth, multi-tenant, persistence beyond local/session state",
  ];
  const right = [
    "A generalized any-category UI — one category, built deep not wide",
    "Separate OCR confidence scoring — folded into the model's own stated confidence for now",
  ];
  let y = 1.6;
  left.forEach((t) => {
    s.addText("—  " + t, { x: 0.6, y, w: 5.8, h: 0.6, fontFace: "Calibri", fontSize: 13.5, color: ICE, isTextBox: true });
    y += 0.65;
  });
  y = 1.6;
  right.forEach((t) => {
    s.addText("—  " + t, { x: 6.6, y, w: 6.0, h: 0.6, fontFace: "Calibri", fontSize: 13.5, color: ICE, isTextBox: true });
    y += 0.65;
  });

  s.addShape(pres.ShapeType.line, { x: 0.6, y: 3.9, w: 12.1, h: 0, line: { color: "3A4460", width: 1 } });

  s.addText("The interesting problem, if I'm honest", {
    x: 0.6, y: 4.2, w: 12, h: 0.5, fontFace: "Calibri", fontSize: 17, bold: true, color: ORANGE, isTextBox: true,
  });
  s.addText("Less in extracting messy documents — models are already good at that — and more in deciding what to do the moment you know something is uncertain: fill it and flag it, or leave it blank, or ask the buyer first. \"Fill and flag, never silently\" became the one rule applied everywhere in this build.", {
    x: 0.6, y: 4.75, w: 11.8, h: 1.4, fontFace: "Calibri", fontSize: 15, color: WHITE, isTextBox: true,
  });

  s.addText("Full write-up in decisions.md  ·  Live build + recorded walkthrough linked separately", {
    x: 0.6, y: 6.7, w: 11.8, h: 0.4, fontFace: "Calibri", fontSize: 12, color: GREY, isTextBox: true,
  });
}

pres.writeFile({ fileName: "/home/claude/aerchain-rfx/deck/Aerchain_KillTheQuoteSpreadsheet.pptx" })
  .then(() => console.log("done"));
