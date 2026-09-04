#!/usr/bin/env python3
"""
Generate M1 ground-truth expected_states.csv.

Expected states are deterministic truth-level checks/aggregates that describe
what should be true in the clean synthetic world. They are NOT anomaly labels
and do not read anomalies.csv.

Reads:
  data/raw/commerce/orders.csv
  data/raw/commerce/invoices.csv
  data/raw/payments/payments.csv
  data/raw/payments/refunds.csv
  data/raw/settlements/settlements.csv
  data/raw/banking/bank_transactions.csv
  data/raw/vendors/vendor_invoices.csv
  data/raw/vendors/vendor_payments.csv
  data/raw/payroll/payroll.csv
  data/raw/accounting/journal_entries.csv

Writes:
  data/ground_truth/expected_states.csv
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "ground_truth" / "expected_states.csv"
Q = Decimal("0.01")

def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def money(x):
    return Decimal(str(x or "0")).quantize(Q, rounding=ROUND_HALF_UP)

def amount(row, *fields):
    for f in fields:
        if row.get(f) not in (None, ""):
            return money(row[f])
    return Decimal("0.00")

def add(rows, state_id, state_type, entity_type, entity_id,
        metric, expected_value, unit, rule, source_system="", source_record_id=""):
    rows.append({
        "state_id": state_id,
        "state_type": state_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metric": metric,
        "expected_value": str(expected_value),
        "unit": unit,
        "rule": rule,
        "source_system": source_system,
        "source_record_id": source_record_id,
    })

def main():
    orders = read(RAW/"commerce/orders.csv")
    invoices = read(RAW/"commerce/invoices.csv")
    payments = read(RAW/"payments/payments.csv")
    refunds = read(RAW/"payments/refunds.csv")
    settlements = read(RAW/"settlements/settlements.csv")
    bank = read(RAW/"banking/bank_transactions.csv")
    vendor_invoices = read(RAW/"vendors/vendor_invoices.csv")
    vendor_payments = read(RAW/"vendors/vendor_payments.csv")
    payroll = read(RAW/"payroll/payroll.csv")
    journals = read(RAW/"accounting/journal_entries.csv")

    rows = []
    seq = 1

    def state(*args):
        nonlocal seq
        add(rows, f"STATE_{seq:06d}", *args)
        seq += 1

    # ------------------------------------------------------------------
    # Per-order commercial invariants
    # ------------------------------------------------------------------
    invoice_by_order = defaultdict(list)
    payment_by_order = defaultdict(list)
    refund_by_order = defaultdict(list)

    for r in invoices:
        if r.get("order_id"):
            invoice_by_order[r["order_id"]].append(r)
    for r in payments:
        if r.get("order_id"):
            payment_by_order[r["order_id"]].append(r)
    for r in refunds:
        if r.get("order_id"):
            refund_by_order[r["order_id"]].append(r)

    for o in orders:
        oid = o.get("order_id", "")
        order_value = amount(o, "net_amount", "total_amount")
        status = (o.get("order_status") or "").upper()

        # Approved world: one commercial order has at most one invoice.
        invs = invoice_by_order.get(oid, [])
        state(
            "ENTITY_INVARIANT", "ORDER", oid,
            "invoice_count", len(invs), "count",
            "Expected 1 invoice for a non-cancelled order; cancelled orders "
            "may remain uninvoiced if invoice_date is absent in the source.",
            "commerce_invoices", oid
        )

        # Refund cannot exceed original order value.
        refund_total = sum(
            (amount(r, "refund_amount", "amount") for r in refund_by_order.get(oid, [])),
            Decimal("0")
        )
        state(
            "ENTITY_INVARIANT", "ORDER", oid,
            "refund_total_not_above_order", str(refund_total <= order_value).lower(),
            "boolean",
            "Total customer refunds for an order must not exceed its net order amount.",
            "refunds", oid
        )

        # Delivered date is expected for delivered/returned orders.
        if status in {"DELIVERED", "RETURNED"}:
            state(
                "ENTITY_INVARIANT", "ORDER", oid,
                "delivery_timestamp_present",
                str(bool(o.get("delivered_date"))).lower(),
                "boolean",
                "Delivered and returned orders require a delivery timestamp.",
                "commerce_orders", oid
            )

    # ------------------------------------------------------------------
    # Payment invariants
    # ------------------------------------------------------------------
    for p in payments:
        pid = p.get("payment_id", "")
        oid = p.get("order_id", "")
        a = amount(p, "amount", "paid_amount", "payment_amount")

        state(
            "ENTITY_INVARIANT", "PAYMENT", pid,
            "amount_positive", str(a > 0).lower(), "boolean",
            "Successful payment amount must be greater than zero.",
            "payments", pid
        )
        state(
            "ENTITY_INVARIANT", "PAYMENT", pid,
            "payment_links_to_order", str(bool(oid)).lower(), "boolean",
            "Every digital payment must reference an order.",
            "payments", pid
        )

    # ------------------------------------------------------------------
    # Refund invariants
    # ------------------------------------------------------------------
    for r in refunds:
        rid = r.get("refund_id", "")
        a = amount(r, "refund_amount", "amount")
        oid = r.get("order_id", "")
        order = next((x for x in orders if x.get("order_id") == oid), None)
        order_value = amount(order or {}, "net_amount", "total_amount")

        state(
            "ENTITY_INVARIANT", "REFUND", rid,
            "amount_positive", str(a > 0).lower(), "boolean",
            "Refund amount must be greater than zero.",
            "refunds", rid
        )
        state(
            "ENTITY_INVARIANT", "REFUND", rid,
            "amount_within_order", str(a <= order_value).lower(), "boolean",
            "Individual refund cannot exceed its order net amount.",
            "refunds", rid
        )

    # ------------------------------------------------------------------
    # Settlement arithmetic
    # ------------------------------------------------------------------
    for s in settlements:
        sid = s.get("settlement_id", "")
        a = amount(s, "settlement_amount", "amount", "net_amount")
        state(
            "ENTITY_INVARIANT", "SETTLEMENT", sid,
            "settlement_amount_positive", str(a > 0).lower(), "boolean",
            "A settlement record represents a positive net gateway settlement.",
            "settlements", sid
        )
        state(
            "ENTITY_INVARIANT", "SETTLEMENT", sid,
            "destination_account", s.get("destination_account_id") or "BANK_002",
            "account_id",
            "PayFlow settlements are deposited into the payment-settlement bank account.",
            "settlements", sid
        )

    # ------------------------------------------------------------------
    # Vendor payment invariants
    # ------------------------------------------------------------------
    for vp in vendor_payments:
        pid = vp.get("vendor_payment_id", "")
        a = amount(vp, "payment_amount", "amount", "paid_amount")
        state(
            "ENTITY_INVARIANT", "VENDOR_PAYMENT", pid,
            "amount_positive", str(a > 0).lower(), "boolean",
            "Vendor payment amount must be positive.",
            "vendor_payments", pid
        )
        state(
            "ENTITY_INVARIANT", "VENDOR_PAYMENT", pid,
            "bank_account", vp.get("bank_account_id") or "BANK_003",
            "account_id",
            "Vendor payments are made from the vendor/expense bank account.",
            "vendor_payments", pid
        )

    # ------------------------------------------------------------------
    # Payroll invariants
    # ------------------------------------------------------------------
    for p in payroll:
        pid = p.get("payroll_id", "")
        gross = amount(p, "gross_salary", "gross_pay", "salary")
        net = amount(p, "net_pay", "net_salary")
        pf = amount(p, "employee_pf", "employee_pf_contribution")
        tds = amount(p, "tds", "income_tax", "tds_amount")
        pt = amount(p, "professional_tax", "pt")
        expected_net = money(gross - pf - tds - pt)

        state(
            "ENTITY_INVARIANT", "PAYROLL", pid,
            "net_pay_formula",
            str(expected_net == net).lower(), "boolean",
            "Net pay = gross salary - employee PF - TDS - professional tax.",
            "payroll", pid
        )
        state(
            "ENTITY_INVARIANT", "PAYROLL", pid,
            "payment_account", p.get("payment_account_id") or "BANK_004",
            "account_id",
            "Payroll is paid from the payroll/statutory bank account.",
            "payroll", pid
        )

    # ------------------------------------------------------------------
    # Bank transfer neutrality
    # ------------------------------------------------------------------
    transfer_groups = defaultdict(list)
    for b in bank:
        key = ""
        for f in ("transfer_id", "reference_id", "reference",
                  "transaction_reference", "counterparty_reference"):
            v = (b.get(f) or "").strip()
            if v.upper().startswith(("XFER_", "TRANSFER_")):
                key = v
                break
        if key:
            transfer_groups[key].append(b)

    for transfer_id, txns in transfer_groups.items():
        net = Decimal("0")
        for b in txns:
            a = amount(b, "amount", "transaction_amount", "net_amount")
            direction = (b.get("direction") or "").upper()
            net += a if direction in {"CREDIT","CR","IN"} else -a

        state(
            "TRANSFER_INVARIANT", "BANK_TRANSFER", transfer_id,
            "company_cash_net_effect", f"{net:.2f}", "INR",
            "Inter-account transfers must have zero net effect on total company cash.",
            "banking", transfer_id
        )

    # ------------------------------------------------------------------
    # Journal-entry balance invariants
    # ------------------------------------------------------------------
    grouped = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for j in journals:
        jid = j.get("journal_entry_id", "")
        grouped[jid][0] += amount(j, "debit")
        grouped[jid][1] += amount(j, "credit")

    for jid, (debit, credit) in grouped.items():
        state(
            "ACCOUNTING_INVARIANT", "JOURNAL_ENTRY", jid,
            "debits_equal_credits",
            str(debit == credit).lower(), "boolean",
            "Every journal entry must have total debits equal to total credits.",
            "accounting", jid
        )

    # ------------------------------------------------------------------
    # Dataset-level expected states
    # ------------------------------------------------------------------
    state(
        "DATASET_EXPECTATION", "DATASET", "orders",
        "order_count", len(orders), "count",
        "Expected order count equals the generated clean commercial world.",
        "commerce_orders", ""
    )
    state(
        "DATASET_EXPECTATION", "DATASET", "payments",
        "successful_payment_count",
        sum(1 for r in payments if (r.get("payment_status") or r.get("status") or "").upper()
            in {"SUCCESS","SUCCEEDED","CAPTURED","PAID",""}),
        "count",
        "Successful digital payments represented in the clean source dataset.",
        "payments", ""
    )
    state(
        "DATASET_EXPECTATION", "DATASET", "payroll",
        "payroll_record_count", len(payroll), "count",
        "One payroll record per employee per month for the synthetic period.",
        "payroll", ""
    )

    # Validate state IDs and write.
    ids = [r["state_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate state IDs detected.")

    fields = [
        "state_id","state_type","entity_type","entity_id","metric",
        "expected_value","unit","rule","source_system","source_record_id"
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"Generated: {OUT}")
    print(f"Expected-state rows: {len(rows):,}")
    print("Validation: unique state IDs")
    print("Ground truth: no anomaly logic or anomaly injection")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
