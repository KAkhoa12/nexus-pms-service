from __future__ import annotations

import re
import unicodedata

from app.modules.agents.state import AgentRoute

REPORTING_KEYWORDS = {
    "kpi",
    "tong quan",
    "tổng quan",
    "ti le lap day",
    "tỷ lệ lấp đầy",
    "doanh thu",
    "thong ke",
    "thống kê",
    "occupancy",
    "report",
    "trạng thái phòng",
    "trang thai phong",
    "phòng",
    "room",
    "chi nhánh",
    "chi nhanh",
    "khu vực",
    "khu vuc",
    "tòa",
    "toa",
    "building",
    "team",
    "nhóm",
    "nhom",
    "thành viên",
    "thanh vien",
    "member",
    "người",
    "nguoi",
}

BILLING_KEYWORDS = {
    "hóa đơn",
    "hoa don",
    "công nợ",
    "cong no",
    "overdue",
    "quá hạn",
    "thanh toán",
    "thu tiền",
    "kỳ hạn",
    "ky han",
    "hợp đồng",
    "hop dong",
    "mã hợp đồng",
    "ma hop dong",
    "khách hàng",
    "khach hang",
    "installment",
    "lịch thanh toán",
    "lich thanh toan",
}

CUSTOMER_KEYWORDS = {
    "khach",
    "khach hang",
    "khach thue",
    "renter",
    "customer",
    "so dien thoai",
    "sdt",
}

CONTRACT_KEYWORDS = {
    "hop dong",
    "hợp đồng",
    "lease",
    "contract",
    "ma hop dong",
    "mã hợp đồng",
    "hd-",
}

ROOM_KEYWORDS = {
    "trang thai phong",
    "trạng thái phòng",
    "phong",
    "phòng",
    "room",
    "toa",
    "tòa",
    "building",
    "chi nhanh",
    "chi nhánh",
    "khu vuc",
    "khu vực",
}

MAINTENANCE_KEYWORDS = {
    "bảo trì",
    "bao tri",
    "ticket",
    "sự cố",
    "su co",
    "work order",
    "thông báo",
    "thong bao",
    "notify",
    "notification",
}

KNOWLEDGE_KEYWORDS = {
    "quy trinh",
    "quy trình",
    "quy dinh",
    "chính sách",
    "chinh sach",
    "hướng dẫn",
    "huong dan",
    "sop",
    "tài liệu",
    "tai lieu",
}

GENERAL_CHAT_KEYWORDS = {
    "xin chao",
    "chao",
    "hello",
    "hi",
    "hey",
    "ban la ai",
    "ban la gi",
    "co the lam gi",
    "giup duoc gi",
    "cam on",
    "thanks",
    "thank you",
}

MEMORY_REQUEST_KEYWORDS = {
    "ghi nho",
    "remember",
    "goi toi la",
    "goi minh la",
    "luu thong tin",
    "nho toi la",
    "nho minh la",
    "ten toi la",
    "ten minh la",
    "toi la",
    "minh la",
    "toi ten la",
    "minh ten la",
}

TEAM_SCOPE_HINTS = {
    "team",
    "nhóm",
    "nhom",
    "workspace",
    "thanh vien",
    "thành viên",
    "member",
}

TEAM_MEMBER_ASK_HINTS = {
    "bao nhiêu",
    "bao nhieu",
    "có ai",
    "co ai",
    "danh sách",
    "danh sach",
    "liệt kê",
    "liet ke",
    "bao gồm",
    "bao gom",
    "người",
    "nguoi",
}


def classify_intent(message: str) -> tuple[str, AgentRoute]:
    normalized = _normalize(message)
    if _looks_like_team_member_query(normalized):
        return "reporting_team_members_query", "reporting"
    if _contains_any(normalized, CUSTOMER_KEYWORDS):
        return "customer_lookup_query", "customer"
    if _contains_any(normalized, CONTRACT_KEYWORDS):
        return "contract_lookup_query", "contract"
    if _contains_any(normalized, ROOM_KEYWORDS):
        return "room_overview_query", "room"
    if _contains_any(normalized, REPORTING_KEYWORDS):
        return "reporting_kpi_query", "reporting"
    if _contains_any(normalized, BILLING_KEYWORDS):
        return "billing_overdue_query", "billing"
    if _contains_any(normalized, MAINTENANCE_KEYWORDS):
        return "maintenance_query", "maintenance"
    if _contains_any(normalized, KNOWLEDGE_KEYWORDS):
        return "knowledge_query", "knowledge"
    if _looks_like_memory_request(normalized):
        return "memory_request", "knowledge"
    if _looks_like_general_chat(normalized):
        return "general_chat", "knowledge"
    # Fallback an toan: neu khong match domain nghiep vu thi xu ly nhu hoi thoai thong thuong
    # de tranh tra loi "khong tim thay tai lieu" cho cac cau ngoai le.
    return "general_chat", "knowledge"


