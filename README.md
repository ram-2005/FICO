# Financial State Reconstructor

### Graph-Based Financial Context Retrieval & LLM-Powered Exception Investigation

> **Razorpay Buildathon 2026 — Track 04: AI Finance Controller**
>
> Reconstruct financial reality from fragmented records, verify it deterministically, retrieve the relevant financial context as a graph, and use an LLM to investigate unresolved exceptions.

---

## The Idea

Financial data does not live in one place.

A payment may exist in a payment gateway, its settlement in another system, the actual movement of money in a bank, and the accounting representation in an ERP.

The difficult question is not only:

> **"Do these numbers match?"**

It is:

> **"If they don't match, what financial events and relationships explain the difference?"**

This project builds a **Financial State Reconstructor** that connects those records into a financial graph, performs deterministic reconciliation, retrieves relevant context around an exception, and gives that evidence to an LLM for investigation.

### Core Pipeline

```text
Raw Financial Records
        ↓
   Normalization
        ↓
 Financial Events
        ↓
   Financial Graph
        ↓
Deterministic Reconciliation
        ↓
     Exception
        ↓
 Graph Context Retrieval
        ↓
   Evidence Builder
        ↓
   LLM Investigation
        ↓
Causes · Evidence · Missing Evidence · Next Action
```

---

## Why a Graph?

Traditional tables are good at storing records.

Financial investigation is about **relationships between records**.

```text
Customer → Order → Payment → Settlement → Bank Transaction → Accounting Entry
```

Real financial activity also branches:

```text
                    ┌── Refund
                    │
Payment ────────────┼── Chargeback
                    │
                    └── Settlement → Bank Transaction → Accounting Entry
```

A graph makes these relationships explicit.

More importantly, the graph becomes a **context retrieval layer**.

When an exception occurs, we do not want to send the entire company's financial data to an LLM.

```text
Exception
    ↓
Find related financial node
    ↓
Traverse relevant relationships
    ↓
Retrieve focused subgraph
    ↓
Build evidence bundle
    ↓
LLM investigation
```

> **The graph determines what is relevant. The LLM reasons about what that evidence could mean.**

---

## Architecture

```text
External Sources
  │
  ├── Payment Gateway
  ├── Bank
  ├── Accounting / ERP
  └── Vendors
  │
  ▼
Data Processing
  │
  ├── Ingestion
  ├── Normalization
  └── Event Builder
  │
  ▼
Financial Modeling
  │
  ├── Financial Graph
  └── Reconciliation Engine
  │
  ▼
Investigation
  │
  ├── Evidence Builder
  ├── LLM Investigator
  └── Verifier
  │
  ▼
Human & Learning
  │
  ├── Controller Review
  └── Exception Memory
```

## UML — Financial Domain Model

The financial graph represents the company's financial reality as connected entities and relationships.

```text
┌──────────────┐        places        ┌──────────────┐
│   Customer   │ ───────────────────► │    Order     │
└──────────────┘                      └──────┬───────┘
                                            │ generates
                                            ▼
                                     ┌──────────────┐
                                     │   Invoice    │
                                     └──────┬───────┘
                                            │ paid by
                                            ▼
                                     ┌──────────────┐
                                     │   Payment    │
                                     └──┬────┬────┬─┘
                                        │    │    │
                                      has  may  may
                                        │   │    │
                                        ▼   ▼    ▼
                                    Refund  Chargeback
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │  Settlement  │
                                 └──────┬───────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │ Bank Transaction │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ Accounting Entry │
                              └──────────────────┘
```

### UML — Graph Retrieval for an Exception

```text
┌─────────────────┐
│    Exception    │
│  SET_000103     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Context Selector│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│        Relevant Financial Graph     │
│                                     │
│ Payment ──► Settlement ──► Bank    │
│    │             │             │    │
│  Refund       Amount       Accounting│
│    │          variance          │    │
│Chargeback                    Entry  │
└─────────────────┬───────────────────┘
                  │
                  ▼
          ┌────────────────┐
          │ Evidence Builder│
          └───────┬────────┘
                  │
                  ▼
          ┌────────────────┐
          │ LLM Investigator│
          └───────┬────────┘
                  │
       ┌──────────┼───────────┐
       ▼          ▼           ▼
   Likely      Supporting   Missing
   Causes       Evidence     Evidence
```

### UML — Reconciliation Model

```text
┌──────────────────┐
│    Settlement    │
├──────────────────┤
│ gross_amount     │
│ refunds          │
│ net_amount       │
└────────┬─────────┘
         │
         │ deterministic calculation
         ▼
┌──────────────────────────┐
│ Expected Amount          │
│ gross - refunds - ...    │
└────────────┬─────────────┘
             │
             │ compare
             ▼
┌──────────────────────────┐
│    Bank Transaction      │
├──────────────────────────┤
│ observed_amount          │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   Reconciliation Result  │
├──────────────────────────┤
│ expected                 │
│ observed                 │
│ variance                 │
│ status                   │
└────────────┬─────────────┘
             │
             ▼
     ┌───────────────┐
     │   Exception   │
     └───────────────┘
```

