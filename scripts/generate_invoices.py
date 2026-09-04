#!/usr/bin/env python3
"""
Generate Aarohan Commerce invoices from data/raw/commerce/orders.csv.

Run from the FICO project root:
    python scripts/generate_invoices.py

Optional:
    python scripts/generate_invoices.py --project-root .
    python scripts/generate_invoices.py --seed 42

Important:
- Invoices are derived from orders; they are NOT independently randomized.
- One invoice is created for every order, including orders later cancelled,
  because the approved synthetic-world design defines Order -> Invoice as 1:1.
- A cancelled order produces an invoice record whose status is CANCELLED.
- Monetary values are copied from the order source and validated with Decimal.
- No anomaly injection occurs here.
"""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from pathlib import Path


FIELDS = [
    "invoice_id",
    "order_id",
    "customer_id",
    "invoice_date",
    "gross_amount",
    "discount",
    "tax",
    "shipping_fee",
    "net_amount",
    "invoice_status",
    "currency",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")

    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def validate_order(order: dict[str, str]) -> None:
    required = [
        "order_id",
        "customer_id",
        "order_date",
        "gross_amount",
        "discount",
        "tax",
        "shipping_fee",
        "net_amount",
        "order_status",
        "invoice_date",
    ]

    missing = [
        field
        for field in required
        if field not in order
    ]

    if missing:
        raise ValueError(
            f"Order {order.get('order_id', '<unknown>')} "
            f"is missing fields: {missing}"
        )

    # Authoritative money invariant from the order source.
    expected = (
        Decimal(order["gross_amount"])
        - Decimal(order["discount"])
        + Decimal(order["shipping_fee"])
        + Decimal(order["tax"])
    )

    actual = Decimal(order["net_amount"])

    if expected != actual:
        raise ValueError(
            f"Order money invariant failed for "
            f"{order['order_id']}: "
            f"expected {expected}, got {actual}"
        )


def invoice_status(order_status: str) -> str:
    """
    Map the commerce order lifecycle into the invoice lifecycle.

    This is source-system representation, not M2 classification.
    """
    if order_status == "CANCELLED":
        return "CANCELLED"

    if order_status == "RETURNED":
        return "RETURNED"

    return "ISSUED"


def generate_invoices(
    orders: list[dict[str, str]],
) -> list[dict[str, str]]:
    invoices: list[dict[str, str]] = []

    seen_orders: set[str] = set()

    for number, order in enumerate(orders, start=1):
        validate_order(order)

        order_id = order["order_id"]

        if order_id in seen_orders:
            raise ValueError(
                f"Duplicate order encountered: {order_id}"
            )

        seen_orders.add(order_id)

        # The approved source design says invoice generation occurs
        # minutes-to-hours after order confirmation. The existing order
        # source already carries invoice_date for non-cancelled orders.
        # For cancelled orders, invoice_date may be blank because the
        # order can be cancelled before invoice generation in the source
        # implementation. We retain that source observation rather than
        # inventing a timestamp.
        invoices.append(
            {
                "invoice_id": f"INV_{number:06d}",
                "order_id": order_id,
                "customer_id": order["customer_id"],
                "invoice_date": order["invoice_date"],
                "gross_amount": order["gross_amount"],
                "discount": order["discount"],
                "tax": order["tax"],
                "shipping_fee": order["shipping_fee"],
                "net_amount": order["net_amount"],
                "invoice_status": invoice_status(
                    order["order_status"]
                ),
                "currency": "INR",
            }
        )

    return invoices


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)


def validate_invoices(
    invoices: list[dict[str, str]],
    orders: list[dict[str, str]],
) -> None:
    if len(invoices) != len(orders):
        raise AssertionError(
            f"Expected 1 invoice per order: "
            f"{len(orders)} orders vs {len(invoices)} invoices"
        )

    invoice_ids = [
        invoice["invoice_id"]
        for invoice in invoices
    ]

    if len(set(invoice_ids)) != len(invoice_ids):
        raise AssertionError("Invoice IDs are not unique")

    order_ids = {
        order["order_id"]
        for order in orders
    }

    invoice_order_ids = {
        invoice["order_id"]
        for invoice in invoices
    }

    if order_ids != invoice_order_ids:
        raise AssertionError(
            "Invoice/order relationship is not 1:1"
        )

    order_by_id = {
        order["order_id"]: order
        for order in orders
    }

    for invoice in invoices:
        order = order_by_id[invoice["order_id"]]

        # Invoice must preserve the authoritative commercial amounts.
        for field in [
            "gross_amount",
            "discount",
            "tax",
            "shipping_fee",
            "net_amount",
        ]:
            if invoice[field] != order[field]:
                raise AssertionError(
                    f"{invoice['invoice_id']}: "
                    f"{field} differs from source order"
                )

        # Customer provenance must agree.
        if invoice["customer_id"] != order["customer_id"]:
            raise AssertionError(
                f"{invoice['invoice_id']}: customer mismatch"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="FICO project root. Defaults to current directory.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Recorded for reproducibility metadata; invoice derivation "
             "itself is deterministic from orders.",
    )
    args = parser.parse_args()

    orders_path = (
        args.project_root
        / "data"
        / "raw"
        / "commerce"
        / "orders.csv"
    )

    output_path = (
        args.project_root
        / "data"
        / "raw"
        / "commerce"
        / "invoices.csv"
    )

    orders = read_csv(orders_path)
    invoices = generate_invoices(orders)

    validate_invoices(invoices, orders)
    write_csv(output_path, invoices)

    status_counts: dict[str, int] = {}
    total = Decimal("0.00")

    for invoice in invoices:
        status = invoice["invoice_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        total += Decimal(invoice["net_amount"])

    print("INVOICES DATASET CREATED + VALIDATED")
    print(f"Seed: {args.seed}")
    print(f"Orders: {len(orders):,}")
    print(f"Invoices: {len(invoices):,}")
    print(f"Invoice total: ₹{total:,.2f}")
    print(f"Statuses: {status_counts}")
    print(f"File: {output_path}")


if __name__ == "__main__":
    main()
