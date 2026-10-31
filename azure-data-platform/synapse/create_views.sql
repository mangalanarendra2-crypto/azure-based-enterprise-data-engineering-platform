-- Run in Synapse Studio against the SERVERLESS SQL pool (Built-in).
-- Replace <storage_account> before running.

IF DB_ID('sales_dw') IS NULL
    CREATE DATABASE sales_dw;
GO

USE sales_dw;
GO

-- Authenticate to the lake with the workspace managed identity
-- (grant it "Storage Blob Data Reader" on the storage account).
IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = '<StrongPassword!123>';
GO

IF NOT EXISTS (SELECT * FROM sys.database_scoped_credentials WHERE name = 'lake_msi')
    CREATE DATABASE SCOPED CREDENTIAL lake_msi WITH IDENTITY = 'Managed Identity';
GO

IF NOT EXISTS (SELECT * FROM sys.external_data_sources WHERE name = 'gold_lake')
    CREATE EXTERNAL DATA SOURCE gold_lake WITH (
        LOCATION   = 'https://<storage_account>.dfs.core.windows.net/gold',
        CREDENTIAL = lake_msi
    );
GO

CREATE OR ALTER VIEW dbo.vw_daily_sales AS
SELECT *
FROM OPENROWSET(BULK 'daily_sales/', DATA_SOURCE = 'gold_lake', FORMAT = 'PARQUET') AS r;
GO

CREATE OR ALTER VIEW dbo.vw_sales_by_category AS
SELECT *
FROM OPENROWSET(BULK 'sales_by_category/', DATA_SOURCE = 'gold_lake', FORMAT = 'PARQUET') AS r;
GO

CREATE OR ALTER VIEW dbo.vw_top_customers AS
SELECT *
FROM OPENROWSET(BULK 'top_customers/', DATA_SOURCE = 'gold_lake', FORMAT = 'PARQUET') AS r;
GO

-- Sample reporting query
SELECT TOP 10 order_date, total_orders, total_revenue
FROM dbo.vw_daily_sales
ORDER BY total_revenue DESC;
