"""Compatibility shim for legacy `server/agent` path.

The production graph runtime lives in `app.modules.agents.graphs`.
"""

from app.modules.agents.graphs.supervisor import build_supervisor_executor  # noqa: F401
