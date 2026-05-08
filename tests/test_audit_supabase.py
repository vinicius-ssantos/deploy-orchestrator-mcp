import httpx

from deploy_orchestrator_mcp.audit import SupabaseAuditLog, audit_log_list, audit_log_status, create_audit_event
from deploy_orchestrator_mcp.redaction import REDACTED


def fixed_now():
    return "2026-05-08T12:00:00+00:00"


def test_supabase_audit_log_record_redacts_and_inserts_row():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = request.json()
        assert body["event_type"] == "provider.credentials.checked"
        assert body["environment"] == "staging"
        assert body["actor"] == "chatgpt"
        assert body["payload"]["metadata"]["token"] == REDACTED
        return httpx.Response(201, json=[{"payload": body["payload"]}])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    audit = SupabaseAuditLog(
        supabase_url="https://example.supabase.co",
        key="service_role_secret",
        client=client,
    )

    event = create_audit_event(
        "provider.credentials.checked",
        {"environment": "staging", "actor": "chatgpt", "token": "secret"},
        now=fixed_now,
    )

    recorded = audit.record(event)

    assert recorded["metadata"]["token"] == REDACTED
    assert requests[0].method == "POST"
    assert requests[0].url == "https://example.supabase.co/rest/v1/audit_events"
    assert requests[0].headers["apikey"] == "service_role_secret"


def test_supabase_audit_log_list_returns_redacted_payloads

():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert "order=created_at.desc" in str(request.url)
        return httpx.Response(
            200,
            json=[
                {
                    "payload": {
                        "type": "render.deploy",
                        "created_at": fixed_now(),
                        "metadata": {"database_url": "postgres://user:pass@example.com/db"},
                    }
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    audit = SupabaseAuditLog(
        supabase_url="https://example.supabase.co",
        key="service_role_secret",
        client=client,
    )

    events = audit.list(limit=1)

    assert events[0]["type"] == "render.deploy"
    assert events[0]["metadata"]["database_url"] == REDACTED


def test_audit_log_status_supabase_backend_from_env(monkeypatch):
    monkeypatch.deletenv("MCP_AUDIT_LOG_PATH", raising=False)
    monkeypatch.setenv("MCP_AUDIT_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service_role_secret")

    status = audit_log_status()

    assert status["enabled"] is True
    assert status["backend"] == "supabase"
    assert status["table"] == "audit_events"
    assert "service_role_secret" not in str(status)


def test_audit_log_list_supabase_returns_error_when_misconfigured(monkeypatch):
    monkeypatch.deletenv("MCP_AUDIT_LOG_PATH", raising=False)
    monkeypatch.setenv("MCP_AUDIT_BACKEND", "supabase")
    monkeypatch.deletenv("SUPABASE_URL", raising=False)
    monkeypatch.deletenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    result = audit_log_list()

    assert result["enabled"] is False
    assert result["backend"] == "supabase"
    assert result["events"] == []
