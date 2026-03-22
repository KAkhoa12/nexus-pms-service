from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.modules.agents.state import ExecutionMode


@dataclass(frozen=True)
class AgentConfig:
    default_model: str
    cheap_model: str
    ollama_host: str
    ollama_api_key: str
    ollama_model_fallbacks: str
    max_tool_calls: int
    default_timeout_seconds: int
    retry_limit: int
    enable_write_actions: bool
    require_approval_for_writes: bool
    default_execution_mode: ExecutionMode
    checkpointer_backend: str
    checkpointer_sqlite_path: str
    token_budget: int
    cost_budget_usd: float


def get_agent_config() -> AgentConfig:
    execution_mode = str(settings.AGENT_DEFAULT_EXECUTION_MODE or "read_only").strip()
    if execution_mode not in {"read_only", "propose_write", "approved_write"}:
        execution_mode = "read_only"

    return AgentConfig(
        default_model=settings.AGENT_DEFAULT_MODEL,
        cheap_model=settings.AGENT_CHEAP_MODEL,
        ollama_host=settings.OLLAMA_HOST,
        ollama_api_key=settings.OLLAMA_API_KEY,
        ollama_model_fallbacks=settings.OLLAMA_MODEL_FALLBACKS,
        max_tool_calls=settings.AGENT_MAX_TOOL_CALLS,
        default_timeout_seconds=settings.AGENT_DEFAULT_TIMEOUT_SECONDS,
        retry_limit=settings.AGENT_RETRY_LIMIT,
        enable_write_actions=settings.AGENT_ENABLE_WRITE_ACTIONS,
        require_approval_for_writes=settings.AGENT_REQUIRE_APPROVAL_FOR_WRITES,
        default_execution_mode=execution_mode,  # type: ignore[arg-type]
        checkpointer_backend=settings.AGENT_CHECKPOINTER_BACKEND,
        checkpointer_sqlite_path=settings.AGENT_CHECKPOINTER_SQLITE_PATH,
        token_budget=settings.AGENT_TOKEN_BUDGET,
        cost_budget_usd=settings.AGENT_COST_BUDGET_USD,
    )
