import json, random
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

random.seed(2)

with open('/home/claude/aerchain-rfx/data/rfx/rfx_spec.json') as f:
    rfx = json.load(f)
with open('/home/claude/aerchain-rfx/data/rfx/base_prices.json') as f:
    base = json.load(f)

USD_INR = 87.0  # assumed FX rate at quote date

styles = getSampleStyleSheet()
title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=18, textColor=colors.HexColor("#1a3c6e"))
small = ParagraphStyle('small', parent=styles['Normal'], fontSize=7.5, textColor=colors.grey)
normal = styles['Normal']

doc = SimpleDocTemplate('/home/claude/aerchain-rfx/data/vendor_responses/vendor_b_globalit.pdf',
                         pagesize=A4, topMargin=20*mm, bottomMargin=15*mm)

elements = []
elements.append(Paragraph("GLOBAL IT SOLUTIONS INC.", title_style))
elements.append(Paragraph("1200 Marina Blvd, Suite 400, San Francisco, CA 94123 | sales@globalitsolutions.com", normal))
elements.append(Spacer(1, 10))
elements.append(Paragraph("<b>Quotation Ref:</b> GIS-Q-88213   <b>Date:</b> Aug 27, 2026   <b>Valid Until:</b> Sep 10, 2026", normal))
elements.append(Paragraph("<b>Attn:</b> Sanket Daundkar, IT Procurement, RFX-2026-0847", normal))
elements.append(Spacer(1, 14))
elements.append(Paragraph("All prices quoted in <b>USD</b>, FOB origin. Buyer to arrange import/customs to Pune, India. "
                           "Lead time 4-5 weeks from PO receipt.", normal))
elements.append(Spacer(1, 10))

# Vendor skips 2 low-value items entirely (barcode scanner, label printer) - they don't stock these lines
skip_codes = {"IT-029", "IT-030"}

desc_map = {li["item_code"]: li["description"] for li in rfx["line_items"]}
data = [["Item", "Description", "Qty Quoted", "Unit Price (USD)"]]
for li in rfx["line_items"]:
    code = li["item_code"]
    if code in skip_codes:
        continue
    price_inr = base[code] * random.uniform(0.90, 1.05)
    price_usd = round(price_inr / USD_INR, 2)
    data.append([code, desc_map[code][:45], str(li["qty"]), f"${price_usd:,.2f}"])

table = Table(data, colWidths=[45, 220, 60, 90])
table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a3c6e")),
    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
    ('FONTSIZE', (0,0), (-1,-1), 8),
    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4fa")]),
    ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
]))
elements.append(table)
elements.append(Spacer(1, 8))
elements.append(Paragraph("Note: Items IT-029 (Barcode Scanner) and IT-030 (Label Printer) are outside our current "
                           "catalog and are not quoted in this response.", normal))
elements.append(Spacer(1, 20))
elements.append(Paragraph("Payment Terms: 30% advance, balance on shipment. Warranty: 1 year standard on all items "
                           "(3yr on compute available at +12% surcharge, not included above).", normal))
elements.append(Spacer(1, 14))
elements.append(Paragraph(
    "<b>Compliance:</b> Global IT Solutions is ISO 9001:2015 and ISO 27001:2013 certified. We are an "
    "authorized reseller for all brands quoted above. We can consolidate to a single shipment to Pune "
    "against one commercial invoice. On-site warranty support in India is provided through our local "
    "partner network (response SLA 48 hours). We can commit to a 5-week delivery window for the full "
    "order, subject to no export licensing delays.", normal))
elements.append(Spacer(1, 40))

# The buried discount - fine print footnote, easy to miss
elements.append(Paragraph(
    "* A 6% volume discount applies to the total order value above and is already reflected as a blanket "
    "adjustment at invoicing; unit prices shown above are pre-discount list prices. Freight, insurance, and "
    "India customs duty (approx. 18-28% depending on HSN classification) are excluded and payable by buyer. "
    "Quote assumes single shipment; split shipments incur additional freight.",
    small))

doc.build(elements)
print("saved")
