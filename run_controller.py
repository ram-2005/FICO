from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

import networkx as nx


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data" / "raw"

PAYMENTS_FILE = DATA_DIR / "payments" / "payments.csv"
SETTLEMENTS_FILE = DATA_DIR / "settlements" / "settlements.csv"
BANK_FILE = DATA_DIR / "banking" / "bank_transactions.csv"


# ============================================================
# CORE MODELS
# ============================================================

@dataclass
class NormalizedObservation:
    observation_id: str
    source_type: str
    source_id: str
    timestamp: Optional[str]
    amount: Optional[Decimal]
    currency: Optional[str]
    status: Optional[str]
    raw: dict = field(default_factory=dict)


@dataclass
class FinancialEvent:
    event_id: str
    event_type: str
    source_id: str
    amount: Optional[Decimal]
    currency: Optional[str]
    timestamp: Optional[str]
    status: Optional[str]


@dataclass
class FinancialRelationship:
    relationship_id: str
    from_event: str
    to_event: str
    relationship_type: str
    confidence: float = 1.0


@dataclass
class ReconciliationResult:
    reconciliation_id: str
    settlement_id: str
    expected_amount: Decimal
    observed_amount: Optional[Decimal]
    variance: Decimal
    status: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class VerifiedFinancialState:
    state_id: str
    event_id: str
    state: str
    confidence: float
    reason: str


@dataclass
class ExceptionRecord:
    exception_id: str
    settlement_id: str
    exception_type: str
    severity: str
    expected: Optional[Decimal]
    observed: Optional[Decimal]
    variance: Optional[Decimal]
    evidence: list[str] = field(default_factory=list)


# ============================================================
# HELPERS
# ============================================================

def money(value) -> Optional[Decimal]:
    if value is None or value == "":
        return None

    return Decimal(str(value))


def decimal_str(value: Optional[Decimal]) -> str:
    if value is None:
        return "N/A"

    return f"₹{value:,.2f}"


# ============================================================
# LOADERS
# ============================================================

def load_csv(path: Path) -> list[dict]:
    print(f"Loading: {path}")

    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    return rows


def load_payments() -> list[NormalizedObservation]:
    rows = load_csv(PAYMENTS_FILE)

    observations = []

    for row in rows:
        observations.append(
            NormalizedObservation(
                observation_id=f"OBS_PAYMENT_{row['payment_id']}",
                source_type="PAYMENT",
                source_id=row["payment_id"],
                timestamp=row["payment_date"],
                amount=money(row["amount"]),
                currency=row["currency"],
                status=row["status"],
                raw=row,
            )
        )

    return observations


def load_settlements() -> list[NormalizedObservation]:
    rows = load_csv(SETTLEMENTS_FILE)

    observations = []

    for row in rows:
        observations.append(
            NormalizedObservation(
                observation_id=f"OBS_SETTLEMENT_{row['settlement_id']}",
                source_type="SETTLEMENT",
                source_id=row["settlement_id"],
                timestamp=row["settlement_date"],
                amount=money(row["net_settlement_amount"]),
                currency=row["currency"],
                status="SETTLED",
                raw=row,
            )
        )

    return observations


def load_bank_transactions() -> list[NormalizedObservation]:
    rows = load_csv(BANK_FILE)

    observations = []

    for row in rows:
        observations.append(
            NormalizedObservation(
                observation_id=f"OBS_BANK_{row['bank_transaction_id']}",
                source_type="BANK_TRANSACTION",
                source_id=row["bank_transaction_id"],
                timestamp=row["transaction_date"],
                amount=money(row["amount"]),
                currency=row["currency"],
                status=row["status"],
                raw=row,
            )
        )

    return observations


# ============================================================
# FINANCIAL GRAPH
# ============================================================

