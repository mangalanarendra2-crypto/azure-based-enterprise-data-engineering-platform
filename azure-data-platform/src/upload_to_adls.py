"""Upload local raw files to the ADLS Gen2 landing container.

Auth uses DefaultAzureCredential (az login, managed identity, or env vars),
so no secrets live in code.

Usage:
    python src/upload_to_adls.py --file data/sample_sales.csv
"""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
from dotenv import load_dotenv


def upload(file_path: Path, account: str, container: str, base_path: str) -> str:
    service = DataLakeServiceClient(
        account_url=f"https://{account}.dfs.core.windows.net",
        credential=DefaultAzureCredential(),
    )
    fs = service.get_file_system_client(container)

    # Partition landing files by ingestion date: sales/ingest_date=YYYY-MM-DD/file.csv
    ingest_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target = f"{base_path}/ingest_date={ingest_date}/{file_path.name}"

    with file_path.open("rb") as f:
        fs.get_file_client(target).upload_data(f, overwrite=True)
    return f"abfss://{container}@{account}.dfs.core.windows.net/{target}"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--account", default=os.getenv("AZURE_STORAGE_ACCOUNT"))
    parser.add_argument("--container", default=os.getenv("LANDING_CONTAINER", "landing"))
    parser.add_argument("--path", default=os.getenv("LANDING_PATH", "sales"))
    args = parser.parse_args()

    if not args.account:
        raise SystemExit("Set AZURE_STORAGE_ACCOUNT in .env or pass --account")
    if not args.file.exists():
        raise SystemExit(f"File not found: {args.file}")

    uri = upload(args.file, args.account, args.container, args.path)
    print(f"Uploaded -> {uri}")


if __name__ == "__main__":
    main()
