import re

from sqlalchemy import text

from app.agent.contracts import AgentError
from app.agent.database import agent_session
from app.hybrid.contracts import Mention, Subject
from app.hybrid.intent import ALIASES

NAMED = {
    "supplier": "suppliers",
    "warehouse": "warehouses",
    "department": "departments",
    "employee": "employees",
    "customer": "customers",
    "product": "products",
}


def database_mentions(question, intent, bind=None):
    """Bounded entity-name matching over visible records, never a business calculation."""
    found = []
    kinds = {m.entity_type for m in intent.mentions}
    candidates = {k for k, pattern in ALIASES.items() if re.search(pattern, question, re.I)}
    for objective in intent.objectives:
        candidates.update(
            {
                "supplier_performance": {"supplier"},
                "supplier_sla": {"supplier"},
                "contract_lookup": {"supplier"},
                "inventory": {"warehouse", "product"},
                "recorded_costs": {"supplier", "warehouse"},
                "fulfilment": {"warehouse"},
                "workforce": {"department", "employee"},
            }.get(objective.capability, set())
        )
    if any(o.capability == "workforce" for o in intent.objectives):
        candidates.add("department")
    normalized = question.casefold()
    with agent_session(bind=bind) as db:
        for kind in sorted(candidates & NAMED.keys() - kinds):
            rows = db.execute(
                text(
                    f"SELECT id,name FROM {NAMED[kind]} WHERE created_at < "
                    "CAST(:cutoff AS date)+interval '1 day' ORDER BY id LIMIT 500"
                ),
                {"cutoff": intent.as_of},
            ).mappings()
            for row in rows:
                label = row["name"].removesuffix(" (synthetic)")
                if re.search(r"(?<!\w)" + re.escape(label.casefold()) + r"(?!\w)", normalized):
                    found.append(Mention(entity_type=kind, term=str(row["id"])))
    return found


async def resolve(intent, question, history, call, bind=None):
    mentions = list(intent.mentions)
    provenance = "database_lookup"
    if intent.reference in {"previous", "first_two"} and not mentions:
        previous = next(
            (turn for turn in reversed(history) if turn.get("status") == "completed"), None
        )
        if not previous:
            raise AgentError(
                "reference_unresolved", "There is no completed verified subject to reference."
            )
        entities = previous.get("entities", [])
        if intent.reference == "first_two":
            if not previous.get("ranking_validated"):
                raise AgentError(
                    "ranking_reference_unverified",
                    "Obtain a verified ranking before this follow-up.",
                )
            entities = [e for e in entities if e.get("rank") is not None][:2]
            if len(entities) != 2:
                raise AgentError(
                    "reference_unresolved", "The preceding ranking has no verified pair."
                )
        mentions = [
            Mention(entity_type=e["entity_type"], term=str(e["entity_id"])) for e in entities[:6]
        ]
        provenance = "verified_conversation"
    if not mentions:
        mentions = database_mentions(question, intent, bind)
    # A partial name after an ontology noun can be resolved, but never guessed.
    if not mentions:
        for kind in ("supplier", "warehouse", "department", "employee", "product"):
            match = re.search(
                ALIASES[kind] + r"\s+([A-Z][\w &'()-]{2,100}?)"
                r"(?=\s+(?:performance|against|delivery|as of|has|is)|[?.;]|$)",
                question,
            )
            if match and not re.search(r"\b(?:with|lowest|highest|worst|best)\b", match[1], re.I):
                mentions.append(Mention(entity_type=kind, term=match[1].strip()))
    subjects = []
    for mention in mentions:
        item = await call(
            "resolve_business_entity",
            {**mention.model_dump(), "as_of": str(intent.as_of)},
            "entity_resolution",
        )
        payload = item.payload
        if payload["status"] == "ambiguous":
            raise AgentError(
                "entity_ambiguous",
                "Multiple visible records match; supply a more specific name or ID.",
            )
        if payload["status"] != "resolved":
            raise AgentError(
                "entity_not_found", "No matching entity exists at the selected cutoff."
            )
        row = payload["matches"][0]
        value = Subject(
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            label=row["name"],
            provenance=provenance,
        )
        if value not in subjects:
            subjects.append(value)
    return subjects
