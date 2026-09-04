#!/usr/bin/env python3
"""
Generate CLEAN PayFlow settlement observations for Aarohan Commerce.

Inputs:
    data/raw/payments/payments.csv
    data/raw/payments/refunds.csv

Output:
    data/raw/settlements/settlements.csv

Clean-world rules:
- Digital PayFlow SUCCESS payments are settled in batches.
- Settlement delay is 1–4 days after payment.
- Refunds that occur before settlement reduce the settlement amount.
- Refunds after settlement are NOT retroactively deducted; they remain a
  separate refund cash-flow event.
- No intentional anomalies are injected.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
PAYMENTS_FILE = ROOT / "data/raw/payments/payments.csv"
REFUNDS_FILE = ROOT / "data/raw/payments/refunds.csv"
OUTPUT_FILE = ROOT / "data/raw/settlements/settlements.csv"

SEED = 42
Q = Decimal("0.01")
GATEWAY = "PayFlow"
DESTINATION_ACCOUNT = "BANK_002"
CURRENCY = "INR"

BATCH_MIN = 25
BATCH_MAX = 75


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
    if not PAYMENTS_FILE.exists():
        print(f"ERROR: Missing {PAYMENTS_FILE}")
        sys.exit(1)

    if not REFUNDS_FILE.exists():
        print(f"ERROR: Missing {REFUNDS_FILE}")
        sys.exit(1)

    rng = random.Random(SEED)

    with PAYMENTS_FILE.open(newline="", encoding="utf-8") as f:
        payments = list(csv.DictReader(f))

    with REFUNDS_FILE.open(newline="", encoding="utf-8") as f:
        refunds = list(csv.DictReader(f))

    if not payments:
        raise ValueError("payments.csv is empty")

    required_payments = {
        "payment_id",
        "order_id",
        "payment_date",
        "amount",
        "status",
        "gateway",
    }
    required_refunds = {
        "refund_id",
        "order_id",
        "refund_date",
        "amount",
        "status",
    }

    missing_p = required_payments - set(payments[0])
    if missing_p:
        raise ValueError(f"payments.csv missing: {sorted(missing_p)}")

    if refunds:
        missing_r = required_refunds - set(refunds[0])
        if missing_r:
            raise ValueError(f"refunds.csv missing: {sorted(missing_r)}")

    # Only successful PayFlow digital payments enter gateway settlement.
    eligible = [
        p for p in payments
        if p["status"].strip().upper() == "SUCCESS"
        and p["gateway"].strip() == GATEWAY
    ]

    payment_map = {p["payment_id"]: p for p in eligible}
    order_payment_map = {p["order_id"]: p for p in eligible}

    # Index refunds by order. COD refunds have no payment_id and therefore
    # must never reduce a PayFlow settlement.
    refunds_by_payment = defaultdict(list)

    for r in refunds:
        payment_id = (r.get("payment_id") or "").strip()
        if not payment_id:
            continue

        if payment_id not in payment_map:
            raise ValueError(
                f"Refund {r['refund_id']} references unknown payment "
                f"{payment_id}"
            )

        if r["status"].strip().upper() != "SUCCESS":
            continue

        refunds_by_payment[payment_id].append(r)

    # Sort by payment timestamp so batching is deterministic.
    eligible.sort(key=lambda p: (parse_dt(p["payment_date"]), p["payment_id"]))

    # Build batches. A settlement is a gateway batch, not a payment-per-row
    # bank movement.
    batches = []
    current = []

    for p in eligible:
        current.append(p)

        target_size = rng.randint(BATCH_MIN, BATCH_MAX)

        if len(current) >= target_size:
            batches.append(current)
            current = []

    if current:
        batches.append(current)

    rows = []

    for batch_index, batch in enumerate(batches, start=1):
        batch_start = min(parse_dt(p["payment_date"]) for p in batch)

        # Settlement occurs 1–4 days after the latest payment in the batch.
        latest_payment_dt = max(parse_dt(p["payment_date"]) for p in batch)
        settlement_dt = latest_payment_dt + timedelta(
            days=rng.randint(1, 4),
            hours=rng.randint(0, 8),
            minutes=rng.randint(0, 59),
        )

        gross = Decimal("0.00")
        refund_deductions = Decimal("0.00")

        for p in batch:
            gross += money(p["amount"])

            for r in refunds_by_payment.get(p["payment_id"], []):
                refund_dt = parse_dt(r["refund_date"])

                # Only refunds known before the settlement are deducted from
                # the gateway settlement batch.
                if refund_dt <= settlement_dt:
                    refund_deductions += money(r["amount"])

        net = money(gross - refund_deductions)

        if net < Decimal("0.00"):
            raise AssertionError(
                f"Negative settlement amount for batch {batch_index}"
            )

        first_payment = min(batch, key=lambda p: parse_dt(p["payment_date"]))
        last_payment = max(batch, key=lambda p: parse_dt(p["payment_date"]))

        rows.append({
            "settlement_id": f"SET_{batch_index:06d}",
            "settlement_date": fmt(settlement_dt),
            "gateway": GATEWAY,
            "currency": CURRENCY,
            "payment_count": str(len(batch)),
            "gross_amount": f"{gross:.2f}",
            "refund_deductions": f"{refund_deductions:.2f}",
            "net_settlement_amount": f"{net:.2f}",
            "destination_account_id": DESTINATION_ACCOUNT,
            "gateway_settlement_reference": f"PFSET_{batch_index:08d}",
            "first_payment_id": first_payment["payment_id"],
            "last_payment_id": last_payment["payment_id"],
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "settlement_id",
        "settlement_date",
        "gateway",
        "currency",
        "payment_count",
        "gross_amount",
        "refund_deductions",
        "net_settlement_amount",
        "destination_account_id",
        "gateway_settlement_reference",
        "first_payment_id",
        "last_payment_id",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # -------------------------
    # Clean-world validations
    # -------------------------
    if len({r["settlement_id"] for r in rows}) != len(rows):
        raise AssertionError("Duplicate settlement_id")

    if len({r["gateway_settlement_reference"] for r in rows}) != len(rows):
        raise AssertionError("Duplicate gateway settlement reference")

    for r in rows:
        gross = money(r["gross_amount"])
        deductions = money(r["refund_deductions"])
        net = money(r["net_settlement_amount"])

        if net != money(gross - deductions):
            raise AssertionError(
                f"Settlement formula mismatch: {r['settlement_id']}"
            )

        if net < 0:
            raise AssertionError(
                f"Negative settlement: {r['settlement_id']}"
            )

        if r["destination_account_id"] != DESTINATION_ACCOUNT:
            raise AssertionError(
                f"Wrong destination account: {r['settlement_id']}"
            )

        if int(r["payment_count"]) <= 0:
            raise AssertionError(
                f"Empty settlement batch: {r['settlement_id']}"
            )

    total_gross = sum(
        (money(r["gross_amount"]) for r in rows),
        Decimal("0.00")
    )
    total_deductions = sum(
        (money(r["refund_deductions"]) for r in rows),
        Decimal("0.00")
    )
    total_net = sum(
        (money(r["net_settlement_amount"]) for r in rows),
        Decimal("0.00")
    )

    expected_gross = sum(
        (money(p["amount"]) for p in eligible),
        Decimal("0.00")
    )

    if total_gross != expected_gross:
        raise AssertionError(
            f"Settlement gross total {total_gross} != "
            f"eligible payment total {expected_gross}"
        )

    if total_net != money(total_gross - total_deductions):
        raise AssertionError("Global settlement total mismatch")

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Successful PayFlow payments: {len(eligible):,}")
    print(f"Settlement batches:           {len(rows):,}")
    print(f"Gross settled:                ₹{total_gross:,.2f}")
    print(f"Refund deductions:            ₹{total_deductions:,.2f}")
    print(f"Net settlement:               ₹{total_net:,.2f}")
    print(f"Destination account:          {DESTINATION_ACCOUNT}")


if __name__ == "__main__":
    main()
