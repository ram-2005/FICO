#!/usr/bin/env python3
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import csv, sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw"

FILES = {
    "orders": DATA/"commerce/orders.csv",
    "invoices": DATA/"commerce/invoices.csv",
    "payments": DATA/"payments/payments.csv",
    "refunds": DATA/"payments/refunds.csv",
    "settlements": DATA/"settlements/settlements.csv",
    "vendor_invoices": DATA/"vendors/vendor_invoices.csv",
    "vendor_payments": DATA/"vendors/vendor_payments.csv",
    "payroll": DATA/"payroll/payroll.csv",
}
OUT = DATA/"accounting/journal_entries.csv"
Q = Decimal("0.01")

def money(x):
    return Decimal(str(x or "0")).quantize(Q, rounding=ROUND_HALF_UP)

def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def val(row, *names):
    for n in names:
        if row.get(n) not in (None, ""):
            return money(row[n])
    return Decimal("0.00")

def dt(row, *names):
    for n in names:
        if row.get(n):
            return row[n]
    return ""

def journal(lines, seq, row, source, source_id, postings, desc, ref=""):
    d = sum((money(x[0]) for x in postings), Decimal("0"))
    c = sum((money(x[1]) for x in postings), Decimal("0"))
    if d != c:
        raise ValueError(f"Unbalanced JRN_{seq:06d}: {d} != {c}")
    jid = f"JRN_{seq:06d}"
    for i,(debit,credit,account,counterparty) in enumerate(postings,1):
        lines.append({
            "journal_entry_id": jid, "line_number": i,
            "timestamp": dt(row,"invoice_date","payment_date","payment_timestamp",
                            "settlement_date","settlement_timestamp","refund_date",
                            "refund_timestamp","payroll_date","paid_at","created_at"),
            "source_system": source, "source_record_id": source_id,
            "account_id": account, "counterparty_id": counterparty or "",
            "debit": f"{money(debit):.2f}", "credit": f"{money(credit):.2f}",
            "currency": "INR", "description": desc,
            "reference_id": ref, "status": "POSTED"
        })
    return seq+1

