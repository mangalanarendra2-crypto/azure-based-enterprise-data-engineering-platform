"""Generate a small, deliberately messy sales CSV used to demo the pipeline.

Dirty rows included on purpose so the Silver layer has something to clean:
duplicate order_ids, null keys, negative quantities, inconsistent casing/whitespace.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

PRODUCTS = {
    "Laptop": ("Electronics", 950.0),
    "Phone": ("Electronics", 600.0),
    "Headphones": ("Electronics", 120.0),
    "Desk": ("Furniture", 250.0),
    "Chair": ("Furniture", 150.0),
    "Notebook": ("Stationery", 4.5),
    "Pen Set": ("Stationery", 12.0),
}
COUNTRIES = ["India", "USA", "UK", "Germany", "Australia"]
STATUSES = ["completed", "completed", "completed", "shipped", "cancelled"]


def build_rows(n: int = 500):
    start = date(2026, 1, 1)
    rows = []
    for i in range(1, n + 1):
        product = random.choice(list(PRODUCTS))
        category, price = PRODUCTS[product]
        rows.append(
            {
                "order_id": f"ORD{i:05d}",
                "customer_id": f"CUST{random.randint(1, 60):03d}",
                "product": product,
                "category": category,
                "quantity": random.randint(1, 5),
                "unit_price": round(price * random.uniform(0.9, 1.1), 2),
                "order_date": (start + timedelta(days=random.randint(0, 120))).isoformat(),
                "country": random.choice(COUNTRIES),
                "status": random.choice(STATUSES),
            }
        )

    # --- inject dirty data ---
    rows += random.sample(rows, 15)  # duplicates
    for r in random.sample(rows, 6):  # null customer
        r["customer_id"] = ""
    for r in random.sample(rows, 6):  # bad quantity
        r["quantity"] = random.choice([0, -1, -3])
    for r in random.sample(rows, 20):  # messy text
        r["country"] = f"  {r['country'].upper()} "
        r["status"] = r["status"].upper()
    random.shuffle(rows)
    return rows


def main():
    out = Path(__file__).parent / "sample_sales.csv"
    rows = build_rows()
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
