"""Independent checks for typed interpretations, beyond source identity alone."""

import re
from decimal import Decimal

from app.agent.contracts import AgentError

QUANTITY_WORDS = set(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy "
    "eighty ninety hundred thousand million billion first second third fourth fifth half "
    "halves quarter quarters twice double triple majority minority percent percentage "
    "percentages pounds gbp approximately roughly dozen days hours weeks months".split()
)
FUZZY_NUMBERS = {
    w
    for w in QUANTITY_WORDS
    if len(w) >= 5
    and w not in {"approximately", "roughly", "percentage", "percentages", "majority", "minority"}
}


def near_number(token, number):
    if token[:2] != number[:2] or token in {"forth"}:
        return False
    if len(token) == len(number):
        return sum(a != b for a, b in zip(token, number, strict=True)) <= 1
    if abs(len(token) - len(number)) == 1:
        longer, shorter = sorted((token, number), key=len, reverse=True)
        return any(longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer)))
    return False


def validate_prose(text):
    words = re.findall(r"[A-Za-z]+", text.lower())
    if (
        len(words) < 3
        or text[-1:] not in ".!?"
        or re.search(r"\s{2}|[\r\n]", text)
        or words[-1] in {"the", "a", "an", "and", "or", "of", "to", "against", "after", "before"}
        or re.search(r"\b([a-z]{2,})(?:[- ]\1){2}", text, re.I)
    ):
        raise AgentError(
            "malformed_prose", "Write a short complete natural sentence without blanks."
        )
    if re.search(r"\d", text) or any(
        word in QUANTITY_WORDS or any(near_number(word, n) for n in FUZZY_NUMBERS) for word in words
    ):
        raise AgentError(
            "unverified_numerical_prose",
            "Do not restate quantities or proportions in prose, including misspellings. "
            "Select exact metric references or source quotations instead.",
        )


def validate_interpretation(finding, metrics, entities, relationships, source_metadata):
    validate_prose(finding.text)
    text = finding.text.lower()
    if finding.claim_type == "interpretation":
        raise AgentError("missing_claim_type", "Classify the interpretation explicitly.")
    if (
        finding.claim_type != "policy_requirement"
        and re.search(r"\ball\b|\bevery\b", text)
        and not (
            finding.claim_type == "unavailable" and re.search(r"\bno\b|\bnot\b|\bcannot\b", text)
        )
    ):
        raise AgentError(
            "unsupported_universal_claim",
            "A bounded evidence selection does not "
            "establish a universal quantitative claim. Render exact metrics instead.",
        )
    if metrics and any("/breakdowns/" in m["pointer"] for m in metrics) and not entities:
        raise AgentError("missing_entity_reference", "Bind row metrics to their actual subject.")
    supplier_ids = {e["entity_id"] for e in entities if e["entity_type"] == "supplier"}
    customer_scope = any(e["entity_type"] in {"sales_order", "customer"} for e in entities)
    for metadata in source_metadata:
        if (
            metadata.get("supplier_id")
            and supplier_ids
            and metadata["supplier_id"] not in supplier_ids
        ):
            raise AgentError("business_scope_mismatch", "Contract belongs to another supplier.")
        if (
            customer_scope
            and metadata.get("document_type") == "supplier_agreement"
            and finding.claim_type
            not in {"association", "possible_explanation", "causal_chain", "unavailable"}
            and not re.search(r"not|separate|distinct", text)
        ):
            raise AgentError(
                "business_scope_mismatch",
                "Supplier agreements do not define customer dispatch promises. Use sales-order "
                "evidence; describe procurement links as qualified associations.",
            )
    causal = bool(re.search(r"\bbecause\b|\bcaused\b|\bled to\b|\btriggered\b|\bprevented\b", text))
    qualified = bool(
        re.search(
            r"\bmay\b|\bmight\b|\bcould\b|possible|not establish|not prove|"
            r"cannot establish|cannot prove|no .*evidence|does not establish|not supported",
            text,
        )
    )
    if finding.claim_type == "causal_chain" or causal and not qualified:
        if (
            finding.claim_type != "causal_chain"
            or not relationships
            or any(row["evidence_class"] != "simulated_causal_chain" for row in relationships)
        ):
            raise AgentError(
                "unsupported_causal_claim",
                "Explicit links establish association, not causation. Select actual simulation-"
                "supported relationship records or qualify it as a possible explanation.",
            )
    if finding.claim_type == "possible_explanation" and not qualified:
        raise AgentError(
            "unqualified_hypothesis", "State explicitly that this explanation is possible."
        )
    if re.search(
        r"before acting|before any action|no other action|forbids? other|only permitted|cannot act",
        text,
    ) and not re.search(r"does not|not imply|not prohibit|no prohibition", text):
        raise AgentError(
            "unsupported_policy_exclusion",
            "Do not infer prohibitions on other proactive actions from an escalation interval.",
        )
    if re.search(r"legal breach|legally liable|automatic penalt", text) and not re.search(
        r"not |no |never|cannot|unproven|unavailable", text
    ):
        raise AgentError(
            "unsupported_legal_conclusion",
            "Operational evidence does not establish legal liability or automatic penalties.",
        )
    if finding.claim_type == "policy_requirement" and not source_metadata:
        raise AgentError(
            "missing_policy_source", "A stated requirement needs an applicable source."
        )
    comparative = bool(
        re.search(
            r"below.*target|above.*target|shortfall.*target|underperform.*target|overperform.*target",
            text,
        )
    )
    if finding.claim_type == "comparison" or comparative:
        actual = [
            m for m in metrics if m["metric"] in {"procurement.on_time_rate", "observed_percent"}
        ]
        target = [
            m for m in metrics if m["metric"] in {"suppliers.sla_target_percent", "target_percent"}
        ]
        if not actual or not target or actual[0]["value"] is None or target[0]["value"] is None:
            raise AgentError(
                "incomplete_comparison",
                "Select both observed on-time rate and applicable target as metric references.",
            )
        if not entities:
            raise AgentError(
                "missing_entity_reference", "Comparison needs the actual supplier subject."
            )
        if actual[0]["evidence_id"] != target[0]["evidence_id"]:
            raise AgentError(
                "comparison_scope_mismatch", "Compare metrics from the same scoped evidence."
            )
        observed, expected = Decimal(str(actual[0]["value"])), Decimal(str(target[0]["value"]))
        if (re.search(r"below|shortfall|underperform", text) and observed >= expected) or (
            re.search(r"above|overperform", text) and observed <= expected
        ):
            raise AgentError(
                "contradictory_comparison", "Interpretation contradicts selected values."
            )
