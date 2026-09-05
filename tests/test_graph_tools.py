from run_controller import (
    load_payments,
    load_settlements,
    load_bank_transactions,
    build_financial_graph,
)

from backend.app.graph.tools import FinancialGraphTools
from backend.app.intelligence.tool_executor import ToolExecutor


def main():

    print("=" * 70)
    print("GRAPH TOOL EXECUTOR TEST")
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

    graph = build_financial_graph(
        payments,
        settlements,
        bank_transactions,
    )

    # --------------------------------------------------------
    # Create tool interface
    # --------------------------------------------------------

    graph_tools = FinancialGraphTools(graph)

    executor = ToolExecutor(
        graph_tools
    )

    test_event = "SET_000103"

    # --------------------------------------------------------
    # TEST 1 — get_event
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("TEST 1: get_event")
    print("-" * 70)

    result = executor.execute(
        "get_event",
        {
            "event_id": test_event,
        },
    )

    print(result)

    # --------------------------------------------------------
    # TEST 2 — get_neighbors
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("TEST 2: get_neighbors")
    print("-" * 70)

    result = executor.execute(
        "get_neighbors",
        {
            "event_id": test_event,
        },
    )

    print(result)

    # --------------------------------------------------------
    # TEST 3 — get_relationships
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("TEST 3: get_relationships")
    print("-" * 70)

    result = executor.execute(
        "get_relationships",
        {
            "event_id": test_event,
        },
    )

    print(result)

    # --------------------------------------------------------
    # TEST 4 — trace_chain
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("TEST 4: trace_chain")
    print("-" * 70)

    result = executor.execute(
        "trace_chain",
        {
            "event_id": test_event,
            "max_depth": 2,
        },
    )

    print(result)

    # --------------------------------------------------------
    # TEST 5 — unauthorized tool
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("TEST 5: unauthorized tool")
    print("-" * 70)

    result = executor.execute(
        "delete_everything",
        {},
    )

    print(result)

    # --------------------------------------------------------
    # Tool definitions
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("AVAILABLE LLM TOOLS")
    print("-" * 70)

    for definition in executor.definitions():
        print(
            f"- {definition['name']}: "
            f"{definition['description']}"
        )

    print()
    print("=" * 70)
    print("GRAPH TOOL EXECUTOR TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
