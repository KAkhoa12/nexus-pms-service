from __future__ import annotations

from app.modules.agents.nodes.responder import compose_final_answer


class _FakeLlmClient:
    def __init__(self, answer: str | None) -> None:
        self.answer = answer
        self.called = False

    def generate_final_answer(self, **kwargs) -> str | None:
        self.called = True
        return self.answer


def _state() -> dict:
    return {
        "route": "reporting",
        "runtime_context": {"locale": "vi-VN"},
        "messages": [{"role": "user", "content": "Cho toi KPI"}],
        "tool_results": [
            {
                "tool_name": "get_tenant_kpi",
                "ok": True,
                "payload": {
                    "total_rooms": 10,
                    "rented_rooms": 6,
                    "occupancy_rate_percent": 60,
                    "overdue_invoices": 2,
                    "overdue_amount": 1000000,
                    "paid_revenue_current_month": 3000000,
                },
            }
        ],
        "task_plan": [],
    }


def test_compose_final_answer_prefers_llm_when_available() -> None:
    llm = _FakeLlmClient("Tra loi tu LLM")
    answer = compose_final_answer(_state(), llm_client=llm)
    assert llm.called is True
    assert answer == "Tra loi tu LLM"


def test_compose_final_answer_fallback_when_llm_returns_none() -> None:
    llm = _FakeLlmClient(None)
    answer = compose_final_answer(_state(), llm_client=llm)
    assert llm.called is True
    assert "KPI hiện tại của tenant" in answer
