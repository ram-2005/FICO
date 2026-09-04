from __future__ import annotations

import networkx as nx


class FinancialGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_payment(self, payment_id, amount, timestamp):
        self.graph.add_node(
            payment_id,
            type="PAYMENT",
            amount=str(amount),
            timestamp=timestamp,
        )

    def add_settlement(self, settlement_id, amount, timestamp):
        self.graph.add_node(
            settlement_id,
            type="SETTLEMENT",
            amount=str(amount),
            timestamp=timestamp,
        )

    def add_bank_transaction(
        self,
        transaction_id,
        amount,
        timestamp,
    ):
        self.graph.add_node(
            transaction_id,
            type="BANK_TRANSACTION",
            amount=str(amount),
            timestamp=timestamp,
        )

    def link(self, source, target, relationship):
        self.graph.add_edge(
            source,
            target,
            relationship=relationship,
        )

    def summary(self):
        return {
            "nodes": self.graph.number_of_nodes(),
            "relationships": self.graph.number_of_edges(),
        }
