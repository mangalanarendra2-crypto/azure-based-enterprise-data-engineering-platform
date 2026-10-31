"""Medallion-layer transformations (pandas version).

These mirror the PySpark logic in databricks/*.py so the business rules can be
unit-tested locally without a Spark cluster or an Azure account.
"""
from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = [
    "order_id", "customer_id", "product", "category",
    "quantity", "unit_price", "order_date", "country", "status",
]


# ---------------------------------------------------------------- Bronze
def to_bronze(raw: pd.DataFrame, source_file: str = "unknown") -> pd.DataFrame:
    """Raw data as-is, plus ingestion metadata. No cleaning here."""
    missing = set(REQUIRED_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    df = raw.copy()
    df["_ingested_at"] = pd.Timestamp.now("UTC").tz_localize(None)
    df["_source_file"] = source_file
    return df


# ---------------------------------------------------------------- Silver
def to_silver(bronze: pd.DataFrame) -> pd.DataFrame:
    """Cleaned, typed, de-duplicated records."""
    df = bronze.copy()

    # Standardise text
    df["country"] = df["country"].astype("string").str.strip().str.upper()
    df["status"] = df["status"].astype("string").str.strip().str.lower()
    df["customer_id"] = df["customer_id"].astype("string").str.strip()
    df["customer_id"] = df["customer_id"].replace("", pd.NA)

    # Enforce types
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce").dt.date

    # Data-quality rules
    df = df.dropna(subset=["order_id", "customer_id", "order_date", "quantity", "unit_price"])
    df = df[(df["quantity"] > 0) & (df["unit_price"] > 0)]

    # De-duplicate on business key (keep latest ingested)
    if "_ingested_at" in df.columns:
        df = df.sort_values("_ingested_at")
    df = df.drop_duplicates(subset=["order_id"], keep="last")

    # Derived column
    df["quantity"] = df["quantity"].astype(int)
    df["total_amount"] = (df["quantity"] * df["unit_price"]).round(2)

    return df.reset_index(drop=True)


# ---------------------------------------------------------------- Gold
def daily_sales(silver: pd.DataFrame) -> pd.DataFrame:
    valid = silver[silver["status"] != "cancelled"]
    return (
        valid.groupby("order_date", as_index=False)
        .agg(total_orders=("order_id", "nunique"), total_revenue=("total_amount", "sum"))
        .assign(total_revenue=lambda d: d["total_revenue"].round(2))
        .sort_values("order_date")
        .reset_index(drop=True)
    )


def sales_by_category(silver: pd.DataFrame) -> pd.DataFrame:
    valid = silver[silver["status"] != "cancelled"]
    return (
        valid.groupby(["category", "country"], as_index=False)
        .agg(units_sold=("quantity", "sum"), total_revenue=("total_amount", "sum"))
        .assign(total_revenue=lambda d: d["total_revenue"].round(2))
        .sort_values(["category", "total_revenue"], ascending=[True, False])
        .reset_index(drop=True)
    )


def top_customers(silver: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    valid = silver[silver["status"] != "cancelled"]
    return (
        valid.groupby("customer_id", as_index=False)
        .agg(total_orders=("order_id", "nunique"), lifetime_value=("total_amount", "sum"))
        .assign(lifetime_value=lambda d: d["lifetime_value"].round(2))
        .sort_values("lifetime_value", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