def build_task_plan(route: AgentRoute) -> list[str]:
    if route == "customer":
        return [
            "Xác định tiêu chí tìm khách hàng từ câu hỏi",
            "Tra cứu danh sách khách theo tenant hiện tại",
            "Trả về thông tin khách và trạng thái công nợ tóm tắt",
        ]
    if route == "contract":
        return [
            "Xác định khách hàng hoặc mã hợp đồng cần tra cứu",
            "Tra cứu hợp đồng theo tenant và bộ lọc",
            "Tổng hợp trạng thái hợp đồng và số tiền còn nợ",
        ]
    if route == "room":
        return [
            "Phân tích filter chi nhánh/khu vực/tòa nhà",
            "Lấy tổng quan trạng thái phòng trong tenant hiện tại",
            "Trả danh sách chi nhánh, khu vực, tòa nhà và phòng khi cần",
        ]
    if route == "reporting":
        return [
            "Kiểm tra quyền tool KPI theo tenant hiện tại",
            "Lấy số liệu tổng hợp phòng/team theo ngữ cảnh câu hỏi",
            "Trả kết quả có kèm danh sách chi nhánh/khu vực/tòa nhà khi cần",
        ]
    if route == "billing":
        return [
            "Kiểm tra quyền tool hóa đơn/công nợ",
            "Nếu hỏi kỳ hạn thì truy xuất kỳ thanh toán theo khách hàng/hợp đồng",
            "Nếu không thì trả danh sách hóa đơn quá hạn",
        ]
    if route == "knowledge":
        return [
            "Tra cứu tài liệu nội bộ theo từ khóa",
            "Ưu tiên tài liệu tenant trước tài liệu global",
            "Trả lời có trích nguồn nội bộ",
        ]
    return [
        "Kiểm tra yêu cầu thông báo hoặc bảo trì",
        "Nếu là thông báo thì chuẩn bị/gửi theo team có quyền",
        "Nếu không phù hợp thì trả trạng thái chưa hỗ trợ",
    ]


def _normalize(value: str) -> str:
    raw = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_marks = "".join(ch for ch in raw if not unicodedata.combining(ch))
    without_marks = without_marks.replace("đ", "d").replace("Đ", "d")
    cleaned = re.sub(r"[^a-z0-9]+", " ", without_marks)
    return " ".join(cleaned.split())


def _contains_any(value: str, keywords: set[str]) -> bool:
    return any(keyword in value for keyword in keywords)


def _looks_like_team_member_query(value: str) -> bool:
    has_team_scope = _contains_any(value, TEAM_SCOPE_HINTS)
    has_member_ask = _contains_any(value, TEAM_MEMBER_ASK_HINTS)
    return has_team_scope and has_member_ask


def _looks_like_general_chat(value: str) -> bool:
    if not value:
        return False
    has_domain_keyword = (
        _contains_any(value, REPORTING_KEYWORDS)
        or _contains_any(value, CUSTOMER_KEYWORDS)
        or _contains_any(value, CONTRACT_KEYWORDS)
        or _contains_any(value, ROOM_KEYWORDS)
        or _contains_any(value, BILLING_KEYWORDS)
        or _contains_any(value, MAINTENANCE_KEYWORDS)
        or _contains_any(value, KNOWLEDGE_KEYWORDS)
    )
    if has_domain_keyword:
        return False
    return _contains_any(value, GENERAL_CHAT_KEYWORDS)


def _looks_like_memory_request(value: str) -> bool:
    if not value:
        return False
    return _contains_any(value, MEMORY_REQUEST_KEYWORDS)
