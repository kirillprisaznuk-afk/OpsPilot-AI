"""Conservative compositional grammar for the enterprise ontology, not case routing."""

import calendar
import re
from datetime import date

from app.agent.contracts import AgentError
from app.hybrid.contracts import Intent, Mention, Objective
from app.hybrid.registry import REGISTRY

ALIASES = {
    "sales_order": r"(?:customer\s+(?:sales\s+)?orders?|sales\s+orders?)",
    "purchase_order": r"purchase\s+orders?",
    "supplier": r"(?:suppliers?|vendors?)",
    "warehouse": r"warehouses?",
    "department": r"departments?",
    "employee": r"employees?",
    "customer": r"customers?(?!\s+(?:sales\s+)?order)",
    "product": r"products?",
    "invoice": r"(?:supplier\s+)?invoices?",
    "incident": r"incidents?",
    "task": r"(?:corrective\s+)?tasks?",
    "shortage": r"shortages?",
}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}


def temporal_scope(question, cutoff, explicit_cutoff=None):
    start, end = None, None
    iso = re.findall(r"\b20\d\d-\d\d-\d\d\b", question)
    if len(iso) > 2:
        raise AgentError("scope_ambiguous", "Specify one cutoff or one observation interval.")
    if iso:
        try:
            values = [date.fromisoformat(v) for v in iso]
        except ValueError as exc:
            raise AgentError("scope_conflict", "A requested calendar date is invalid.") from exc
        if len(values) == 2:
            start, end = values
        else:
            end = values[0]
    else:
        month = re.search(
            r"\b(?:(as of|at|by)\s+)?(?:the\s+)?(?:end of\s+)?("
            + "|".join(MONTHS)
            + r")(?:\s+(20\d\d))?\b",
            question.lower(),
        )
        if month:
            year, number = int(month[3] or cutoff.year), MONTHS[month[2]]
            end = date(year, number, calendar.monthrange(year, number)[1])
            if re.search(r"\b(?:during|in|for)\s+" + month[2] + r"\b", question.lower()):
                start = date(year, number, 1)
    if end:
        if explicit_cutoff and end > explicit_cutoff:
            raise AgentError("scope_conflict", "Question dates exceed the established cutoff.")
        cutoff = explicit_cutoff or end
    return cutoff, start, end


