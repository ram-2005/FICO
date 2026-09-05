from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from backend.app.intelligence.evidence_builder import InvestigationCase
from backend.app.intelligence.llm_client import OllamaClient
from backend.app.intelligence.tool_executor import ToolExecutor


@dataclass
class LLMInvestigation:
    settlement_id: str
    summary: str
    likely_causes: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""
    confidence: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "settlement_id": self.settlement_id,
            "summary": self.summary,
            "likely_causes": self.likely_causes,
            "supporting_evidence": self.supporting_evidence,
            "missing_evidence": self.missing_evidence,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "tool_calls": self.tool_calls,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            indent=2,
            default=str,
        )


class Investigator:
    """
    LLM-powered financial investigator.

    MVP architecture:

        Reconciliation
              |
              v
        InvestigationCase
              |
              v
        NetworkX Graph
              |
              v
        Graph Evidence
              |
              v
           Gemma
              |
              v
      LLMInvestigation

    The deterministic reconciliation engine remains
    the financial authority.

    Gemma interprets evidence and explains possible
    causes. It does not determine authoritative
    accounting truth.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        tool_executor: ToolExecutor,
        max_tool_calls: int = 3,
    ) -> None:
        self.client = llm_client
        self.executor = tool_executor
        self.max_tool_calls = max_tool_calls

    # ==================================================================
    # PROMPTS
    # ==================================================================

    def build_initial_prompt(
        self,
        case: InvestigationCase,
    ) -> str:

        return f"""
You are a financial investigation assistant.

You are investigating ONE settlement reconciliation case.

Do not give a generic explanation.

Use the ACTUAL VALUES supplied below.


AUTHORITATIVE CASE FACTS
========================

Settlement ID: {case.settlement_id}

Expected amount: {case.expected_amount}

Observed amount: {case.observed_amount}

Variance: {case.variance}

Reconciliation status: {case.reconciliation_status}


ROLE
====

The deterministic reconciliation engine is authoritative.

You must NOT override its financial conclusion.

Your job is to explain the discrepancy using the available evidence.

You must:

1. State what actually happened.
2. Identify possible causes supported by evidence.
3. Cite concrete evidence.
4. Identify what evidence is still missing.
5. Recommend the next investigation step.


IMPORTANT
=========

Use the actual settlement ID.

Use the actual expected amount.

Use the actual observed amount.

Use the actual variance.

Do not replace these values with placeholders.

Do not write generic statements such as:

"Explain the reconciliation situation."

Instead, write the actual explanation.

For example:

"Settlement SET_000103 has a shortfall of 88.40 because the expected amount is 39283.87 while the observed amount is 39195.47."

The example above is only an illustration of the required level of specificity.


FINANCIAL RULES
===============

- Do NOT invent financial facts.
- Do NOT invent transactions.
- Do NOT invent payment amounts.
- Do NOT change expected amount.
- Do NOT change observed amount.
- Do NOT change variance.
- Do NOT claim that a discrepancy is resolved without evidence.
- Do NOT claim that a graph relationship is financially correct merely because it exists.
- If evidence is insufficient, explicitly say so.
- The reconciliation engine is authoritative.
- You are an investigator and explainer, not the accounting authority.


AVAILABLE GRAPH TOOLS
=====================

get_event
get_neighbors
get_relationships
trace_chain


FIRST ACTION
============

Start by inspecting the graph around the settlement.

Return exactly:

{{
  "action": "get_neighbors",
  "arguments": {{
    "event_id": "{case.settlement_id}"
  }}
}}


OUTPUT RULES
============

Return JSON only.

Do NOT use markdown.

Do NOT use Python.

Do NOT use code fences.

Do NOT add commentary outside JSON.

When returning the final investigation, every JSON string must remain on ONE LINE.
""".strip()

    def build_tool_result_prompt(
        self,
        case: InvestigationCase,
        history: list[dict[str, Any]],
    ) -> str:

        latest = history[-1] if history else {}

        tool_name = latest.get(
            "tool",
            "",
        )

        tool_result = latest.get(
            "result",
            {},
        )

        history_text = json.dumps(
            history,
            indent=2,
            default=str,
        )

        tool_result_text = json.dumps(
            tool_result,
            indent=2,
            default=str,
        )

        return f"""
You are continuing a financial investigation.

Do NOT produce a generic answer.

Use the ACTUAL CASE FACTS and GRAPH EVIDENCE below.


AUTHORITATIVE CASE
==================

Settlement ID: {case.settlement_id}

Expected amount: {case.expected_amount}

Observed amount: {case.observed_amount}

Variance: {case.variance}

Reconciliation status: {case.reconciliation_status}


