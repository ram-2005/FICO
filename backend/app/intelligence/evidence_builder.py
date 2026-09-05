from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any
import json


# ============================================================
# EVIDENCE MODEL
# ============================================================

@dataclass
class Evidence:
    evidence_id: str
    evidence_type: str
    source_id: str
    description: str
    value: str | None = None


# ============================================================
# INVESTIGATION CASE
# ============================================================

@dataclass
class InvestigationCase:
    settlement_id: str

    expected_amount: str
    observed_amount: str | None
    variance: str

    reconciliation_status: str

    evidence: list[Evidence]

    graph_relationships: list[dict[str, Any]]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# HELPERS
# ============================================================

def decimal_to_string(
    value: Decimal | None,
) -> str | None:

    if value is None:
        return None

    return f"{value:.2f}"


# ============================================================
# BUILD INVESTIGATION CASE
# ============================================================

def build_investigation_case(
    settlement,
    reconciliation_result,
    bank_transactions,
    financial_graph,
) -> InvestigationCase:

    settlement_id = settlement.source_id

    evidence: list[Evidence] = []

    # --------------------------------------------------------
    # Settlement evidence
    # --------------------------------------------------------

    raw = settlement.raw

    evidence.append(
        Evidence(
            evidence_id=f"EVD_{settlement_id}_SETTLEMENT",
            evidence_type="SETTLEMENT",
            source_id=settlement_id,
            description=(
                "Gateway settlement record containing "
                "gross amount, refund deductions and "
                "net settlement amount."
            ),
            value=decimal_to_string(
                reconciliation_result.expected_amount
            ),
        )
    )

    # --------------------------------------------------------
    # Bank evidence
    # --------------------------------------------------------

    related_bank_transactions = []

    for bank in bank_transactions:

        if bank.raw.get("reference_id") == settlement_id:
            related_bank_transactions.append(bank)

    for bank in related_bank_transactions:

        evidence.append(
            Evidence(
                evidence_id=(
                    f"EVD_{settlement_id}_"
                    f"{bank.source_id}"
                ),
                evidence_type="BANK_TRANSACTION",
                source_id=bank.source_id,
                description=(
                    "Bank transaction referencing "
                    "this settlement."
                ),
                value=decimal_to_string(
                    bank.amount
                ),
            )
        )

    # --------------------------------------------------------
    # Reconciliation evidence
    # --------------------------------------------------------

    evidence.append(
        Evidence(
            evidence_id=(
                f"EVD_{settlement_id}_"
                f"RECONCILIATION"
            ),
            evidence_type="RECONCILIATION",
            source_id=(
                reconciliation_result.reconciliation_id
            ),
            description=(
                "Deterministic reconciliation result "
                "comparing expected settlement value "
                "with observed bank value."
            ),
            value=decimal_to_string(
                reconciliation_result.variance
            ),
        )
    )

    # --------------------------------------------------------
    # Existing reconciliation evidence
    # --------------------------------------------------------

    for index, item in enumerate(
        reconciliation_result.evidence,
        start=1,
    ):

        evidence.append(
            Evidence(
                evidence_id=(
                    f"EVD_{settlement_id}_"
                    f"DETAIL_{index}"
                ),
                evidence_type="RECONCILIATION_DETAIL",
                source_id=settlement_id,
                description=item,
            )
        )

    # --------------------------------------------------------
    # Graph relationships
    # --------------------------------------------------------

    graph_relationships = []

    graph = financial_graph.graph

    # Incoming relationships to settlement
    for source, target, data in graph.in_edges(
        settlement_id,
        data=True,
    ):

        graph_relationships.append(
            {
                "from": source,
                "to": target,
                "relationship_type": data.get(
                    "relationship_type"
                ),
                "confidence": data.get(
                    "confidence"
                ),
            }
        )

    # Outgoing relationships from settlement
    for source, target, data in graph.out_edges(
        settlement_id,
        data=True,
    ):

        graph_relationships.append(
            {
                "from": source,
                "to": target,
                "relationship_type": data.get(
                    "relationship_type"
                ),
                "confidence": data.get(
                    "confidence"
                ),
            }
        )

    # --------------------------------------------------------
    # Final investigation case
    # --------------------------------------------------------

    return InvestigationCase(
        settlement_id=settlement_id,

        expected_amount=decimal_to_string(
            reconciliation_result.expected_amount
        ),

        observed_amount=decimal_to_string(
            reconciliation_result.observed_amount
        ),

        variance=decimal_to_string(
            reconciliation_result.variance
        ),

        reconciliation_status=(
            reconciliation_result.status
        ),

        evidence=evidence,

        graph_relationships=graph_relationships,
    )
