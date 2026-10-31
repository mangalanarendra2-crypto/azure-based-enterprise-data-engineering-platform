import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import transforms as t  # noqa: E402


def make_raw(rows):
    cols = t.REQUIRED_COLUMNS
    return pd.DataFrame(rows, columns=cols).astype(str)


GOOD = ["O1", "C1", "Laptop", "Electronics", "2", "100.00", "2026-01-05", "india", "completed"]


def test_bronze_adds_metadata_and_validates_schema():
    bronze = t.to_bronze(make_raw([GOOD]), "f.csv")
    assert {"_ingested_at", "_source_file"} <= set(bronze.columns)
    assert bronze.loc[0, "_source_file"] == "f.csv"
    with pytest.raises(ValueError):
        t.to_bronze(pd.DataFrame({"order_id": ["1"]}))


def test_silver_cleans_text_and_computes_total():
    row = GOOD.copy()
    row[7] = "  India "
    row[8] = "COMPLETED"
    silver = t.to_silver(t.to_bronze(make_raw([row])))
    assert silver.loc[0, "country"] == "INDIA"
    assert silver.loc[0, "status"] == "completed"
    assert silver.loc[0, "total_amount"] == 200.0


def test_silver_drops_bad_rows_and_duplicates():
    null_cust = ["O2", "", "Pen Set", "Stationery", "1", "10", "2026-01-06", "UK", "completed"]
    neg_qty = ["O3", "C2", "Desk", "Furniture", "-1", "250", "2026-01-07", "UK", "completed"]
    bad_date = ["O4", "C3", "Desk", "Furniture", "1", "250", "not-a-date", "UK", "completed"]
    bronze = t.to_bronze(make_raw([GOOD, GOOD, null_cust, neg_qty, bad_date]))
    silver = t.to_silver(bronze)
    assert list(silver["order_id"]) == ["O1"]


def test_gold_excludes_cancelled_and_aggregates():
    cancelled = ["O2", "C1", "Desk", "Furniture", "1", "250", "2026-01-05", "INDIA", "cancelled"]
    second = ["O3", "C2", "Desk", "Furniture", "1", "250", "2026-01-05", "INDIA", "shipped"]
    silver = t.to_silver(t.to_bronze(make_raw([GOOD, cancelled, second])))

    daily = t.daily_sales(silver)
    assert len(daily) == 1
    assert daily.loc[0, "total_orders"] == 2
    assert daily.loc[0, "total_revenue"] == 450.0

    cat = t.sales_by_category(silver)
    assert set(cat["category"]) == {"Electronics", "Furniture"}

    top = t.top_customers(silver, 1)
    assert top.loc[0, "customer_id"] == "C2"  # 250 shipped beats C1's 200
    assert top.loc[0, "lifetime_value"] == 250.0
