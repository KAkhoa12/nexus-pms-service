from __future__ import annotations

from app.modules.agents.policies.errors import AgentPolicyError
from app.modules.agents.state import ExecutionMode

READ_ONLY_MODE: ExecutionMode = "read_only"
PROPOSE_WRITE_MODE: ExecutionMode = "propose_write"
APPROVED_WRITE_MODE: ExecutionMode = "approved_write"
ALL_EXECUTION_MODES: set[str] = {
    READ_ONLY_MODE,
    PROPOSE_WRITE_MODE,
    APPROVED_WRITE_MODE,
}


def normalize_execution_mode(
    *,
    requested_mode: str | None,
    default_mode: ExecutionMode,
    enable_write_actions: bool,
) -> ExecutionMode:
    mode = (requested_mode or default_mode or READ_ONLY_MODE).strip().lower()
    if mode not in ALL_EXECUTION_MODES:
        mode = READ_ONLY_MODE

    if not enable_write_actions and mode != READ_ONLY_MODE:
        return READ_ONLY_MODE
    return mode  # type: ignore[return-value]


def requires_approval_for_mode(mode: ExecutionMode) -> bool:
    return mode in {PROPOSE_WRITE_MODE, APPROVED_WRITE_MODE}


def ensure_write_allowed(mode: ExecutionMode) -> None:
    if mode == READ_ONLY_MODE:
        raise AgentPolicyError(
            "Execution mode read_only does not allow write actions",
            code="read_only_mode",
        )
