#!/usr/bin/env python3
"""
Generate CLEAN refund observations for Aarohan Commerce.

Inputs:
    data/raw/commerce/orders.csv
    data/raw/payments/payments.csv

Output:
    data/raw/payments/refunds.csv

No intentional anomalies are injected here.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import csv
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
ORDERS_FILE = ROOT / "data/raw/commerce/orders.csv"
PAYMENTS_FILE = ROOT / "data/raw/payments/payments.csv"
OUTPUT_FILE = ROOT / "data/raw/payments/refunds.csv"

SEED = 42
Q = Decimal("0.01")


def money(v):
    return Decimal(str(v)).quantize(Q, rounding=ROUND_HALF_UP)


def parse_dt(v):
    v = (v or "").strip()
    if not v:
        return None
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                pass
    raise ValueError(f"Unsupported timestamp: {v!r}")


def fmt(dt):
    return dt.isoformat(timespec="seconds")


def main():
    if not ORDERS_FILE.exists():
        raise FileNotFoundError(ORDERS_FILE)
    if not PAYMENTS_FILE.exists():
        raise FileNotFoundError(PAYMENTS_FILE)

    rng = random.Random(SEED)

    with ORDERS_FILE.open(newline="", encoding="utf-8") as f:
        orders = list(csv.DictReader(f))
    with PAYMENTS_FILE.open(newline="", encoding="utf-8") as f:
        payments = list(csv.DictReader(f))

    if not orders or not payments:
        raise ValueError("Orders/payments cannot be empty")

    required_orders = {
        "order_id", "customer_id", "order_date", "net_amount",
        "order_status"
    }
    required_payments = {
        "payment_id", "order_id", "payment_date", "amount",
        "status", "payment_method"
    }

    missing_o = required_orders - set(orders[0])
    missing_p = required_payments - set(payments[0])

    if missing_o:
        raise ValueError(f"orders.csv missing: {sorted(missing_o)}")
    if missing_p:
        raise ValueError(f"payments.csv missing: {sorted(missing_p)}")

    order_map = {o["order_id"]: o for o in orders}
    payment_map = {
        p["order_id"]: p
        for p in payments
        if p["status"].upper() == "SUCCESS"
    }

    # Refund policy for the synthetic clean world:
    # - Returned orders are refunded.
    # - A small deterministic share of delivered orders receive customer refunds.
    # - Confirmed/shipped orders are not refunded in this source.
    #
    # This produces realistic refund activity without introducing errors.
    candidates = []

    for o in orders:
        oid = o["order_id"]
        status = o["order_status"].strip().upper()

        if status == "RETURNED":
            candidates.append((o, "RETURN"))
        elif status == "DELIVERED" and rng.random() < 0.018:
            candidates.append((o, "CUSTOMER_REQUEST"))

    rows = []

    for o, reason_type in candidates:
        oid = o["order_id"]
        amount = money(o["net_amount"])

        if amount <= 0:
            continue

        order_dt = parse_dt(o["order_date"])
        if order_dt is None:
            raise ValueError(f"Missing order_date for {oid}")

        payment = payment_map.get(oid)

        # Digital refund: linked to the successful PayFlow payment.
        if payment:
            payment_dt = parse_dt(payment["payment_date"])
            if payment_dt is None:
                raise ValueError(f"Missing payment_date for {payment['payment_id']}")

            # Returned orders tend to be refunded after delivery/return processing.
            # Other refunds occur shortly after order/payment.
            delivered_dt = parse_dt(o.get("delivered_date"))
            if reason_type == "RETURN" and delivered_dt:
                refund_dt = delivered_dt + timedelta(
                    days=rng.randint(1, 7),
                    hours=rng.randint(1, 12)
                )
            else:
                refund_dt = payment_dt + timedelta(
                    days=rng.randint(1, 5),
                    hours=rng.randint(1, 8)
                )

            # Mostly full refunds, with a controlled amount of partial refunds.
            if reason_type == "RETURN" or rng.random() < 0.72:
                refund_amount = amount
                refund_type = "FULL"
            else:
                # Partial refund between 10% and 60%, rounded to paise.
                pct = Decimal(str(rng.randint(10, 60))) / Decimal("100")
                refund_amount = (amount * pct).quantize(
                    Q, rounding=ROUND_HALF_UP
                )
                refund_amount = max(Q, min(refund_amount, amount))
                refund_type = "PARTIAL"

            rows.append({
                "refund_id": f"REF_{len(rows)+1:06d}",
                "order_id": oid,
                "payment_id": payment["payment_id"],
                "refund_date": fmt(refund_dt),
                "refund_type": refund_type,
                "refund_reason": (
                    "RETURNED_ORDER"
                    if reason_type == "RETURN"
                    else "CUSTOMER_REQUEST"
                ),
                "amount": f"{refund_amount:.2f}",
                "currency": payment.get("currency", "INR"),
                "status": "SUCCESS",
                "gateway": payment.get("gateway", "PayFlow"),
                "gateway_reference": f"RF_{len(rows)+1:08d}",
                "customer_id": o["customer_id"],
            })

        # COD refund: no PayFlow payment exists. The refund is linked to the order
        # and remains on the separate COD collection/refund path.
        else:
            if o["payment_method_selected"].strip().upper() != "COD":
                # A non-COD order without a successful payment should not silently
                # receive a refund in the clean world.
                continue

            delivered_dt = parse_dt(o.get("delivered_date"))
            base_dt = delivered_dt or order_dt
            refund_dt = base_dt + timedelta(
                days=rng.randint(2, 8),
                hours=rng.randint(1, 10)
            )

            # COD returned orders are fully refunded.
            refund_amount = amount
            refund_type = "FULL"

            rows.append({
                "refund_id": f"REF_{len(rows)+1:06d}",
                "order_id": oid,
                "payment_id": "",
                "refund_date": fmt(refund_dt),
                "refund_type": refund_type,
                "refund_reason": "RETURNED_ORDER",
                "amount": f"{refund_amount:.2f}",
                "currency": "INR",
                "status": "SUCCESS",
                "gateway": "",
                "gateway_reference": "",
                "customer_id": o["customer_id"],
            })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "refund_id", "order_id", "payment_id", "refund_date",
        "refund_type", "refund_reason", "amount", "currency",
        "status", "gateway", "gateway_reference", "customer_id"
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # -------------------------
    # Clean-world validations
    # -------------------------
    if len({r["refund_id"] for r in rows}) != len(rows):
        raise AssertionError("Duplicate refund_id")

    for r in rows:
        oid = r["order_id"]
        o = order_map[oid]
        refund_amount = money(r["amount"])
        order_amount = money(o["net_amount"])

        if refund_amount <= 0:
            raise AssertionError(f"Non-positive refund: {r['refund_id']}")

        if refund_amount > order_amount:
            raise AssertionError(
                f"Refund exceeds order amount: {r['refund_id']}"
            )

        refund_dt = parse_dt(r["refund_date"])
        order_dt = parse_dt(o["order_date"])

        if refund_dt < order_dt:
            raise AssertionError(
                f"Refund before order: {r['refund_id']}"
            )

        if r["payment_id"]:
            p = payment_map.get(oid)
            if not p or p["payment_id"] != r["payment_id"]:
                raise AssertionError(
                    f"Invalid payment reference: {r['refund_id']}"
                )

            payment_dt = parse_dt(p["payment_date"])
            if refund_dt < payment_dt:
                raise AssertionError(
                    f"Refund before payment: {r['refund_id']}"
                )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Orders read:       {len(orders):,}")
    print(f"Payments read:     {len(payments):,}")
    print(f"Refunds generated: {len(rows):,}")
    print(
        f"Total refunds:     ₹"
        f"{sum((money(r['amount']) for r in rows), Decimal('0.00')):,.2f}"
    )

    full = sum(r["refund_type"] == "FULL" for r in rows)
    partial = sum(r["refund_type"] == "PARTIAL" for r in rows)
    digital = sum(bool(r["payment_id"]) for r in rows)
    cod = len(rows) - digital

    print("\nRefund breakdown:")
    print(f"  Full:             {full:,}")
    print(f"  Partial:          {partial:,}")
    print(f"  Digital-linked:   {digital:,}")
    print(f"  COD path:         {cod:,}")


if __name__ == "__main__":
    main()
