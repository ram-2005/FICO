#!/usr/bin/env python3
"""
Generate the independent M1 ground-truth event ledger.

Reads clean source observations from data/raw and creates:
    data/ground_truth/events.csv

Ground truth describes what actually happened in the synthetic world.
It does NOT read anomalies.csv and does not attempt anomaly detection.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import csv, sys

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "ground_truth" / "events.csv"
Q = Decimal("0.01")

def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def amount(row, *fields):
    for f in fields:
        if row.get(f) not in (None, ""):
            return Decimal(str(row[f])).quantize(Q, rounding=ROUND_HALF_UP)
    return Decimal("0.00")

def first(row, *fields):
    for f in fields:
        if row.get(f):
            return row[f]
    return ""

def add(events, seq, event_type, timestamp, entity_type, entity_id,
        amount_value, counterparty_id="", reference_id="", source_record_id="",
        description=""):
    events.append({
        "event_id": f"EVT_{seq:06d}",
        "event_type": event_type,
        "timestamp": timestamp,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "amount": f"{amount_value:.2f}",
        "currency": "INR",
        "direction": "",
        "counterparty_id": counterparty_id,
        "reference_id": reference_id,
        "source_record_id": source_record_id,
        "description": description,
    })
    return seq + 1

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

    events = []
    seq = 1

    # Commercial world
    for r in orders:
        seq = add(events, seq, "ORDER_PLACED",
                  first(r,"order_date","created_at"),
                  "ORDER", r.get("order_id",""),
                  amount(r,"net_amount","total_amount"),
                  r.get("customer_id",""), r.get("order_id",""),
                  r.get("order_id",""), "Customer order placed")

        status = (r.get("order_status") or "").upper()
        if r.get("delivered_date"):
            seq = add(events, seq, "ORDER_DELIVERED", r["delivered_date"],
                      "ORDER", r.get("order_id",""), amount(r,"net_amount"),
                      r.get("customer_id",""), r.get("order_id",""),
                      r.get("order_id",""), "Order delivered")
        if status == "RETURNED":
            seq = add(events, seq, "ORDER_RETURNED",
                      first(r,"returned_date","delivered_date"),
                      "ORDER", r.get("order_id",""), amount(r,"net_amount"),
                      r.get("customer_id",""), r.get("order_id",""),
                      r.get("order_id",""), "Order returned")
        if status == "CANCELLED":
            seq = add(events, seq, "ORDER_CANCELLED",
                      first(r,"cancelled_date","order_date"),
                      "ORDER", r.get("order_id",""), amount(r,"net_amount"),
                      r.get("customer_id",""), r.get("order_id",""),
                      r.get("order_id",""), "Order cancelled")

    # Invoices
    for r in invoices:
        status = (r.get("invoice_status") or r.get("status") or "").upper()
        event = "INVOICE_ISSUED" if status != "CANCELLED" else "INVOICE_CANCELLED"
        seq = add(events, seq, event,
                  first(r,"invoice_date","created_at"),
                  "INVOICE", r.get("invoice_id",""),
                  amount(r,"net_amount","total_amount","invoice_amount"),
                  r.get("customer_id",""), r.get("order_id",""),
                  r.get("invoice_id",""), "Customer invoice event")

    # Payments
    for r in payments:
        status = (r.get("payment_status") or r.get("status") or "").upper()
        if status in {"SUCCESS","SUCCEEDED","CAPTURED","PAID",""}:
            seq = add(events, seq, "PAYMENT_RECEIVED",
                      first(r,"payment_timestamp","payment_date","created_at"),
                      "PAYMENT", r.get("payment_id",""),
                      amount(r,"amount","paid_amount","payment_amount"),
                      r.get("customer_id",""), r.get("order_id",""),
                      r.get("payment_id",""), "Digital customer payment")

    # Refunds
    for r in refunds:
        status = (r.get("refund_status") or r.get("status") or "").upper()
        if status in {"SUCCESS","SUCCEEDED","PROCESSED","COMPLETED","REFUNDED",""}:
            seq = add(events, seq, "CUSTOMER_REFUND",
                      first(r,"refund_date","refund_timestamp","created_at"),
                      "REFUND", r.get("refund_id",""),
                      amount(r,"refund_amount","amount"),
                      r.get("customer_id",""), r.get("order_id",""),
                      r.get("refund_id",""), "Customer refund")

    # Gateway settlements
    for r in settlements:
        seq = add(events, seq, "GATEWAY_SETTLEMENT",
                  first(r,"settlement_date","settlement_timestamp","created_at"),
                  "SETTLEMENT", r.get("settlement_id",""),
                  amount(r,"settlement_amount","amount","net_amount"),
                  "PayFlow", r.get("settlement_id",""),
                  r.get("settlement_id",""), "Gateway settlement")

    # Vendor obligations
    for r in vendor_invoices:
        status = (r.get("invoice_status") or r.get("status") or "").upper()
        if status not in {"CANCELLED","REJECTED"}:
            seq = add(events, seq, "VENDOR_INVOICE_RECORDED",
                      first(r,"invoice_date","created_at"),
                      "VENDOR_INVOICE", r.get("vendor_invoice_id",""),
                      amount(r,"total_amount","invoice_amount","amount"),
                      r.get("vendor_id",""), r.get("vendor_invoice_id",""),
                      r.get("vendor_invoice_id",""), "Vendor invoice recorded")

    for r in vendor_payments:
        status = (r.get("payment_status") or r.get("status") or "").upper()
        if status in {"SUCCESS","SUCCEEDED","PAID","COMPLETED",""}:
            seq = add(events, seq, "VENDOR_PAYMENT",
                      first(r,"payment_date","payment_timestamp","created_at"),
                      "VENDOR_PAYMENT", r.get("vendor_payment_id",""),
                      amount(r,"payment_amount","amount","paid_amount"),
                      r.get("vendor_id",""), r.get("vendor_invoice_id",""),
                      r.get("vendor_payment_id",""), "Vendor payment")

    # Payroll
    for r in payroll:
        status = (r.get("status") or r.get("payroll_status") or "").upper()
        if status in {"PAID","PROCESSED","COMPLETED",""}:
            seq = add(events, seq, "PAYROLL_PAID",
                      first(r,"payment_date","paid_at","payroll_date"),
                      "PAYROLL", r.get("payroll_id",""),
                      amount(r,"net_pay","net_salary"),
                      r.get("employee_id",""), r.get("payroll_id",""),
                      r.get("payroll_id",""), "Employee payroll paid")

    # Bank observations become cash events, preserving the bank transaction
    # as the observed source record.
    for r in bank:
        amt = amount(r,"amount","transaction_amount","net_amount")
        if amt == 0:
            continue
        direction = (r.get("direction") or "").upper()
        event_type = "BANK_CASH_IN" if direction in {"CREDIT","CR","IN"} else "BANK_CASH_OUT"
        seq = add(events, seq, event_type,
                  first(r,"transaction_timestamp","transaction_date","timestamp","created_at"),
                  "BANK_TRANSACTION", r.get("transaction_id",""),
                  abs(amt), r.get("counterparty_id",""),
                  first(r,"reference_id","reference","transaction_reference"),
                  r.get("transaction_id",""), "Bank cash movement")

    # Journal postings are accounting events. Grouped journal entries are
    # represented by their balanced entry total rather than duplicating each
    # debit/credit line as separate economic events.
    groups = {}
    for r in journals:
        groups.setdefault(r.get("journal_entry_id",""), []).append(r)

    for jid, rows in groups.items():
        if not rows:
            continue
        debit = sum((amount(x,"debit") for x in rows), Decimal("0"))
        if debit == 0:
            continue
        first_row = rows[0]
        seq = add(events, seq, "ACCOUNTING_POSTED",
                  first_row.get("timestamp",""),
                  "JOURNAL_ENTRY", jid, debit,
                  first_row.get("counterparty_id",""),
                  first_row.get("reference_id",""),
                  first_row.get("source_record_id",""),
                  "Balanced accounting entry posted")

    fields = [
        "event_id","event_type","timestamp","entity_type","entity_id",
        "amount","currency","direction","counterparty_id","reference_id",
        "source_record_id","description"
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(events)

    # Basic validation
    ids = [x["event_id"] for x in events]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate event IDs detected.")
    if any(Decimal(x["amount"]) < 0 for x in events):
        raise ValueError("Negative event amount detected.")

    print(f"Generated: {OUT}")
    print(f"Events: {len(events):,}")
    print("Validation: unique IDs and non-negative amounts")
    print("Ground truth generated independently of anomalies.csv")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