class FinancialGraph:

    def __init__(self):
        self.graph = nx.MultiDiGraph()

    def add_event(self, event: FinancialEvent):
        self.graph.add_node(
            event.event_id,
            event_type=event.event_type,
            source_id=event.source_id,
            amount=str(event.amount) if event.amount is not None else None,
            currency=event.currency,
            timestamp=event.timestamp,
            status=event.status,
        )

    def add_relationship(self, relationship: FinancialRelationship):
        self.graph.add_edge(
            relationship.from_event,
            relationship.to_event,
            relationship_type=relationship.relationship_type,
            confidence=relationship.confidence,
            relationship_id=relationship.relationship_id,
        )

    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def nodes_by_type(self, event_type: str) -> int:
        return sum(
            1
            for _, data in self.graph.nodes(data=True)
            if data.get("event_type") == event_type
        )

    def edges_by_type(self, relationship_type: str) -> int:
        return sum(
            1
            for _, _, data in self.graph.edges(data=True)
            if data.get("relationship_type") == relationship_type
        )


# ============================================================
# BUILD FINANCIAL GRAPH
# ============================================================

def build_financial_graph(
    payments: list[NormalizedObservation],
    settlements: list[NormalizedObservation],
    bank_transactions: list[NormalizedObservation],
) -> FinancialGraph:

    graph = FinancialGraph()

    print()
    print("=" * 70)
    print("BUILDING FINANCIAL GRAPH")
    print("=" * 70)

    # --------------------------------------------------------
    # Add PAYMENT nodes
    # --------------------------------------------------------

    for observation in payments:

        event = FinancialEvent(
            event_id=observation.source_id,
            event_type="PAYMENT",
            source_id=observation.source_id,
            amount=observation.amount,
            currency=observation.currency,
            timestamp=observation.timestamp,
            status=observation.status,
        )

        graph.add_event(event)

    print(f"Payment nodes added       : {len(payments):,}")

    # --------------------------------------------------------
    # Add SETTLEMENT nodes
    # --------------------------------------------------------

    for observation in settlements:

        event = FinancialEvent(
            event_id=observation.source_id,
            event_type="SETTLEMENT",
            source_id=observation.source_id,
            amount=observation.amount,
            currency=observation.currency,
            timestamp=observation.timestamp,
            status=observation.status,
        )

        graph.add_event(event)

    print(f"Settlement nodes added    : {len(settlements):,}")

    # --------------------------------------------------------
    # Add BANK nodes
    # --------------------------------------------------------

    for observation in bank_transactions:

        event = FinancialEvent(
            event_id=observation.source_id,
            event_type="BANK_TRANSACTION",
            source_id=observation.source_id,
            amount=observation.amount,
            currency=observation.currency,
            timestamp=observation.timestamp,
            status=observation.status,
        )

        graph.add_event(event)

    print(f"Bank transaction nodes    : {len(bank_transactions):,}")

    # --------------------------------------------------------
    # Settlement → Bank relationships
    #
    # Bank transaction contains reference_id = SET_xxxxxx
    # --------------------------------------------------------

    bank_relationships = 0

    settlement_ids = {
        s.source_id
        for s in settlements
    }

    for bank in bank_transactions:

        reference_id = bank.raw.get("reference_id")

        if reference_id in settlement_ids:

            relationship = FinancialRelationship(
                relationship_id=(
                    f"REL_{reference_id}_{bank.source_id}"
                ),
                from_event=reference_id,
                to_event=bank.source_id,
                relationship_type="SETTLEMENT_TO_BANK",
                confidence=1.0,
            )

            graph.add_relationship(relationship)

            bank_relationships += 1

    print(
        f"Settlement → Bank edges  : "
        f"{bank_relationships:,}"
    )

    # --------------------------------------------------------
    # Payment → Settlement relationships
    #
    # IMPORTANT:
    # The current dataset provides first_payment_id and
    # last_payment_id rather than an explicit payment list.
    #
    # For this MVP we use the payment ID range as a prototype
    # relationship heuristic.
    # --------------------------------------------------------

    payment_map = {
        p.source_id: p
        for p in payments
    }

    payment_relationships = 0

    for settlement in settlements:

        first_payment = settlement.raw.get(
            "first_payment_id"
        )

        last_payment = settlement.raw.get(
            "last_payment_id"
        )

        if not first_payment or not last_payment:
            continue

        try:
            first_num = int(
                first_payment.replace("PAY_", "")
            )

            last_num = int(
                last_payment.replace("PAY_", "")
            )

        except ValueError:
            continue

        if last_num < first_num:
            continue

        for number in range(first_num, last_num + 1):

            payment_id = f"PAY_{number:06d}"

            if payment_id not in payment_map:
                continue

            relationship = FinancialRelationship(
                relationship_id=(
                    f"REL_{payment_id}_"
                    f"{settlement.source_id}"
                ),
                from_event=payment_id,
                to_event=settlement.source_id,
                relationship_type="PAYMENT_TO_SETTLEMENT",
                confidence=0.5,
            )

            graph.add_relationship(relationship)

            payment_relationships += 1

    print(
        f"Payment → Settlement edges: "
        f"{payment_relationships:,}"
    )

    # --------------------------------------------------------
    # FINAL GRAPH STATISTICS
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("FINANCIAL GRAPH CREATED")
    print("-" * 70)

    print(
        f"Total graph nodes        : "
        f"{graph.node_count():,}"
    )

    print(
        f"Total graph edges        : "
        f"{graph.edge_count():,}"
    )

    print()
    print("NODE BREAKDOWN")

    print(
        f"  PAYMENT               : "
        f"{graph.nodes_by_type('PAYMENT'):,}"
    )

    print(
        f"  SETTLEMENT            : "
        f"{graph.nodes_by_type('SETTLEMENT'):,}"
    )

    print(
        f"  BANK_TRANSACTION      : "
        f"{graph.nodes_by_type('BANK_TRANSACTION'):,}"
    )

    print()
    print("EDGE BREAKDOWN")

    print(
        f"  PAYMENT → SETTLEMENT  : "
        f"{graph.edges_by_type('PAYMENT_TO_SETTLEMENT'):,}"
    )

    print(
        f"  SETTLEMENT → BANK     : "
        f"{graph.edges_by_type('SETTLEMENT_TO_BANK'):,}"
    )

    print("=" * 70)

    return graph


