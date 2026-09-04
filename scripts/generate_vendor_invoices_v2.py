#!/usr/bin/env python3
"""
GENERATE_VENDOR_INVOICES_V2

Generate CLEAN vendor invoice observations for Aarohan Commerce.

Inputs:
    data/raw/master/vendors.csv
    data/raw/master/products.csv
    data/raw/commerce/orders.csv

Actual vendors.csv schema:
    vendor_id,vendor_name,vendor_category,credit_period_days,
    gst_registered,handles_cod

Output:
    data/raw/vendors/vendor_invoices.csv

No intentional anomalies are injected.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import csv
import random
import sys

ROOT = Path(__file__).resolve().parents[1]

VENDORS_FILE = ROOT / "data/raw/master/vendors.csv"
PRODUCTS_FILE = ROOT / "data/raw/master/products.csv"
ORDERS_FILE = ROOT / "data/raw/commerce/orders.csv"
OUTPUT_FILE = ROOT / "data/raw/vendors/vendor_invoices.csv"

SEED = 42
Q = Decimal("0.01")
CURRENCY = "INR"

VALID_CATEGORIES = {"GOODS", "LOGISTICS", "SERVICES"}


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
    for path in (VENDORS_FILE, PRODUCTS_FILE, ORDERS_FILE):
        if not path.exists():
            print(f"ERROR: Missing input: {path}")
            sys.exit(1)

    rng = random.Random(SEED)

    with VENDORS_FILE.open(newline="", encoding="utf-8") as f:
        vendors = list(csv.DictReader(f))

    with PRODUCTS_FILE.open(newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))

    with ORDERS_FILE.open(newline="", encoding="utf-8") as f:
        orders = list(csv.DictReader(f))

    if not vendors:
        raise ValueError("vendors.csv is empty")
    if not products:
        raise ValueError("products.csv is empty")
    if not orders:
        raise ValueError("orders.csv is empty")

    # Validate the exact master-data contract we discovered.
    required_vendor_fields = {
        "vendor_id",
        "vendor_name",
        "vendor_category",
        "credit_period_days",
        "gst_registered",
        "handles_cod",
    }

    missing = required_vendor_fields - set(vendors[0])
    if missing:
        raise ValueError(
            f"vendors.csv missing required columns: {sorted(missing)}"
        )

    vendor_records = []

    for v in vendors:
        category = v["vendor_category"].strip().upper()

        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid vendor_category for {v['vendor_id']}: {category!r}"
            )

        try:
            credit_days = int(v["credit_period_days"])
        except ValueError:
            raise ValueError(
                f"Invalid credit_period_days for {v['vendor_id']}: "
                f"{v['credit_period_days']!r}"
            )

        if credit_days < 0:
            raise ValueError(
                f"Negative credit period for {v['vendor_id']}"
            )

        gst_registered = v["gst_registered"].strip().upper()
        handles_cod = v["handles_cod"].strip().upper()

        if gst_registered not in {"Y", "N"}:
            raise ValueError(
                f"Invalid gst_registered for {v['vendor_id']}"
            )

        if handles_cod not in {"Y", "N"}:
            raise ValueError(
                f"Invalid handles_cod for {v['vendor_id']}"
            )

        if category == "LOGISTICS" and handles_cod == "Y":
            # Valid and expected: this vendor participates in the COD path.
            pass

        vendor_records.append({
            "vendor_id": v["vendor_id"],
            "vendor_name": v["vendor_name"],
            "vendor_category": category,
            "credit_period_days": credit_days,
            "gst_registered": gst_registered,
            "handles_cod": handles_cod,
        })

    by_category = {
        category: [
            v for v in vendor_records
            if v["vendor_category"] == category
        ]
        for category in VALID_CATEGORIES
    }

    for category, group in by_category.items():
        if not group:
            raise ValueError(
                f"No vendors found for category {category}"
            )

    # Count actual order volume by month. This lets vendor activity follow
    # the commercial world's seasonality rather than being disconnected from it.
    month_orders = {}

    for o in orders:
        dt = parse_dt(o["order_date"])
        if dt is None:
            continue

        key = (dt.year, dt.month)
        month_orders[key] = month_orders.get(key, 0) + 1

    if not month_orders:
        raise ValueError("No usable order dates found")

    rows = []

    goods_descriptions = [
        "Inventory replenishment",
        "Merchandise procurement",
        "Packaging and merchandise supplies",
        "Product stock replenishment",
    ]

    logistics_descriptions = [
        "Outbound logistics services",
        "Last-mile delivery services",
        "COD collection and remittance services",
        "Reverse logistics services",
    ]

    service_descriptions = [
        "Technology services",
        "Marketing services",
        "Professional services",
        "Facilities and administrative services",
    ]

    for year, month in sorted(month_orders):
        order_count = month_orders[(year, month)]

        # -------------------------
        # GOODS
        # -------------------------
        goods_count = max(2, int(round(order_count * 0.03)))

        for _ in range(goods_count):
            vendor = rng.choice(by_category["GOODS"])

            subtotal = money(
                Decimal(rng.randint(45000, 220000))
            )

            tax_rate = (
                Decimal("0.18")
                if vendor["gst_registered"] == "Y"
                else Decimal("0.00")
            )

            tax = money(subtotal * tax_rate)
            total = money(subtotal + tax)

            invoice_day = rng.randint(2, 25)
            invoice_dt = datetime(
                year, month, min(invoice_day, 28),
                10, rng.randint(0, 59)
            )

            due_dt = invoice_dt + timedelta(
                days=vendor["credit_period_days"]
            )

            rows.append({
                "vendor_invoice_id": f"VINV_{len(rows)+1:06d}",
                "vendor_id": vendor["vendor_id"],
                "vendor_category": vendor["vendor_category"],
                "invoice_date": fmt(invoice_dt),
                "due_date": fmt(due_dt),
                "invoice_type": "GOODS",
                "description": rng.choice(goods_descriptions),
                "subtotal": f"{subtotal:.2f}",
                "tax_amount": f"{tax:.2f}",
                "total_amount": f"{total:.2f}",
                "currency": CURRENCY,
                "status": "APPROVED",
                "purchase_reference": f"PO_{len(rows)+1:08d}",
                "handles_cod": vendor["handles_cod"],
            })

        # -------------------------
        # LOGISTICS
        # -------------------------
        logistics_count = max(1, int(round(order_count * 0.015)))

        for _ in range(logistics_count):
            # Prefer logistics vendors that actually handle COD for some
            # invoices, reflecting the approved COD operating path.
            if rng.random() < 0.35:
                cod_vendors = [
                    v for v in by_category["LOGISTICS"]
                    if v["handles_cod"] == "Y"
                ]
                vendor = rng.choice(cod_vendors or by_category["LOGISTICS"])
            else:
                vendor = rng.choice(by_category["LOGISTICS"])

            subtotal = money(
                Decimal(rng.randint(18000, 95000))
            )

            tax_rate = (
                Decimal("0.18")
                if vendor["gst_registered"] == "Y"
                else Decimal("0.00")
            )

            tax = money(subtotal * tax_rate)
            total = money(subtotal + tax)

            invoice_day = rng.randint(3, 26)
            invoice_dt = datetime(
                year, month, min(invoice_day, 28),
                11, rng.randint(0, 59)
            )

            due_dt = invoice_dt + timedelta(
                days=vendor["credit_period_days"]
            )

            rows.append({
                "vendor_invoice_id": f"VINV_{len(rows)+1:06d}",
                "vendor_id": vendor["vendor_id"],
                "vendor_category": vendor["vendor_category"],
                "invoice_date": fmt(invoice_dt),
                "due_date": fmt(due_dt),
                "invoice_type": "LOGISTICS",
                "description": rng.choice(logistics_descriptions),
                "subtotal": f"{subtotal:.2f}",
                "tax_amount": f"{tax:.2f}",
                "total_amount": f"{total:.2f}",
                "currency": CURRENCY,
                "status": "APPROVED",
                "purchase_reference": f"LOG_{len(rows)+1:08d}",
                "handles_cod": vendor["handles_cod"],
            })

        # -------------------------
        # SERVICES
        # -------------------------
        for _ in range(3):
            vendor = rng.choice(by_category["SERVICES"])

            subtotal = money(
                Decimal(rng.randint(25000, 120000))
            )

            tax_rate = (
                Decimal("0.18")
                if vendor["gst_registered"] == "Y"
                else Decimal("0.00")
            )

            tax = money(subtotal * tax_rate)
            total = money(subtotal + tax)

            invoice_day = rng.choice([5, 10, 15, 20, 25])
            invoice_dt = datetime(
                year, month, invoice_day,
                12, rng.randint(0, 59)
            )

            due_dt = invoice_dt + timedelta(
                days=vendor["credit_period_days"]
            )

            rows.append({
                "vendor_invoice_id": f"VINV_{len(rows)+1:06d}",
                "vendor_id": vendor["vendor_id"],
                "vendor_category": vendor["vendor_category"],
                "invoice_date": fmt(invoice_dt),
                "due_date": fmt(due_dt),
                "invoice_type": "SERVICES",
                "description": rng.choice(service_descriptions),
                "subtotal": f"{subtotal:.2f}",
                "tax_amount": f"{tax:.2f}",
                "total_amount": f"{total:.2f}",
                "currency": CURRENCY,
                "status": "APPROVED",
                "purchase_reference": f"SVC_{len(rows)+1:08d}",
                "handles_cod": vendor["handles_cod"],
            })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "vendor_invoice_id",
        "vendor_id",
        "vendor_category",
        "invoice_date",
        "due_date",
        "invoice_type",
        "description",
        "subtotal",
        "tax_amount",
        "total_amount",
        "currency",
        "status",
        "purchase_reference",
        "handles_cod",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # -------------------------
    # Validations
    # -------------------------
    invoice_ids = [r["vendor_invoice_id"] for r in rows]
    references = [r["purchase_reference"] for r in rows]

    if len(invoice_ids) != len(set(invoice_ids)):
        raise AssertionError("Duplicate vendor_invoice_id")

    if len(references) != len(set(references)):
        raise AssertionError("Duplicate purchase_reference")

    vendor_map = {v["vendor_id"]: v for v in vendor_records}

    for r in rows:
        vendor = vendor_map.get(r["vendor_id"])
        if not vendor:
            raise AssertionError(
                f"Unknown vendor reference: {r['vendor_invoice_id']}"
            )

        if r["vendor_category"] != vendor["vendor_category"]:
            raise AssertionError(
                f"Vendor category mismatch: {r['vendor_invoice_id']}"
            )

        subtotal = money(r["subtotal"])
        tax = money(r["tax_amount"])
        total = money(r["total_amount"])

        if subtotal <= 0:
            raise AssertionError(
                f"Non-positive subtotal: {r['vendor_invoice_id']}"
            )

        if total != money(subtotal + tax):
            raise AssertionError(
                f"Invoice formula mismatch: {r['vendor_invoice_id']}"
            )

        invoice_dt = parse_dt(r["invoice_date"])
        due_dt = parse_dt(r["due_date"])

        expected_due = invoice_dt + timedelta(
            days=vendor["credit_period_days"]
        )

        if due_dt != expected_due:
            raise AssertionError(
                f"Credit period mismatch: {r['vendor_invoice_id']}"
            )

        expected_tax = (
            money(subtotal * Decimal("0.18"))
            if vendor["gst_registered"] == "Y"
            else Decimal("0.00")
        )

        if tax != expected_tax:
            raise AssertionError(
                f"GST calculation mismatch: {r['vendor_invoice_id']}"
            )

    total_value = sum(
        (money(r["total_amount"]) for r in rows),
        Decimal("0.00"),
    )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Vendor invoices:       {len(rows):,}")
    print(f"Total obligations:     ₹{total_value:,.2f}")

    print("\nBy vendor category:")
    for category in ("GOODS", "LOGISTICS", "SERVICES"):
        group = [
            r for r in rows
            if r["vendor_category"] == category
        ]
        value = sum(
            (money(r["total_amount"]) for r in group),
            Decimal("0.00"),
        )
        print(
            f"  {category:10s}: "
            f"{len(group):,} invoices | ₹{value:,.2f}"
        )

    cod_logistics = sum(
        r["vendor_category"] == "LOGISTICS"
        and r["handles_cod"] == "Y"
        for r in rows
    )
    print(f"\nCOD-handling logistics invoices: {cod_logistics:,}")


if __name__ == "__main__":
    main()
