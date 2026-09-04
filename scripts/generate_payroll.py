#!/usr/bin/env python3
"""
Generate CLEAN monthly payroll observations for Aarohan Commerce.

Input:
    data/raw/master/employees.csv

Output:
    data/raw/payroll/payroll.csv

Clean-world only:
- 80 employees from the approved master data.
- One payroll record per employee per month for Sep 2025–Aug 2026.
- Uses employee master salary data where available.
- Falls back only to deterministic salary bands if the master schema does not
  contain salary information.
- Employee deductions and employer contributions are calculated separately.
- Net pay = gross pay - employee deductions.
- Payroll is paid from BANK_004.
- No intentional anomalies are injected.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import csv
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
EMPLOYEES_FILE = ROOT / "data/raw/master/employees.csv"
OUTPUT_FILE = ROOT / "data/raw/payroll/payroll.csv"

SEED = 42
Q = Decimal("0.01")
CURRENCY = "INR"
PAYROLL_ACCOUNT = "BANK_004"

START_YEAR = 2025
START_MONTH = 9
MONTHS = 12

# Fallback monthly salary bands if the employee master has no salary field.
# These are deterministic and only used when needed.
SALARY_BANDS = [
    (Decimal("22000"), Decimal("32000")),
    (Decimal("32000"), Decimal("48000")),
    (Decimal("48000"), Decimal("75000")),
    (Decimal("75000"), Decimal("110000")),
    (Decimal("110000"), Decimal("175000")),
]


def money(v):
    return Decimal(str(v)).quantize(Q, rounding=ROUND_HALF_UP)


def first_value(row, names, default=""):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def add_month(year, month, offset):
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def main():
    if not EMPLOYEES_FILE.exists():
        print(f"ERROR: Missing input: {EMPLOYEES_FILE}")
        sys.exit(1)

    rng = random.Random(SEED)

    with EMPLOYEES_FILE.open(newline="", encoding="utf-8") as f:
        employees = list(csv.DictReader(f))

    if not employees:
        raise ValueError("employees.csv is empty")

    required = {"employee_id"}
    missing = required - set(employees[0])

    if missing:
        raise ValueError(
            f"employees.csv missing required columns: {sorted(missing)}"
        )

    employee_records = []

    salary_candidates = [
        "monthly_salary",
        "base_salary",
        "salary",
        "gross_salary",
        "annual_salary",
    ]

    for employee in employees:
        employee_id = employee["employee_id"].strip()

        if not employee_id:
            raise ValueError("Employee row has empty employee_id")

        raw_salary = first_value(employee, salary_candidates, "")

        salary = None

        if raw_salary:
            salary = money(raw_salary)

            # If annual salary is the source field, convert it to monthly.
            if "annual_salary" in employee and employee["annual_salary"] == raw_salary:
                salary = money(salary / Decimal("12"))

        # Deterministic fallback for the current master schema if salary is absent.
        if salary is None:
            band = SALARY_BANDS[rng.randrange(len(SALARY_BANDS))]
            low, high = band

            # Salary is selected in ₹1,000 increments.
            low_i = int(low)
            high_i = int(high)
            salary = Decimal(
                rng.randrange(low_i // 1000, high_i // 1000 + 1) * 1000
            ).quantize(Q)

        if salary <= 0:
            raise ValueError(
                f"Invalid monthly salary for {employee_id}: {salary}"
            )

        employee_records.append({
            "employee_id": employee_id,
            "employee_name": first_value(
                employee,
                ["employee_name", "name", "full_name"],
                employee_id,
            ),
            "department": first_value(
                employee,
                ["department", "dept"],
                "GENERAL",
            ),
            "designation": first_value(
                employee,
                ["designation", "role", "job_title"],
                "EMPLOYEE",
            ),
            "monthly_salary": salary,
        })

    # Prevent accidental duplicate employee master records.
    employee_ids = [e["employee_id"] for e in employee_records]

    if len(employee_ids) != len(set(employee_ids)):
        raise ValueError("Duplicate employee_id in employees.csv")

    rows = []

    # Clean payroll assumptions:
    # Employee PF: 12% of basic component, where basic = 50% of gross.
    # Employee professional tax: ₹200/month, capped to ₹0 for very low gross.
    # TDS: deterministic progressive approximation for synthetic data.
    # Employer PF: 12% of basic.
    # Employer ESIC: 3.25% for employees under ₹21,000 gross (rare given bands).
    #
    # These are synthetic accounting assumptions, not Indian tax advice.

    for month_offset in range(MONTHS):
        year, month = add_month(START_YEAR, START_MONTH, month_offset)

        # Salary payment normally occurs on the last working-day proxy.
        # For deterministic data, use the 28th.
        pay_date = date(year, month, 28)

        for employee in employee_records:
            gross = money(employee["monthly_salary"])

            basic = money(gross * Decimal("0.50"))
            employee_pf = money(basic * Decimal("0.12"))

            # Synthetic professional tax rule.
            professional_tax = (
                Decimal("200.00")
                if gross >= Decimal("15000.00")
                else Decimal("0.00")
            )

            # Synthetic TDS approximation. This is deliberately simple and
            # deterministic because this is a financial data generator, not a
            # tax computation engine.
            annualized = gross * Decimal("12")

            if annualized <= Decimal("500000"):
                tds = Decimal("0.00")
            elif annualized <= Decimal("1000000"):
                tds = money((annualized - Decimal("500000")) * Decimal("0.05") / Decimal("12"))
            elif annualized <= Decimal("1500000"):
                tds = money(
                    (
                        Decimal("25000")
                        + (annualized - Decimal("1000000")) * Decimal("0.10")
                    ) / Decimal("12")
                )
            else:
                tds = money(
                    (
                        Decimal("75000")
                        + (annualized - Decimal("1500000")) * Decimal("0.15")
                    ) / Decimal("12")
                )

            employee_deductions = money(
                employee_pf + professional_tax + tds
            )

            net_pay = money(gross - employee_deductions)

            employer_pf = money(basic * Decimal("0.12"))
            employer_esic = (
                money(gross * Decimal("0.0325"))
                if gross <= Decimal("21000.00")
                else Decimal("0.00")
            )

            employer_contributions = money(
                employer_pf + employer_esic
            )

            total_employer_cost = money(
                gross + employer_contributions
            )

            payroll_id = f"PYR_{len(rows)+1:06d}"

            rows.append({
                "payroll_id": payroll_id,
                "employee_id": employee["employee_id"],
                "employee_name": employee["employee_name"],
                "department": employee["department"],
                "designation": employee["designation"],
                "payroll_period": f"{year:04d}-{month:02d}",
                "pay_date": pay_date.isoformat(),
                "gross_salary": f"{gross:.2f}",
                "employee_pf": f"{employee_pf:.2f}",
                "professional_tax": f"{professional_tax:.2f}",
                "tds": f"{tds:.2f}",
                "employee_deductions": f"{employee_deductions:.2f}",
                "net_pay": f"{net_pay:.2f}",
                "employer_pf": f"{employer_pf:.2f}",
                "employer_esic": f"{employer_esic:.2f}",
                "employer_contributions": f"{employer_contributions:.2f}",
                "total_employer_cost": f"{total_employer_cost:.2f}",
                "currency": CURRENCY,
                "payment_account_id": PAYROLL_ACCOUNT,
                "status": "PAID",
                "bank_reference": f"PAYROLL_{len(rows)+1:08d}",
            })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "payroll_id",
        "employee_id",
        "employee_name",
        "department",
        "designation",
        "payroll_period",
        "pay_date",
        "gross_salary",
        "employee_pf",
        "professional_tax",
        "tds",
        "employee_deductions",
        "net_pay",
        "employer_pf",
        "employer_esic",
        "employer_contributions",
        "total_employer_cost",
        "currency",
        "payment_account_id",
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
    if len(rows) != len(employee_records) * MONTHS:
        raise AssertionError(
            "Expected exactly one payroll record per employee per month"
        )

    payroll_ids = [r["payroll_id"] for r in rows]
    bank_refs = [r["bank_reference"] for r in rows]

    if len(payroll_ids) != len(set(payroll_ids)):
        raise AssertionError("Duplicate payroll_id")

    if len(bank_refs) != len(set(bank_refs)):
        raise AssertionError("Duplicate payroll bank reference")

    for r in rows:
        gross = money(r["gross_salary"])
        pf = money(r["employee_pf"])
        pt = money(r["professional_tax"])
        tds = money(r["tds"])
        deductions = money(r["employee_deductions"])
        net = money(r["net_pay"])

        employer_pf = money(r["employer_pf"])
        employer_esic = money(r["employer_esic"])
        employer_contributions = money(r["employer_contributions"])
        employer_cost = money(r["total_employer_cost"])

        if deductions != money(pf + pt + tds):
            raise AssertionError(
                f"Employee deduction formula mismatch: {r['payroll_id']}"
            )

        if net != money(gross - deductions):
            raise AssertionError(
                f"Net pay formula mismatch: {r['payroll_id']}"
            )

        if employer_contributions != money(employer_pf + employer_esic):
            raise AssertionError(
                f"Employer contribution formula mismatch: {r['payroll_id']}"
            )

        if employer_cost != money(gross + employer_contributions):
            raise AssertionError(
                f"Employer cost formula mismatch: {r['payroll_id']}"
            )

        if net <= 0 or gross <= 0:
            raise AssertionError(
                f"Non-positive payroll amount: {r['payroll_id']}"
            )

        if r["payment_account_id"] != PAYROLL_ACCOUNT:
            raise AssertionError(
                f"Wrong payroll account: {r['payroll_id']}"
            )

        if r["status"] != "PAID":
            raise AssertionError(
                f"Unexpected payroll status: {r['payroll_id']}"
            )

    total_gross = sum(
        (money(r["gross_salary"]) for r in rows),
        Decimal("0.00"),
    )
    total_net = sum(
        (money(r["net_pay"]) for r in rows),
        Decimal("0.00"),
    )
    total_employer_cost = sum(
        (money(r["total_employer_cost"]) for r in rows),
        Decimal("0.00"),
    )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Employees:             {len(employee_records):,}")
    print(f"Payroll records:       {len(rows):,}")
    print(f"Gross salary total:    ₹{total_gross:,.2f}")
    print(f"Net salary total:      ₹{total_net:,.2f}")
    print(f"Employer total cost:   ₹{total_employer_cost:,.2f}")
    print(f"Payroll account:       {PAYROLL_ACCOUNT}")


if __name__ == "__main__":
    main()