# ============================================================
# BANK LOOKUP
# ============================================================

def build_bank_reference_index(
    bank_transactions: list[NormalizedObservation],
):
    index = {}

    for bank in bank_transactions:

        reference_id = bank.raw.get("reference_id")

        if reference_id:
            index.setdefault(reference_id, []).append(bank)

    return index


# ============================================================
# RECONCILIATION
# ============================================================

def reconcile_settlement(
    settlement: NormalizedObservation,
    payments: list[NormalizedObservation],
    bank_index,
) -> ReconciliationResult:

    raw = settlement.raw

    settlement_id = settlement.source_id

    gross_amount = money(
        raw.get("gross_amount")
    ) or Decimal("0")

    refund_deductions = money(
        raw.get("refund_deductions")
    ) or Decimal("0")

    net_settlement_amount = money(
        raw.get("net_settlement_amount")
    ) or Decimal("0")

    # --------------------------------------------------------
    # Settlement internal arithmetic
    # --------------------------------------------------------

    calculated_net = (
        gross_amount - refund_deductions
    )

    arithmetic_variance = (
        net_settlement_amount - calculated_net
    )

    evidence = []

    if arithmetic_variance != Decimal("0"):

        evidence.append(
            "Settlement gross/refund/net arithmetic mismatch"
        )

    # --------------------------------------------------------
    # Bank observation
    # --------------------------------------------------------

    bank_rows = bank_index.get(
        settlement_id,
        []
    )

    observed_bank_amount = None

    if bank_rows:

        observed_bank_amount = sum(
            (
                b.amount or Decimal("0")
                for b in bank_rows
            ),
            Decimal("0"),
        )

        evidence.append(
            f"{len(bank_rows)} bank transaction(s) "
            f"reference this settlement"
        )

    else:

        evidence.append(
            "No bank transaction found for settlement"
        )

    # --------------------------------------------------------
    # Compare settlement with bank
    # --------------------------------------------------------

    if observed_bank_amount is None:

        variance = arithmetic_variance

        status = "PENDING"

    else:

        variance = (
            observed_bank_amount
            - net_settlement_amount
        )

        if (
            arithmetic_variance == Decimal("0")
            and variance == Decimal("0")
        ):
            status = "MATCHED"

        else:
            status = "EXCEPTION"

    return ReconciliationResult(
        reconciliation_id=f"REC_{settlement_id}",
        settlement_id=settlement_id,
        expected_amount=net_settlement_amount,
        observed_amount=observed_bank_amount,
        variance=variance,
        status=status,
        evidence=evidence,
    )