LATEST GRAPH TOOL
=================

Tool: {tool_name}


GRAPH RESULT
============

{tool_result_text}


INVESTIGATION HISTORY
====================

{history_text}


TASK
====

Explain what the evidence tells us.

Your final answer must contain:

1. A concrete summary of the discrepancy.
2. Evidence-based possible causes.
3. Specific supporting evidence.
4. Missing evidence.
5. A practical next action.
6. A confidence score.


CRITICAL INSTRUCTIONS
=====================

Use the actual values.

Do NOT copy wording from the output template.

Do NOT write:

"Explain the reconciliation situation using only the evidence."

Instead, replace that text with the actual explanation.

Do NOT write:

"Evidence-based possible cause."

Instead, provide an actual possible cause.

Do NOT write:

"Specific evidence from the case or graph."

Instead, provide actual evidence.

Do NOT write:

"Important evidence that is not available."

Instead, state what evidence is actually missing.

Do NOT write:

"Reasonable next investigation step."

Instead, provide the actual next step.


FINANCIAL SAFETY
================

- The deterministic reconciliation result is authoritative.
- Do NOT invent transactions.
- Do NOT invent payment amounts.
- Do NOT invent missing evidence.
- Do NOT alter expected amount.
- Do NOT alter observed amount.
- Do NOT alter variance.
- Do NOT claim that a transaction matched unless the evidence proves it.
- Do NOT claim that the discrepancy is resolved unless evidence proves it.
- Do NOT assume graph relationships are financially correct.
- Clearly distinguish facts from possible causes.
- If evidence is insufficient, say that explicitly.


FINAL JSON FORMAT
=================

Return exactly one JSON object:

{{
  "action": "final",
  "summary": "A concrete explanation using the actual settlement values.",
  "likely_causes": [
    "An actual evidence-based possible cause."
  ],
  "supporting_evidence": [
    "An actual fact from the reconciliation case or graph."
  ],
  "missing_evidence": [
    "An actual piece of evidence that is still unavailable."
  ],
  "recommended_action": "An actual next investigation step.",
  "confidence": 0.75
}}


JSON REQUIREMENTS
=================

