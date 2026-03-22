from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from ollama import Client

from app.modules.agents.config import AgentConfig

logger = logging.getLogger(__name__)
DEFAULT_HISTORY_WINDOW = 16
MAX_HISTORY_WINDOW = 40


@dataclass
class ToolDefinition:
    name: str
    description: str
    json_schema: dict[str, Any]


@dataclass
class ToolCallRecord:
    tool_name: str
    ok: bool
    payload: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class ToolCallExecution:
    called: bool
    calls: list[ToolCallRecord]
    assistant_message: str | None = None


@dataclass
class AgentLlmClient:
    host: str
    api_key: str
    model: str
    fallback_models: tuple[str, ...] = ()
    timeout_seconds: int = 20

    @classmethod
    def from_config(
        cls,
        config: AgentConfig,
        *,
        model_tier: str = "standard",
    ) -> AgentLlmClient:
        tier = (model_tier or "standard").strip().lower()
        selected_model = config.cheap_model if tier == "cheap" else config.default_model
        fallback_models = tuple(
            item.strip()
            for item in str(config.ollama_model_fallbacks or "").split(",")
            if item.strip()
        )
        return cls(
            host=str(config.ollama_host or "").strip(),
            api_key=str(config.ollama_api_key or "").strip(),
            model=selected_model,
            fallback_models=fallback_models,
            timeout_seconds=config.default_timeout_seconds,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.model.strip())

    def _candidate_models(self) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for raw in (self.model, *self.fallback_models):
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return tuple(ordered)

    def _build_client(self) -> Client:
        kwargs: dict[str, Any] = {
            "timeout": self.timeout_seconds,
        }
        if self.api_key:
            kwargs["headers"] = {"Authorization": f"Bearer {self.api_key}"}
        host = self.host or None
        return Client(host=host, **kwargs)

    def generate_final_answer(
        self,
        *,
        route: str,
        user_message: str,
        locale: str,
        task_plan: list[str],
        tool_results: list[dict[str, Any]],
        fallback_answer: str,
        conversation_messages: list[dict[str, str]] | None = None,
        history_window: int = DEFAULT_HISTORY_WINDOW,
        on_delta: Callable[[str], bool] | None = None,
    ) -> str | None:
        if not self.enabled:
            return None

        last_error: Exception | None = None
        try:
            client = self._build_client()
            tool_snapshot = _trim_tool_results(tool_results)
            history_messages = _build_conversation_context_messages(
                conversation_messages,
                history_window=history_window,
                current_user_message=user_message,
            )
            request_messages = [
                {
                    "role": "system",
                    "content": (
                        "Ban la tro ly phan tich van hanh cho he thong quan ly phong tro. "
                        "Chi duoc dua tren du lieu tool da cung cap. "
                        "Khong duoc tu suy dien quyen truy cap, khong bịa so lieu. "
                        "Neu thieu du lieu, phai noi ro la thieu du lieu. "
                        "Tra loi ngan gon, de hieu, dung tieng Viet."
                    ),
                },
                *history_messages,
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "locale": locale,
                            "route": route,
                            "question": user_message,
                            "task_plan": task_plan,
                            "tool_results": tool_snapshot,
                            "fallback_answer": fallback_answer,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ]

            for model_name in self._candidate_models():
                try:
                    if on_delta is not None:
                        stream = client.chat(
                            model=model_name,
                            messages=request_messages,
                            stream=True,
                        )
                        chunks: list[str] = []
                        for chunk in stream:
                            delta_text = _extract_stream_chunk_text(chunk)
                            if not delta_text:
                                continue
                            chunks.append(delta_text)
                            try:
                                should_continue = on_delta(delta_text)
                            except Exception as callback_exc:
                                logger.warning(
                                    "agent_llm_delta_callback_failed: %s",
                                    callback_exc,
                                )
                                should_continue = False
                            if not should_continue:
                                break
                        streamed_text = "".join(chunks).strip()
                        if streamed_text:
                            return streamed_text
                    else:
                        completion = client.chat(
                            model=model_name,
                            messages=request_messages,
                            stream=False,
                        )
                        content = _extract_content(completion)
                        if content:
                            return content
                except Exception as exc:
                    last_error = exc
                    continue
            return None
        except Exception as exc:
            last_error = exc
        if last_error is not None:
            logger.warning(
                "agent_llm_generate_failed: %s", _format_llm_error(last_error)
            )
        return None

    def execute_tool_calls(
        self,
        *,
        route: str,
        user_message: str,
        locale: str,
        tool_definitions: list[ToolDefinition],
        max_calls: int,
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        conversation_messages: list[dict[str, str]] | None = None,
        history_window: int = DEFAULT_HISTORY_WINDOW,
    ) -> ToolCallExecution:
        if not self.enabled or not tool_definitions:
            return ToolCallExecution(called=False, calls=[])

        last_error: Exception | None = None
        try:
            client = self._build_client()
            system_prompt = (
                "Ban la bo dieu phoi tool cho he thong quan ly phong tro. "
                "Chi duoc chon tool tu danh sach backend cap. "
                "Khong tu bịa du lieu. Neu thong tin dau vao thieu, "
                "van co the goi tool voi tham so mac dinh hop ly."
            )
            if str(route or "").strip().lower() == "supervisor":
                system_prompt = (
                    "Ban la bo dieu phoi tool cap supervisor cho he thong quan ly phong tro. "
                    "Chi goi tool khi cau hoi can du lieu nghiep vu co the kiem chung. "
                    "Neu cau hoi la giao tiep thong thuong, chao hoi, danh tinh tro ly, "
                    "hoac yeu cau ghi nho thong tin ca nhan ma chua co memory-write flow, "
                    "thi KHONG goi tool."
                )
            history_messages = _build_conversation_context_messages(
                conversation_messages,
                history_window=history_window,
                current_user_message=user_message,
            )
            request_messages = [
                {"role": "system", "content": system_prompt},
                *history_messages,
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "route": route,
                            "locale": locale,
                            "question": user_message,
                            "instruction": "Chon tool phu hop nhat va tao arguments JSON.",
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ]
            request_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": definition.name,
                        "description": definition.description,
                        "parameters": definition.json_schema,
                    },
                }
                for definition in tool_definitions
            ]

            response: Any | None = None
            for model_name in self._candidate_models():
                try:
                    response = client.chat(
                        model=model_name,
                        messages=request_messages,
                        tools=request_tools,
                        stream=False,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    continue

            if response is None:
                return ToolCallExecution(called=False, calls=[])

            message = _extract_message(response)
            assistant_message = _extract_message_content(message)
            tool_calls = _extract_tool_calls(message)
            if not tool_calls:
                return ToolCallExecution(
                    called=False,
                    calls=[],
                    assistant_message=assistant_message,
                )

            allowed_names = {item.name for item in tool_definitions}
            records: list[ToolCallRecord] = []
            for call in tool_calls[: max(1, max_calls)]:
                function_obj = _to_dict(call.get("function"))
                tool_name = str(function_obj.get("name") or "").strip()
                raw_args = function_obj.get("arguments")

                if not tool_name:
                    records.append(
                        ToolCallRecord(
                            tool_name="unknown",
                            ok=False,
                            error_code="tool_name_missing",
                            error_message="Tool call is missing function name.",
                        )
                    )
                    continue
                if tool_name not in allowed_names:
                    records.append(
                        ToolCallRecord(
                            tool_name=tool_name,
                            ok=False,
                            error_code="tool_not_whitelisted",
                            error_message=f"Tool {tool_name} is not in allowed tool list.",
                        )
                    )
                    continue

                parsed_args: dict[str, Any] = {}
                if isinstance(raw_args, dict):
                    parsed_args = raw_args
                elif isinstance(raw_args, str) and raw_args.strip():
                    try:
                        candidate = json.loads(raw_args)
                        if isinstance(candidate, dict):
                            parsed_args = candidate
                    except Exception:
                        records.append(
                            ToolCallRecord(
                                tool_name=tool_name,
                                ok=False,
                                error_code="tool_args_invalid_json",
                                error_message=f"Arguments for {tool_name} are not valid JSON.",
                            )
                        )
                        continue

                try:
                    output = tool_executor(tool_name, parsed_args)
                    records.append(
                        ToolCallRecord(
                            tool_name=tool_name,
                            ok=True,
                            payload=_normalize_payload(output),
                        )
                    )
                except Exception as exc:
                    records.append(
                        ToolCallRecord(
                            tool_name=tool_name,
                            ok=False,
                            error_code=getattr(exc, "code", "tool_execution_failed"),
                            error_message=str(exc),
                        )
                    )

            return ToolCallExecution(
                called=bool(records),
                calls=records,
                assistant_message=assistant_message,
            )
        except Exception as exc:
            last_error = exc
        if last_error is not None:
            logger.warning(
                "agent_llm_tool_call_failed: %s", _format_llm_error(last_error)
            )
        return ToolCallExecution(called=False, calls=[])


def _trim_tool_results(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not tool_results:
        return []
    trimmed: list[dict[str, Any]] = []
    for item in tool_results[-3:]:
        trimmed.append(
            {
                "tool_name": item.get("tool_name"),
                "ok": item.get("ok"),
                "payload": item.get("payload"),
                "error_code": item.get("error_code"),
                "error_message": item.get("error_message"),
            }
        )
    return trimmed


def _extract_content(completion: Any) -> str | None:
    message = _extract_message(completion)
    content = str(message.get("content") or "").strip()
    return content or None


def _extract_stream_chunk_text(chunk: Any) -> str:
    message = _extract_message(chunk)
    return str(message.get("content") or "")


def _extract_message(response: Any) -> dict[str, Any]:
    data = _to_dict(response)
    message = data.get("message")
    return _to_dict(message)


def _extract_message_content(message: dict[str, Any]) -> str | None:
    content = str(message.get("content") or "").strip()
    return content or None


def _extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    raw = message.get("tool_calls")
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        call = _to_dict(item)
        function_obj = _to_dict(call.get("function"))
        if function_obj:
            normalized.append({"function": function_obj})
    return normalized


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _normalize_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {"value": str(value)}


def _format_llm_error(exc: Exception) -> str:
    raw = str(exc or "").strip()
    return raw or "unknown_llm_error"


def _build_conversation_context_messages(
    conversation_messages: list[dict[str, str]] | None,
    *,
    history_window: int,
    current_user_message: str,
) -> list[dict[str, str]]:
    if not conversation_messages:
        return []

    limit = max(
        1, min(int(history_window or DEFAULT_HISTORY_WINDOW), MAX_HISTORY_WINDOW)
    )
    normalized: list[dict[str, str]] = []
    for item in conversation_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        normalized.append({"role": role, "content": content})

    if not normalized:
        return []

    windowed = normalized[-limit:]
    latest_user = str(current_user_message or "").strip()
    if (
        latest_user
        and windowed
        and windowed[-1]["role"] == "user"
        and windowed[-1]["content"].strip() == latest_user
    ):
        windowed = windowed[:-1]
    return windowed
