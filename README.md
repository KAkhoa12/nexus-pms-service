## Local Setup

1. Copy `.env.example` to `.env` and set:
- `DATABASE_URL`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`

2. Install dependencies:
```bash
uv sync
```

3. Run migrations:
```bash
alembic upgrade head
```

4. Start API:
```bash
uv run uvicorn main:app --reload --port 8000
```

## Developer Portal Login

- Endpoint login: `POST /api/v1/developer/auth/login`
- Endpoint profile: `GET /api/v1/developer/auth/me`
- Default seeded account after migration:
  - email: `developer@quanlyphongtro.local`
  - password: `Admin123@`
- This account is stored in table `platform_admins` and is isolated from normal tenant users.

## Google Login Flow

- Frontend sends Google ID token to `POST /api/v1/auth/google`.
- Backend verifies token with Google Identity Services.
- Backend identifies user by `google_sub`.
- New Google user:
  - creates tenant + user
  - assigns `ADMIN` role
  - attaches default `FREE` package if no active subscription
- Backend returns app `access_token` + `refresh_token`.

## AI Agent Runtime (Phase 1 - Read Only)

- API query: `POST /api/v1/agents/query`
- API checkpoints: `GET /api/v1/agents/threads/{thread_id}/checkpoints`
- Runtime context luôn lấy từ backend auth middleware (`tenant_id`, `workspace_key`, `permissions`), không lấy từ prompt.
- Phase hiện tại chỉ bật `read_only`.
- LLM mặc định qua Ollama:
  - `standard`: `gpt-oss:120b-cloud`
  - `cheap`: `kimi-k2.5:cloud`
- Cấu hình trong `.env`:
  - `OLLAMA_HOST=http://127.0.0.1:11434` (hoặc endpoint cloud của bạn)
  - `OLLAMA_API_KEY=` (nếu endpoint yêu cầu token)
  - `OLLAMA_MODEL_FALLBACKS=` (danh sách model fallback, phân tách bằng dấu phẩy)
  - `AGENT_RUN_EVENTS_RETENTION_DAYS=30` (xóa event stream cũ hơn N ngày, đặt `0` để tắt)
  - `AGENT_RUN_EVENTS_RETENTION_INTERVAL_MINUTES=30` (chu kỳ dọn dữ liệu)

Sau khi pull code mới, chạy migration:

```bash
alembic upgrade head
```

Ví dụ request:

```json
{
  "message": "Cho tôi KPI vận hành hiện tại",
  "locale": "vi-VN"
}
```

## Dọn dữ liệu agent_run_events cũ

Nếu bảng `agent_run_events` đã phình lớn vì các bản ghi `delta` cũ, chạy script:

```sql
source scripts/sql/cleanup_agent_run_events.sql;
```