def interpret(question, cutoff, *, explicit_cutoff=None):
    text = question.lower().replace("’", "'")
    cutoff, start, end = temporal_scope(text, cutoff, explicit_cutoff)
    result = Intent(as_of=cutoff, start_date=start, end_date=end)
    objectives = []

    def add(capability, **values):
        objective = Objective(capability=capability, **values)
        if objective not in objectives:
            objectives.append(objective)

    for kind, alias in ALIASES.items():
        for match in re.finditer(
            r"\b" + alias + r"\s*(?:#|id\s*)?(\d+(?:\s*(?:,|and)\s*\d+)*)\b", text
        ):
            for term in re.findall(r"\d+", match[1]):
                mention = Mention(entity_type=kind, term=term)
                if mention not in result.mentions:
                    result.mentions.append(mention)
        for match in re.finditer(r"\b" + alias + r'\s+["\']([^"\']+)["\']', question, re.I):
            result.mentions.append(Mention(entity_type=kind, term=match[1]))
    # Unnumbered references are resolved against actual visible database names later.
    if re.search(
        r"\b(?:those|them|their (?:contracts?|agreements?|sla)|"
        r"that (?:supplier|customer order|warehouse|ranking)|first (?:two|2))\b",
        text,
    ):
        result.reference = "first_two" if re.search(r"first (?:two|2)", text) else "previous"
    if re.search(r"\b(?:was|were|is|are)\s+(?:that|it|those|they)\b", text):
        result.reference = "previous"
    if re.search(r"\bwhich warehouse\b", text) and re.search(r"affected|linked", text):
        result.reference = "previous"

    supplier = bool(re.search(r"\b(?:suppliers?|vendors?)\b", text))
    sales_order = any(m.entity_type == "sales_order" for m in result.mentions) or bool(
        re.search(r"\bcustomer\s+(?:sales\s+)?order\b", text)
    )
    purchase_order = any(m.entity_type == "purchase_order" for m in result.mentions) or bool(
        re.search(r"\bpurchase order\b", text)
    )
    contract = bool(re.search(r"\b(?:contracts?|agreements?|sla|contractual)\b", text))
    policy = bool(re.search(r"\b(?:polic(?:y|ies)|procedures?)\b", text))
    investigation = bool(
        re.search(r"\b(?:investigat\w*|why|impact|associated|linked|caus\w*|coincid\w*)\b", text)
    )
    rank = supplier and bool(
        re.search(
            r"\b(?:rank\w*|weakest|worst|best|lowest|highest|largest|smallest|poorest)\b", text
        )
    )
    if result.reference == "first_two" and not re.search(r"re-rank|rank .*\bby\b", text):
        rank = False
    if re.search(r"\b(?:how many|how much|total|number|count)\b", text) and not re.search(
        r"\b(?:why|investigat\w*|caus\w*|impact)\b", text
    ):
        investigation = False
    # A mention explicitly contrasts another metric; do not let it override the main objective.
    primary = re.split(r"\b(?:rather than|not about)\b", text)[0]
    count = re.search(
        r"\b(?:top|first|the|list|compare|which|rank|show|return)\s+"
        r"(\d+|one|two|three|four|five|ten)\s+(?:suppliers?|vendors?)",
        primary,
    )
    limit = (
        COUNTS.get(count[1], int(count[1]) if count and count[1].isdigit() else 3) if count else 3
    )
    if limit > 10:
        result.clarification = "Narrow the requested ranking to at most ten subjects."
    if rank:
        if re.search(r"\b(?:gbp|exposure|commitments?|spend|pounds)\b", primary):
            metric = "overdue_commitment" if "overdue" in primary else "open_commitment"
        elif "overdue" in primary and re.search(r"\b(?:number|count|orders?)\b", primary):
            metric = "overdue_outstanding_orders"
        elif re.search(r"\b(?:gap|shortfall)\b", primary):
            metric = "sla_gap"
        elif re.search(r"on[ -]time|delivery|punctual|performance", primary):
            metric = "on_time_rate"
        else:
            metric = None
            result.clarification = "Which defined metric should determine the supplier ranking?"
        if metric:
            low = bool(re.search(r"\b(?:lowest|weakest|worst|poorest|smallest)\b", primary))
            direction = "asc" if low else "desc"
            if metric == "sla_gap" and re.search(r"largest|highest|worst", primary):
                direction = "asc"
            add("supplier_ranking", metric=metric, direction=direction, count=limit)
            if re.search(r"\bthe supplier\b", text) and (contract or investigation):
                result.reference = "rank_extreme"
                objectives[-1].count = 1
    if supplier and not rank and not policy and not sales_order:
        if contract:
            add("supplier_sla")
        elif re.search(r"performance|on[ -]time|delivery|punctual", text):
            add("supplier_performance")
    if contract and not supplier and not sales_order:
        add("contract_lookup")
    if rank and contract:
        add("supplier_sla")
    if policy:
        topic = (
            "procurement"
            if supplier and not re.search(r"\bincident\b", text)
            else ("incident escalation" if re.search(r"\bincident\b", text) else None)
        )
        add("policy_lookup", topic=topic)
    if sales_order or purchase_order:
        add("investigation")
    if re.search(r"\b(?:stock|inventory|shortages?)\b", text) and not sales_order:
        add("inventory")
    if re.search(r"fulfil\w*|dispatch|customer orders?", text) and not sales_order:
        add("fulfilment")
    if (
        re.search(r"\b(?:costs?|expenses?|invoice exposure|outstanding amount)\b", text)
        and not rank
    ):
        add("recorded_costs")
    if re.search(r"\b(?:workforce|backlog|tasks?)\b", text) and not policy:
        add("workforce")
    if re.search(r"\bincidents?\b", text) and not policy and not investigation:
        add("incidents")
    if investigation:
        add("investigation")
        result.causality = (
            "universal"
            if re.search(r"\b(?:every|all)\b", text) and re.search(r"caus", text)
            else "association"
        )
    if result.reference == "previous" and re.search(r"\bwhich warehouse\b", text):
        add("investigation")
    if re.search(r"automatic penalt|legal breach", text):
        result.unsupported_concept = "automatic_legal_or_penalty_conclusion"
    if re.search(r"\b(?:ebitda|profit|margin|utili[sz]ation|productivity)\b", text):
        result.unsupported_concept = re.search(
            r"\b(?:ebitda|profit|margin|utili[sz]ation|productivity)\b", text
        )[0]
        if not re.search(r"do not|not estimate|rather than|without", text):
            objectives = []
        else:
            result.unsupported_concept = None
    if re.search(r"\b(?:overview|enterprise summary)\b", text):
        add("overview")
    if contract and supplier and not any(o.capability == "supplier_sla" for o in objectives):
        # Policy-only questions do not imply a request for every supplier's contract.
        if any(m.entity_type == "supplier" for m in result.mentions) or rank:
            add("supplier_sla")
    result.objectives = objectives
    if not objectives and not result.unsupported_concept:
        result.clarification = (
            "Specify an analytical objective, business subject or corporate procedure."
        )
    return Intent.model_validate(result.model_dump())


def validate_intent(intent):
    for objective in intent.objectives:
        if objective.capability not in REGISTRY:
            raise AgentError("unsupported_capability", "Requested capability is not registered.")
        if objective.metric and objective.metric not in REGISTRY[objective.capability].metrics:
            raise AgentError("unsupported_metric", "Metric is not defined by this capability.")
        if objective.capability == "supplier_ranking" and (
            objective.metric
            not in {
                "on_time_rate",
                "overdue_outstanding_orders",
                "overdue_commitment",
                "open_commitment",
                "sla_gap",
            }
            or objective.direction is None
        ):
            raise AgentError(
                "ranking_metric_required", "Select a defined ranking metric and direction."
            )
    # Reuse the established authoritative window contract, with no date repair.
    from app.analytics.contracts import AnalyticsQuery

    try:
        AnalyticsQuery(
            as_of=intent.as_of,
            **{
                k: v
                for k, v in {"start_date": intent.start_date, "end_date": intent.end_date}.items()
                if v is not None
            },
        )
    except ValueError as exc:
        raise AgentError(
            "scope_conflict", "Observation interval is outside the supported window."
        ) from exc
