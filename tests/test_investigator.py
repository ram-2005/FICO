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

from backend.app.intelligence.llm_client import (
    OllamaClient,
)

from backend.app.intelligence.investigator import (
    Investigator,
)


def main():

    print()
    print("=" * 70)
    print("AI FINANCIAL INVESTIGATION TEST")
    print("=" * 70)

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    payments = load_payments()
    settlements = load_settlements()
    bank_transactions = load_bank_transactions()

    # --------------------------------------------------------
    # Build graph
    # --------------------------------------------------------

    financial_graph = build_financial_graph(
        payments,
        settlements,
        bank_transactions,
    )

    # --------------------------------------------------------
    # Bank index
    # --------------------------------------------------------

    bank_index = build_bank_reference_index(
        bank_transactions
    )

    # --------------------------------------------------------
    # Find first exception
    # --------------------------------------------------------

    settlement = None
    reconciliation_result = None

    for current_settlement in settlements:

        result = reconcile_settlement(
            current_settlement,
            payments,
            bank_index,
        )

        if result.status == "EXCEPTION":

            settlement = current_settlement
            reconciliation_result = result

            break

    if settlement is None:

        print("No exception found.")
        return

    # --------------------------------------------------------
    # Build evidence
    # --------------------------------------------------------

    case = build_investigation_case(
        settlement=settlement,
        reconciliation_result=reconciliation_result,
        bank_transactions=bank_transactions,
        financial_graph=financial_graph,
    )

    # --------------------------------------------------------
    # Ollama
    # --------------------------------------------------------

    client = OllamaClient(
        model="gemma:2b"
    )

    investigator = Investigator(
        llm_client=client
    )

    # --------------------------------------------------------
    # Investigate
    # --------------------------------------------------------

    print()
    print("Sending financial evidence to Gemma...")
    print()

    investigation = investigator.investigate(
        case
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print("=" * 70)
    print("AI INVESTIGATION RESULT")
    print("=" * 70)

    print()
    print(
        f"Settlement: "
        f"{investigation.settlement_id}"
    )

    print()
    print("SUMMARY")
    print("-" * 70)
    print(investigation.summary)

    print()
    print("LIKELY CAUSES")
    print("-" * 70)

    for cause in investigation.likely_causes:
        print(f"- {cause}")

    print()
    print("SUPPORTING EVIDENCE")
    print("-" * 70)

    for evidence in investigation.supporting_evidence:
        print(f"- {evidence}")

    print()
    print("MISSING EVIDENCE")
    print("-" * 70)

    for evidence in investigation.missing_evidence:
        print(f"- {evidence}")

    print()
    print("RECOMMENDED ACTION")
    print("-" * 70)
    print(investigation.recommended_action)

    print()
    print(
        f"AI CONFIDENCE: "
        f"{investigation.confidence:.2f}"
    )

    print()
    print("=" * 70)
    print("AI INVESTIGATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