### UML — Truth vs Reasoning Boundary

```text
                 FINANCIAL SYSTEM
                        │
                        ▼
              ┌──────────────────┐
              │ Deterministic    │
              │ Verification     │
              ├──────────────────┤
              │ amounts          │
              │ arithmetic       │
              │ matching         │
              │ variance         │
              └────────┬─────────┘
                       │
                 VERIFIED FACTS
                       │
                       ▼
              ┌──────────────────┐
              │ Financial Graph  │
              │ + Context        │
              │ Retrieval        │
              └────────┬─────────┘
                       │
                 RELEVANT EVIDENCE
                       │
                       ▼
              ┌──────────────────┐
              │       LLM        │
              │   Investigation  │
              ├──────────────────┤
              │ hypotheses       │
              │ explanations     │
              │ missing evidence │
              │ next action      │
              └──────────────────┘

       FACTS ≠ HYPOTHESES
```

### UML — End-to-End Controller Sequence

```text
Source        Ingestion      Graph       Reconciliation    LLM
  │              │             │               │            │
  │── records ──►│             │               │            │
  │              │── events ──►│               │            │
  │              │             │── context ───►│            │
  │              │             │               │            │
  │              │             │◄── exception ─│            │
  │              │             │               │            │
  │              │             │── subgraph ───────────────►│
  │              │             │               │            │
  │              │             │               │── evidence►│
  │              │             │               │            │
  │              │             │               │◄─ analysis │
  │              │             │               │            │
```

### Core Design Principle

**Financial truth and AI reasoning are separate.**

| Responsibility | System |
|---|---|
| Normalize source records | Deterministic pipeline |
| Build financial events | Financial modeling |
| Establish relationships | Financial graph |
| Calculate expected amounts | Deterministic reconciliation |
| Calculate variance | Deterministic reconciliation |
| Detect exceptions | Deterministic verification |
| Retrieve investigation context | Graph + evidence builder |
| Explain possible causes | LLM |
| Identify missing evidence | LLM |
| Suggest next investigation step | LLM |
| Establish authoritative financial truth | **Never delegated to the LLM** |

---

## Example

Suppose a settlement contains:

```text
Gross amount       ₹10,000
Refund deductions    -₹200
Expected settlement ₹9,800
```

The bank shows:

```text
Observed            ₹9,650
```

The deterministic engine establishes:

```text
Expected            ₹9,800
Observed             ₹9,650
Variance               ₹150
Status              EXCEPTION
```

The system then retrieves the financial context around that exception:

```text
Settlement
   ├── contributing Payments
   │      ├── Refunds
   │      └── Chargebacks
   │
   └── Bank Transaction
          └── Accounting Entry
```

The LLM receives this evidence bundle and investigates:

- What could explain the ₹150 variance?
- Which records support each explanation?
- What evidence is still missing?
- What should the controller check next?

The LLM does **not** recalculate the ₹150.

---

## What Is Implemented

### Data Ingestion & Normalization

- Multi-source financial record ingestion
- Common normalized representation
- Source identifiers and provenance
- Timestamp and event-type normalization

### Financial Graph

The current prototype models the core payment flow:

```text
Payment → Settlement → Bank Transaction
```

with related financial context available for investigation.

The prototype uses **NetworkX** for graph construction and traversal.

### Reconciliation

The deterministic layer performs:

- Expected vs observed amount checks
- Settlement arithmetic checks
- Variance detection
- Exception generation
- Verified-state generation

### AI Investigation

The current AI layer uses:

- **Ollama**
- **Gemma 2B**
- Evidence Builder
- Structured investigation prompts
- JSON investigation output

The investigator is instructed to distinguish:

```text
FACTS → EVIDENCE → HYPOTHESES
```

rather than treating an LLM response as accounting truth.

---

## Dataset

The project uses a controlled synthetic financial environment representing a fictional D2C company.

- **21 source datasets**
- **4,885,743 generated rows**
- INR
- Asia/Kolkata
- Payment, settlement and banking data
- Commerce, vendor, payroll and accounting data
- Controlled financial anomalies
- Independent ground-truth records

Core financial relationships include:

```text
Customer → Order → Invoice → Payment
Payment → Settlement → Bank Transaction
Payment → Refund
Payment → Chargeback
Settlement → Reversal
Vendor → Vendor Invoice → Vendor Payment → Bank
Bank Account → Inter-account Transfer → Bank Account
```