def main():
    invoices = read(FILES["invoices"])
    payments = read(FILES["payments"])
    refunds = read(FILES["refunds"])
    settlements = read(FILES["settlements"])
    vinv = read(FILES["vendor_invoices"])
    vpay = read(FILES["vendor_payments"])
    payroll = read(FILES["payroll"])

    lines=[]; seq=1

    # Customer invoices: Dr AR / Cr Revenue + GST output
    for r in invoices:
        if (r.get("invoice_status") or r.get("status") or "").upper() in {"CANCELLED","REJECTED"}:
            continue
        total=val(r,"net_amount","total_amount","invoice_amount")
        tax=val(r,"tax","tax_amount","gst_amount")
        if total<=0: continue
        revenue=money(total-tax)
        postings=[(total,0,"AR_CUSTOMERS",r.get("customer_id","")),
                  (0,revenue,"REVENUE_SALES",r.get("customer_id",""))]
        if tax>0: postings.append((0,tax,"GST_OUTPUT_PAYABLE",""))
        seq=journal(lines,seq,r,"commerce_invoices",r.get("invoice_id",""),
                    postings,"Customer invoice recognized",r.get("order_id",""))

    # Successful digital payments: Dr Gateway receivable / Cr AR
    for r in payments:
        if (r.get("payment_status") or r.get("status") or "").upper() not in {"","SUCCESS","SUCCEEDED","CAPTURED","PAID"}:
            continue
        a=val(r,"amount","paid_amount","payment_amount")
        if a<=0: continue
        seq=journal(lines,seq,r,"payments",r.get("payment_id",""),
                    [(a,0,"GATEWAY_RECEIVABLE",r.get("customer_id","")),
                     (0,a,"AR_CUSTOMERS",r.get("customer_id",""))],
                    "Customer digital payment recorded",r.get("order_id",""))

    # Gateway settlements: Dr bank / Cr gateway receivable
    for r in settlements:
        a=val(r,"settlement_amount","amount","net_amount")
        if a<=0: continue
        bank=r.get("destination_account_id") or "BANK_002"
        seq=journal(lines,seq,r,"settlements",r.get("settlement_id",""),
                    [(a,0,bank,"PayFlow"),(0,a,"GATEWAY_RECEIVABLE","PayFlow")],
                    "Payment gateway settlement received",r.get("settlement_id",""))

    # Refunds: Dr refund expense/contra-revenue / Cr gateway or bank
    for r in refunds:
        if (r.get("refund_status") or r.get("status") or "").upper() not in {"","SUCCESS","SUCCEEDED","PROCESSED","COMPLETED","REFUNDED"}:
            continue
        a=val(r,"refund_amount","amount")
        if a<=0: continue
        credit="BANK_002" if (r.get("payment_method") or "").upper()=="COD" or not r.get("payment_id") else "GATEWAY_RECEIVABLE"
        seq=journal(lines,seq,r,"refunds",r.get("refund_id",""),
                    [(a,0,"REFUNDS_CUSTOMER",r.get("customer_id","")),(0,a,credit,r.get("customer_id",""))],
                    "Customer refund recorded",r.get("order_id",""))

    # Vendor invoices: Dr inventory/expense + input GST / Cr AP
    for r in vinv:
        if (r.get("invoice_status") or r.get("status") or "").upper() in {"CANCELLED","REJECTED"}:
            continue
        total=val(r,"total_amount","invoice_amount","amount")
        tax=val(r,"tax","tax_amount","gst_amount")
        if total<=0: continue
        cat=(r.get("vendor_category") or "").upper()
        acct="INVENTORY_PURCHASES" if cat in {"GOODS",""} else ("LOGISTICS_EXPENSE" if cat=="LOGISTICS" else "OPERATING_EXPENSES")
        postings=[(money(total-tax),0,acct,r.get("vendor_id",""))]
        if tax>0: postings.append((tax,0,"GST_INPUT_CREDIT",r.get("vendor_id","")))
        postings.append((0,total,"AP_VENDORS",r.get("vendor_id","")))
        seq=journal(lines,seq,r,"vendor_invoices",r.get("vendor_invoice_id",""),
                    postings,"Vendor invoice recognized",r.get("vendor_invoice_id",""))

    # Vendor payments: Dr AP / Cr BANK_003
    for r in vpay:
        if (r.get("payment_status") or r.get("status") or "").upper() not in {"","SUCCESS","SUCCEEDED","PAID","COMPLETED"}:
            continue
        a=val(r,"payment_amount","amount","paid_amount")
        if a<=0: continue
        bank=r.get("bank_account_id") or "BANK_003"
        seq=journal(lines,seq,r,"vendor_payments",r.get("vendor_payment_id",""),
                    [(a,0,"AP_VENDORS",r.get("vendor_id","")),(0,a,bank,r.get("vendor_id",""))],
                    "Vendor invoice payment recorded",r.get("vendor_invoice_id",""))

    # Payroll accrual + net salary payment
    for r in payroll:
        if (r.get("status") or r.get("payroll_status") or "").upper() not in {"","PAID","PROCESSED","COMPLETED"}:
            continue
        gross=val(r,"gross_salary","gross_pay","salary")
        net=val(r,"net_pay","net_salary")
        pf_e=val(r,"employee_pf","employee_pf_contribution")
        tds=val(r,"tds","income_tax","tds_amount")
        pt=val(r,"professional_tax","pt")
        pf_er=val(r,"employer_pf","employer_pf_contribution")
        esic=val(r,"employer_esic","employer_esic_contribution")
        if gross<=0: continue
        expected=money(gross-pf_e-tds-pt)
        if expected!=net:
            raise ValueError(f"Payroll net mismatch for {r.get('payroll_id','')}: {expected} != {net}")
        total_cost=money(gross+pf_er+esic)
        postings=[(total_cost,0,"SALARY_EXPENSE",r.get("employee_id","")),
                  (0,net,"SALARY_PAYABLE",r.get("employee_id",""))]
        for a,acct in [(pf_e,"PF_PAYABLE"),(tds,"TDS_PAYABLE"),(pt,"PROFESSIONAL_TAX_PAYABLE"),
                       (pf_er,"PF_PAYABLE"),(esic,"ESIC_PAYABLE")]:
            if a>0: postings.append((0,a,acct,r.get("employee_id","")))
        seq=journal(lines,seq,r,"payroll",r.get("payroll_id",""),postings,"Monthly payroll accrued",r.get("employee_id",""))
        bank=r.get("payment_account_id") or "BANK_004"
        seq=journal(lines,seq,r,"payroll",r.get("payroll_id",""),
                    [(net,0,"SALARY_PAYABLE",r.get("employee_id","")),(0,net,bank,r.get("employee_id",""))],
                    "Employee salary paid",r.get("payroll_id",""))

    groups={}
    for x in lines: groups.setdefault(x["journal_entry_id"],[]).append(x)
    for jid,g in groups.items():
        if sum((money(x["debit"]) for x in g),Decimal()) != sum((money(x["credit"]) for x in g),Decimal()):
            raise ValueError(f"Final balance failure: {jid}")

    OUT.parent.mkdir(parents=True,exist_ok=True)
    fields=["journal_entry_id","line_number","timestamp","source_system","source_record_id",
            "account_id","counterparty_id","debit","credit","currency","description","reference_id","status"]
    with OUT.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(lines)
    print(f"Generated: {OUT}")
    print(f"Journal entries: {len(groups):,}")
    print(f"Journal lines: {len(lines):,}")
    print("Validation: ALL JOURNAL ENTRIES BALANCED")
    print("Clean source layer: NO INTENTIONAL ANOMALIES")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print(f"ERROR: {e}",file=sys.stderr); sys.exit(1)
