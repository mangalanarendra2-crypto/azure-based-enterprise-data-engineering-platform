# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Gold aggregates
# MAGIC Business-ready tables. Written as Parquet so Synapse serverless SQL can query them directly.

# COMMAND ----------

dbutils.widgets.text("storage_account", "")
storage_account = dbutils.widgets.get("storage_account")

scope = "kv-data-platform"
spark.conf.set(f"fs.azure.account.auth.type.{storage_account}.dfs.core.windows.net", "OAuth")
spark.conf.set(
    f"fs.azure.account.oauth.provider.type.{storage_account}.dfs.core.windows.net",
    "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider",
)
spark.conf.set(
    f"fs.azure.account.oauth2.client.id.{storage_account}.dfs.core.windows.net",
    dbutils.secrets.get(scope, "sp-client-id"),
)
spark.conf.set(
    f"fs.azure.account.oauth2.client.secret.{storage_account}.dfs.core.windows.net",
    dbutils.secrets.get(scope, "sp-client-secret"),
)
spark.conf.set(
    f"fs.azure.account.oauth2.client.endpoint.{storage_account}.dfs.core.windows.net",
    f"https://login.microsoftonline.com/{dbutils.secrets.get(scope, 'sp-tenant-id')}/oauth2/token",
)

def lake(container: str, path: str = "") -> str:
    return f"abfss://{container}@{storage_account}.dfs.core.windows.net/{path}"

# COMMAND ----------

from pyspark.sql import functions as F

silver = spark.read.format("delta").load(lake("silver", "sales"))
valid = silver.filter(F.col("status") != "cancelled")

daily_sales = (
    valid.groupBy("order_date")
    .agg(F.countDistinct("order_id").alias("total_orders"),
         F.round(F.sum("total_amount"), 2).alias("total_revenue"))
    .orderBy("order_date")
)

sales_by_category = (
    valid.groupBy("category", "country")
    .agg(F.sum("quantity").alias("units_sold"),
         F.round(F.sum("total_amount"), 2).alias("total_revenue"))
)

top_customers = (
    valid.groupBy("customer_id")
    .agg(F.countDistinct("order_id").alias("total_orders"),
         F.round(F.sum("total_amount"), 2).alias("lifetime_value"))
    .orderBy(F.desc("lifetime_value"))
    .limit(10)
)

for name, df in {
    "daily_sales": daily_sales,
    "sales_by_category": sales_by_category,
    "top_customers": top_customers,
}.items():
    df.write.mode("overwrite").parquet(lake("gold", name))
    print(f"gold/{name}: {df.count()} rows")
