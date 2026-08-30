import json, random

random.seed(5)

with open('/home/claude/aerchain-rfx/data/rfx/rfx_spec.json') as f:
    rfx = json.load(f)
with open('/home/claude/aerchain-rfx/data/rfx/base_prices.json') as f:
    base = json.load(f)

desc_map = {li["item_code"]: li["description"] for li in rfx["line_items"]}

# Apex Systems is an EXISTING vendor with a price list on file from last year (FY26).
# We fabricate that historical record (system-side data, not part of the vendor's email).
last_year = {}
for code, price in base.items():
    last_year[code] = round(price * random.uniform(0.85, 0.95), -1)  # last year was cheaper

with open('/home/claude/aerchain-rfx/data/rfx/apex_last_year_prices.json', 'w') as f:
    json.dump(last_year, f, indent=2)

# Apex's email only calls out the items that changed materially this year (5 items),
# and waves at "rest same as last year" for everything else - exactly the ugly edge
# from the brief. They also don't answer the questionnaire in a structured way.
changed_codes = ["IT-001", "IT-002", "IT-015", "IT-020", "IT-028"]
lines = []
labels = {
    "IT-001": "the i5 laptop", "IT-002": "the i3 laptop", "IT-015": "24-port switch",
    "IT-020": "3kVA online UPS", "IT-028": "PTZ camera"
}
for code in changed_codes:
    new_price = round(base[code] * random.uniform(0.98, 1.12), -1)
    lines.append(f"{labels[code]} is now {int(new_price):,}")

email_body = f"""From: Rakesh Menon <rakesh.menon@apexsystems.co.in>
To: Sanket Daundkar <sanket.d@buyerco.com>
Subject: RE: RFX-2026-0847 - IT Hardware Refresh - Apex quote

Hi Sanket,

Good to hear from you again, hope the team is doing well since the last refresh cycle.

Been a busy few weeks so keeping this quick - prices this year, only flagging what actually moved:
- {lines[0]}
- {lines[1]}
- {lines[2]} (chip prices went up, sorry)
- {lines[3]}
- {lines[4]}

Rest of the lineup is same as last year's rates, you already have that sheet from the FY26 order
(PO-4471 I think). GST and freight extra as usual, freight will be around 15-18k for the full
consignment to Pune given the volumes you mentioned.

On the questionnaire - yes to pretty much everything same as before (OEM authorized, we did the
Pune onsite support last time too so that's a yes, ISO 9001 yes we renewed it in March). Can't
commit to 6 weeks flat out though, realistically 7-8 weeks for the laptops specifically since
there's a chip shortage going around, rest of the stuff we can do in 4.

Let me know if you want a formal PO-ready doc, happy to send one once you've zeroed in.

Thanks,
Rakesh
Apex Systems | Sales
"""

with open('/home/claude/aerchain-rfx/data/vendor_responses/vendor_e_apex_email.txt', 'w') as f:
    f.write(email_body)

print("saved")
print(email_body)
