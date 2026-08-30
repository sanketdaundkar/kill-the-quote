import json, random, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

random.seed(4)

with open('/home/claude/aerchain-rfx/data/rfx/rfx_spec.json') as f:
    rfx = json.load(f)
with open('/home/claude/aerchain-rfx/data/rfx/base_prices.json') as f:
    base = json.load(f)

desc_map = {li["item_code"]: li["description"] for li in rfx["line_items"]}
qty_map = {li["item_code"]: li["qty"] for li in rfx["line_items"]}

# QuickSupply doesn't stock networking/rack infra - skip those 3
skip = {"IT-015", "IT-016", "IT-018"}

items = [c for c in desc_map if c not in skip]

W, H = 1400, 2000
img = Image.new("RGB", (W, H), "white")
draw = ImageDraw.Draw(img)

try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    font_hdr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    font_row = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
except Exception:
    font_title = font_hdr = font_row = font_small = ImageFont.load_default()

y = 40
draw.text((40, y), "QUICKSUPPLY TRADERS", font=font_title, fill="black"); y += 45
draw.text((40, y), "Rate Card - IT Hardware - Effective 25 Aug 2026 (Contact: 98xxxxxx21, Pune)", font=font_small, fill="black"); y += 40
draw.line((40, y, W-40, y), fill="black", width=2); y += 20

draw.text((40, y), "Item", font=font_hdr, fill="black")
draw.text((110, y), "Description", font=font_hdr, fill="black")
draw.text((900, y), "Qty", font=font_hdr, fill="black")
draw.text((1000, y), "Rate/box", font=font_hdr, fill="black")
y += 30
draw.line((40, y, W-40, y), fill="black", width=1); y += 10

# QuickSupply quotes small items "per box" too, sows another unit ambiguity (different box sizes than Vendor C!)
BOX_ITEMS_D = {"IT-008": 12, "IT-013": 20, "IT-014": 40}

for code in items:
    price = base[code] * random.uniform(0.90, 1.06)
    if code in BOX_ITEMS_D:
        n = BOX_ITEMS_D[code]
        rate_str = f"Rs {round(price*n,-1):,.0f} /box({n})"
    else:
        rate_str = f"Rs {round(price,-1):,.0f} /pc"
    desc = desc_map[code]
    if len(desc) > 48:
        desc = desc[:45] + "..."
    draw.text((40, y), code, font=font_row, fill="black")
    draw.text((110, y), desc, font=font_row, fill="black")
    draw.text((900, y), str(qty_map[code]), font=font_row, fill="black")
    draw.text((1000, y), rate_str, font=font_row, fill="black")
    y += 32

y += 20
draw.line((40, y, W-40, y), fill="black", width=1); y += 15
draw.text((40, y), "All rates in INR, excl GST 18%. Freight extra @ actuals. Delivery 4wks.", font=font_small, fill="black"); y += 25
draw.text((40, y), "Warranty: 1yr standard all items. 3yr onsite avail for laptops @ Rs.2500/unit extra.", font=font_small, fill="black"); y += 25
draw.text((40, y), "Not stocked / not quoted: 24-port switch, 48-port switch, network rack (please source separately).", font=font_small, fill="black")

img = img.crop((0, 0, W, y + 80))

# --- Simulate a phone photo taken at an angle ---
W2, H2 = img.size
img = img.convert("RGB")

# perspective skew
coeffs = None
def find_coeffs(pa, pb):
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p2[0], p2[1], 1, 0, 0, 0, -p1[0]*p2[0], -p1[0]*p2[1]])
        matrix.append([0, 0, 0, p2[0], p2[1], 1, -p1[1]*p2[0], -p1[1]*p2[1]])
    import numpy as np
    A = np.matrix(matrix, dtype=float)
    B = np.array(pa).reshape(8)
    res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
    return np.array(res).reshape(8)

pa = [(60, 40), (W2-30, 0), (W2-90, H2-20), (0, H2-70)]
pb = [(0,0), (W2,0), (W2,H2), (0,H2)]
coeffs = find_coeffs(pa, pb)
img = img.transform((W2, H2), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor="white")

img = img.rotate(-3.5, expand=True, fillcolor="white")
img = img.filter(ImageFilter.GaussianBlur(radius=1.1))

# add a subtle vignette / shadow gradient for "photo" feel
overlay = Image.new("L", img.size, 0)
odraw = ImageDraw.Draw(overlay)
for i in range(img.size[0]):
    shade = int(25 * abs(i - img.size[0]/2) / (img.size[0]/2))
    odraw.line((i, 0, i, img.size[1]), fill=shade)
img = Image.composite(Image.new("RGB", img.size, "black"), img, overlay.point(lambda p: int(p*0.5)))

img.save('/home/claude/aerchain-rfx/data/vendor_responses/vendor_d_quicksupply_ratecard.jpg', quality=82)
print("saved", img.size)
