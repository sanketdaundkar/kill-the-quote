import json, random

random.seed(42)

with open('/home/claude/aerchain-rfx/data/rfx/rfx_spec.json') as f:
    rfx = json.load(f)

# Base INR unit price per item (rough IT hardware market pricing)
BASE_PRICE_INR = {
    "IT-001": 68000, "IT-002": 42000, "IT-003": 9500, "IT-004": 21000,
    "IT-005": 7800, "IT-006": 1400, "IT-007": 550, "IT-008": 350,
    "IT-009": 2200, "IT-010": 2800, "IT-011": 3200, "IT-012": 900,
    "IT-013": 650, "IT-014": 180, "IT-015": 42000, "IT-016": 78000,
    "IT-017": 15500, "IT-018": 22000, "IT-019": 8500, "IT-020": 65000,
    "IT-021": 6800, "IT-022": 4200, "IT-023": 3400, "IT-024": 750,
    "IT-025": 1600, "IT-026": 2900, "IT-027": 18500, "IT-028": 45000,
    "IT-029": 5200, "IT-030": 9800
}

with open('/home/claude/aerchain-rfx/data/rfx/base_prices.json', 'w') as f:
    json.dump(BASE_PRICE_INR, f, indent=2)

print("done", len(BASE_PRICE_INR))
