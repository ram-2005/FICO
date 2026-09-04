#!/usr/bin/env python3
"""
Generate Aarohan Commerce orders for M1.

Run from the FICO project root:
    python scripts/generate_orders.py

Or:
    python scripts/generate_orders.py --seed 42 --baseline-orders 12000

This script reads:
    data/raw/master/customers.csv
    data/raw/master/products.csv

and writes:
    data/raw/commerce/orders.csv

It uses Decimal for authoritative money calculations and a deterministic
random seed.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, datetime, timedelta, time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


MONTHS = [
    (date(2025, 9, 1), Decimal("1.00")),
    (date(2025, 10, 1), Decimal("1.55")),
    (date(2025, 11, 1), Decimal("1.15")),
    (date(2025, 12, 1), Decimal("1.20")),
    (date(2026, 1, 1), Decimal("1.10")),
    (date(2026, 2, 1), Decimal("0.85")),
    (date(2026, 3, 1), Decimal("1.05")),
    (date(2026, 4, 1), Decimal("0.80")),
    (date(2026, 5, 1), Decimal("0.95")),
    (date(2026, 6, 1), Decimal("1.30")),
    (date(2026, 7, 1), Decimal("1.10")),
    (date(2026, 8, 1), Decimal("1.00")),
]

GST_RATES = {
    "Home & Kitchen": Decimal("0.18"),
    "Personal Care & Wellness": Decimal("0.18"),
    "Apparel & Accessories": Decimal("0.12"),
    "Electronics Accessories": Decimal("0.18"),
    "Home & Lifestyle Decor": Decimal("0.18"),
}

FIELDS = [
    "order_id",
    "customer_id",
    "order_date",
    "gross_amount",
    "discount",
    "tax",
    "shipping_fee",
    "net_amount",
    "order_status",
    "payment_method_selected",
    "fulfillment_hub",
    "invoice_date",
    "delivered_date",
    "sku_lines",
]


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def month_end(first_day: date) -> date:
    if first_day.month == 12:
        return date(first_day.year + 1, 1, 1) - timedelta(days=1)
    return date(first_day.year, first_day.month + 1, 1) - timedelta(days=1)


def weighted_day(rng: random.Random, first_day: date, last_day: date) -> date:
    days = []
    weights = []
    current = first_day

    # Mild weekday/weekend effect.
    weekday_weights = {
        0: 1.00,  # Mon
        1: 1.08,
        2: 1.10,
        3: 1.08,
        4: 1.02,
        5: 0.95,
        6: 0.90,
    }

    while current <= last_day:
        days.append(current)
        weights.append(weekday_weights[current.weekday()])
        current += timedelta(days=1)

    return rng.choices(days, weights=weights, k=1)[0]


def order_timestamp(rng: random.Random, day: date) -> datetime:
    # Evening-heavy e-commerce ordering pattern.
    hours = list(range(7, 24))
    weights = [1, 1, 1, 1, 1, 2, 3, 4, 6, 8, 10, 11, 12, 11, 9, 7, 5]
    hour = rng.choices(hours, weights=weights, k=1)[0]

    return datetime.combine(
        day,
        time(hour, rng.randrange(60), rng.randrange(60)),
    )


def build_product_weights(
    products: list[dict[str, str]], seed: int
) -> list[float]:
    weights = []

    for product in products:
        price = Decimal(product["unit_price"])
        product_number = int(product["product_id"].split("_")[1])

        local_rng = random.Random(seed * 100_000 + product_number)
        popularity = Decimal(str(0.75 + local_rng.expovariate(1.0)))

        # Lower-priced products are more frequently purchased.
        weight = float(
            (Decimal("1") / (price ** Decimal("1.55")))
            * popularity
        )
        weights.append(weight)

    return weights


def build_customer_weights(
    customers: list[dict[str, str]], seed: int
) -> list[float]:
    weights = []

    for customer in customers:
        customer_number = int(customer["customer_id"].split("_")[1])
        local_rng = random.Random(seed * 200_000 + customer_number)
        weights.append(0.4 + 1.6 * local_rng.expovariate(1.0))

    return weights


def choose_hub(state: str) -> str:
    if state in {
        "Karnataka",
        "Tamil Nadu",
        "Kerala",
        "Telangana",
        "Andhra Pradesh",
    }:
        return "BENGALURU"

    if state in {
        "Delhi",
        "Haryana",
        "Uttar Pradesh",
        "Rajasthan",
        "Punjab",
    }:
        return "DELHI_NCR"

    return "MUMBAI"


def generate_orders(
    *,
    customers: list[dict[str, str]],
    products: list[dict[str, str]],
    seed: int,
    baseline_orders: int,
) -> list[dict[str, str]]:
    rng = random.Random(seed)

    customer_weights = build_customer_weights(customers, seed)
    product_weights = build_product_weights(products, seed)

    customer_ids = {c["customer_id"] for c in customers}
    orders: list[dict[str, str]] = []
    order_number = 1

    for month_start, seasonality in MONTHS:
        target = round(baseline_orders * float(seasonality))
        target += rng.randint(-180, 180)

        for _ in range(target):
            customer = rng.choices(
                customers,
                weights=customer_weights,
                k=1,
            )[0]

            order_day = weighted_day(
                rng,
                month_start,
                month_end(month_start),
            )
            created_at = order_timestamp(rng, order_day)

            # Most orders contain one SKU; a smaller number contain
            # multiple SKUs.
            line_count = rng.choices(
                [1, 2, 3],
                weights=[91, 8, 1],
                k=1,
            )[0]

            selected_products = []
            selected_ids = set()

            for _ in range(line_count):
                for _attempt in range(20):
                    product = rng.choices(
                        products,
                        weights=product_weights,
                        k=1,
                    )[0]

                    if product["product_id"] not in selected_ids:
                        selected_ids.add(product["product_id"])
                        selected_products.append(product)
                        break

            lines = []
            subtotal = Decimal("0.00")
            tax = Decimal("0.00")

            for product in selected_products:
                quantity = rng.choices(
                    [1, 2],
                    weights=[99, 1],
                    k=1,
                )[0]

                unit_price = Decimal(product["unit_price"])

                # SKU-level promotion.
                promo_rate = rng.choices(
                    [
                        Decimal("0.00"),
                        Decimal("0.05"),
                        Decimal("0.10"),
                    ],
                    weights=[78, 17, 5],
                    k=1,
                )[0]

                sale_unit_price = money(
                    unit_price * (Decimal("1.00") - promo_rate)
                )
                line_total = money(sale_unit_price * quantity)

                subtotal += line_total
                tax += (
                    line_total
                    * GST_RATES[product["category"]]
                )

                lines.append(
                    {
                        "product_id": product["product_id"],
                        "quantity": quantity,
                        "unit_price": f"{sale_unit_price:.2f}",
                        "line_total": f"{line_total:.2f}",
                    }
                )

            # Order-level promotion. Festive/EOSS months have a higher
            # chance of larger discounts.
            if seasonality >= Decimal("1.30"):
                discount_rate = rng.choices(
                    [
                        Decimal("0.00"),
                        Decimal("0.05"),
                        Decimal("0.10"),
                        Decimal("0.15"),
                    ],
                    weights=[45, 30, 20, 5],
                    k=1,
                )[0]
            else:
                discount_rate = rng.choices(
                    [
                        Decimal("0.00"),
                        Decimal("0.05"),
                        Decimal("0.10"),
                        Decimal("0.15"),
                    ],
                    weights=[67, 21, 10, 2],
                    k=1,
                )[0]

            discount = money(subtotal * discount_rate)

            # Shipping is free above ₹999 after order-level discount.
            taxable_subtotal = subtotal - discount
            if taxable_subtotal >= Decimal("999"):
                shipping = Decimal("0.00")
            else:
                shipping = Decimal(
                    str(rng.choice([49, 59, 69]))
                )

            # Explicit synthetic tax policy:
            # SKU tax is calculated before order-level discount; the
            # discount is treated as reducing the tax base at 18%.
            tax = money(
                tax
                - discount * Decimal("0.18")
                + shipping * Decimal("0.18")
            )

            net_amount = money(
                subtotal
                - discount
                + shipping
                + tax
            )

            # COD target is approximately 12%, with modest behavioral
            # variation for lower-ticket orders and geography.
            cod_probability = Decimal("0.12")

            if net_amount < Decimal("1000"):
                cod_probability *= Decimal("1.16")
            else:
                cod_probability *= Decimal("0.93")

            if customer["preferred_payment_method"] == "COD":
                cod_probability *= Decimal("1.18")

            if customer["state"] in {
                "Uttar Pradesh",
                "Rajasthan",
                "Odisha",
                "Madhya Pradesh",
                "Gujarat",
                "Andhra Pradesh",
            }:
                cod_probability *= Decimal("1.08")

            if rng.random() < min(Decimal("0.22"), cod_probability):
                payment_method = "COD"
            else:
                payment_method = rng.choices(
                    ["UPI", "CARD", "NET_BANKING"],
                    weights=[50, 28, 10],
                    k=1,
                )[0]

            status = rng.choices(
                [
                    "DELIVERED",
                    "SHIPPED",
                    "CONFIRMED",
                    "CANCELLED",
                    "RETURNED",
                ],
                weights=[79, 7, 7, 5, 2],
                k=1,
            )[0]

            invoice_at = (
                created_at + timedelta(
                    minutes=rng.randint(5, 360)
                )
                if status != "CANCELLED"
                else None
            )

            delivered_at = None
            if (
                invoice_at
                and status in {"DELIVERED", "RETURNED"}
            ):
                delivered_at = (
                    invoice_at
                    + timedelta(
                        days=rng.randint(2, 7),
                        hours=rng.randint(0, 10),
                    )
                )

            orders.append(
                {
                    "order_id": f"ORD_{order_number:06d}",
                    "customer_id": customer["customer_id"],
                    "order_date": created_at.isoformat(),
                    "gross_amount": f"{subtotal:.2f}",
                    "discount": f"{discount:.2f}",
                    "tax": f"{tax:.2f}",
                    "shipping_fee": f"{shipping:.2f}",
                    "net_amount": f"{net_amount:.2f}",
                    "order_status": status,
                    "payment_method_selected": payment_method,
                    "fulfillment_hub": choose_hub(customer["state"]),
                    "invoice_date": (
                        invoice_at.isoformat()
                        if invoice_at
                        else ""
                    ),
                    "delivered_date": (
                        delivered_at.isoformat()
                        if delivered_at
                        else ""
                    ),
                    "sku_lines": json.dumps(
                        lines,
                        separators=(",", ":"),
                    ),
                }
            )

            order_number += 1

    # Generator invariants.
    assert len({o["order_id"] for o in orders}) == len(orders)
    assert all(
        o["customer_id"] in customer_ids
        for o in orders
    )

    for order in orders:
        expected = (
            Decimal(order["gross_amount"])
            - Decimal(order["discount"])
            + Decimal(order["shipping_fee"])
            + Decimal(order["tax"])
        )
        assert expected == Decimal(order["net_amount"]), (
            f"Money invariant failed: {order['order_id']}"
        )

    return orders


def write_orders(path: Path, orders: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(orders)


def print_summary(orders: list[dict[str, str]]) -> None:
    methods: dict[str, int] = {}
    statuses: dict[str, int] = {}
    monthly: dict[str, int] = {}
    total = Decimal("0.00")

    for order in orders:
        method = order["payment_method_selected"]
        status = order["order_status"]
        month = order["order_date"][:7]

        methods[method] = methods.get(method, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1
        monthly[month] = monthly.get(month, 0) + 1
        total += Decimal(order["net_amount"])

    aov = total / Decimal(len(orders))

    print("\nORDERS DATASET CREATED + VALIDATED")
    print(f"Records: {len(orders):,}")
    print(f"AOV: ₹{aov.quantize(Decimal('0.01')):,}")
    print(f"Total order value: ₹{total:,.2f}")
    print(
        f"COD share: "
        f"{methods.get('COD', 0) / len(orders):.2%}"
    )
    print(f"Payment methods: {methods}")
    print(f"Statuses: {statuses}")
    print(f"Monthly counts: {monthly}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--baseline-orders",
        type=int,
        default=12000,
        help="Baseline monthly order count.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="FICO project root. Defaults to current directory.",
    )
    args = parser.parse_args()

    master = args.project_root / "data" / "raw" / "master"
    output = (
        args.project_root
        / "data"
        / "raw"
        / "commerce"
        / "orders.csv"
    )

    customers_path = master / "customers.csv"
    products_path = master / "products.csv"

    if not customers_path.exists():
        raise FileNotFoundError(
            f"Missing {customers_path}"
        )
    if not products_path.exists():
        raise FileNotFoundError(
            f"Missing {products_path}"
        )

    customers = read_csv(customers_path)
    products = read_csv(products_path)

    orders = generate_orders(
        customers=customers,
        products=products,
        seed=args.seed,
        baseline_orders=args.baseline_orders,
    )

    write_orders(output, orders)
    print_summary(orders)
    print(f"\nWrote: {output}")


if __name__ == "__main__":
    main()
