#!/usr/bin/env python3
"""
Generate clean payment observations for the Aarohan Commerce synthetic world.

Input:
    data/raw/commerce/orders.csv

Output:
    data/raw/payments/payments.csv

Design:
- Clean source observations only. No intentional anomalies are injected here.
- Digital methods: UPI, CARD, NET_BANKING.
- COD orders do NOT create gateway payment records.
- One successful payment observation is generated for each eligible digital order.
- Payment amounts equal the order total.
- Uses Decimal for authoritative monetary calculations.
- Deterministic with a fixed seed.
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

DIGITAL_METHODS = {"UPI", "CARD", "NET_BANKING"}

# Approved payment mix for the synthetic world.
# COD is deliberately excluded because it follows a separate collection/remittance path.
METHOD_WEIGHTS = {
    "UPI": 0.50,
    "CARD": 0.28,
    "NET_BANKING": 0.10,
}

Q = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


def parse_dt(value):
    value = (value or "").strip()
    if not value:
        return None

    # Handle common ISO forms emitted by the order generator.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Fallback for plain timestamps.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass

    raise ValueError(f"Unsupported timestamp format: {value!r}")


def format_dt(dt):
    # Keep a deterministic ISO-style timestamp without timezone conversion.
    return dt.isoformat(timespec="seconds")


def weighted_choice(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def main():
    if not ORDERS_FILE.exists():
        print(f"ERROR: Orders file not found: {ORDERS_FILE}")
        print("Run the order generator first.")
        sys.exit(1)

    rng = random.Random(SEED)

    with ORDERS_FILE.open("r", newline="", encoding="utf-8") as f:
        orders = list(csv.DictReader(f))

    if not orders:
        raise ValueError("orders.csv is empty")

    required = {
        "order_id",
        "order_date",
        "total_amount",
        "payment_method",
        "currency",
    }
    missing = required - set(orders[0].keys())
    if missing:
        raise ValueError(f"orders.csv is missing required columns: {sorted(missing)}")

    digital_orders = []
    skipped_cod = 0

    for order in orders:
        method = (order.get("payment_method") or "").strip().upper()

        if method == "COD":
            skipped_cod += 1
            continue

        if method not in DIGITAL_METHODS:
            raise ValueError(
                f"Unexpected payment method {method!r} for order {order.get('order_id')}"
            )

        # Only create gateway payment observations for orders that can legitimately
        # have a completed digital payment.
        status = (order.get("status") or "").strip().upper()
        if status in {"CANCELLED"}:
            continue

        digital_orders.append(order)

    methods = list(METHOD_WEIGHTS.keys())
    weights = list(METHOD_WEIGHTS.values())

    rows = []

    for i, order in enumerate(digital_orders, start=1):
        order_id = order["order_id"]
        order_dt = parse_dt(order["order_date"])
        amount = money(order["total_amount"])

        if order_dt is None:
            raise ValueError(f"Missing order_date for {order_id}")

        # Payment occurs shortly after order creation.
        # This is a clean-world observation; later anomaly injection may alter it.
        payment_dt = order_dt + timedelta(
            seconds=rng.randint(15, 20 * 60)
        )

        source_method = (order["payment_method"] or "").strip().upper()

        # Preserve the order's legitimate payment method. The method weights are
        # enforced by the order generator; we do not randomly rewrite it here.
        method = source_method

        rows.append({
            "payment_id": f"PAY_{i:06d}",
            "order_id": order_id,
            "payment_date": format_dt(payment_dt),
            "gateway": GATEWAY,
            "payment_method": method,
            "amount": f"{amount:.2f}",
            "currency": order.get("currency") or CURRENCY,
            "status": "SUCCESS",
            "gateway_reference": f"PF_{i:08d}",
            "customer_id": order.get("customer_id", ""),
            "invoice_id": order.get("invoice_id", ""),
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "payment_id",
        "order_id",
        "payment_date",
        "gateway",
        "payment_method",
        "amount",
        "currency",
        "status",
        "gateway_reference",
        "customer_id",
        "invoice_id",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # -------------------------
    # Deterministic validations
    # -------------------------
    payment_order_ids = [r["order_id"] for r in rows]

    if len(payment_order_ids) != len(set(payment_order_ids)):
        raise AssertionError("Duplicate order_id found in payments")

    if any(m not in DIGITAL_METHODS for m in [r["payment_method"] for r in rows]):
        raise AssertionError("COD or unknown method leaked into gateway payments")

    order_map = {o["order_id"]: o for o in orders}

    for r in rows:
        order = order_map[r["order_id"]]
        if money(r["amount"]) != money(order["total_amount"]):
            raise AssertionError(
                f"Payment/order amount mismatch: {r['payment_id']} / {r['order_id']}"
            )

        if r["status"] != "SUCCESS":
            raise AssertionError(f"Unexpected payment status: {r['payment_id']}")

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Orders read:              {len(orders):,}")
    print(f"Digital payments:        {len(rows):,}")
    print(f"COD orders excluded:      {skipped_cod:,}")
    print(f"Gateway:                  {GATEWAY}")
    print(f"Total digital payment ₹:  {sum((money(r['amount']) for r in rows), Decimal('0')):,.2f}")

    by_method = {}
    for r in rows:
        by_method[r["payment_method"]] = by_method.get(r["payment_method"], 0) + 1

    print("\nPayment methods:")
    for method in methods:
        print(f"  {method:12s}: {by_method.get(method, 0):,}")


if __name__ == "__main__":
    main()
