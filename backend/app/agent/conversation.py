import asyncio
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from app.agent.contracts import AgentError


@dataclass
class Conversation:
    as_of: object
    owner: uuid.UUID | None = None
    turns: list = field(default_factory=list)
    touched: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Conversations:
    def __init__(self):
        self.entries = OrderedDict()

    def get(self, identifier, as_of, *, owner=None):
        now = time.monotonic()
        for key in list(self.entries):
            if now - self.entries[key].touched > 1800 and not self.entries[key].lock.locked():
                del self.entries[key]
        if identifier:
            conversation = self.entries.get(identifier)
            if conversation is None or conversation.owner != owner:
                raise AgentError(
                    "conversation_not_found",
                    "Conversation is unknown or expired; start a new request.",
                )
            if as_of is not None and as_of != conversation.as_of:
                raise AgentError(
                    "conversation_window_conflict",
                    "Start a new conversation to change the business cutoff.",
                )
            conversation.touched = now
            self.entries.move_to_end(identifier)
            return identifier, conversation
        if len(self.entries) >= 50:
            available = next((k for k, v in self.entries.items() if not v.lock.locked()), None)
            if available is None:
                raise AgentError("conversation_capacity", "Conversation capacity reached.")
            del self.entries[available]
        identifier = uuid.uuid4().hex
        conversation = Conversation(as_of, owner)
        self.entries[identifier] = conversation
        return identifier, conversation

    def save(self, conversation, response):
        entities = []
        accepted = response.status == "completed"
        for finding in response.key_findings if accepted else []:
            for entity in finding.entities:
                entities.append(
                    {
                        k: entity.get(k)
                        for k in (
                            "entity_type",
                            "entity_id",
                            "label",
                            "name",
                            "rank",
                            "criterion",
                            "direction",
                        )
                    }
                )
        selected_entities = bool(entities)
        for e in response.evidence if accepted and not selected_entities else []:
            for row in e.payload.get("matches", []):
                entities.append(row)
            for row in e.payload.get("breakdowns", []):
                entities.append(
                    {
                        "entity_type": row["entity_type"],
                        "entity_id": row["entity_id"],
                        "name": row["label"],
                    }
                )
        unique_entities = []
        seen = set()
        for entity in entities:
            identity = (entity["entity_type"], entity["entity_id"])
            if identity not in seen:
                seen.add(identity)
                unique_entities.append(entity)
        facts = []
        for finding in response.key_findings if accepted else []:
            for metric in finding.metrics:
                facts.append(
                    {
                        k: metric.get(k)
                        for k in ("metric", "value", "unit", "numerator", "denominator", "window")
                    }
                )
        conversation.turns.append(
            {
                "question": response.question[:1000],
                "verified_metric_selections": facts[:8],
                "entities": unique_entities[:10],
                "status": response.status,
                "ranking_validated": accepted
                and any(f.claim_type == "ranking" for f in response.key_findings),
                "as_of": str(response.as_of),
                "authority": "Prior selections only; obtain fresh current-run evidence. "
                "No model narrative is retained as a source of truth.",
            }
        )
        conversation.turns = conversation.turns[-4:]
        conversation.touched = time.monotonic()


conversations = Conversations()
