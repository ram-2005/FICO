from __future__ import annotations

from typing import Any

from backend.app.graph.tools import FinancialGraphTools


class ToolExecutor:
    """
    Controlled execution layer between the LLM and the
    financial graph.

    The LLM can request read-only graph operations.
    It cannot directly access files, Python, or mutate
    the graph.
    """

    def __init__(self, graph_tools: FinancialGraphTools):
        self.graph_tools = graph_tools

        self.allowed_tools = {
            "get_event",
            "get_neighbors",
            "get_relationships",
            "trace_chain",
        }

    def execute(
        self,
        action: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        arguments = arguments or {}

        # ----------------------------------------------------
        # Security boundary
        # ----------------------------------------------------

        if action not in self.allowed_tools:
            return {
                "success": False,
                "error": f"Unknown or unauthorized tool: {action}",
            }

        # ----------------------------------------------------
        # Dispatch
        # ----------------------------------------------------

        if action == "get_event":

            return self.graph_tools.get_event(
                event_id=arguments.get("event_id")
            )

        if action == "get_neighbors":

            return self.graph_tools.get_neighbors(
                event_id=arguments.get("event_id")
            )

        if action == "get_relationships":

            return self.graph_tools.get_relationships(
                event_id=arguments.get("event_id")
            )

        if action == "trace_chain":

            max_depth = arguments.get(
                "max_depth",
                3,
            )

            # Prevent excessively large graph traversals.
            try:
                max_depth = int(max_depth)
            except (TypeError, ValueError):
                max_depth = 3

            max_depth = max(
                1,
                min(max_depth, 5),
            )

            return self.graph_tools.trace_chain(
                event_id=arguments.get("event_id"),
                max_depth=max_depth,
            )

        return {
            "success": False,
            "error": "Tool dispatch failed.",
        }

    def definitions(self) -> list[dict]:
        """
        Return the tools that may be exposed to the LLM.
        """

        return self.graph_tools.definitions()