- action must be "final"
- confidence must be between 0 and 1
- All strings must be on one line.
- Do not put line breaks inside quoted strings.
- Do not use markdown.
- Do not use Python.
- Do not use code fences.
- Do not copy the placeholder wording from the template.
- Return JSON only.
""".strip()

    # ==================================================================
    # RESPONSE CLEANING / JSON PARSING
    # ==================================================================

    @staticmethod
    def _clean_response(
        response: str,
    ) -> str:

        response = response.strip()

        if response.startswith("```"):

            lines = response.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            response = "\n".join(lines).strip()

        return response

    @staticmethod
    def _extract_json_object(
        response: str,
    ) -> str:

        start = response.find("{")

        if start == -1:
            raise ValueError(
                "LLM did not return a JSON object."
            )

        depth = 0

        in_string = False

        escape = False

        for index in range(
            start,
            len(response),
        ):

            char = response[index]

            if escape:

                escape = False

                continue

            if char == "\\" and in_string:

                escape = True

                continue

            if char == '"':

                in_string = not in_string

                continue

            if in_string:

                continue

            if char == "{":

                depth += 1

            elif char == "}":

                depth -= 1

                if depth == 0:

                    return response[
                        start:index + 1
                    ]

        raise ValueError(
            "LLM returned an incomplete JSON object."
        )

    @staticmethod
    def _repair_json(
        text: str,
    ) -> str:

        result: list[str] = []

        in_string = False

        escape = False

        for char in text:

            if escape:

                result.append(char)

                escape = False

                continue

            if char == "\\" and in_string:

                result.append(char)

                escape = True

                continue

            if char == '"':

                in_string = not in_string

                result.append(char)

                continue

            if char == "\n" and in_string:

                result.append(" ")

                continue

            if char == "\r" and in_string:

                result.append(" ")

                continue

            if char == "\t" and in_string:

                result.append(" ")

                continue

            result.append(char)

        return "".join(result)

    @staticmethod
    def _parse_json(
        response: str,
    ) -> dict[str, Any]:

        response = Investigator._clean_response(
            response
        )

        try:

            parsed = json.loads(
                response
            )

            if isinstance(parsed, dict):

                return parsed

        except json.JSONDecodeError:

            pass

        candidate = (
            Investigator._extract_json_object(
                response
            )
        )

        try:

            parsed = json.loads(
                candidate
            )

            if isinstance(parsed, dict):

                return parsed

        except json.JSONDecodeError:

            pass

        repaired = (
            Investigator._repair_json(
                candidate
            )
        )

        try:

            parsed = json.loads(
                repaired
            )

            if isinstance(parsed, dict):

                return parsed

        except json.JSONDecodeError as exc:

            raise ValueError(
                "LLM returned malformed JSON "
                f"after repair: {exc}"
            ) from exc

        raise ValueError(
            "LLM returned invalid JSON."
        )

    # ==================================================================
    # RESULT VALIDATION
    # ==================================================================

    def _build_final_result(
        self,
        case: InvestigationCase,
        parsed: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> LLMInvestigation:

        summary = parsed.get(
            "summary",
            "",
        )

        likely_causes = parsed.get(
            "likely_causes",
            [],
        )

        supporting_evidence = parsed.get(
            "supporting_evidence",
            [],
        )

        missing_evidence = parsed.get(
            "missing_evidence",
            [],
        )

        recommended_action = parsed.get(
            "recommended_action",
            "",
        )

        confidence = parsed.get(
            "confidence",
            0.0,
        )

        if isinstance(
            likely_causes,
            str,
        ):

            likely_causes = [
                likely_causes
            ]

        if not isinstance(
            likely_causes,
            list,
        ):

            likely_causes = []

        if isinstance(
            supporting_evidence,
            str,
        ):

            supporting_evidence = [
                supporting_evidence
            ]

        if not isinstance(
            supporting_evidence,
            list,
        ):

            supporting_evidence = []

        if isinstance(
            missing_evidence,
            str,
        ):

            missing_evidence = [
                missing_evidence
            ]

        if not isinstance(
            missing_evidence,
            list,
        ):

            missing_evidence = []

        try:

            confidence = float(
                confidence
            )

        except (
            TypeError,
            ValueError,
        ):

            confidence = 0.0

        confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

        # --------------------------------------------------------------
        # Detect obvious placeholder responses.
        # --------------------------------------------------------------

        placeholder_phrases = {
            "Explain the reconciliation situation using only the evidence.",
            "Evidence-based possible cause",
            "Specific evidence from the case or graph",
            "Important evidence that is not available",
            "Reasonable next investigation step.",
            "Possible cause supported by evidence",
            "Cause supported by evidence",
        }

        def contains_placeholder(
            value: Any,
        ) -> bool:

            if not isinstance(
                value,
                str,
            ):

                return False

            normalized = value.strip()

            return normalized in placeholder_phrases

        if contains_placeholder(
            summary
        ):

            summary = (
                f"Settlement {case.settlement_id} "
                f"has an observed amount of "
                f"{case.observed_amount} against an "
                f"expected amount of "
                f"{case.expected_amount}, resulting "
                f"in a variance of "
                f"{case.variance}."
            )

        likely_causes = [
            str(item)
            for item in likely_causes
            if not contains_placeholder(item)
        ]

        supporting_evidence = [
            str(item)
            for item in supporting_evidence
            if not contains_placeholder(item)
        ]

        missing_evidence = [
            str(item)
            for item in missing_evidence
            if not contains_placeholder(item)
        ]

        if contains_placeholder(
            recommended_action
        ):

            recommended_action = (
                "Review the settlement components "
                "and supporting gateway and bank "
                "evidence."
            )

        return LLMInvestigation(
            settlement_id=case.settlement_id,
            summary=str(summary),
            likely_causes=likely_causes,
            supporting_evidence=supporting_evidence,
            missing_evidence=missing_evidence,
            recommended_action=str(
                recommended_action
            ),
            confidence=confidence,
            tool_calls=history,
        )

    # ==================================================================
    # MAIN INVESTIGATION
    # ==================================================================

    def investigate(
        self,
        case: InvestigationCase,
    ) -> LLMInvestigation:

        history: list[
            dict[str, Any]
        ] = []

        # ==============================================================
        # STEP 1 — GRAPH LOOKUP
        # ==============================================================

        print(
            "\n[INVESTIGATOR] "
            "Graph investigation"
        )

        action = "get_neighbors"

        arguments = {
            "event_id": case.settlement_id
        }

        print(
            f"[INVESTIGATOR] Tool request: "
            f"{action}"
        )

        print(
            "[INVESTIGATOR] Arguments: "
            f"{arguments}"
        )

        try:

            tool_result = (
                self.executor.execute(
                    action,
                    arguments,
                )
            )

        except Exception as exc:

            tool_result = {
                "error": str(exc)
            }

        print(
            "[INVESTIGATOR] Tool result:"
        )

        print(tool_result)

        history.append(
            {
                "step": 1,
                "tool": action,
                "arguments": arguments,
                "result": tool_result,
            }
        )

        # ==============================================================
        # STEP 2 — BUILD COMPACT EVIDENCE
        # ==============================================================

        graph_evidence = json.dumps(
            tool_result,
            indent=2,
            default=str,
        )

        # ==============================================================
        # STEP 3 — ASK GEMMA
        # ==============================================================

        print(
            "\n[INVESTIGATOR] "
            "Asking Gemma for final analysis"
        )

        prompt = f"""
