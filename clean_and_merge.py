from __future__ import annotations

import csv
import sqlite3
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_FILE = BASE_DIR / "clean_and_merge.db"

EXCHANGE_RATES = {
    "USD": 6.9,
    "EUR": 7.5,
    "CNY": 1.0,
    "JPY": 0.05,
}


def resolve_input_file(file_name: str) -> Path:
    data_file = DATA_DIR / file_name
    root_file = BASE_DIR / file_name

    if data_file.exists():
        return data_file
    return root_file


CUSTOMER_FILE = resolve_input_file("customer.txt")
ORDER_FILE = resolve_input_file("order.txt")



def read_csv_rows(file_path: Path, required_columns: Iterable[str]) -> list[dict[str, str]]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"{file_path.name} is empty or missing a header row.")

        missing_columns = [column for column in required_columns if column not in reader.fieldnames]
        if missing_columns:
            raise ValueError(f"{file_path.name} is missing columns: {', '.join(missing_columns)}")

        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned_row = {key: (value or "").strip() for key, value in row.items()}
            if any(cleaned_row.values()):
                rows.append(cleaned_row)
        return rows


def deduplicate_by_key(rows: list[dict[str, str]], key_field: str) -> list[dict[str, str]]:
    deduplicated: OrderedDict[str, dict[str, str]] = OrderedDict()
    for row in rows:
        key = row.get(key_field, "").strip()
        if key and key not in deduplicated:
            deduplicated[key] = row
    return list(deduplicated.values())


def convert_to_cny(amount_text: str, currency_text: str) -> float:
    currency = currency_text.strip().upper()
    if currency not in EXCHANGE_RATES:
        raise ValueError(f"Unsupported currency: {currency_text}")

    amount = float(amount_text)
    return round(amount * EXCHANGE_RATES[currency], 2)


def merge_orders_with_customers(
    orders: list[dict[str, str]],
    customers: list[dict[str, str]],
) -> list[dict[str, object]]:
    customer_lookup = {row["customer_id"]: row for row in customers}
    merged_rows: list[dict[str, object]] = []

    for order in orders:
        customer = customer_lookup.get(order["customer_id"], {})
        amount_cny = convert_to_cny(order["amount"], order["currency"])
        merged_rows.append(
            {
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "customer_name": customer.get("customer_name"),
                "region": customer.get("region"),
                "amount": float(order["amount"]),
                "currency": order["currency"].upper(),
                "amount_cny": amount_cny,
            }
        )

    return merged_rows


def write_to_sqlite(merged_rows: list[dict[str, object]], database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()

        cursor.execute("DROP TABLE IF EXISTS merged_orders")
        cursor.execute("DROP TABLE IF EXISTS region_summary")

        cursor.execute(
            """
            CREATE TABLE merged_orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                customer_name TEXT,
                region TEXT,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                amount_cny REAL NOT NULL
            )
            """
        )

        cursor.executemany(
            """
            INSERT INTO merged_orders (
                order_id,
                customer_id,
                customer_name,
                region,
                amount,
                currency,
                amount_cny
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["order_id"],
                    row["customer_id"],
                    row["customer_name"],
                    row["region"],
                    row["amount"],
                    row["currency"],
                    row["amount_cny"],
                )
                for row in merged_rows
            ],
        )

        cursor.execute(
            """
            CREATE TABLE region_summary AS
            SELECT
                region,
                ROUND(AVG(amount_cny), 2) AS avg_amount_cny
            FROM merged_orders
            WHERE region IS NOT NULL AND region <> ''
            GROUP BY region
            ORDER BY region
            """
        )

        connection.commit()


def main() -> None:
    customers = read_csv_rows(CUSTOMER_FILE, ["customer_id", "customer_name", "region"])
    orders = read_csv_rows(ORDER_FILE, ["order_id", "customer_id", "amount", "currency"])

    unique_customers = deduplicate_by_key(customers, "customer_id")
    unique_orders = deduplicate_by_key(orders, "order_id")
    merged_rows = merge_orders_with_customers(unique_orders, unique_customers)

    write_to_sqlite(merged_rows, DATABASE_FILE)

    print(f"Customers read: {len(customers)} | after dedupe: {len(unique_customers)}")
    print(f"Orders read: {len(orders)} | after dedupe: {len(unique_orders)}")
    print(f"Merged rows written to: {DATABASE_FILE}")
    print("SQLite tables created: merged_orders, region_summary")


if __name__ == "__main__":
    main()
