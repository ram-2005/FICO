from run_controller import (
    load_payments,
    load_settlements,
    load_bank_transactions,
    build_financial_graph,
    build_bank_reference_index,
    reconcile_settlement,
)

from backend.app.intelligence.evidence_builder import (
    build_investigation_case,
)


def main():

    print()
    print("=" * 70)
    print("EVIDENCE BUILDER TEST")
    print("=" * 70)

    # --------------------------------------------------------
    # Load the same data as run_controller
    # --------------------------------------------------------

    payments = load_payments()
    settlements = load_settlements()
    bank_transactions = load_bank_transactions()

    print(
        f"Payments: {len(payments):,}"
    )

    print(
        f"Settlements: {len(settlements):,}"
    )

    print(
        f"Bank transactions: {len(bank_transactions):,}"
    )

    # --------------------------------------------------------
    # Build financial graph
    # --------------------------------------------------------

    financial_graph = build_financial_graph(
        payments,
        settlements,
        bank_transactions,
    )

    # --------------------------------------------------------
    # Build bank index
    # --------------------------------------------------------

    bank_index = build_bank_reference_index(
        bank_transactions
    )

    # --------------------------------------------------------
    # Find first exception
    # --------------------------------------------------------

    exception_result = None
    exception_settlement = None

    for settlement in settlements:

        result = reconcile_settlement(
            settlement,
            payments,
            bank_index,
        )

        if result.status == "EXCEPTION":

            exception_result = result
            exception_settlement = settlement

            break

    if exception_result is None:

        print()
        print("No exception found.")
        return

    # --------------------------------------------------------
    # Build investigation case
    # --------------------------------------------------------

    case = build_investigation_case(
        settlement=exception_settlement,
        reconciliation_result=exception_result,
        bank_transactions=bank_transactions,
        financial_graph=financial_graph,
    )

    # --------------------------------------------------------
    # Display result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("INVESTIGATION CASE CREATED")
    print("=" * 70)

    print(
        case.to_json()
    )

    print()
    print("=" * 70)
    print("EVIDENCE BUILDER TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
