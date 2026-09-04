#!/usr/bin/env python3
"""
Generate M1 ground-truth relationships.csv.

Reads source datasets plus events and builds deterministic entity-to-entity
relationships. This is ground truth: no anomaly detection or anomaly injection.
"""

from pathlib import Path
import csv, sys

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GT = ROOT / "data" / "ground_truth"
OUT = GT / "relationships.csv"

def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def index(rows, *fields):
    out = {}
    for r in rows:
        for f in fields:
            v = (r.get(f) or "").strip()
            if v:
                out.setdefault(v, []).append(r)
    return out

def add(rel, seq, rel_type, from_type, from_id, to_type, to_id,
        source_system="", source_record_id="", description=""):
    if not from_id or not to_id:
        return seq
    rel.append({
        "relationship_id": f"REL_{seq:06d}",
        "relationship_type": rel_type,
        "from_entity_type": from_type,
        "from_entity_id": from_id,
        "to_entity_type": to_type,
        "to_entity_id": to_id,
        "source_system": source_system,
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
    events = read(GT/"events.csv")

    rel = []
    seq = 1

    orders_by_id = index(orders, "order_id")
    invoices_by_order = index(invoices, "order_id")
    payments_by_order = index(payments, "order_id")
    refunds_by_order = index(refunds, "order_id")
    settlements_by_id = index(settlements, "settlement_id")
    vendor_inv_by_id = index(vendor_invoices, "vendor_invoice_id")
    vendor_pay_by_inv = index(vendor_payments, "vendor_invoice_id")
    bank_by_ref = index(bank, "reference_id", "reference", "transaction_reference")
    payroll_by_id = index(payroll, "payroll_id")
    events_by_source = index(events, "source_record_id")

    # ORDER -> CUSTOMER
    for o in orders:
        oid = o.get("order_id","")
        cid = o.get("customer_id","")
        seq = add(rel, seq, "ORDER_FOR_CUSTOMER",
                  "ORDER", oid, "CUSTOMER", cid,
                  "commerce_orders", oid, "Order belongs to customer")

    # ORDER -> INVOICE
    for o in orders:
        oid = o.get("order_id","")
        for inv in invoices_by_order.get(oid, []):
            seq = add(rel, seq, "ORDER_HAS_INVOICE",
                      "ORDER", oid, "INVOICE", inv.get("invoice_id",""),
                      "commerce_invoices", inv.get("invoice_id",""),
                      "Order generated invoice")

    # ORDER -> PAYMENT
    for o in orders:
        oid = o.get("order_id","")
        for p in payments_by_order.get(oid, []):
            seq = add(rel, seq, "ORDER_HAS_PAYMENT",
                      "ORDER", oid, "PAYMENT", p.get("payment_id",""),
                      "payments", p.get("payment_id",""),
                      "Order payment")

    # PAYMENT -> SETTLEMENT
    for s in settlements:
        sid = s.get("settlement_id","")
        # Common settlement schemas contain payment_ids, payment_refs, or a
        # delimited list. Support all without assuming a single field name.
        candidates = []
        for field in ("payment_ids", "payment_references", "payments", "payment_id"):
            value = (s.get(field) or "").strip()
            if value:
                candidates.extend(x.strip() for x in value.replace("|", ",").split(",") if x.strip())

        # If settlement rows use a single source-record field, match it.
        for p in payments:
            pid = p.get("payment_id","")
            if pid and (
                pid in candidates or
                pid == s.get("source_record_id","") or
                pid == s.get("payment_reference","")
            ):
                candidates.append(pid)

        for pid in dict.fromkeys(candidates):
            if pid:
                seq = add(rel, seq, "PAYMENT_INCLUDED_IN_SETTLEMENT",
                          "PAYMENT", pid, "SETTLEMENT", sid,
                          "settlements", sid,
                          "Payment included in gateway settlement")

    # SETTLEMENT -> BANK TRANSACTION
    for s in settlements:
        sid = s.get("settlement_id","")
        matched = []
        for field in ("bank_transaction_id", "bank_transaction_reference", "transaction_id"):
            v = (s.get(field) or "").strip()
            if v:
                matched.append(v)
        for b in bank_by_ref.get(sid, []):
            matched.append(b.get("transaction_id",""))
        for bid in dict.fromkeys(x for x in matched if x):
            seq = add(rel, seq, "SETTLEMENT_TO_BANK_TRANSACTION",
                      "SETTLEMENT", sid, "BANK_TRANSACTION", bid,
                      "banking", bid, "Settlement cash movement")

    # ORDER -> REFUND
    for o in orders:
        oid = o.get("order_id","")
        for r in refunds_by_order.get(oid, []):
            seq = add(rel, seq, "ORDER_HAS_REFUND",
                      "ORDER", oid, "REFUND", r.get("refund_id",""),
                      "refunds", r.get("refund_id",""),
                      "Refund belongs to order")

    # PAYMENT -> REFUND when payment_id exists
    payment_by_id = index(payments, "payment_id")
    for r in refunds:
        pid = (r.get("payment_id") or "").strip()
        if pid:
            seq = add(rel, seq, "PAYMENT_HAS_REFUND",
                      "PAYMENT", pid, "REFUND", r.get("refund_id",""),
                      "refunds", r.get("refund_id",""),
                      "Refund references original payment")

    # VENDOR -> VENDOR INVOICE
    for v in vendor_invoices:
        vid = v.get("vendor_id","")
        viid = v.get("vendor_invoice_id","")
        seq = add(rel, seq, "VENDOR_HAS_INVOICE",
                  "VENDOR", vid, "VENDOR_INVOICE", viid,
                  "vendor_invoices", viid,
                  "Vendor issued invoice")

    # VENDOR INVOICE -> VENDOR PAYMENT
    for v in vendor_invoices:
        viid = v.get("vendor_invoice_id","")
        for p in vendor_pay_by_inv.get(viid, []):
            seq = add(rel, seq, "VENDOR_INVOICE_PAID_BY",
                      "VENDOR_INVOICE", viid, "VENDOR_PAYMENT",
                      p.get("vendor_payment_id",""),
                      "vendor_payments", p.get("vendor_payment_id",""),
                      "Vendor invoice payment")

    # VENDOR PAYMENT -> BANK TRANSACTION
    for p in vendor_payments:
        pid = p.get("vendor_payment_id","")
        candidates = []
        for field in ("bank_transaction_id", "bank_transaction_reference",
                      "transaction_id", "bank_reference", "reference_id"):
            v = (p.get(field) or "").strip()
            if v:
                candidates.append(v)
        for b in bank_by_ref.get(pid, []):
            candidates.append(b.get("transaction_id",""))
        for bid in dict.fromkeys(x for x in candidates if x):
            seq = add(rel, seq, "VENDOR_PAYMENT_TO_BANK_TRANSACTION",
                      "VENDOR_PAYMENT", pid, "BANK_TRANSACTION", bid,
                      "banking", bid, "Vendor payment cash movement")

    # EMPLOYEE -> PAYROLL
    for p in payroll:
        eid = p.get("employee_id","")
        pid = p.get("payroll_id","")
        seq = add(rel, seq, "PAYROLL_FOR_EMPLOYEE",
                  "PAYROLL", pid, "EMPLOYEE", eid,
                  "payroll", pid, "Payroll record for employee")

    # PAYROLL -> BANK TRANSACTION
    for p in payroll:
        pid = p.get("payroll_id","")
        candidates = []
        for field in ("bank_transaction_id", "bank_transaction_reference",
                      "transaction_id", "bank_reference", "reference_id"):
            v = (p.get(field) or "").strip()
            if v:
                candidates.append(v)
        for b in bank_by_ref.get(pid, []):
            candidates.append(b.get("transaction_id",""))
        for bid in dict.fromkeys(x for x in candidates if x):
            seq = add(rel, seq, "PAYROLL_PAID_BY_BANK_TRANSACTION",
                      "PAYROLL", pid, "BANK_TRANSACTION", bid,
                      "banking", bid, "Payroll cash movement")

    # JOURNAL ENTRY -> source record
    # Every journal line repeats the same journal/source pair. Deduplicate.
    seen = set()
    for j in journals:
        jid = j.get("journal_entry_id","")
        sid = j.get("source_record_id","")
        source = j.get("source_system","")
        key = (jid, source, sid)
        if key in seen or not jid or not sid:
            continue
        seen.add(key)
        seq = add(rel, seq, "JOURNAL_REFERENCES_SOURCE",
                  "JOURNAL_ENTRY", jid, "SOURCE_RECORD",
                  sid, source, sid,
                  "Accounting entry references source observation")

    # BANK TRANSFER PAIRS
    # Match explicit transfer identifiers/reference fields and create a
    # single relationship between the debit and credit bank transactions.
    transfer_groups = {}
    for b in bank:
        direction = (b.get("direction") or "").upper()
        tid = ""
        for field in ("transfer_id", "reference_id", "reference",
                      "transaction_reference", "counterparty_reference"):
            v = (b.get(field) or "").strip()
            if v.upper().startswith(("XFER_", "TRANSFER_")):
                tid = v
                break
        if tid:
            transfer_groups.setdefault(tid, []).append(b)

    for tid, rows in transfer_groups.items():
        debits = [r for r in rows if (r.get("direction") or "").upper() in {"DEBIT","DR","OUT"}]
        credits = [r for r in rows if (r.get("direction") or "").upper() in {"CREDIT","CR","IN"}]
        for d in debits:
            for c in credits:
                seq = add(rel, seq, "BANK_TRANSFER_PAIR",
                          "BANK_TRANSACTION", d.get("transaction_id",""),
                          "BANK_TRANSACTION", c.get("transaction_id",""),
                          "banking", tid,
                          "Matching sides of inter-account transfer")

    # EVENT -> source record, giving each event a traceable source when one
    # exists. This does not replace the entity relationships above.
    for e in events:
        sid = e.get("source_record_id","")
        if sid:
            seq = add(rel, seq, "EVENT_SOURCE_OBSERVATION",
                      "EVENT", e.get("event_id",""),
                      "SOURCE_RECORD", sid,
                      e.get("source_system",""),
                      sid, "Ground-truth event traced to source observation")

    # Remove exact duplicate relationship rows defensively.
    unique=[]
    seen=set()
    for r in rel:
        key=tuple(r.values())
        if key not in seen:
            seen.add(key); unique.append(r)

    fields = [
        "relationship_id","relationship_type",
        "from_entity_type","from_entity_id",
        "to_entity_type","to_entity_id",
        "source_system","source_record_id","description"
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(unique)

    print(f"Generated: {OUT}")
    print(f"Relationships: {len(unique):,}")
    print("Validation: duplicate relationship rows removed")
    print("Ground truth: no anomaly logic or anomaly injection used")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
