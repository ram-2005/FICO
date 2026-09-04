#!/usr/bin/env python3
"""
Generate CLEAN bank transaction observations for Aarohan Commerce.

Inputs:
    data/raw/master/bank_accounts.csv
    data/raw/settlements/settlements.csv
    data/raw/payments/payments.csv
    data/raw/payments/refunds.csv
    data/raw/commerce/orders.csv

Output:
    data/raw/banking/bank_transactions.csv

This is the clean financial world.
NO intentional anomalies are injected here.

Important:
- Settlement credits hit BANK_002.
- Digital refunds are represented as legitimate debits from BANK_002.
- COD orders are NOT PayFlow settlements.
- Inter-account transfers are first-class events and cancel at company level.
- A small set of legitimate operating/administrative bank movements is included
  so the bank ledger resembles a real operating account.
- Vendor/payroll source transactions will later be reconciled to vendor/payroll
  datasets; this generator only creates the bank observation layer for flows
  already available at this stage.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import random
import sys

ROOT = Path(__file__).resolve().parents[1]

BANK_ACCOUNTS_FILE = ROOT / "data/raw/master/bank_accounts.csv"
SETTLEMENTS_FILE = ROOT / "data/raw/settlements/settlements.csv"
PAYMENTS_FILE = ROOT / "data/raw/payments/payments.csv"
REFUNDS_FILE = ROOT / "data/raw/payments/refunds.csv"
ORDERS_FILE = ROOT / "data/raw/commerce/orders.csv"

OUTPUT_FILE = ROOT / "data/raw/banking/bank_transactions.csv"

SEED = 42
Q = Decimal("0.01")
CURRENCY = "INR"

BANK_001 = "BANK_001"
BANK_002 = "BANK_002"
BANK_003 = "BANK_003"
BANK_004 = "BANK_004"


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


def add_tx(rows, account_id, dt, amount, direction, tx_type,
           description, reference_id="", counterparty_id="",
           currency=CURRENCY):
    amount = money(amount)

    if amount <= 0:
        raise ValueError(f"Bank transaction amount must be positive: {amount}")

    rows.append({
        "_dt": dt,
        "bank_transaction_id": f"BANK_{len(rows)+1:06d}",
        "account_id": account_id,
        "transaction_date": fmt(dt),
        "value_date": fmt(dt),
        "amount": f"{amount:.2f}",
        "currency": currency,
        "direction": direction,
        "transaction_type": tx_type,
        "description": description,
        "reference_id": reference_id,
        "counterparty_id": counterparty_id,
        "status": "POSTED",
    })


def main():
    for path in (
        BANK_ACCOUNTS_FILE,
        SETTLEMENTS_FILE,
        PAYMENTS_FILE,
        REFUNDS_FILE,
        ORDERS_FILE,
    ):
        if not path.exists():
            print(f"ERROR: Missing required input: {path}")
            sys.exit(1)

    rng = random.Random(SEED)

    with BANK_ACCOUNTS_FILE.open(newline="", encoding="utf-8") as f:
        bank_accounts = list(csv.DictReader(f))

    with SETTLEMENTS_FILE.open(newline="", encoding="utf-8") as f:
        settlements = list(csv.DictReader(f))

    with PAYMENTS_FILE.open(newline="", encoding="utf-8") as f:
        payments = list(csv.DictReader(f))

    with REFUNDS_FILE.open(newline="", encoding="utf-8") as f:
        refunds = list(csv.DictReader(f))

    with ORDERS_FILE.open(newline="", encoding="utf-8") as f:
        orders = list(csv.DictReader(f))

    if not bank_accounts:
        raise ValueError("bank_accounts.csv is empty")

    account_ids = {r["account_id"] for r in bank_accounts}

    expected_accounts = {BANK_001, BANK_002, BANK_003, BANK_004}
    missing_accounts = expected_accounts - account_ids

    if missing_accounts:
        raise ValueError(
            f"bank_accounts.csv missing expected accounts: "
            f"{sorted(missing_accounts)}"
        )

    rows = []

    # ------------------------------------------------------------
    # 1. PayFlow settlement credits -> BANK_002
    # ------------------------------------------------------------
    for s in settlements:
        dt = parse_dt(s["settlement_date"])

        add_tx(
            rows=rows,
            account_id=s["destination_account_id"],
            dt=dt,
            amount=s["net_settlement_amount"],
            direction="CREDIT",
            tx_type="PAYMENT_GATEWAY_SETTLEMENT",
            description=f"PayFlow settlement {s['settlement_id']}",
            reference_id=s["settlement_id"],
            counterparty_id="PAYFLOW",
            currency=s.get("currency", CURRENCY),
        )

    # ------------------------------------------------------------
    # 2. Digital refunds -> BANK_002 debit
    #
    # Only refunds with a payment_id belong to the PayFlow path.
    # COD refunds have no PayFlow bank movement here.
    # ------------------------------------------------------------
    payment_map = {p["payment_id"]: p for p in payments}

    for r in refunds:
        payment_id = (r.get("payment_id") or "").strip()

        if not payment_id:
            continue

        if r["status"].strip().upper() != "SUCCESS":
            continue

        if payment_id not in payment_map:
            raise ValueError(
                f"Refund {r['refund_id']} references unknown payment "
                f"{payment_id}"
            )

        refund_dt = parse_dt(r["refund_date"])

        add_tx(
            rows=rows,
            account_id=BANK_002,
            dt=refund_dt,
            amount=r["amount"],
            direction="DEBIT",
            tx_type="CUSTOMER_REFUND",
            description=f"Customer refund {r['refund_id']}",
            reference_id=r["refund_id"],
            counterparty_id=r["customer_id"],
            currency=r.get("currency", CURRENCY),
        )

    # ------------------------------------------------------------
    # 3. Legitimate inter-account transfers
    #
    # Every transfer produces two bank observations:
    # source DEBIT + destination CREDIT.
    #
    # These are first-class events but net to zero at company level.
    # ------------------------------------------------------------
    transfer_specs = [
        # (source, destination, amount, date offset)
        (BANK_001, BANK_002, Decimal("3500000.00"), 8),
        (BANK_002, BANK_001, Decimal("1200000.00"), 19),
        (BANK_001, BANK_003, Decimal("2500000.00"), 31),
        (BANK_001, BANK_004, Decimal("1800000.00"), 46),
        (BANK_003, BANK_001, Decimal("750000.00"), 73),
        (BANK_001, BANK_002, Decimal("2800000.00"), 91),
        (BANK_002, BANK_001, Decimal("900000.00"), 112),
        (BANK_001, BANK_003, Decimal("2200000.00"), 137),
        (BANK_001, BANK_004, Decimal("1700000.00"), 161),
        (BANK_003, BANK_001, Decimal("600000.00"), 188),
        (BANK_001, BANK_002, Decimal("3000000.00"), 214),
        (BANK_002, BANK_001, Decimal("1000000.00"), 239),
        (BANK_001, BANK_003, Decimal("2400000.00"), 263),
        (BANK_001, BANK_004, Decimal("1750000.00"), 287),
        (BANK_003, BANK_001, Decimal("650000.00"), 315),
    ]

    base_dt = datetime(2025, 9, 5, 10, 0, 0)

    for i, (source, destination, amount, day_offset) in enumerate(
        transfer_specs,
        start=1
    ):
        dt = base_dt + timedelta(
            days=day_offset,
            hours=rng.randint(0, 5),
            minutes=rng.randint(0, 59),
        )

        transfer_ref = f"XFER_{i:06d}"

        add_tx(
            rows=rows,
            account_id=source,
            dt=dt,
            amount=amount,
            direction="DEBIT",
            tx_type="INTER_ACCOUNT_TRANSFER",
            description=f"Transfer to {destination}",
            reference_id=transfer_ref,
            counterparty_id=destination,
        )

        add_tx(
            rows=rows,
            account_id=destination,
            dt=dt,
            amount=amount,
            direction="CREDIT",
            tx_type="INTER_ACCOUNT_TRANSFER",
            description=f"Transfer from {source}",
            reference_id=transfer_ref,
            counterparty_id=source,
        )

    # ------------------------------------------------------------
    # 4. Legitimate recurring bank charges / operating expenses
    #
    # These are ordinary bank observations and do not intentionally
    # create mismatches. They give the bank ledger realistic noise.
    # ------------------------------------------------------------
    monthly_dates = [
        datetime(2025, 9, 28),
        datetime(2025, 10, 28),
        datetime(2025, 11, 28),
        datetime(2025, 12, 28),
        datetime(2026, 1, 28),
        datetime(2026, 2, 28),
        datetime(2026, 3, 28),
        datetime(2026, 4, 28),
        datetime(2026, 5, 28),
        datetime(2026, 6, 28),
        datetime(2026, 7, 28),
        datetime(2026, 8, 28),
    ]

    for i, dt in enumerate(monthly_dates, start=1):
        add_tx(
            rows=rows,
            account_id=BANK_001,
            dt=dt + timedelta(hours=9),
            amount=money("8500.00"),
            direction="DEBIT",
            tx_type="BANK_CHARGES",
            description="Monthly banking service charge",
            reference_id=f"BCHG_{i:06d}",
            counterparty_id="BANKING_PROVIDER",
        )

    # A small number of legitimate utility/office debits.
    operating_expenses = [
        ("2025-09-12", "42000.00", "Utilities and connectivity"),
        ("2025-10-14", "38500.00", "Office and technology services"),
        ("2025-11-16", "51000.00", "Utilities and connectivity"),
        ("2025-12-17", "46500.00", "Office and technology services"),
        ("2026-01-15", "44000.00", "Utilities and connectivity"),
        ("2026-02-13", "39500.00", "Office and technology services"),
        ("2026-03-17", "52000.00", "Utilities and connectivity"),
        ("2026-04-14", "41000.00", "Utilities and connectivity"),
        ("2026-05-16", "47000.00", "Office and technology services"),
        ("2026-06-17", "55000.00", "Utilities and connectivity"),
        ("2026-07-15", "48500.00", "Office and technology services"),
        ("2026-08-16", "45500.00", "Utilities and connectivity"),
    ]

    for i, (date_s, amount_s, description) in enumerate(
        operating_expenses, start=1
    ):
        dt = parse_dt(date_s) + timedelta(
            hours=rng.randint(9, 16),
            minutes=rng.randint(0, 59),
        )

        add_tx(
            rows=rows,
            account_id=BANK_001,
            dt=dt,
            amount=amount_s,
            direction="DEBIT",
            tx_type="OPERATING_EXPENSE",
            description=description,
            reference_id=f"EXPBANK_{i:06d}",
            counterparty_id="OPERATING_VENDOR",
        )

    # ------------------------------------------------------------
    # Sort chronologically and reassign bank transaction IDs so IDs
    # follow bank-observation order.
    # ------------------------------------------------------------
    rows.sort(key=lambda r: (r["_dt"], r["account_id"], r["reference_id"]))

    for i, row in enumerate(rows, start=1):
        row["bank_transaction_id"] = f"BANK_{i:06d}"
        del row["_dt"]

    fields = [
        "bank_transaction_id",
        "account_id",
        "transaction_date",
        "value_date",
        "amount",
        "currency",
        "direction",
        "transaction_type",
        "description",
        "reference_id",
        "counterparty_id",
        "status",
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # ------------------------------------------------------------
    # Validations
    # ------------------------------------------------------------
    ids = [r["bank_transaction_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("Duplicate bank_transaction_id")

    for r in rows:
        if r["account_id"] not in expected_accounts:
            raise AssertionError(
                f"Unknown bank account: {r['account_id']}"
            )

        if money(r["amount"]) <= 0:
            raise AssertionError(
                f"Invalid bank amount: {r['bank_transaction_id']}"
            )

        if r["direction"] not in {"CREDIT", "DEBIT"}:
            raise AssertionError(
                f"Invalid direction: {r['bank_transaction_id']}"
            )

    # Settlement total must equal settlement source total.
    settlement_total = sum(
        (money(s["net_settlement_amount"]) for s in settlements),
        Decimal("0.00"),
    )

    bank_settlement_total = sum(
        (
            money(r["amount"])
            for r in rows
            if r["transaction_type"] == "PAYMENT_GATEWAY_SETTLEMENT"
        ),
        Decimal("0.00"),
    )

    if bank_settlement_total != settlement_total:
        raise AssertionError(
            "Bank settlement credits do not equal settlement source total"
        )

    # Refund bank debits must equal digital refund total.
    digital_refund_total = sum(
        (
            money(r["amount"])
            for r in refunds
            if r.get("payment_id") and r["status"].strip().upper() == "SUCCESS"
        ),
        Decimal("0.00"),
    )

    bank_refund_total = sum(
        (
            money(r["amount"])
            for r in rows
            if r["transaction_type"] == "CUSTOMER_REFUND"
        ),
        Decimal("0.00"),
    )

    if bank_refund_total != digital_refund_total:
        raise AssertionError(
            "Bank refund debits do not equal digital refund total"
        )

    # Inter-account transfers must net to zero across the company.
    transfer_balance = Decimal("0.00")

    for r in rows:
        if r["transaction_type"] != "INTER_ACCOUNT_TRANSFER":
            continue

        amount = money(r["amount"])
        transfer_balance += amount if r["direction"] == "CREDIT" else -amount

    if transfer_balance != Decimal("0.00"):
        raise AssertionError(
            f"Inter-account transfers do not net to zero: {transfer_balance}"
        )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Bank transactions:          {len(rows):,}")
    print(f"Settlement credits:         ₹{bank_settlement_total:,.2f}")
    print(f"Digital refund debits:      ₹{bank_refund_total:,.2f}")
    print(f"Inter-account net movement: ₹{transfer_balance:,.2f}")
    print("\nTransactions by account:")

    for account_id in (
        BANK_001,
        BANK_002,
        BANK_003,
        BANK_004,
    ):
        count = sum(r["account_id"] == account_id for r in rows)
        print(f"  {account_id}: {count:,}")


if __name__ == "__main__":
    main()
