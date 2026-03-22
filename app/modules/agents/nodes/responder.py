from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from app.modules.agents.state import AgentState


def compose_final_answer(
    state: AgentState,
    *,
    llm_client: Any | None = None,
    on_delta: Callable[[str], bool] | None = None,
) -> str:
    deterministic_answer = _compose_deterministic_answer(state)
    if str(state.get("intent") or "").strip().lower() == "memory_request":
        return deterministic_answer
    if llm_client is None:
        return deterministic_answer

    messages = state.get("messages") or []
    user_message = ""
    for item in reversed(messages):
        if item.get("role") == "user":
            user_message = str(item.get("content", "")).strip()
            break

    try:
        llm_answer = llm_client.generate_final_answer(
            route=str(state.get("route") or "unknown"),
            user_message=user_message,
            locale=str(state.get("runtime_context", {}).get("locale", "vi-VN")),
            task_plan=list(state.get("task_plan") or []),
            tool_results=list(state.get("tool_results") or []),
            fallback_answer=deterministic_answer,
            conversation_messages=[
                {
                    "role": str(item.get("role", "")),
                    "content": str(item.get("content", "")),
                }
                for item in messages
                if isinstance(item, dict)
            ],
            on_delta=on_delta,
        )
    except Exception:
        llm_answer = None
    if isinstance(llm_answer, str) and llm_answer.strip():
        return llm_answer.strip()
    return deterministic_answer


def _compose_deterministic_answer(state: AgentState) -> str:
    intent = str(state.get("intent") or "").strip().lower()
    if intent == "general_chat":
        return (
            "Tôi là AI trợ lý cho hệ thống quản lý phòng trọ. "
            "Tôi hỗ trợ tốt các câu hỏi về KPI vận hành, thành viên team, trạng thái phòng, "
            "hóa đơn/công nợ và tra cứu tài liệu nội bộ theo tenant/workspace hiện tại."
        )
    if intent == "memory_request":
        execution_mode = str(
            (state.get("runtime_context") or {}).get("execution_mode", "read_only")
        )
        if execution_mode == "read_only":
            return (
                "Hiện agent đang ở chế độ read_only nên chưa thể ghi nhớ thông tin cá nhân mới. "
                "Bạn có thể lưu thông tin này trong hồ sơ người dùng, hoặc bật flow propose_write/approved_write "
                "khi triển khai memory write an toàn."
            )
        return (
            "Yêu cầu ghi nhớ đã được nhận, nhưng tính năng memory write chưa bật trong phiên bản hiện tại. "
            "Hiện agent chỉ lưu ngữ cảnh hội thoại theo thread để phục vụ trả lời."
        )

    route = state.get("route")
    tool_results = state.get("tool_results") or []
    if not tool_results:
        return (
            "Không có dữ liệu tool để trả lời. Vui lòng thử lại với câu hỏi cụ thể hơn."
        )

    latest = tool_results[-1]
    if not latest.get("ok", False):
        return (
            f"Không thể lấy dữ liệu từ tool `{latest.get('tool_name', 'unknown')}`. "
            f"Lý do: {latest.get('error_message', 'Lỗi không xác định')}."
        )

    tool_name = str(latest.get("tool_name") or "")
    payload = latest.get("payload") or {}
    if tool_name == "get_tenant_kpi":
        return _compose_reporting(payload)
    if tool_name == "get_room_status_overview":
        return _compose_room_status_overview(payload)
    if tool_name == "get_team_members":
        return _compose_team_members(payload)
    if tool_name == "list_overdue_invoices":
        return _compose_billing(payload)
    if tool_name == "get_invoice_installments":
        return _compose_invoice_installments(payload)
    if tool_name == "search_customers":
        return _compose_customers(payload)
    if tool_name == "get_contracts":
        return _compose_contracts(payload)
    if tool_name == "search_internal_knowledge":
        return _compose_knowledge(payload)
    if tool_name == "dispatch_team_notification":
        return _compose_team_notification(payload)

    if route == "customer":
        return _compose_customers(payload)
    if route == "contract":
        return _compose_contracts(payload)
    if route == "room":
        return _compose_room_status_overview(payload)
    if route == "reporting":
        return _compose_reporting(payload)
    if route == "billing":
        return _compose_billing(payload)
    if route == "knowledge":
        return _compose_knowledge(payload)
    return "Đã nhận yêu cầu bảo trì. Bản read-only hiện chỉ trả về dữ liệu tham khảo."