### Dataset Validation

```text
Rows generated        4,885,743
Generator errors              0
Validation warnings            3
Known anomalies                8
```

---

## Why Not Just Use an LLM?

Financial systems need more than normal question answering.

An LLM can reason about evidence, but it should not be the authority for:

- arithmetic
- reconciliation
- transaction amounts
- accounting balances
- financial state verification

Our architecture therefore follows:

```text
DETERMINISTIC
What happened?
      ↓
Is it consistent?
      ↓
Exception
      ↓
GRAPH
What is related?
      ↓
LLM
What could it mean?
```

> **Rules establish what is true. AI helps determine what it means.**

---

## Current Prototype vs Future Controller

### Current Prototype

```text
Ingest
  ↓
Normalize
  ↓
Build Graph
  ↓
Reconcile
  ↓
Detect Exception
  ↓
Retrieve Context
  ↓
LLM Investigation
```

### Longer-Term Controller

```text
Detect
  ↓
Investigate
  ↓
Verify
  ↓
Human Approval
  ↓
Act
  ↓
Learn
  ↺
```

Future work includes stronger graph retrieval, RAG over resolved exceptions, human approval feedback, exception classification, explainable prioritization, verifier loops, temporal financial graphs, and production graph storage.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python |
| Data | Synthetic financial dataset |
| Graph | NetworkX |
| LLM Runtime | Ollama |
| Model | Gemma 2B |
| Reconciliation | Deterministic Python |
| AI Investigation | Structured LLM pipeline |

---

## Quick Start

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_REPOSITORY>

python -m venv .venv
source .venv/bin/activate

pip install -r backend/requirements.txt
```

Install and start Ollama, then:

```bash
ollama pull gemma:2b
ollama serve
```

Run:

```bash
PYTHONPATH=. python run_controller.py
```

The controller runs:

```text
Load data
  ↓
Build financial graph
  ↓
Run reconciliation
  ↓
Generate exception
  ↓
Build evidence
  ↓
Run LLM investigation
```

---

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── accounting/
│   │   ├── classification/
│   │   ├── exceptions/
│   │   ├── forecasting/
│   │   ├── graph/
│   │   ├── ingestion/
│   │   ├── intelligence/
│   │   └── models/
│   └── tests/
│
├── data/
│   ├── ground_truth/
│   ├── manifests/
│   ├── processed/
│   └── raw/
│
├── models/
├── notebooks/
├── scripts/
└── tests/
```

---

## Demo

**5-minute technical walkthrough:**  
`<ADD_VIDEO_LINK>`

The demo shows:

1. Financial data ingestion
2. Graph construction
3. Deterministic reconciliation
4. Exception detection
5. Evidence construction
6. LLM investigation

---

## Evaluation & Honesty

This project was built for **Razorpay Buildathon 2026 — Track 04: AI Finance Controller**, whose bar emphasizes throughput, measured accuracy, and an honest exception list.

The current implementation is a working prototype focused on the end-to-end architecture and AI investigation loop.

The graph-to-LLM retrieval layer is currently a prototype implementation, and the reconciliation relationship logic is still being hardened. We therefore do **not** present current prototype output as production-grade financial accuracy.

The intended evaluation is:

```text
Ground Truth
     ↓
Controller Output
     ↓
Match / Pending / Exception
     ↓
Compare
     ↓
Measured Accuracy / Match Rate
     ↓
Honest Unresolved Exception List
```

**No cherry-picked match is treated as proof of correctness.**

---

## Design Principles

### 1. Financial truth before AI

Deterministic systems establish financial facts before the LLM reasons about them.

### 2. Context before prompting

The LLM should receive relevant evidence, not an uncontrolled dump of the financial dataset.

### 3. Hypotheses are not facts

An LLM explanation remains a hypothesis until verified against financial evidence.

---

## System State Model

The controller treats a financial record as moving through progressively stronger states:

```text
RAW
 │
 ▼
NORMALIZED
 │
 ▼
CLASSIFIED
 │
 ▼
MATCHED
 │
 ├──────────────► PENDING
 │
 ▼
VERIFIED
 │
 └──────────────► EXCEPTION
                         │
                         ▼
                    INVESTIGATED
                         │
                         ▼
                      REVIEWED
```

The important distinction is that an **investigation result is not automatically a verified financial fact**.

---

## Status

**Prototype / Buildathon Submission**

The core vertical slice is implemented:

```text
Payment
   ↓
Settlement
   ↓
Bank Transaction
   ↓
Reconciliation
   ↓
Exception
   ↓
Evidence
   ↓
LLM Investigation
```

---

## Built For

**Razorpay Buildathon 2026 — Track 04: AI Finance Controller**

> *Run the books and the cash position.*
