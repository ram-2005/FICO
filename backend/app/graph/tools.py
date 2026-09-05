from __future__ import annotations

from typing import Any, Dict, List


class FinancialGraphTools:
    """
    Read-only tools for inspecting the financial graph.

    IMPORTANT:
    These tools intentionally return bounded graph evidence.
    The underlying graph may contain millions of relationships,
    but an LLM should never receive the entire neighborhood.
    """

    def __init__(self, graph):
        self.graph = graph

    # ------------------------------------------------------------------
    # Event lookup
    # ------------------------------------------------------------------

    def get_event(self, event_id: str) -> Dict[str, Any]:
        """
        Return a single graph event/node.
        """
        if event_id not in self.graph:
            return {
                "event_id": event_id,
                "found": False,
            }

        return {
            "event_id": event_id,
            "found": True,
            "attributes": dict(self.graph.nodes[event_id]),
        }

    # ------------------------------------------------------------------
    # Neighbor lookup
    # ------------------------------------------------------------------

    def get_neighbors(
        self,
        event_id: str,
        max_items: int = 10,
    ) -> Dict[str, Any]:
        """
        Return a bounded summary of the event's neighborhood.

        The graph itself may contain millions of edges. We therefore
        expose only counts and a small sample to the LLM.
        """

        if event_id not in self.graph:
            return {
                "event_id": event_id,
                "found": False,
                "neighbor_count": 0,
                "neighbors": [],
            }

        incoming = []
        outgoing = []

        # --------------------------------------------------------------
        # Incoming relationships
        # --------------------------------------------------------------

        for source, _, data in self.graph.in_edges(
            event_id,
            data=True,
        ):
            incoming.append(
                {
                    "event_id": source,
                    "relationship": data.get(
                        "relationship",
                        data.get("type"),
                    ),
                    "confidence": data.get("confidence"),
                }
            )

        # --------------------------------------------------------------
        # Outgoing relationships
        # --------------------------------------------------------------

        for _, target, data in self.graph.out_edges(
            event_id,
            data=True,
        ):
            outgoing.append(
                {
                    "event_id": target,
                    "relationship": data.get(
                        "relationship",
                        data.get("type"),
                    ),
                    "confidence": data.get("confidence"),
                }
            )

        # --------------------------------------------------------------
        # Bound what is returned to the LLM
        # --------------------------------------------------------------

        incoming_sample = incoming[:max_items]
        outgoing_sample = outgoing[:max_items]

        return {
            "event_id": event_id,
            "found": True,

            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
            "neighbor_count": len(incoming) + len(outgoing),

            "incoming_sample": incoming_sample,
            "outgoing_sample": outgoing_sample,
        }

    # ------------------------------------------------------------------
    # Relationship lookup
    # ------------------------------------------------------------------

    def get_relationships(
        self,
        event_id: str,
        max_items: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Return a bounded list of relationships for an event.
        """

        if event_id not in self.graph:
            return []

        relationships = []

        for source, target, data in self.graph.in_edges(
            event_id,
            data=True,
        ):
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": data.get(
                        "relationship",
                        data.get("type"),
                    ),
                    "confidence": data.get("confidence"),
                }
            )

            if len(relationships) >= max_items:
                return relationships

        for source, target, data in self.graph.out_edges(
            event_id,
            data=True,
        ):
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": data.get(
                        "relationship",
                        data.get("type"),
                    ),
                    "confidence": data.get("confidence"),
                }

            )

            if len(relationships) >= max_items:
                break

        return relationships

    # ------------------------------------------------------------------
    # Chain tracing
    # ------------------------------------------------------------------

    def trace_chain(
        self,
        event_id: str,
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Trace a bounded graph chain.

        This is deliberately conservative so a large financial graph
        cannot accidentally create an enormous LLM prompt.
        """

        if event_id not in self.graph:
            return []

        max_depth = min(max_depth, 5)

        visited = {event_id}
        frontier = [event_id]
        chain = []

        for depth in range(max_depth):
            next_frontier = []

            for current in frontier:
                if current not in self.graph:
                    continue

                # Limit expansion per node.
                edges_seen = 0

                for source, target, data in self.graph.out_edges(
                    current,
                    data=True,
                ):
                    if edges_seen >= 10:
                        break

                    if target in visited:
                        continue

                    visited.add(target)

                    chain.append(
                        {
                            "depth": depth + 1,
                            "source": source,
                            "target": target,
                            "relationship": data.get(
                                "relationship",
                                data.get("type"),
                            ),
                            "confidence": data.get("confidence"),
                        }
                    )

                    next_frontier.append(target)
                    edges_seen += 1

                # Also inspect a small number of incoming edges.
                edges_seen = 0

                for source, target, data in self.graph.in_edges(
                    current,
                    data=True,
                ):
                    if edges_seen >= 10:
                        break

                    if source in visited:
                        continue

                    visited.add(source)

                    chain.append(
                        {
                            "depth": depth + 1,
                            "source": source,
                            "target": target,
                            "relationship": data.get(
                                "relationship",
                                data.get("type"),
                            ),
                            "confidence": data.get("confidence"),
                        }
                    )

                    next_frontier.append(source)
                    edges_seen += 1

            frontier = next_frontier

            if not frontier:
                break

        return chain