# ============================================================
# EXCEPTION CREATION
# ============================================================

def create_exception(
    result: ReconciliationResult,
) -> Optional[ExceptionRecord]:

    if result.status != "EXCEPTION":
        return None

    severity = "HIGH"

    if abs(result.variance) < Decimal("100"):
        severity = "LOW"

    elif abs(result.variance) < Decimal("10000"):
        severity = "MEDIUM"

    return ExceptionRecord(
        exception_id=f"EXC_{result.settlement_id}",
        settlement_id=result.settlement_id,
        exception_type="SETTLEMENT_BANK_MISMATCH",
        severity=severity,
        expected=result.expected_amount,
        observed=result.observed_amount,
        variance=result.variance,
        evidence=result.evidence,
    )


# ============================================================
# VERIFIED STATE
# ============================================================

def create_verified_state(
    result: ReconciliationResult,
) -> VerifiedFinancialState:

    if result.status == "MATCHED":

        state = "VERIFIED"
        confidence = 1.0
        reason = (
            "Settlement amount reconciles with "
            "bank transaction."
        )

    elif result.status == "PENDING":

        state = "PENDING"
        confidence = 0.5
        reason = (
            "Settlement exists but corresponding "
            "bank transaction is not yet observed."
        )

    else:

        state = "EXCEPTION"
        confidence = 0.0
        reason = (
            "Settlement could not be reconciled "
            "with observed bank evidence."
        )

    return VerifiedFinancialState(
        state_id=f"STATE_{result.settlement_id}",
        event_id=result.settlement_id,
        state=state,
        confidence=confidence,
        reason=reason,
    )


# ============================================================
# EXCEPTION REPORT
# ============================================================

def print_exception_report(
    exceptions: list[ExceptionRecord],
):

    print()
    print("=" * 70)
    print("EXCEPTION REPORT")
    print("=" * 70)

    if not exceptions:

        print("No exceptions detected.")
        return

    print(
        f"Exceptions detected: "
        f"{len(exceptions):,}"
    )

    print()

    for exception in exceptions[:10]:

        print(
            f"[{exception.severity}] "
            f"{exception.settlement_id}"
        )

        print(
            f"  Expected : "
            f"{decimal_str(exception.expected)}"
        )

        print(
            f"  Observed : "
            f"{decimal_str(exception.observed)}"
        )

        print(
            f"  Variance : "
            f"{decimal_str(exception.variance)}"
        )

        for evidence in exception.evidence:

            print(
                f"  Evidence : {evidence}"
            )

        print()


# ============================================================
# MAIN CONTROLLER
# ============================================================

