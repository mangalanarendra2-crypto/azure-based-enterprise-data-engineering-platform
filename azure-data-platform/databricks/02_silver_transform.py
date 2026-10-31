# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Silver transform
# MAGIC Cleans, types and de-duplicates Bronze. Same rules as `src/transforms.py::to_silver`.

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

from pyspark.sql import functions as F, Window

bronze = spark.read.format("delta").load(lake("bronze", "sales"))

cleaned = (
    bronze
    .withColumn("country", F.upper(F.trim("country")))
    .withColumn("status", F.lower(F.trim("status")))
    .withColumn("customer_id", F.nullif(F.trim("customer_id"), F.lit("")))
    .withColumn("quantity", F.col("quantity").cast("int"))
    .withColumn("unit_price", F.col("unit_price").cast("double"))
    .withColumn("order_date", F.to_date("order_date", "yyyy-MM-dd"))
    .dropna(subset=["order_id", "customer_id", "order_date", "quantity", "unit_price"])
    .filter((F.col("quantity") > 0) & (F.col("unit_price") > 0))
)

# Keep the most recently ingested record per order_id
w = Window.partitionBy("order_id").orderBy(F.col("_ingested_at").desc())
silver = (
    cleaned
    .withColumn("_rn", F.row_number().over(w))
    .filter("_rn = 1").drop("_rn")
    .withColumn("total_amount", F.round(F.col("quantity") * F.col("unit_price"), 2))
)

(silver.write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .save(lake("silver", "sales")))

print(f"Silver rows: {silver.count()}")
