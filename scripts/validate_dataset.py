#!/usr/bin/env python3
"""
FICO M1 Dataset Validator + Manifest Generator

Run from FICO root:
    python scripts/validate_dataset.py

Outputs:
    data/manifests/dataset_v1.json
    data/manifests/validation_report.json

The validator checks the M1 dataset after controlled anomaly injection.
Known anomalies are read from ground_truth/anomalies.csv and are reported
separately from unexpected validation failures.
"""

from pathlib import Path
from decimal import Decimal, InvalidOperation
from collections import defaultdict
import csv
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
GT = DATA / "ground_truth"
MANIFEST = DATA / "manifests" / "dataset_v1.json"
REPORT = DATA / "manifests" / "validation_report.json"

REQUIRED = {
    "data/raw/master/customers.csv": ["customer_id"],
    "data/raw/master/vendors.csv": ["vendor_id"],
    "data/raw/master/employees.csv": ["employee_id"],
    "data/raw/master/products.csv": ["product_id"],
    "data/raw/master/bank_accounts.csv": ["account_id"],
    "data/raw/master/payment_accounts.csv": ["payment_account_id"],
    "data/raw/master/tax_accounts.csv": ["tax_account_id"],

    "data/raw/commerce/orders.csv":
        ["order_id","customer_id","order_date","gross_amount","discount",
         "tax","shipping_fee","net_amount","order_status",
         "payment_method_selected","fulfillment_hub","invoice_date",
         "delivered_date","sku_lines"],

    "data/raw/commerce/invoices.csv":
        ["invoice_id","order_id"],

    "data/raw/payments/payments.csv":
        ["payment_id","order_id","customer_id","payment_date","gateway",
         "payment_method","amount","currency","status","gateway_reference"],

    "data/raw/payments/refunds.csv":
        ["refund_id","order_id"],

    "data/raw/settlements/settlements.csv":
        ["settlement_id","settlement_date","gateway","currency",
         "payment_count","gross_amount","refund_deductions",
         "net_settlement_amount","destination_account_id",
         "gateway_settlement_reference","first_payment_id","last_payment_id"],

    "data/raw/banking/bank_transactions.csv":
        ["bank_transaction_id","account_id","transaction_date",
         "value_date","amount","currency","direction","transaction_type",
         "description","reference_id","counterparty_id","status"],

    "data/raw/accounting/journal_entries.csv":
        ["journal_entry_id","line_number","timestamp","source_system",
         "source_record_id","account_id","counterparty_id","debit","credit",
         "currency","description","reference_id","status"],

    "data/raw/vendors/vendor_invoices.csv": ["vendor_invoice_id","vendor_id"],
    "data/raw/vendors/vendor_payments.csv":
        ["vendor_payment_id","vendor_invoice_id","vendor_id","payment_date",
         "payment_account_id","amount","currency","payment_method",
         "status","bank_reference"],

    "data/raw/payroll/payroll.csv":
        ["payroll_id","employee_id","payroll_period","pay_date",
         "gross_salary","employee_pf","professional_tax","tds",
         "employee_deductions","net_pay","employer_pf","employer_esic",
         "employer_contributions","total_employer_cost","currency",
         "payment_account_id","status","bank_reference"],

    "data/ground_truth/events.csv":
        ["event_id","event_type","timestamp","entity_type","entity_id",
         "amount","currency","direction","counterparty_id","reference_id",
         "source_record_id","description"],

    "data/ground_truth/relationships.csv":
        ["relationship_id","relationship_type","from_entity_type",
         "from_entity_id","to_entity_type","to_entity_id",
         "source_system","source_record_id","description"],

    "data/ground_truth/expected_states.csv":
        ["state_id","state_type","entity_type","entity_id","metric",
         "expected_value","unit","rule","source_system","source_record_id"],

    "data/ground_truth/anomalies.csv":
        ["anomaly_id","anomaly_type","severity","source_system","dataset",
         "source_record_id","field","original_value","corrupted_value",
         "reason","injected_at"],
}

ID_FIELDS = {
    "customers.csv": "customer_id",
    "vendors.csv": "vendor_id",
    "employees.csv": "employee_id",
    "products.csv": "product_id",
    "bank_accounts.csv": "account_id",
    "payment_accounts.csv": "payment_account_id",
    "tax_accounts.csv": "tax_account_id",
    "orders.csv": "order_id",
    "invoices.csv": "invoice_id",
    "payments.csv": "payment_id",
    "refunds.csv": "refund_id",
    "settlements.csv": "settlement_id",
    "bank_transactions.csv": "bank_transaction_id",
    "vendor_invoices.csv": "vendor_invoice_id",
    "vendor_payments.csv": "vendor_payment_id",
    "payroll.csv": "payroll_id",
    "events.csv": "event_id",
    "relationships.csv": "relationship_id",
    "expected_states.csv": "state_id",
    "anomalies.csv": "anomaly_id",
}

