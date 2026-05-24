from deploy_orchestrator_mcp.app_logs import (
    MAX_TAIL,
    app_get_build_logs,
    app_get_runtime_logs,
    app_search_logs,
)


def test_app_get_runtime_logs_filters_query_and_redacts():
    captured = {}

    def fetcher(*, service_id, tail):
        captured["service_id"] = service_id
        captured["tail"] = tail
        return {
            "lines": [
                {"timestamp": "2026-05-24T00:00:00Z", "message": "INFO boot ok"},
                {"timestamp": "2026-05-24T00:00:01Z", "message": "ERROR token=super-secret failure"},
            ],
            "truncated": False,
        }

    result = app_get_runtime_logs(
        provider="render",
        service_id="srv-123",
        tail=100,
        query="failure",
        fetcher=fetcher,
    )

    assert captured == {"service_id": "srv-123", "tail": 100}
    assert result["ok"] is True
    assert result["provider"] == "render"
    assert result["service_id"] == "srv-123"
    assert result["count"] == 1
    assert result["redacted"] is True
    assert result["lines"][0]["level"] == "error"
    assert "super-secret" not in str(result)


def test_app_get_runtime_logs_caps_tail():
    captured = {}

    def fetcher(*, service_id, tail):
        captured["tail"] = tail
        return {"lines": [], "truncated": False}

    result = app_get_runtime_logs(
        provider="render",
        service_id="srv-123",
        tail=9999,
        fetcher=fetcher,
    )

    assert captured["tail"] == MAX_TAIL
    assert result["truncated"] is True


def test_app_get_runtime_logs_filters_level():
    def fetcher(*, service_id, tail):
        return {
            "lines": [
                {"timestamp": "2026-05-24T00:00:00Z", "message": "INFO ready"},
                {"timestamp": "2026-05-24T00:00:01Z", "message": "WARNING slow response"},
            ],
            "truncated": False,
        }

    result = app_get_runtime_logs(
        provider="render",
        service_id="srv-123",
        level="warning",
        fetcher=fetcher,
    )

    assert result["count"] == 1
    assert result["lines"][0]["level"] == "warning"


def test_app_get_build_logs_filters_query():
    captured = {}

    def fetcher(*, deploy_id, tail):
        captured["deploy_id"] = deploy_id
        captured["tail"] = tail
        return {
            "lines": [
                {"timestamp": "2026-05-24T00:00:00Z", "message": "install deps"},
                {"timestamp": "2026-05-24T00:00:01Z", "message": "build failed"},
            ],
            "truncated": False,
        }

    result = app_get_build_logs(
        provider="render",
        deploy_id="dep-123",
        tail=50,
        query="failed",
        fetcher=fetcher,
    )

    assert captured == {"deploy_id": "dep-123", "tail": 50}
    assert result["ok"] is True
    assert result["deploy_id"] == "dep-123"
    assert result["count"] == 1
    assert result["lines"][0]["message"] == "build failed"


def test_app_search_logs_requires_query():
    result = app_search_logs(
        provider="render",
        service_id="srv-123",
        query="",
    )

    assert result["ok"] is False
    assert result["errors"] == ["query is required"]


def test_app_search_logs_delegates_to_runtime_search():
    def fetcher(*, service_id, tail):
        return {
            "lines": [
                {"timestamp": "2026-05-24T00:00:00Z", "message": "timeout waiting for db"},
                {"timestamp": "2026-05-24T00:00:01Z", "message": "ready"},
            ],
            "truncated": False,
        }

    result = app_search_logs(
        provider="render",
        service_id="srv-123",
        query="timeout",
        fetcher=fetcher,
    )

    assert result["ok"] is True
    assert result["count"] == 1
    assert "timeout" in result["lines"][0]["message"]


def test_app_logs_rejects_unsupported_provider():
    result = app_get_runtime_logs(
        provider="railway",
        service_id="srv-123",
    )

    assert result["ok"] is False
    assert result["provider"] == "railway"
    assert result["lines"] == []
    assert "not supported" in result["errors"][0]


def test_app_logs_wraps_provider_errors_without_raw_lines():
    def fetcher(*, deploy_id, tail):
        return {"errors": ["provider unavailable"], "lines": [{"message": "raw secret"}]}

    result = app_get_build_logs(
        provider="render",
        deploy_id="dep-123",
        fetcher=fetcher,
    )

    assert result["ok"] is False
    assert result["lines"] == []
    assert result["errors"] == ["provider unavailable"]
    assert "raw secret" not in str(result)
