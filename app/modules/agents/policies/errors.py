from __future__ import annotations


class AgentPolicyError(Exception):
    def __init__(self, message: str, *, code: str = "policy_error") -> None:
        super().__init__(message)
        self.code = code