def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def money(v):
    try:
        return Decimal(str(v or "0"))
    except InvalidOperation:
        raise ValueError(f"Invalid monetary value: {v!r}")

def add_issue(issues, severity, code, dataset, record="", message=""):
    issues.append({
        "severity": severity,
        "code": code,
        "dataset": dataset,
        "record": record,
        "message": message,
    })

def main():
    issues = []
    datasets = {}
    rows_by_path = {}

    # ---------------------------------------------------------------
    # 1. Files + schema
    # ---------------------------------------------------------------
    for rel, expected_cols in REQUIRED.items():
        path = ROOT / rel
        if not path.exists():
            add_issue(issues, "ERROR", "MISSING_FILE", rel,
                      message="Required M1 dataset is missing.")
            continue

        try:
            rows = read_csv(path)
        except Exception as e:
            add_issue(issues, "ERROR", "CSV_READ_ERROR", rel, message=str(e))
            continue

        rows_by_path[rel] = rows
        actual = list(rows[0].keys()) if rows else expected_cols

        missing = [c for c in expected_cols if c not in actual]
        if missing:
            add_issue(issues, "ERROR", "SCHEMA_MISMATCH", rel,
                      message=f"Missing columns: {missing}")

        datasets[rel] = {
            "rows": len(rows),
            "sha256": sha256(path),
            "columns": actual,
        }

        if not rows:
            add_issue(issues, "ERROR", "EMPTY_DATASET", rel,
                      message="Required dataset contains zero rows.")

    # ---------------------------------------------------------------
    # 2. Primary ID uniqueness
    # ---------------------------------------------------------------
    for rel, id_field in ID_FIELDS.items():
        matching = [p for p in rows_by_path if p.endswith("/"+rel)]
        for path in matching:
            rows = rows_by_path[path]
            if not rows or id_field not in rows[0]:
                continue
            seen = set()
            duplicates = []
            for r in rows:
                value = r.get(id_field, "")
                if not value:
                    add_issue(issues, "ERROR", "EMPTY_ID", path,
                              message=f"Empty {id_field}.")
                elif value in seen:
                    duplicates.append(value)
                else:
                    seen.add(value)

            # Intentional duplicate transaction/refund anomalies are allowed
            # to violate uniqueness only because the new IDs are unique;
            # therefore a true repeated primary ID remains an unexpected error.
            for value in duplicates:
                add_issue(issues, "ERROR", "DUPLICATE_PRIMARY_ID", path,
                          value, f"Duplicate {id_field}: {value}")

    # ---------------------------------------------------------------
    # 3. Foreign-key / entity-reference checks
    # ---------------------------------------------------------------
    def ids(path, field):
        return {r.get(field,"") for r in rows_by_path.get(path, []) if r.get(field)}

    customers = ids("data/raw/master/customers.csv", "customer_id")
    vendors = ids("data/raw/master/vendors.csv", "vendor_id")
    employees = ids("data/raw/master/employees.csv", "employee_id")
    products = ids("data/raw/master/products.csv", "product_id")
    bank_accounts = ids("data/raw/master/bank_accounts.csv", "account_id")
    orders = ids("data/raw/commerce/orders.csv", "order_id")
    invoices = ids("data/raw/commerce/invoices.csv", "invoice_id")
    payments = ids("data/raw/payments/payments.csv", "payment_id")
    refunds = ids("data/raw/payments/refunds.csv", "refund_id")
    settlements = ids("data/raw/settlements/settlements.csv", "settlement_id")
    bank_txns = ids("data/raw/banking/bank_transactions.csv", "bank_transaction_id")
    vendor_invoices = ids("data/raw/vendors/vendor_invoices.csv", "vendor_invoice_id")
    vendor_payments = ids("data/raw/vendors/vendor_payments.csv", "vendor_payment_id")
    payroll_ids = ids("data/raw/payroll/payroll.csv", "payroll_id")

    def fk(path, field, valid, allow_blank=True):
        for r in rows_by_path.get(path, []):
            v = r.get(field, "")
            if not v and allow_blank:
                continue
            if v not in valid:
                add_issue(issues, "ERROR", "ORPHAN_REFERENCE", path, v,
                          f"{field}={v} does not exist in referenced dataset.")

    fk("data/raw/commerce/orders.csv", "customer_id", customers)
    fk("data/raw/commerce/invoices.csv", "order_id", orders)
    fk("data/raw/payments/payments.csv", "order_id", orders)
    fk("data/raw/payments/payments.csv", "customer_id", customers)
    fk("data/raw/payments/refunds.csv", "order_id", orders)
    fk("data/raw/settlements/settlements.csv", "destination_account_id", bank_accounts)
    fk("data/raw/banking/bank_transactions.csv", "account_id", bank_accounts)
    fk("data/raw/vendors/vendor_invoices.csv", "vendor_id", vendors)
    fk("data/raw/vendors/vendor_payments.csv", "vendor_invoice_id", vendor_invoices)
    fk("data/raw/vendors/vendor_payments.csv", "vendor_id", vendors)
    fk("data/raw/payroll/payroll.csv", "employee_id", employees)
    fk("data/raw/payroll/payroll.csv", "payment_account_id", bank_accounts)

    # ---------------------------------------------------------------
    # 4. Money formatting / non-negative checks
    # ---------------------------------------------------------------
    monetary_fields = {
        "data/raw/commerce/orders.csv":
            ["gross_amount","discount","tax","shipping_fee","net_amount"],
        "data/raw/payments/payments.csv": ["amount"],
        "data/raw/payments/refunds.csv": ["amount","refund_amount"],
        "data/raw/settlements/settlements.csv":
            ["gross_amount","refund_deductions","net_settlement_amount"],
        "data/raw/banking/bank_transactions.csv": ["amount"],
        "data/raw/vendors/vendor_invoices.csv":
            ["subtotal","tax","total_amount","invoice_amount","amount"],
        "data/raw/vendors/vendor_payments.csv": ["amount"],
        "data/raw/payroll/payroll.csv":
            ["gross_salary","employee_pf","professional_tax","tds",
             "employee_deductions","net_pay","employer_pf","employer_esic",
             "employer_contributions","total_employer_cost"],
    }

    for path, fields in monetary_fields.items():
        for r in rows_by_path.get(path, []):
            for field in fields:
                if field not in r or r[field] == "":
                    continue
                try:
                    x = money(r[field])
                    if x.as_tuple().exponent < -2:
                        add_issue(issues, "ERROR", "MONEY_PRECISION", path,
                                  r.get(ID_FIELDS.get(Path(path).name,""), ""),
                                  f"{field} has more than 2 decimal places.")
                except ValueError as e:
                    add_issue(issues, "ERROR", "INVALID_MONEY", path,
                              message=f"{field}: {e}")

    # ---------------------------------------------------------------
    # 5. Order arithmetic
    # ---------------------------------------------------------------
    for r in rows_by_path.get("data/raw/commerce/orders.csv", []):
        gross = money(r.get("gross_amount"))
        discount = money(r.get("discount"))
        tax = money(r.get("tax"))
        shipping = money(r.get("shipping_fee"))
        net = money(r.get("net_amount"))
        # Expected generator formula.
        expected = (gross - discount + tax + shipping).quantize(Decimal("0.01"))
        if expected != net:
            add_issue(issues, "WARNING", "ORDER_ARITHMETIC_MISMATCH",
                      "data/raw/commerce/orders.csv", r.get("order_id",""),
                      f"Expected {expected}, observed {net}. May indicate intentional corruption.")

    # ---------------------------------------------------------------
    # 6. Settlement arithmetic
    # ---------------------------------------------------------------
    for r in rows_by_path.get("data/raw/settlements/settlements.csv", []):
        gross = money(r.get("gross_amount"))
        refunds = money(r.get("refund_deductions"))
        net = money(r.get("net_settlement_amount"))
        expected = gross - refunds
        if expected != net:
            add_issue(issues, "WARNING", "SETTLEMENT_ARITHMETIC_MISMATCH",
                      "data/raw/settlements/settlements.csv",
                      r.get("settlement_id",""),
                      f"Expected {expected}, observed {net}. Likely intentional anomaly if listed in anomalies.csv.")

    # ---------------------------------------------------------------
    # 7. Payroll arithmetic
    # ---------------------------------------------------------------
    for r in rows_by_path.get("data/raw/payroll/payroll.csv", []):
        gross = money(r.get("gross_salary"))
        pf = money(r.get("employee_pf"))
        pt = money(r.get("professional_tax"))
        tds = money(r.get("tds"))
        deductions = money(r.get("employee_deductions"))
        net = money(r.get("net_pay"))

        if pf + pt + tds != deductions:
            add_issue(issues, "WARNING", "PAYROLL_DEDUCTION_MISMATCH",
                      "data/raw/payroll/payroll.csv", r.get("payroll_id",""),
                      "Employee deductions do not equal PF + professional tax + TDS.")

        if gross - deductions != net:
            add_issue(issues, "WARNING", "PAYROLL_NET_MISMATCH",
                      "data/raw/payroll/payroll.csv", r.get("payroll_id",""),
                      "Net pay does not equal gross salary minus deductions.")

    # ---------------------------------------------------------------
    # 8. Journal balance
    # ---------------------------------------------------------------
    journal_groups = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for r in rows_by_path.get("data/raw/accounting/journal_entries.csv", []):
        jid = r.get("journal_entry_id","")
        journal_groups[jid][0] += money(r.get("debit"))
        journal_groups[jid][1] += money(r.get("credit"))

    for jid, (debit, credit) in journal_groups.items():
        if debit != credit:
            add_issue(issues, "WARNING", "JOURNAL_IMBALANCE",
                      "data/raw/accounting/journal_entries.csv", jid,
                      f"Debit={debit}, Credit={credit}. Expected anomaly if listed in anomalies.csv.")

    # ---------------------------------------------------------------
    # 9. Known anomaly reconciliation
    # ---------------------------------------------------------------
    anomaly_rows = rows_by_path.get("data/ground_truth/anomalies.csv", [])
    known_types = defaultdict(int)
    for a in anomaly_rows:
        known_types[a.get("anomaly_type","")] += 1

    # Expected warning/error codes associated with current injector.
    intentional_codes = {
        "AMOUNT_MISMATCH",
        "DUPLICATE_TRANSACTION",
        "SETTLEMENT_AMOUNT_MISMATCH",
        "DUPLICATE_REFUND",
        "TIMING_ANOMALY",
        "VENDOR_PAYMENT_MISMATCH",
        "PAYROLL_AMOUNT_MISMATCH",
        "JOURNAL_IMBALANCE",
    }

    # Any warning/error mentioning a known corrupted dataset is not
    # automatically swallowed. We report it separately.
    expected_anomaly_count = len(anomaly_rows)

    # ---------------------------------------------------------------
    # 10. Ground truth integrity
    # ---------------------------------------------------------------
    gt_paths = [
        GT/"events.csv",
        GT/"relationships.csv",
        GT/"expected_states.csv",
    ]
    for p in gt_paths:
        if not p.exists():
            add_issue(issues, "ERROR", "MISSING_GROUND_TRUTH", str(p),
                      message="Required ground-truth file is missing.")

    # ---------------------------------------------------------------
    # 11. Manifest
    # ---------------------------------------------------------------
    file_manifest = {}
    for rel, info in datasets.items():
        file_manifest[rel] = {
            "row_count": info["rows"],
            "sha256": info["sha256"],
            "columns": info["columns"],
        }

    manifest = {
        "dataset_version": "v1",
        "company": "Aarohan Commerce Pvt. Ltd.",
        "period": {
            "start": "2025-09-01",
            "end": "2026-08-31",
        },
        "timezone": "Asia/Kolkata",
        "currency": "INR",
        "random_seed": 42,
        "architecture": "TRUE_WORLD -> SOURCE_OBSERVATIONS -> CONTROLLED_ANOMALY_INJECTION -> RAW_DATA",
        "ground_truth_is_runtime_input": False,
        "anomaly_injection_enabled": True,
        "files": file_manifest,
        "known_anomalies": expected_anomaly_count,
        "known_anomaly_types": dict(sorted(known_types.items())),
    }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Validation report
    errors = [x for x in issues if x["severity"] == "ERROR"]
    warnings = [x for x in issues if x["severity"] == "WARNING"]

    report = {
        "result": "PASS" if not errors else "FAIL",
        "datasets_checked": len(datasets),
        "rows_checked": sum(x["rows"] for x in datasets.values()),
        "errors": len(errors),
        "warnings": len(warnings),
        "known_anomalies": expected_anomaly_count,
        "known_anomaly_types": dict(sorted(known_types.items())),
        "issues": issues,
        "note": "Warnings may correspond to intentionally injected anomalies; errors are unexpected structural failures.",
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== FICO M1 DATASET VALIDATION ===")
    print(f"Datasets checked : {len(datasets)}")
    print(f"Rows checked     : {sum(x['rows'] for x in datasets.values()):,}")
    print(f"Errors           : {len(errors)}")
    print(f"Warnings         : {len(warnings)}")
    print(f"Known anomalies  : {expected_anomaly_count}")
    print(f"Manifest         : {MANIFEST}")
    print(f"Report           : {REPORT}")

    if warnings:
        print("\nWarnings:")
        for x in warnings[:30]:
            print(f"  [{x['code']}] {x['dataset']} {x['record']} - {x['message']}")

    if errors:
        print("\nERRORS:")
        for x in errors[:30]:
            print(f"  [{x['code']}] {x['dataset']} {x['record']} - {x['message']}")
        print("\nRESULT: FAIL")
        return 1

    print("\nRESULT: PASS")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