You are a financial investigator.

You must investigate settlement:

{case.settlement_id}


AUTHORITATIVE RECONCILIATION FACTS
==================================

Settlement ID:
{case.settlement_id}

Expected amount:
{case.expected_amount}

Observed amount:
{case.observed_amount}

Variance:
{case.variance}

Reconciliation status:
{case.reconciliation_status}


GRAPH EVIDENCE
==============

{graph_evidence}


WHAT YOU MUST DO
================

Write a REAL investigation.

Do not describe what an investigation should do.

Do the investigation using the evidence supplied above.


SUMMARY
=======

The summary MUST describe the actual case.

It must mention the actual settlement ID and actual financial discrepancy.

Do not output:

"Explain the reconciliation situation using only the evidence."

Instead write something like:

"Settlement SET_000103 has a variance of 88.40 between the expected amount of 39283.87 and the observed amount of 39195.47."

Only use numbers that are actually supplied in the evidence.


LIKELY CAUSES
=============

List actual possible explanations supported by evidence.

If the evidence does not establish a cause, say:

"The available evidence does not establish the root cause."

Do NOT invent a cause.


SUPPORTING EVIDENCE
===================

List concrete facts from the reconciliation result or graph.

For example:

"Expected settlement amount is 39283.87."

"Observed settlement amount is 39195.47."

"Variance is 88.40."

Do NOT write:

"Specific evidence from the case or graph."


MISSING EVIDENCE
================

List concrete information that would be needed to determine the root cause.

Do NOT write:

"Important evidence that is not available."


RECOMMENDED ACTION
==================

Give one concrete next step.

Do NOT write:

"Reasonable next investigation step."


FINANCIAL AUTHORITY
===================

The deterministic reconciliation engine is authoritative.

You are NOT allowed to:

- change the reconciliation result
- change expected amount
- change observed amount
- change variance
- invent payments
- invent payment amounts
- invent bank transactions
- invent refunds
- declare a match without evidence
- declare the discrepancy resolved without evidence


GRAPH RULE
==========

A graph relationship is evidence of a recorded relationship.

It does NOT automatically prove that the financial relationship is correct.


JSON ONLY
=========

Return exactly:

{{
  "action": "final",
  "summary": "Actual explanation of this settlement.",
  "likely_causes": [
    "Actual possible cause based on evidence."
  ],
  "supporting_evidence": [
    "Actual evidence."
  ],
  "missing_evidence": [
    "Actual missing evidence."
  ],
  "recommended_action": "Actual next step.",
  "confidence": 0.75
}}

IMPORTANT:

The text inside the example above is a FORMAT EXAMPLE.

Replace every example sentence with actual content.

Never copy the example sentences into your answer.

Return JSON only.

No markdown.

No Python.

No code fences.

Keep every JSON string on one line.
""".strip()

        response = self.client.generate(
            prompt
        )

        print(
            "[INVESTIGATOR] "
            "Gemma response:"
        )

        print(response)

        # ==============================================================
        # STEP 4 — PARSE RESPONSE
        # ==============================================================

        try:

            parsed = self._parse_json(
                response
            )

        except ValueError as exc:

            print(
                "[INVESTIGATOR] "
                "JSON parsing failed."
            )

            return LLMInvestigation(
                settlement_id=case.settlement_id,
                summary=(
                    "LLM returned invalid JSON."
                ),
                likely_causes=[],
                supporting_evidence=[],
                missing_evidence=[
                    str(exc)
                ],
                recommended_action=(
                    "Review the investigation manually."
                ),
                confidence=0.0,
                tool_calls=history,
            )

        # ==============================================================
        # STEP 5 — VALIDATE ACTION
        # ==============================================================

        if parsed.get(
            "action"
        ) != "final":

            return LLMInvestigation(
                settlement_id=case.settlement_id,
                summary=(
                    "LLM did not return "
                    "a final investigation."
                ),
                likely_causes=[],
                supporting_evidence=[],
                missing_evidence=[
                    "LLM returned an unsupported action."
                ],
                recommended_action=(
                    "Review the investigation manually."
                ),
                confidence=0.0,
                tool_calls=history,
            )

        # ==============================================================
        # STEP 6 — BUILD STRUCTURED RESULT
        # ==============================================================

        return self._build_final_result(
            case=case,
            parsed=parsed,
            history=history,
        )
