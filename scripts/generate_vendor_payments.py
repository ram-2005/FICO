#!/usr/bin/env python3
"""
Generate CLEAN vendor payment observations for Aarohan Commerce.

Input:
    data/raw/vendors/vendor_invoices.csv

Output:
    data/raw/vendors/vendor_payments.csv

Design:
- Approved vendor invoices are paid according to their credit terms.
- Most invoices are paid in full with one payment.
- Payments are made from BANK_003 (Vendor / Expense account).
- No intentional anomalies are injected.
- No payment is created before the invoice date.
- No payment exceeds the invoice balance.
- Uses Decimal and deterministic seed.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import csv
import random
import sys

ROOT = Path(__file__).resolve().parents[1]

INVOICES_FILE = ROOT / "data/raw/vendors/vendor_invoices.csv"
OUTPUT_FILE = ROOT / "data/raw/vendors/vendor_payments.csv"

SEED = 42
Q = Decimal("0.01")
CURRENCY = "INR"
PAYMENT_ACCOUNT = "BANK_003"


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
    if not INVOICES_FILE.exists():
        print(f"ERROR: Missing input: {INVOICES_FILE}")
        print("Generate vendor invoices first.")
        sys.exit(1)

    rng = random.Random(SEED)

    with INVOICES_FILE.open(newline="", encoding="utf-8") as f:
        invoices = list(csv.DictReader(f))

    if not invoices:
        raise ValueError("vendor_invoices.csv is empty")

    required = {
        "vendor_invoice_id",
        "vendor_id",
        "invoice_date",
        "due_date",
        "total_amount",
        "currency",
        "status",
    }

    missing = required - set(invoices[0])
    if missing:
        raise ValueError(
            f"vendor_invoices.csv missing required columns: {sorted(missing)}"
        )

    rows = []

    # Clean-world policy:
    # Every APPROVED invoice is paid in full.
    # Most are paid on the due date; some are paid slightly early and some
    # slightly late, but never by enough to imply an anomaly.
    for invoice in invoices:
        status = invoice["status"].strip().upper()

        if status != "APPROVED":
            continue

        invoice_id = invoice["vendor_invoice_id"]
        vendor_id = invoice["vendor_id"]

        invoice_dt = parse_dt(invoice["invoice_date"])
        due_dt = parse_dt(invoice["due_date"])

        if invoice_dt is None or due_dt is None:
            raise ValueError(
                f"Missing invoice/due date for {invoice_id}"
            )

        amount = money(invoice["total_amount"])

        if amount <= 0:
            raise ValueError(
                f"Invalid invoice amount for {invoice_id}: {amount}"
            )

        # 70% on due date, 20% early, 10% modestly late.
        timing = rng.random()

        if timing < 0.20:
            days_offset = -rng.randint(1, 5)
        elif timing < 0.90:
            days_offset = 0
        else:
            days_offset = rng.randint(1, 3)

        payment_dt = due_dt + timedelta(
            days=days_offset,
            hours=rng.randint(9, 16),
            minutes=rng.randint(0, 59),
        )

        # Never allow payment before invoice date.
        if payment_dt < invoice_dt:
            payment_dt = invoice_dt + timedelta(
                days=1,
                hours=rng.randint(9, 16),
                minutes=rng.randint(0, 59),
            )

        payment_number = len(rows) + 1

        rows.append({
            "vendor_payment_id": f"VPAY_{payment_number:06d}",
            "vendor_invoice_id": invoice_id,
            "vendor_id": vendor_id,
            "payment_date": fmt(payment_dt),
            "payment_account_id": PAYMENT_ACCOUNT,
            "amount": f"{amount:.2f}",
            "currency": invoice.get("currency") or CURRENCY,
            "payment_method": "BANK_TRANSFER",
            "status": "SUCCESS",
            "bank_reference": f"VENDPAY_{payment_number:08d}",
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "vendor_payment_id",
        "vendor_invoice_id",
        "vendor_id",
        "payment_date",
        "payment_account_id",
        "amount",
        "currency",
        "payment_method",
        "status",
        "bank_reference",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # -------------------------
    # Clean-world validations
    # -------------------------
    invoice_map = {
        i["vendor_invoice_id"]: i
        for i in invoices
    }

    payment_ids = [r["vendor_payment_id"] for r in rows]
    bank_refs = [r["bank_reference"] for r in rows]

    if len(payment_ids) != len(set(payment_ids)):
        raise AssertionError("Duplicate vendor_payment_id")

    if len(bank_refs) != len(set(bank_refs)):
        raise AssertionError("Duplicate bank_reference")

    for r in rows:
        invoice = invoice_map.get(r["vendor_invoice_id"])

        if not invoice:
            raise AssertionError(
                f"Unknown vendor invoice: {r['vendor_invoice_id']}"
            )

        if r["vendor_id"] != invoice["vendor_id"]:
            raise AssertionError(
                f"Vendor mismatch: {r['vendor_payment_id']}"
            )

        payment_amount = money(r["amount"])
        invoice_amount = money(invoice["total_amount"])

        if payment_amount != invoice_amount:
            raise AssertionError(
                f"Payment does not fully settle invoice: "
                f"{r['vendor_payment_id']}"
            )

        payment_dt = parse_dt(r["payment_date"])
        invoice_dt = parse_dt(invoice["invoice_date"])

        if payment_dt < invoice_dt:
            raise AssertionError(
                f"Payment before invoice: {r['vendor_payment_id']}"
            )

        if r["payment_account_id"] != PAYMENT_ACCOUNT:
            raise AssertionError(
                f"Wrong payment account: {r['vendor_payment_id']}"
            )

        if r["status"] != "SUCCESS":
            raise AssertionError(
                f"Unexpected payment status: {r['vendor_payment_id']}"
            )

    total_invoiced = sum(
        (
            money(i["total_amount"])
            for i in invoices
            if i["status"].strip().upper() == "APPROVED"
        ),
        Decimal("0.00"),
    )

    total_paid = sum(
        (money(r["amount"]) for r in rows),
        Decimal("0.00"),
    )

    if total_paid != total_invoiced:
        raise AssertionError(
            f"Total paid ₹{total_paid} != "
            f"approved invoices ₹{total_invoiced}"
        )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Approved invoices: {len([i for i in invoices if i['status'].strip().upper() == 'APPROVED']):,}")
    print(f"Vendor payments:   {len(rows):,}")
    print(f"Total paid:        ₹{total_paid:,.2f}")
    print(f"Payment account:   {PAYMENT_ACCOUNT}")


if __name__ == "__main__":
    main()
