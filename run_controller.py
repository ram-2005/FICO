from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

import networkx as nx

from backend.app.graph.tools import FinancialGraphTools
from backend.app.intelligence.evidence_builder import (
    build_investigation_case,
)
from backend.app.intelligence.investigator import (
    Investigator,
)
from backend.app.intelligence.llm_client import (
    OllamaClient,
)
from backend.app.intelligence.tool_executor import (
    ToolExecutor,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data" / "raw"

PAYMENTS_FILE = (
    DATA_DIR / "payments" / "payments.csv"
)

SETTLEMENTS_FILE = (
    DATA_DIR / "settlements" / "settlements.csv"
)

BANK_FILE = (
    DATA_DIR / "banking" / "bank_transactions.csv"
)

OLLAMA_MODEL = "qwen3:4b"
OLLAMA_URL = "http://localhost:11434"

# Investigate only one exception for the demo.
DEMO_EXCEPTION_LIMIT = 1


# ============================================================
# TERMINAL UI HELPERS
# ============================================================

WIDTH = 70


def banner(title: str) -> None:
    print()
    print("=" * WIDTH)
    print(title.center(WIDTH))
    print("=" * WIDTH)


def section(title: str) -> None:
    print()
    print("-" * WIDTH)
    print(title)
    print("-" * WIDTH)


def metric(
    label: str,
    value,
) -> None:
    print(
        f"{label:<30} {value}"
    )


def decimal_str(
    value: Optional[Decimal],
) -> str:

    if value is None:
        return "N/A"

    return f"₹{value:,.2f}"


def status_symbol(
    status: str,
) -> str:

    if status == "MATCHED":
        return "✓"

    if status == "PENDING":
        return "○"

    if status == "EXCEPTION":
        return "⚠"

    return "•"


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
    evidence: list[str] = field(
        default_factory=list
    )


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
    evidence: list[str] = field(
        default_factory=list
    )


# ============================================================
# MONEY
# ============================================================

def money(
    value,
) -> Optional[Decimal]:

    if value is None or value == "":
        return None

    return Decimal(str(value))


# ============================================================
# CSV LOADING
# ============================================================

def load_csv(
    path: Path,
) -> list[dict]:

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return list(
            csv.DictReader(file)
        )


# ============================================================
# PAYMENT LOADER
# ============================================================

def load_payments() -> list[
    NormalizedObservation
]:

    rows = load_csv(
        PAYMENTS_FILE
    )

    observations = []

    for row in rows:

        observations.append(
            NormalizedObservation(
                observation_id=(
                    f"OBS_PAYMENT_"
                    f"{row['payment_id']}"
                ),
                source_type="PAYMENT",
                source_id=row["payment_id"],
                timestamp=row["payment_date"],
                amount=money(
                    row["amount"]
                ),
                currency=row["currency"],
                status=row["status"],
                raw=row,
            )
        )

    return observations


# ============================================================
# SETTLEMENT LOADER
# ============================================================

def load_settlements() -> list[
    NormalizedObservation
]:

    rows = load_csv(
        SETTLEMENTS_FILE
    )

    observations = []

    for row in rows:

        observations.append(
            NormalizedObservation(
                observation_id=(
                    f"OBS_SETTLEMENT_"
                    f"{row['settlement_id']}"
                ),
                source_type="SETTLEMENT",
                source_id=row["settlement_id"],
                timestamp=row["settlement_date"],
                amount=money(
                    row[
                        "net_settlement_amount"
                    ]
                ),
                currency=row["currency"],
                status="SETTLED",
                raw=row,
            )
        )

    return observations


# ============================================================
# BANK LOADER
# ============================================================

def load_bank_transactions() -> list[
    NormalizedObservation
]:

    rows = load_csv(
        BANK_FILE
    )

    observations = []

    for row in rows:

        observations.append(
            NormalizedObservation(
                observation_id=(
                    f"OBS_BANK_"
                    f"{row['bank_transaction_id']}"
                ),
                source_type="BANK_TRANSACTION",
                source_id=(
                    row[
                        "bank_transaction_id"
                    ]
                ),
                timestamp=(
                    row[
                        "transaction_date"
                    ]
                ),
                amount=money(
                    row["amount"]
                ),
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

    def add_event(
        self,
        event: FinancialEvent,
    ):

        self.graph.add_node(
            event.event_id,
            event_type=event.event_type,
            source_id=event.source_id,
            amount=(
                str(event.amount)
                if event.amount is not None
                else None
            ),
            currency=event.currency,
            timestamp=event.timestamp,
            status=event.status,
        )

    def add_relationship(
        self,
        relationship: FinancialRelationship,
    ):

        self.graph.add_edge(
            relationship.from_event,
            relationship.to_event,
            relationship_type=(
                relationship.relationship_type
            ),
            confidence=(
                relationship.confidence
            ),
            relationship_id=(
                relationship.relationship_id
            ),
        )

    def node_count(self) -> int:

        return self.graph.number_of_nodes()

    def edge_count(self) -> int:

        return self.graph.number_of_edges()

    def nodes_by_type(
        self,
        event_type: str,
    ) -> int:

        return sum(
            1
            for _, data
            in self.graph.nodes(
                data=True
            )
            if data.get(
                "event_type"
            ) == event_type
        )

    def edges_by_type(
        self,
        relationship_type: str,
    ) -> int:

        return sum(
            1
            for _, _, data
            in self.graph.edges(
                data=True
            )
            if data.get(
                "relationship_type"
            ) == relationship_type
        )


# ============================================================
# BUILD FINANCIAL GRAPH
# ============================================================

def build_financial_graph(
    payments,
    settlements,
    bank_transactions,
) -> FinancialGraph:

    graph = FinancialGraph()

    # --------------------------------------------------------
    # PAYMENT NODES
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

    # --------------------------------------------------------
    # SETTLEMENT NODES
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

    # --------------------------------------------------------
    # BANK NODES
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

    # --------------------------------------------------------
    # SETTLEMENT → BANK
    # --------------------------------------------------------

    settlement_ids = {
        settlement.source_id
        for settlement in settlements
    }

    bank_relationships = 0

    for bank in bank_transactions:

        reference_id = bank.raw.get(
            "reference_id"
        )

        if reference_id in settlement_ids:

            relationship = (
                FinancialRelationship(
                    relationship_id=(
                        f"REL_"
                        f"{reference_id}_"
                        f"{bank.source_id}"
                    ),
                    from_event=reference_id,
                    to_event=bank.source_id,
                    relationship_type=(
                        "SETTLEMENT_TO_BANK"
                    ),
                    confidence=1.0,
                )
            )

            graph.add_relationship(
                relationship
            )

            bank_relationships += 1

    # --------------------------------------------------------
    # PAYMENT → SETTLEMENT
    #
    # IMPORTANT:
    # This remains the existing MVP heuristic.
    # It is intentionally not presented as verified
    # accounting truth.
    # --------------------------------------------------------

    payment_map = {
        payment.source_id: payment
        for payment in payments
    }

    payment_relationships = 0

    for settlement in settlements:

        first_payment = settlement.raw.get(
            "first_payment_id"
        )

        last_payment = settlement.raw.get(
            "last_payment_id"
        )

        if (
            not first_payment
            or not last_payment
        ):
            continue

        try:

            first_number = int(
                first_payment.replace(
                    "PAY_",
                    "",
                )
            )

            last_number = int(
                last_payment.replace(
                    "PAY_",
                    "",
                )
            )

        except ValueError:

            continue

        if last_number < first_number:
            continue

        for number in range(
            first_number,
            last_number + 1,
        ):

            payment_id = (
                f"PAY_{number:06d}"
            )

            if payment_id not in payment_map:
                continue

            relationship = (
                FinancialRelationship(
                    relationship_id=(
                        f"REL_"
                        f"{payment_id}_"
                        f"{settlement.source_id}"
                    ),
                    from_event=payment_id,
                    to_event=settlement.source_id,
                    relationship_type=(
                        "PAYMENT_TO_SETTLEMENT"
                    ),
                    confidence=0.5,
                )
            )

            graph.add_relationship(
                relationship
            )

            payment_relationships += 1

    return graph


# ============================================================
# BANK INDEX
# ============================================================

def build_bank_reference_index(
    bank_transactions,
):

    index = {}

    for bank in bank_transactions:

        reference_id = bank.raw.get(
            "reference_id"
        )

        if reference_id:

            index.setdefault(
                reference_id,
                [],
            ).append(bank)

    return index


# ============================================================
# RECONCILIATION
# ============================================================

def reconcile_settlement(
    settlement,
    bank_index,
) -> ReconciliationResult:

    raw = settlement.raw

    settlement_id = (
        settlement.source_id
    )

    gross_amount = (
        money(
            raw.get(
                "gross_amount"
            )
        )
        or Decimal("0")
    )

    refund_deductions = (
        money(
            raw.get(
                "refund_deductions"
            )
        )
        or Decimal("0")
    )

    net_settlement_amount = (
        money(
            raw.get(
                "net_settlement_amount"
            )
        )
        or Decimal("0")
    )

    calculated_net = (
        gross_amount
        - refund_deductions
    )

    arithmetic_variance = (
        net_settlement_amount
        - calculated_net
    )

    evidence = []

    if arithmetic_variance != Decimal("0"):

        evidence.append(
            "Settlement gross/refund/net "
            "arithmetic mismatch"
        )

    bank_rows = bank_index.get(
        settlement_id,
        [],
    )

    observed_bank_amount = None

    if bank_rows:

        observed_bank_amount = sum(
            (
                bank.amount
                or Decimal("0")
                for bank in bank_rows
            ),
            Decimal("0"),
        )

        evidence.append(
            f"{len(bank_rows)} bank transaction(s) "
            f"reference this settlement"
        )

    else:

        evidence.append(
            "No bank transaction found "
            "for settlement"
        )

    if observed_bank_amount is None:

        variance = arithmetic_variance

        status = "PENDING"

    else:

        variance = (
            observed_bank_amount
            - net_settlement_amount
        )

        if (
            arithmetic_variance
            == Decimal("0")
            and variance
            == Decimal("0")
        ):

            status = "MATCHED"

        else:

            status = "EXCEPTION"

    return ReconciliationResult(
        reconciliation_id=(
            f"REC_{settlement_id}"
        ),
        settlement_id=settlement_id,
        expected_amount=(
            net_settlement_amount
        ),
        observed_amount=(
            observed_bank_amount
        ),
        variance=variance,
        status=status,
        evidence=evidence,
    )


# ============================================================
# EXCEPTION
# ============================================================

def create_exception(
    result: ReconciliationResult,
) -> Optional[ExceptionRecord]:

    if result.status != "EXCEPTION":
        return None

    absolute_variance = abs(
        result.variance
    )

    if absolute_variance < Decimal("100"):

        severity = "LOW"

    elif absolute_variance < Decimal("10000"):

        severity = "MEDIUM"

    else:

        severity = "HIGH"

    return ExceptionRecord(
        exception_id=(
            f"EXC_{result.settlement_id}"
        ),
        settlement_id=(
            result.settlement_id
        ),
        exception_type=(
            "SETTLEMENT_BANK_MISMATCH"
        ),
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
            "Settlement amount reconciles "
            "with bank transaction."
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
        state_id=(
            f"STATE_{result.settlement_id}"
        ),
        event_id=(
            result.settlement_id
        ),
        state=state,
        confidence=confidence,
        reason=reason,
    )


# ============================================================
# AI INVESTIGATION
# ============================================================

def run_ai_investigation(
    settlement,
    result,
    bank_transactions,
    financial_graph,
    investigator,
):

    case = build_investigation_case(
        settlement=settlement,
        reconciliation_result=result,
        bank_transactions=bank_transactions,
        financial_graph=financial_graph,
    )

    print()
    print(
        "Building investigation evidence..."
    )

    print(
        f"Evidence items          : "
        f"{len(case.evidence)}"
    )

    print(
        f"Graph relationships     : "
        f"{len(case.graph_relationships)}"
    )

    print()
    print(
        f"Running {OLLAMA_MODEL} "
        "investigator..."
    )

    investigation = (
        investigator.investigate(
            case
        )
    )

    return investigation


# ============================================================
# PRINT AI RESULT
# ============================================================

def print_ai_result(
    investigation,
):

    banner(
        "AI INVESTIGATION"
    )

    print(
        f"Settlement: "
        f"{investigation.settlement_id}"
    )

    section(
        "AI SUMMARY"
    )

    print(
        investigation.summary
    )

    section(
        "LIKELY CAUSES"
    )

    if investigation.likely_causes:

        for cause in (
            investigation.likely_causes
        ):

            print(
                f"• {cause}"
            )

    else:

        print(
            "• No evidence-based cause established."
        )

    section(
        "SUPPORTING EVIDENCE"
    )

    if investigation.supporting_evidence:

        for evidence in (
            investigation.supporting_evidence
        ):

            print(
                f"• {evidence}"
            )

    else:

        print(
            "• No supporting evidence returned."
        )

    section(
        "MISSING EVIDENCE"
    )

    if investigation.missing_evidence:

        for evidence in (
            investigation.missing_evidence
        ):

            print(
                f"• {evidence}"
            )

    else:

        print(
            "• No missing evidence reported."
        )

    section(
        "RECOMMENDED ACTION"
    )

    print(
        investigation.recommended_action
    )

    section(
        "AI CONFIDENCE"
    )

    print(
        f"{investigation.confidence:.0%}"
    )

    section(
        "GRAPH TOOL USAGE"
    )

    print(
        f"{len(investigation.tool_calls)} "
        f"graph tool call(s)"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # HEADER
    # ========================================================

    banner(
        "AI FINANCE CONTROLLER"
    )

    print(
        "Deterministic financial reconciliation "
        "+ graph-based investigation + local AI"
    )

    # ========================================================
    # AI INITIALIZATION
    # ========================================================

    section(
        "INITIALIZING AI"
    )

    print(
        f"Provider                 : Ollama"
    )

    print(
        f"Model                    : {OLLAMA_MODEL}"
    )

    print(
        f"Endpoint                 : {OLLAMA_URL}"
    )

    llm_client = OllamaClient(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_URL,
    )

    # ========================================================
    # DATA INGESTION
    # ========================================================

    banner(
        "STEP 1 — FINANCIAL DATA INGESTION"
    )

    print(
        "Loading financial observations..."
    )

    payments = load_payments()

    settlements = load_settlements()

    bank_transactions = (
        load_bank_transactions()
    )

    print()

    metric(
        "Payments",
        f"{len(payments):,}",
    )

    metric(
        "Settlements",
        f"{len(settlements):,}",
    )

    metric(
        "Bank transactions",
        f"{len(bank_transactions):,}",
    )

    # ========================================================
    # GRAPH
    # ========================================================

    banner(
        "STEP 2 — FINANCIAL RELATIONSHIP GRAPH"
    )

    print(
        "Constructing NetworkX financial graph..."
    )

    financial_graph = (
        build_financial_graph(
            payments,
            settlements,
            bank_transactions,
        )
    )

    section(
        "GRAPH METRICS"
    )

    metric(
        "Total nodes",
        f"{financial_graph.node_count():,}",
    )

    metric(
        "Total relationships",
        f"{financial_graph.edge_count():,}",
    )

    metric(
        "Payment nodes",
        f"{financial_graph.nodes_by_type('PAYMENT'):,}",
    )

    metric(
        "Settlement nodes",
        f"{financial_graph.nodes_by_type('SETTLEMENT'):,}",
    )

    metric(
        "Bank transaction nodes",
        f"{financial_graph.nodes_by_type('BANK_TRANSACTION'):,}",
    )

    metric(
        "Payment → Settlement",
        f"{financial_graph.edges_by_type('PAYMENT_TO_SETTLEMENT'):,}",
    )

    metric(
        "Settlement → Bank",
        f"{financial_graph.edges_by_type('SETTLEMENT_TO_BANK'):,}",
    )

    print()
    print(
        "✓ Financial relationship graph ready"
    )

    # ========================================================
    # GRAPH TOOLS
    # ========================================================

    section(
        "GRAPH INVESTIGATION TOOLS"
    )

    graph_tools = FinancialGraphTools(
        financial_graph.graph
    )

    tool_executor = ToolExecutor(
        graph_tools
    )

    investigator = Investigator(
        llm_client=llm_client,
        tool_executor=tool_executor,
        max_tool_calls=3,
    )

    print(
        "✓ Graph tools initialized"
    )

    print(
        "✓ Tool executor initialized"
    )

    print(
        "✓ AI investigator initialized"
    )

    # ========================================================
    # BANK INDEX
    # ========================================================

    banner(
        "STEP 3 — BANK REFERENCE INDEX"
    )

    bank_index = (
        build_bank_reference_index(
            bank_transactions
        )
    )

    metric(
        "Indexed bank references",
        f"{len(bank_index):,}",
    )

    # ========================================================
    # RECONCILIATION
    # ========================================================

    banner(
        "STEP 4 — DETERMINISTIC RECONCILIATION"
    )

    print(
        "Reconciling settlements against "
        "recorded bank transactions..."
    )

    results = []

    exceptions = []

    verified_states = []

    first_exception_context = None

    for settlement in settlements:

        result = reconcile_settlement(
            settlement,
            bank_index,
        )

        results.append(result)

        exception = create_exception(
            result
        )

        if exception:

            exceptions.append(
                exception
            )

            if (
                first_exception_context
                is None
            ):

                first_exception_context = (
                    settlement,
                    result,
                )

        state = create_verified_state(
            result
        )

        verified_states.append(
            state
        )

    # ========================================================
    # RECONCILIATION METRICS
    # ========================================================

    matched = sum(
        1
        for result in results
        if result.status == "MATCHED"
    )

    pending = sum(
        1
        for result in results
        if result.status == "PENDING"
    )

    exception_count = sum(
        1
        for result in results
        if result.status == "EXCEPTION"
    )

    total = len(results)

    match_rate = (
        matched / total * 100
        if total
        else 0
    )

    total_variance = sum(
        (
            abs(result.variance)
            for result in results
            if result.status == "EXCEPTION"
        ),
        Decimal("0"),
    )

    section(
        "RECONCILIATION RESULTS"
    )

    metric(
        "Settlements analyzed",
        f"{total:,}",
    )

    metric(
        "Matched",
        f"{matched:,}",
    )

    metric(
        "Pending",
        f"{pending:,}",
    )

    metric(
        "Exceptions",
        f"{exception_count:,}",
    )

    metric(
        "Match rate",
        f"{match_rate:.2f}%",
    )

    metric(
        "Exception variance",
        decimal_str(
            total_variance
        ),
    )

    # ========================================================
    # EXCEPTION PREVIEW
    # ========================================================

    banner(
        "STEP 5 — EXCEPTION DETECTION"
    )

    if not exceptions:

        print(
            "✓ No reconciliation exceptions detected."
        )

    else:

        print(
            f"⚠ {len(exceptions):,} "
            "exception(s) detected."
        )

        print()

        for exception in exceptions[:5]:

            print(
                f"{status_symbol('EXCEPTION')} "
                f"{exception.settlement_id}"
            )

            print(
                f"  Severity : "
                f"{exception.severity}"
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

            for evidence in (
                exception.evidence
            ):

                print(
                    f"  Evidence : "
                    f"{evidence}"
                )

            print()

    # ========================================================
    # AI INVESTIGATION
    # ========================================================

    investigation = None

    if first_exception_context:

        settlement, result = (
            first_exception_context
        )

        banner(
            "STEP 6 — AI EXCEPTION INVESTIGATION"
        )

        print(
            f"Target settlement: "
            f"{settlement.source_id}"
        )

        print()
        print(
            "Authoritative financial facts:"
        )

        metric(
            "Expected amount",
            decimal_str(
                result.expected_amount
            ),
        )

        metric(
            "Observed amount",
            decimal_str(
                result.observed_amount
            ),
        )

        metric(
            "Variance",
            decimal_str(
                result.variance
            ),
        )

        metric(
            "Reconciliation status",
            result.status,
        )

        try:

            investigation = (
                run_ai_investigation(
                    settlement=settlement,
                    result=result,
                    bank_transactions=(
                        bank_transactions
                    ),
                    financial_graph=(
                        financial_graph
                    ),
                    investigator=investigator,
                )
            )

        except Exception as exc:

            print()
            print(
                "⚠ AI investigation failed."
            )

            print(
                f"Reason: {exc}"
            )

    # ========================================================
    # AI RESULT
    # ========================================================

    if investigation:

        print_ai_result(
            investigation
        )

    # ========================================================
    # VERIFIED STATE
    # ========================================================

    banner(
        "STEP 7 — VERIFIED FINANCIAL STATE"
    )

    state_counts = {
        "VERIFIED": 0,
        "PENDING": 0,
        "EXCEPTION": 0,
    }

    for state in verified_states:

        state_counts[
            state.state
        ] = (
            state_counts.get(
                state.state,
                0,
            )
            + 1
        )

    metric(
        "Verified",
        f"{state_counts.get('VERIFIED', 0):,}",
    )

    metric(
        "Pending",
        f"{state_counts.get('PENDING', 0):,}",
    )

    metric(
        "Exception",
        f"{state_counts.get('EXCEPTION', 0):,}",
    )

    # ========================================================
    # FINAL CONTROLLER DECISION
    # ========================================================

    banner(
        "CONTROLLER DECISION"
    )

    if exception_count:

        print(
            "⚠ EXCEPTION REQUIRES REVIEW"
        )

        print()

        print(
            "The controller detected a financial "
            "reconciliation exception."
        )

        print(
            "The deterministic reconciliation "
            "engine remains authoritative."
        )

        if investigation:

            print(
                "The AI investigator supplied "
                "evidence-based analysis."
            )

    elif pending:

        print(
            "○ FINANCIAL STATE PENDING"
        )

        print(
            "Some settlements require "
            "additional financial evidence."
        )

    else:

        print(
            "✓ FINANCIAL STATE RECONCILED"
        )

    # ========================================================
    # ARCHITECTURE SUMMARY
    # ========================================================

    section(
        "CONTROLLER ARCHITECTURE"
    )

    print(
        "RAW FINANCIAL DATA"
    )

    print(
        "        ↓"
    )

    print(
        "NORMALIZED OBSERVATIONS"
    )

    print(
        "        ↓"
    )

    print(
        "FINANCIAL RELATIONSHIP GRAPH"
    )

    print(
        "        ↓"
    )

    print(
        "DETERMINISTIC RECONCILIATION"
    )

    print(
        "        ↓"
    )

    print(
        "EXCEPTION + EVIDENCE"
    )

    print(
        "        ↓"
    )

    print(
        "AI INVESTIGATION"
    )

    print(
        "        ↓"
    )

    print(
        "VERIFIED FINANCIAL STATE"
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    banner(
        "AI FINANCE CONTROLLER — RUN COMPLETE"
    )

    print(
        "Financial data processed."
    )

    print(
        "Reconciliation completed."
    )

    print(
        "Exceptions identified."
    )

    if investigation:

        print(
            "AI investigation completed."
        )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
