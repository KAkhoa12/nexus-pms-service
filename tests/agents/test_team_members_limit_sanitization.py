from __future__ import annotations

from datetime import datetime, timezone

from app.modules.agents.graphs.reporting import _execute_reporting_tool
from app.modules.agents.graphs.supervisor import _execute_supervisor_tool
from app.modules.agents.policies.permissions import TOOL_GET_TEAM_MEMBERS
from app.modules.agents.schemas.tools import TeamMembersOutput


class _FakeGateway:
    def __init__(self) -> None:
        self.payloads = []

    def get_team_members(self, payload, *, graph_name: str, node_name: str):
        self.payloads.append(payload)
        return TeamMembersOutput(
            total_teams=0,
            items=[],
            generated_at=datetime.now(timezone.utc),
        )


def test_supervisor_tool_clamps_team_members_limits() -> None:
    gateway = _FakeGateway()
    _ = _execute_supervisor_tool(
        tool_name=TOOL_GET_TEAM_MEMBERS,
        args={"team_id": "7", "team_limit": 100, "member_limit": 999},
        user_message="Trong team toi bao gom ai?",
        tool_gateway=gateway,
    )

    payload = gateway.payloads[0]
    assert payload.team_id == 7
    assert payload.team_limit == 50
    assert payload.member_limit == 500


def test_reporting_tool_clamps_invalid_team_members_limits() -> None:
    gateway = _FakeGateway()
    _ = _execute_reporting_tool(
        tool_name="get_team_members",
        args={"team_limit": "invalid", "member_limit": None},
        user_message="Trong team toi bao gom ai?",
        tool_gateway=gateway,
    )

    payload = gateway.payloads[0]
    assert payload.team_id is None
    assert payload.team_limit == 10
    assert payload.member_limit == 200
