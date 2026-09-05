from run_controller import (
    load_payments,
    load_settlements,
    load_bank_transactions,
    build_financial_graph,
    build_bank_reference_index,
    reconcile_settlement,
)

from backend.app.graph.tools import FinancialGraphTools

from backend.app.intelligence.tool_executor import (
    ToolExecutor,
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

    print("=" * 70)
    print("LLM + FINANCIAL GRAPH INVESTIGATION TEST")
    print("=" * 70)

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    payments = load_payments()
    settlements = load_settlements()
    bank_transactions = load_bank_transactions()

    # --------------------------------------------------------
    # Build graph
    # --------------------------------------------------------

    graph = build_financial_graph(
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
    # Find an exception
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

    if exception_settlement is None:

        print("No exception found.")

        return

    print()
    print("=" * 70)
    print(
        f"INVESTIGATING: "
        f"{exception_settlement.source_id}"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Build evidence case
    # --------------------------------------------------------

    case = build_investigation_case(
        exception_settlement,
        exception_result,
        bank_transactions,
        graph,
    )

    # --------------------------------------------------------
    # Graph tools
    # --------------------------------------------------------

    graph_tools = FinancialGraphTools(
        graph
    )

    tool_executor = ToolExecutor(
        graph_tools
    )

    # --------------------------------------------------------
    # Ollama
    # --------------------------------------------------------

    llm = OllamaClient(
        model="gemma:2b",
        base_url="http://localhost:11434",
    )

    # --------------------------------------------------------
    # Investigator
    # --------------------------------------------------------

    investigator = Investigator(
        llm_client=llm,
        tool_executor=tool_executor,
        max_tool_calls=3,
    )

    # --------------------------------------------------------
    # Run investigation
    # --------------------------------------------------------

    investigation = investigator.investigate(
        case
    )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FINAL LLM INVESTIGATION")
    print("=" * 70)

    print()
    print("Settlement:")
    print(
        investigation.settlement_id
    )

    print()
    print("Summary:")
    print(
        investigation.summary
    )

    print()
    print("Likely causes:")

    for cause in investigation.likely_causes:
        print(
            f"  • {cause}"
        )

    print()
    print("Supporting evidence:")

    for evidence in investigation.supporting_evidence:
        print(
            f"  • {evidence}"
        )

    print()
    print("Missing evidence:")

    for evidence in investigation.missing_evidence:
        print(
            f"  • {evidence}"
        )

    print()
    print("Recommended action:")
    print(
        investigation.recommended_action
    )

    print()
    print(
        f"Confidence: "
        f"{investigation.confidence:.0%}"
    )

    print()
    print(
        f"Graph tool calls: "
        f"{len(investigation.tool_calls)}"
    )

    print()
    print("=" * 70)
    print("LLM GRAPH INVESTIGATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
