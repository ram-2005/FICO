#!/usr/bin/env python3
"""
Generate CLEAN vendor invoice observations for Aarohan Commerce.

Inputs:
    data/raw/master/vendors.csv
    data/raw/master/products.csv
    data/raw/commerce/orders.csv

Output:
    data/raw/vendors/vendor_invoices.csv

Design:
- Clean true-world vendor obligations.
- No intentional anomalies are injected.
- Vendor invoices represent legitimate procurement/services/logistics costs.
- Goods invoices are associated with vendors classified as GOODS.
- Logistics invoices are associated with logistics vendors.
- Services invoices are associated with service vendors.
- Amounts use Decimal and deterministic ROUND_HALF_UP.
- Seed = 42.
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

GOODS = "GOODS"
LOGISTICS = "LOGISTICS"
SERVICES = "SERVICES"


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


def first_value(row, names, default=""):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def normalize_vendor_class(row):
    raw = first_value(
        row,
        ["vendor_class", "vendor_type", "category", "type"],
        "",
    ).strip().upper()

    if raw in {"GOODS", "PRODUCT", "PRODUCTS", "MERCHANDISE"}:
        return GOODS
    if raw in {"LOGISTICS", "LOGISTIC", "COURIER", "DELIVERY"}:
        return LOGISTICS
    if raw in {"SERVICES", "SERVICE"}:
        return SERVICES

    # Some master datasets may encode these as descriptive strings.
    if "LOGISTIC" in raw or "COURIER" in raw or "DELIVERY" in raw:
        return LOGISTICS
    if "SERVICE" in raw:
        return SERVICES
    if "GOOD" in raw or "PRODUCT" in raw:
        return GOODS

    raise ValueError(
        f"Unable to determine vendor class for "
        f"{first_value(row, ['vendor_id', 'id'], '?')}: {raw!r}"
    )


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

    # Resolve vendor IDs without assuming every master column name.
    vendor_records = []
    for v in vendors:
        vendor_id = first_value(v, ["vendor_id", "id"])
        if not vendor_id:
            raise ValueError("Vendor row has no vendor_id/id")

        vendor_records.append({
            "vendor_id": vendor_id,
            "vendor_class": normalize_vendor_class(v),
            "vendor_name": first_value(
                v, ["vendor_name", "name", "company_name"], vendor_id
            ),
        })

    by_class = {
        GOODS: [v for v in vendor_records if v["vendor_class"] == GOODS],
        LOGISTICS: [v for v in vendor_records if v["vendor_class"] == LOGISTICS],
        SERVICES: [v for v in vendor_records if v["vendor_class"] == SERVICES],
    }

    for cls, group in by_class.items():
        if not group:
            raise ValueError(f"No vendors found for class {cls}")

    # Product costs are derived from product selling prices using a realistic
    # procurement margin. This creates a clean payable obligation without
    # duplicating the customer-side order amount.
    product_price = {}
    for p in products:
        pid = first_value(p, ["product_id", "id"])
        price_raw = first_value(
            p,
            ["unit_price", "selling_price", "price", "mrp"],
            "",
        )
        if not pid or not price_raw:
            continue
        product_price[pid] = money(price_raw)

    # Estimate monthly commerce activity from the actual orders.
    month_orders = {}
    for o in orders:
        dt = parse_dt(o["order_date"])
        if not dt:
            continue
        key = (dt.year, dt.month)
        month_orders[key] = month_orders.get(key, 0) + 1

    # Generate procurement invoices across the 12-month period represented by
    # the order data. These are legitimate obligations, not anomalies.
    rows = []

    # Goods: approximately 3% of monthly orders, batched into procurement POs.
    # Logistics: approximately 1.5% of monthly orders, representing logistics
    # and COD handling services.
    # Services: a few recurring monthly invoices for technology, marketing,
    # facilities, professional services, etc.
    #
    # Amounts are deliberately independent from customer order revenue so the
    # vendor ledger represents a separate source system.

    sorted_months = sorted(month_orders)

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

    for year, month in sorted_months:
        count = month_orders[(year, month)]

        # Goods procurement.
        goods_count = max(2, int(round(count * 0.03)))
        for _ in range(goods_count):
            vendor = rng.choice(by_class[GOODS])

            # Typical purchase invoice size.
            subtotal = money(
                Decimal(str(rng.randint(45000, 220000)))
            )
            tax_rate = rng.choice(
                [Decimal("0.05"), Decimal("0.12"), Decimal("0.18")]
            )
            tax = money(subtotal * tax_rate)
            total = money(subtotal + tax)

            day = rng.randint(2, 25)
            dt = datetime(year, month, min(day, 28), 10, rng.randint(0, 59))

            rows.append({
                "vendor_invoice_id": f"VINV_{len(rows)+1:06d}",
                "vendor_id": vendor["vendor_id"],
                "vendor_class": GOODS,
                "invoice_date": fmt(dt),
                "due_date": fmt(dt + timedelta(days=rng.choice([15, 30, 45]))),
                "invoice_type": "GOODS",
                "description": rng.choice(goods_descriptions),
                "subtotal": f"{subtotal:.2f}",
                "tax_amount": f"{tax:.2f}",
                "total_amount": f"{total:.2f}",
                "currency": CURRENCY,
                "status": "APPROVED",
                "purchase_reference": f"PO_{len(rows)+1:08d}",
            })

        # Logistics procurement.
        logistics_count = max(1, int(round(count * 0.015)))
        for _ in range(logistics_count):
            vendor = rng.choice(by_class[LOGISTICS])

            subtotal = money(
                Decimal(str(rng.randint(18000, 95000)))
            )
            tax_rate = Decimal("0.18")
            tax = money(subtotal * tax_rate)
            total = money(subtotal + tax)

            day = rng.randint(3, 26)
            dt = datetime(year, month, min(day, 28), 11, rng.randint(0, 59))

            rows.append({
                "vendor_invoice_id": f"VINV_{len(rows)+1:06d}",
                "vendor_id": vendor["vendor_id"],
                "vendor_class": LOGISTICS,
                "invoice_date": fmt(dt),
                "due_date": fmt(dt + timedelta(days=rng.choice([15, 30]))),
                "invoice_type": "LOGISTICS",
                "description": rng.choice(logistics_descriptions),
                "subtotal": f"{subtotal:.2f}",
                "tax_amount": f"{tax:.2f}",
                "total_amount": f"{total:.2f}",
                "currency": CURRENCY,
                "status": "APPROVED",
                "purchase_reference": f"LOG_{len(rows)+1:08d}",
            })

        # Recurring service invoices.
        for _ in range(3):
            vendor = rng.choice(by_class[SERVICES])

            subtotal = money(
                Decimal(str(rng.randint(25000, 120000)))
            )
            tax_rate = Decimal("0.18")
            tax = money(subtotal * tax_rate)
            total = money(subtotal + tax)

            day = rng.choice([5, 10, 15, 20, 25])
            dt = datetime(year, month, day, 12, rng.randint(0, 59))

            rows.append({
                "vendor_invoice_id": f"VINV_{len(rows)+1:06d}",
                "vendor_id": vendor["vendor_id"],
                "vendor_class": SERVICES,
                "invoice_date": fmt(dt),
                "due_date": fmt(dt + timedelta(days=rng.choice([15, 30]))),
                "invoice_type": "SERVICES",
                "description": rng.choice(service_descriptions),
                "subtotal": f"{subtotal:.2f}",
                "tax_amount": f"{tax:.2f}",
                "total_amount": f"{total:.2f}",
                "currency": CURRENCY,
                "status": "APPROVED",
                "purchase_reference": f"SVC_{len(rows)+1:08d}",
            })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "vendor_invoice_id",
        "vendor_id",
        "vendor_class",
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
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # -------------------------
    # Clean-world validations
    # -------------------------
    if len({r["vendor_invoice_id"] for r in rows}) != len(rows):
        raise AssertionError("Duplicate vendor_invoice_id")

    if len({r["purchase_reference"] for r in rows}) != len(rows):
        raise AssertionError("Duplicate purchase_reference")

    valid_classes = {GOODS, LOGISTICS, SERVICES}

    for r in rows:
        subtotal = money(r["subtotal"])
        tax = money(r["tax_amount"])
        total = money(r["total_amount"])

        if r["vendor_class"] not in valid_classes:
            raise AssertionError(
                f"Invalid vendor class: {r['vendor_invoice_id']}"
            )

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

        if due_dt < invoice_dt:
            raise AssertionError(
                f"Due date before invoice date: {r['vendor_invoice_id']}"
            )

        if r["status"] != "APPROVED":
            raise AssertionError(
                f"Unexpected clean invoice status: {r['vendor_invoice_id']}"
            )

    total_value = sum(
        (money(r["total_amount"]) for r in rows),
        Decimal("0.00"),
    )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Vendor invoices: {len(rows):,}")
    print(f"Total vendor obligations: ₹{total_value:,.2f}")

    print("\nBy vendor class:")
    for cls in (GOODS, LOGISTICS, SERVICES):
        group = [r for r in rows if r["vendor_class"] == cls]
        value = sum(
            (money(r["total_amount"]) for r in group),
            Decimal("0.00"),
        )
        print(f"  {cls:10s}: {len(group):,} invoices | ₹{value:,.2f}")


if __name__ == "__main__":
    main()
