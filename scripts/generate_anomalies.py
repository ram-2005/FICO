
#!/usr/bin/env python3
"""
generate_anomalies_v2.py
Exact-schema anomaly injector for the Aarohan/FICO M1 dataset.

IMPORTANT:
1. Restore RAW from data/raw_clean_backup BEFORE running this script if a
   previous anomaly injection attempt already modified the RAW files.
2. This script injects exactly 8 anomalies.
3. It writes the anomaly truth metadata to data/ground_truth/anomalies.csv.
4. Ground-truth events/relationships/expected_states are never modified.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import csv, random, shutil, sys

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BACKUP = ROOT / "data" / "raw_clean_backup"
GT = ROOT / "data" / "ground_truth"
OUT = GT / "anomalies.csv"
SEED = 42
Q = Decimal("0.01")

TARGETS = {
    "payments": RAW/"payments/payments.csv",
    "settlements": RAW/"settlements/settlements.csv",
    "bank": RAW/"banking/bank_transactions.csv",
    "vendor_payments": RAW/"vendors/vendor_payments.csv",
    "payroll": RAW/"payroll/payroll.csv",
    "journal": RAW/"accounting/journal_entries.csv",
    "refunds": RAW/"payments/refunds.csv",
}

def money(x):
    return Decimal(str(x or "0")).quantize(Q, rounding=ROUND_HALF_UP)

def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def write(path, rows):
    if not rows:
        raise ValueError(f"Cannot write empty dataset: {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def restore_clean():
    missing = []
    for path in TARGETS.values():
        backup_path = BACKUP / path.relative_to(RAW)
        if not backup_path.exists():
            missing.append(str(backup_path))
        else:
            shutil.copy2(backup_path, path)
    if missing:
        raise FileNotFoundError(
            "Clean backups are missing. Cannot safely re-run anomaly injection:\n"
            + "\n".join(missing)
        )

def dt_parse(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None

def dt_fmt(value):
    d = dt_parse(value)
    if d is None:
        raise ValueError(f"Cannot parse timestamp: {value}")
    return d.strftime("%Y-%m-%dT%H:%M:%S")

def main():
    rng = random.Random(SEED)

    # Always start from the clean backup. This makes the operation idempotent.
    restore_clean()

    payments = read(TARGETS["payments"])
    settlements = read(TARGETS["settlements"])
    bank = read(TARGETS["bank"])
    vpay = read(TARGETS["vendor_payments"])
    payroll = read(TARGETS["payroll"])
    journals = read(TARGETS["journal"])
    refunds = read(TARGETS["refunds"])

    anomalies = []

    def record(aid, typ, severity, system, dataset, rid, field, old, new, reason):
        anomalies.append({
            "anomaly_id": aid,
            "anomaly_type": typ,
            "severity": severity,
            "source_system": system,
            "dataset": dataset,
            "source_record_id": rid,
            "field": field,
            "original_value": str(old),
            "corrupted_value": str(new),
            "reason": reason,
            "injected_at": "2026-09-04",
        })

    # 1. Payment amount mismatch
    r = rng.choice([x for x in payments if x["payment_id"]])
    old = money(r["amount"])
    new = money(old + Decimal("137.25"))
    r["amount"] = f"{new:.2f}"
    record("ANOM_000001", "AMOUNT_MISMATCH", "HIGH", "payments",
           "data/raw/payments/payments.csv", r["payment_id"], "amount",
           f"{old:.2f}", f"{new:.2f}",
           "Observed payment amount differs from the true transaction amount.")

    # 2. Duplicate payment with a new observed record ID
    r = rng.choice([x for x in payments if x["payment_id"]])
    source_id = r["payment_id"]
    dup = dict(r)
    dup_id = "PAY_900001"
    dup["payment_id"] = dup_id
    dup["gateway_reference"] = "PF_90000001"
    payments.append(dup)
    record("ANOM_000002", "DUPLICATE_TRANSACTION", "HIGH", "payments",
           "data/raw/payments/payments.csv", dup_id, "payment_id",
           source_id, dup_id,
           "A second observed payment record duplicates an existing payment.")

    # 3. Settlement net amount mismatch
    r = rng.choice([x for x in settlements if x["settlement_id"]])
    old = money(r["net_settlement_amount"])
    new = money(old - Decimal("88.40"))
    if new <= 0:
        new = money(old + Decimal("88.40"))
    r["net_settlement_amount"] = f"{new:.2f}"
    record("ANOM_000003", "SETTLEMENT_AMOUNT_MISMATCH", "HIGH", "settlements",
           "data/raw/settlements/settlements.csv", r["settlement_id"],
           "net_settlement_amount", f"{old:.2f}", f"{new:.2f}",
           "Observed settlement amount no longer agrees with settlement inputs.")

    # 4. Duplicate refund
    r = rng.choice([x for x in refunds if x.get("refund_id")])
    source_id = r["refund_id"]
    dup = dict(r)
    dup_id = "REF_900001"
    if any(x.get("refund_id") == dup_id for x in refunds):
        dup_id = "REF_999999"
    dup["refund_id"] = dup_id
    refunds.append(dup)
    record("ANOM_000004", "DUPLICATE_REFUND", "MEDIUM", "refunds",
           "data/raw/payments/refunds.csv", dup_id, "refund_id",
           source_id, dup_id,
           "An identical refund observation was recorded twice.")

    # 5. Bank timing anomaly
    r = rng.choice([x for x in bank if x.get("bank_transaction_id") and
                    x.get("transaction_date")])
    old = r["transaction_date"]
    new = dt_fmt(old)
    parsed = dt_parse(new)
    new = (parsed + timedelta(days=12)).strftime("%Y-%m-%dT%H:%M:%S")
    r["transaction_date"] = new
    record("ANOM_000005", "TIMING_ANOMALY", "MEDIUM", "banking",
           "data/raw/banking/bank_transactions.csv",
           r["bank_transaction_id"], "transaction_date", old, new,
           "Observed bank cash movement occurs materially later than expected.")

    # 6. Vendor payment amount mismatch
    r = rng.choice([x for x in vpay if x["vendor_payment_id"]])
    old = money(r["amount"])
    new = money(old + Decimal("215.00"))
    r["amount"] = f"{new:.2f}"
    record("ANOM_000006", "VENDOR_PAYMENT_MISMATCH", "HIGH", "vendor_payments",
           "data/raw/vendors/vendor_payments.csv", r["vendor_payment_id"],
           "amount", f"{old:.2f}", f"{new:.2f}",
           "Vendor payment differs from the underlying invoice obligation.")

    # 7. Payroll net-pay mismatch
    r = rng.choice([x for x in payroll if x["payroll_id"]])
    old = money(r["net_pay"])
    new = money(old + Decimal("500.00"))
    r["net_pay"] = f"{new:.2f}"
    # Keep employee_deductions and gross unchanged so the formula is broken.
    record("ANOM_000007", "PAYROLL_AMOUNT_MISMATCH", "HIGH", "payroll",
           "data/raw/payroll/payroll.csv", r["payroll_id"], "net_pay",
           f"{old:.2f}", f"{new:.2f}",
           "Observed net pay no longer agrees with gross salary and deductions.")

    # 8. Journal imbalance
    debit_rows = [x for x in journals
                  if x.get("journal_entry_id") and money(x.get("debit")) > 0]
    r = rng.choice(debit_rows)
    old = money(r["debit"])
    new = money(old + Decimal("41.00"))
    r["debit"] = f"{new:.2f}"
    record("ANOM_000008", "JOURNAL_IMBALANCE", "CRITICAL", "accounting",
           "data/raw/accounting/journal_entries.csv",
           r["journal_entry_id"], "debit", f"{old:.2f}", f"{new:.2f}",
           "A posted accounting line was altered, making the journal entry unbalanced.")

    # Write corrupted source observations.
    write(TARGETS["payments"], payments)
    write(TARGETS["settlements"], settlements)
    write(TARGETS["refunds"], refunds)
    write(TARGETS["bank"], bank)
    write(TARGETS["vendor_payments"], vpay)
    write(TARGETS["payroll"], payroll)
    write(TARGETS["journal"], journals)

    expected = {f"ANOM_{i:06d}" for i in range(1, 9)}
    actual = {x["anomaly_id"] for x in anomalies}
    if actual != expected:
        raise RuntimeError(f"Anomaly ID mismatch. Expected {expected}, got {actual}")

    fields = [
        "anomaly_id","anomaly_type","severity","source_system","dataset",
        "source_record_id","field","original_value","corrupted_value",
        "reason","injected_at"
    ]
    write(OUT, anomalies)

    print(f"Generated: {OUT}")
    print("Injected anomalies: 8")
    for a in anomalies:
        print(f"  {a['anomaly_id']} | {a['anomaly_type']} | "
              f"{a['source_record_id']} | {a['field']}")
    print("RAW data was restored from raw_clean_backup before injection.")
    print("Ground-truth events/relationships/expected_states were NOT modified.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