def main():

    print()
    print("=" * 70)
    print("AI FINANCE CONTROLLER — MVP")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. INGESTION
    # --------------------------------------------------------

    print()
    print("STEP 1 — INGESTION")

    payments = load_payments()
    settlements = load_settlements()
    bank_transactions = load_bank_transactions()

    print()
    print(
        f"Payments loaded           : "
        f"{len(payments):,}"
    )

    print(
        f"Settlements loaded        : "
        f"{len(settlements):,}"
    )

    print(
        f"Bank transactions loaded  : "
        f"{len(bank_transactions):,}"
    )

    # --------------------------------------------------------
    # 2. GRAPH
    # --------------------------------------------------------

    print()
    print("STEP 2 — FINANCIAL GRAPH")

    financial_graph = build_financial_graph(
        payments,
        settlements,
        bank_transactions,
    )

    # --------------------------------------------------------
    # 3. BANK INDEX
    # --------------------------------------------------------

    print()
    print("STEP 3 — BUILDING BANK INDEX")

    bank_index = build_bank_reference_index(
        bank_transactions
    )

    print(
        f"Bank references indexed   : "
        f"{len(bank_index):,}"
    )

    # --------------------------------------------------------
    # 4. RECONCILIATION
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("STEP 4 — RECONCILIATION")
    print("=" * 70)

    results = []
    exceptions = []
    verified_states = []

    for settlement in settlements:

        result = reconcile_settlement(
            settlement,
            payments,
            bank_index,
        )

        results.append(result)

        exception = create_exception(result)

        if exception:
            exceptions.append(exception)

        state = create_verified_state(result)

        verified_states.append(state)

    # --------------------------------------------------------
    # 5. METRICS
    # --------------------------------------------------------

    matched = sum(
        1
        for r in results
        if r.status == "MATCHED"
    )

    pending = sum(
        1
        for r in results
        if r.status == "PENDING"
    )

    exception_count = sum(
        1
        for r in results
        if r.status == "EXCEPTION"
    )

    total = len(results)

    match_rate = (
        matched / total * 100
        if total
        else 0
    )

    total_variance = sum(
        (
            abs(r.variance)
            for r in results
            if r.status == "EXCEPTION"
        ),
        Decimal("0"),
    )

    # --------------------------------------------------------
    # 6. FINAL CONTROLLER OUTPUT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CONTROLLER RESULT")
    print("=" * 70)

    print(
        f"Settlements analyzed     : "
        f"{total:,}"
    )

    print(
        f"Matched                  : "
        f"{matched:,}"
    )

    print(
        f"Pending                  : "
        f"{pending:,}"
    )

    print(
        f"Exceptions               : "
        f"{exception_count:,}"
    )

    print(
        f"Match rate               : "
        f"{match_rate:.2f}%"
    )

    print(
        f"Exception variance       : "
        f"{decimal_str(total_variance)}"
    )

    # --------------------------------------------------------
    # 7. GRAPH SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("GRAPH SUMMARY")
    print("=" * 70)

    print(
        f"Nodes                    : "
        f"{financial_graph.node_count():,}"
    )

    print(
        f"Edges                    : "
        f"{financial_graph.edge_count():,}"
    )

    print(
        f"Payment nodes            : "
        f"{financial_graph.nodes_by_type('PAYMENT'):,}"
    )

    print(
        f"Settlement nodes         : "
        f"{financial_graph.nodes_by_type('SETTLEMENT'):,}"
    )

    print(
        f"Bank transaction nodes   : "
        f"{financial_graph.nodes_by_type('BANK_TRANSACTION'):,}"
    )

    print(
        f"Payment → Settlement     : "
        f"{financial_graph.edges_by_type('PAYMENT_TO_SETTLEMENT'):,}"
    )

    print(
        f"Settlement → Bank        : "
        f"{financial_graph.edges_by_type('SETTLEMENT_TO_BANK'):,}"
    )

    # --------------------------------------------------------
    # 8. EXCEPTIONS
    # --------------------------------------------------------

    print_exception_report(exceptions)

    # --------------------------------------------------------
    # 9. SAMPLE VERIFIED STATES
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("VERIFIED FINANCIAL STATE")
    print("=" * 70)

    for state in verified_states[:10]:

        print(
            f"{state.event_id:<15} "
            f"{state.state:<10} "
            f"confidence={state.confidence:.2f}"
        )

    print()
    print("=" * 70)
    print("CONTROLLER RUN COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
