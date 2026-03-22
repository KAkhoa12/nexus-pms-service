from __future__ import annotations

from app.modules.agents.state import AgentState


def has_grounded_facts(state: AgentState) -> bool:
    facts = state.get("retrieved_facts") or []
    return len(facts) > 0