def _compose_reporting(payload: dict[str, Any]) -> str:
    return (
        "KPI hiện tại của tenant:\n"
        f"- Tổng số phòng: {payload.get('total_rooms', 0)}\n"
        f"- Phòng đang thuê: {payload.get('rented_rooms', 0)}\n"
        f"- Tỷ lệ lấp đầy: {payload.get('occupancy_rate_percent', 0)}%\n"
        f"- Hóa đơn quá hạn: {payload.get('overdue_invoices', 0)}\n"
        f"- Tổng công nợ quá hạn: {_fmt_money(payload.get('overdue_amount'))}\n"
        f"- Doanh thu đã thu tháng này: {_fmt_money(payload.get('paid_revenue_current_month'))}"
    )


def _compose_room_status_overview(payload: dict[str, Any]) -> str:
    status_summary = payload.get("status_summary") or []
    branches = payload.get("branches") or []
    areas = payload.get("areas") or []
    buildings = payload.get("buildings") or []

    summary_text = ", ".join(
        f"{item.get('status', '-')}: {item.get('count', 0)}" for item in status_summary
    )
    if not summary_text:
        summary_text = "Không có dữ liệu trạng thái phòng"

    branch_preview = ", ".join(
        f"{item.get('branch_id')}:{item.get('branch_name')}" for item in branches[:10]
    )
    area_preview = ", ".join(
        f"{item.get('area_id')}:{item.get('area_name')}" for item in areas[:10]
    )
    building_preview = ", ".join(
        f"{item.get('building_id')}:{item.get('building_name')}"
        for item in buildings[:10]
    )

    lines = [
        "Tổng quan trạng thái phòng:",
        f"- Tổng số phòng: {payload.get('total_rooms', 0)}",
        f"- Trạng thái: {summary_text}",
        f"- Danh sách chi nhánh: {branch_preview or 'Không có'}",
        f"- Danh sách khu vực: {area_preview or 'Không có'}",
        f"- Danh sách tòa nhà: {building_preview or 'Không có'}",
    ]
    rooms = payload.get("rooms") or []
    if rooms:
        room_preview = ", ".join(
            f"{item.get('room_code')}({item.get('status')})" for item in rooms[:15]
        )
        lines.append(f"- Mẫu danh sách phòng: {room_preview}")
    return "\n".join(lines)


