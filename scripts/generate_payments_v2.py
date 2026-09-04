#!/usr/bin/env python3
"""
Generate clean payment observations for the Aarohan Commerce synthetic world.

Input:
    data/raw/commerce/orders.csv

Expected order schema:
    order_id,customer_id,order_date,gross_amount,discount,tax,shipping_fee,
    net_amount,order_status,payment_method_selected,fulfillment_hub,
    invoice_date,delivered_date,sku_lines

Output:
    data/raw/payments/payments.csv

Important:
- This generator creates CLEAN source observations.
- No intentional anomalies/miscalculations are injected here.
- Digital orders create PayFlow gateway payment records.
- COD orders do NOT create gateway payment records.
- Payment amount = order net_amount.
- Decimal is used for authoritative money calculations.
- Deterministic seed = 42.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import csv
import random
import sys


ROOT = Path(__file__).resolve().parents[1]
ORDERS_FILE = ROOT / "data/raw/commerce/orders.csv"
OUTPUT_FILE = ROOT / "data/raw/payments/payments.csv"

SEED = 42
GATEWAY = "PayFlow"
CURRENCY = "INR"
Q = Decimal("0.01")

DIGITAL_METHODS = {"UPI", "CARD", "NET_BANKING"}


def money(value):
    return Decimal(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


def parse_dt(value):
    value = (value or "").strip()
    if not value:
        return None

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass

    raise ValueError(f"Unsupported timestamp format: {value!r}")


def format_dt(dt):
    return dt.isoformat(timespec="seconds")


def main():
    if not ORDERS_FILE.exists():
        print(f"ERROR: Orders file not found: {ORDERS_FILE}")
        sys.exit(1)

    rng = random.Random(SEED)

    with ORDERS_FILE.open("r", newline="", encoding="utf-8") as f:
        orders = list(csv.DictReader(f))

    if not orders:
        raise ValueError("orders.csv is empty")

    required = {
        "order_id",
        "customer_id",
        "order_date",
        "net_amount",
        "order_status",
        "payment_method_selected",
    }

    missing = required - set(orders[0].keys())
    if missing:
        raise ValueError(
            f"orders.csv is missing required columns: {sorted(missing)}"
        )

    rows = []
    skipped_cod = 0
    skipped_cancelled = 0

    for order in orders:
        order_id = order["order_id"]
        method = (order["payment_method_selected"] or "").strip().upper()
        status = (order["order_status"] or "").strip().upper()

        # COD follows a separate collection/remittance path.
        if method == "COD":
            skipped_cod += 1
            continue

        if method not in DIGITAL_METHODS:
            raise ValueError(
                f"Unexpected payment method {method!r} "
                f"for order {order_id}"
            )

        # A cancelled order should not create a successful gateway payment.
        if status == "CANCELLED":
            skipped_cancelled += 1
            continue

        order_dt = parse_dt(order["order_date"])
        if order_dt is None:
            raise ValueError(f"Missing order_date for {order_id}")

        amount = money(order["net_amount"])

        if amount < Decimal("0.00"):
            raise ValueError(
                f"Negative net_amount for {order_id}: {amount}"
            )

        # Payment is observed shortly after order placement.
        payment_dt = order_dt + timedelta(
            seconds=rng.randint(15, 20 * 60)
        )

        payment_number = len(rows) + 1

        rows.append({
            "payment_id": f"PAY_{payment_number:06d}",
            "order_id": order_id,
            "customer_id": order["customer_id"],
            "payment_date": format_dt(payment_dt),
            "gateway": GATEWAY,
            "payment_method": method,
            "amount": f"{amount:.2f}",
            "currency": CURRENCY,
            "status": "SUCCESS",
            "gateway_reference": f"PF_{payment_number:08d}",
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "payment_id",
        "order_id",
        "customer_id",
        "payment_date",
        "gateway",
        "payment_method",
        "amount",
        "currency",
        "status",
        "gateway_reference",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # -------------------------
    # Deterministic validations
    # -------------------------
    payment_ids = [r["payment_id"] for r in rows]
    order_ids = [r["order_id"] for r in rows]
    gateway_refs = [r["gateway_reference"] for r in rows]

    if len(payment_ids) != len(set(payment_ids)):
        raise AssertionError("Duplicate payment_id found")

    if len(order_ids) != len(set(order_ids)):
        raise AssertionError("Duplicate order_id found in payments")

    if len(gateway_refs) != len(set(gateway_refs)):
        raise AssertionError("Duplicate gateway_reference found")

    order_map = {o["order_id"]: o for o in orders}

    for row in rows:
        order = order_map[row["order_id"]]

        if row["payment_method"] == "COD":
            raise AssertionError(
                f"COD leaked into gateway payments: {row['payment_id']}"
            )

        if row["status"] != "SUCCESS":
            raise AssertionError(
                f"Unexpected payment status: {row['payment_id']}"
            )

        if money(row["amount"]) != money(order["net_amount"]):
            raise AssertionError(
                f"Payment/order amount mismatch: "
                f"{row['payment_id']} / {row['order_id']}"
            )

        payment_dt = parse_dt(row["payment_date"])
        order_dt = parse_dt(order["order_date"])

        if payment_dt < order_dt:
            raise AssertionError(
                f"Payment occurs before order: {row['payment_id']}"
            )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Orders read:             {len(orders):,}")
    print(f"Digital payments:       {len(rows):,}")
    print(f"COD orders excluded:    {skipped_cod:,}")
    print(f"Cancelled excluded:     {skipped_cancelled:,}")
    print(f"Gateway:                {GATEWAY}")
    print(
        f"Total digital payments: "
        f"₹{sum((money(r['amount']) for r in rows), Decimal('0.00')):,.2f}"
    )

    print("\nPayment methods:")
    counts = {}
    for row in rows:
        method = row["payment_method"]
        counts[method] = counts.get(method, 0) + 1

    for method in ("UPI", "CARD", "NET_BANKING"):
        print(f"  {method:12s}: {counts.get(method, 0):,}")


if __name__ == "__main__":
    main()
