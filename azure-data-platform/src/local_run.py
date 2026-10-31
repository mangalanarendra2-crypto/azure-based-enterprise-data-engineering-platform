"""Run the full Bronze -> Silver -> Gold pipeline locally (no Azure needed).

Usage:  python src/local_run.py
Output: ./local_lake/{bronze,silver,gold}/*.parquet
"""
from pathlib import Path

import pandas as pd

import transforms as t

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "sample_sales.csv"
LAKE = ROOT / "local_lake"


def write(df: pd.DataFrame, layer: str, name: str) -> None:
    out = LAKE / layer
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / f"{name}.parquet", index=False)
    print(f"  [{layer:<6}] {name:<20} {len(df):>5} rows")


def main() -> None:
    if not RAW.exists():
        raise SystemExit("Run `python data/generate_sample_data.py` first.")

    raw = pd.read_csv(RAW, dtype=str)
    print(f"Read {len(raw)} raw rows from {RAW.name}")

    bronze = t.to_bronze(raw, source_file=RAW.name)
    write(bronze, "bronze", "sales")

    silver = t.to_silver(bronze)
    write(silver, "silver", "sales")

    write(t.daily_sales(silver), "gold", "daily_sales")
    write(t.sales_by_category(silver), "gold", "sales_by_category")
    write(t.top_customers(silver), "gold", "top_customers")

    print(f"\nDropped {len(bronze) - len(silver)} bad/duplicate rows in Silver.")
    print("\nTop 5 customers:")
    print(t.top_customers(silver, 5).to_string(index=False))


if __name__ == "__main__":
    main()