def _compose_team_members(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    if not items:
        return "Không tìm thấy team hoặc bạn không có quyền xem thành viên team."

    lines = [f"Bạn có thể xem {payload.get('total_teams', len(items))} team:"]
    for index, team in enumerate(items[:10], start=1):
        members = team.get("members") or []
        member_preview = ", ".join(
            f"{member.get('full_name')}[{member.get('member_role')}]"
            for member in members[:8]
        )
        lines.append(
            f"{index}. Team {team.get('team_id')} - {team.get('team_name')} | "
            f"{team.get('member_count', 0)} thành viên | {member_preview or 'Không có thành viên'}"
        )
    return "\n".join(lines)


def _compose_billing(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    if not items:
        return "Không có hóa đơn quá hạn theo điều kiện hiện tại."

    lines: list[str] = []
    total_outstanding = Decimal("0")
    for idx, item in enumerate(items[:10], start=1):
        outstanding = Decimal(str(item.get("outstanding_amount", "0")))
        total_outstanding += outstanding
        lines.append(
            f"{idx}. HĐ {item.get('invoice_id')} | Phòng {item.get('room_code') or '-'} | "
            f"Khách {item.get('renter_name') or '-'} | "
            f"Quá hạn {item.get('days_overdue', 0)} ngày | "
            f"Còn nợ {_fmt_money(outstanding)}"
        )

    return (
        f"Có {payload.get('total_items', len(items))} hóa đơn quá hạn. "
        f"Tổng nợ (top hiển thị): {_fmt_money(total_outstanding)}\n" + "\n".join(lines)
    )


def _compose_invoice_installments(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    if not items:
        return "Không tìm thấy kỳ hạn hóa đơn theo khách hàng hoặc mã hợp đồng đã nhập."

    lines = [
        f"Tìm thấy {payload.get('total_matches', len(items))} hợp đồng phù hợp.",
    ]
    for idx, lease in enumerate(items[:5], start=1):
        installments = lease.get("installments") or []
        next_installments = installments[:5]
        installment_preview = "; ".join(
            (
                f"HĐơn {item.get('invoice_id')} "
                f"(kỳ {item.get('period_month')}, "
                f"status {item.get('status')}, "
                f"nợ {_fmt_money(Decimal(str(item.get('outstanding_amount', 0))))})"
            )
            for item in next_installments
        )
        lines.append(
            f"{idx}. {lease.get('lease_code')} | Khách {lease.get('renter_name')} "
            f"({lease.get('renter_phone') or '-'}) | Phòng {lease.get('room_code') or '-'} | "
            f"Trạng thái HĐ {lease.get('lease_status')}."
        )
        lines.append(f"   Kỳ hạn gần nhất: {installment_preview or 'Không có kỳ hạn'}")
    return "\n".join(lines)


def _compose_customers(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    if not items:
        return "Không tìm thấy khách hàng phù hợp trong tenant/workspace hiện tại."

    lines = [f"Tìm thấy {payload.get('total_items', len(items))} khách hàng phù hợp:"]
    for idx, item in enumerate(items[:10], start=1):
        lines.append(
            f"{idx}. KH#{item.get('renter_id')} - {item.get('full_name')} | "
            f"SĐT {item.get('phone') or '-'} | Email {item.get('email') or '-'} | "
            f"HĐ active {item.get('active_lease_count', 0)}/{item.get('total_lease_count', 0)} | "
            f"Công nợ {_fmt_money(item.get('outstanding_amount', 0))}"
        )
    return "\n".join(lines)


def _compose_contracts(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    if not items:
        return "Không tìm thấy hợp đồng phù hợp trong tenant/workspace hiện tại."

    lines = [f"Tìm thấy {payload.get('total_items', len(items))} hợp đồng:"]
    for idx, item in enumerate(items[:10], start=1):
        lines.append(
            f"{idx}. {item.get('lease_code')} | Trạng thái {item.get('lease_status')} | "
            f"Khách {item.get('renter_name')} ({item.get('renter_phone') or '-'}) | "
            f"Phòng {item.get('room_code') or '-'} | "
            f"Giá thuê {_fmt_money(item.get('rent_price', 0))} | "
            f"Còn nợ {_fmt_money(item.get('outstanding_amount', 0))}"
        )
    return "\n".join(lines)


def _compose_team_notification(payload: dict[str, Any]) -> str:
    if payload.get("draft_only"):
        return (
            "Đã tạo nháp thông báo (chưa gửi) do đang ở chế độ propose_write:\n"
            f"- Team: {payload.get('team_id')}\n"
            f"- Tiêu đề: {payload.get('title')}\n"
            f"- Số người nhận: {payload.get('total_recipients', 0)}"
        )
    if payload.get("sent"):
        return (
            "Đã gửi thông báo cho team thành công:\n"
            f"- Notification ID: {payload.get('notification_id')}\n"
            f"- Team: {payload.get('team_id')}\n"
            f"- Số người nhận: {payload.get('total_recipients', 0)}"
        )
    return "Thông báo chưa được gửi."


def _compose_knowledge(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    if not items:
        return "Không tìm thấy tài liệu nội bộ phù hợp với truy vấn."
    lines = []
    for idx, item in enumerate(items[:5], start=1):
        lines.append(
            f"{idx}. [{item.get('source_type')}] {item.get('title')}\n"
            f"   {item.get('snippet')}"
        )
    return "Kết quả tra cứu tài liệu nội bộ:\n" + "\n".join(lines)


def _fmt_money(value: Any) -> str:
    try:
        amount = Decimal(str(value or 0))
    except Exception:
        amount = Decimal("0")
    return f"{amount:,.0f} VND"
