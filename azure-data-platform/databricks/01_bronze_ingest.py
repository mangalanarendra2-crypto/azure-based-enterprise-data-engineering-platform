# Databricks notebook source
# MAGIC %md
# MAGIC # 01 - Bronze ingestion
# MAGIC Reads raw CSVs from the **landing** container and writes them untouched (plus metadata) to **bronze** as Delta.

# COMMAND ----------

dbutils.widgets.text("storage_account", "")
dbutils.widgets.text("landing_path", "sales")

storage_account = dbutils.widgets.get("storage_account")
landing_path = dbutils.widgets.get("landing_path")

# Auth: service principal creds kept in a Databricks secret scope (backed by Key Vault).
# Create the scope + secrets first - see README.
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

raw = (
    spark.read.option("header", True)
    .option("inferSchema", False)  # keep everything as string in Bronze
    .csv(lake("landing", f"{landing_path}/*/*.csv"))
)

bronze = (
    raw.withColumn("_ingested_at", F.current_timestamp())
       .withColumn("_source_file", F.input_file_name())
)

(bronze.write.format("delta")
    .mode("append")
    .save(lake("bronze", "sales")))

print(f"Bronze rows written: {bronze.count()}")
