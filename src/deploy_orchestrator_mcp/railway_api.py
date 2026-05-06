from typing import Any

import time

import httpx

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.credentials import get_credential
from deploy_orchestrator_mcp.execution import evaluate_execution_gate
from deploy_orchestrator_mcp.redaction import redact

RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"

# ---------------------------------------------------------------------------
# GraphQL queries / mutations
# ---------------------------------------------------------------------------

_Q_ME = """
query Me {
  me {
    id
    name
    email
  }
}
"""

_Q_PROJECTS = """
query Projects {
  projects {
    edges {
      node {
        id
        name
        description
        createdAt
        updatedAt
      }
    }
  }
}
"""

_Q_PROJECT = """
query Project($id: String!) {
  project(id: $id) {
    id
    name
    description
    services {
      edges {
        node {
          id
          name
          createdAt
          serviceInstances {
            edges {
              node {
                id
                environmentId
                buildCommand
                startCommand
                domains {
                  serviceDomains {
                    domain
                  }
                }
              }
            }
          }
        }
      }
    }
    environments {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
"""

_Q_DEPLOYMENTS = """
query Deployments($serviceId: String!, $environmentId: String!) {
  deployments(
    first: 5
    input: { serviceId: $serviceId, environmentId: $environmentId }
  ) {
    edges {
      node {
        id
        status
        createdAt
        updatedAt
        url
        meta
      }
    }
  }
}
"""

_Q_DEPLOYMENT = """
query Deployment($id: String!) {
  deployment(id: $id) {
    id
    status
    url
    createdAt
    updatedAt
  }
}
"""

# serviceInstanceRedeploy re-deploys the current HEAD — no commit SHA required.
# This is the canonical deploy strategy for this orchestrator.
_M_REDEPLOY = """
mutation ServiceInstanceRedeploy($serviceId: String!, $environmentId: String!) {
  serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
}
"""

FINAL_DEPLOY_STATUSES = {"SUCCESS", "FAILED", "CRASHED", "REMOVED", "SKIPPED"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _railway_token(token: str | None = None) -> str | None:
    return token or get_credential("railway")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _missing_token_result(operation: str) -> dict[str, Any]:
    return {
        "provider": "railway",
        "valid": False,
        "errors": ["Railway token is not configured (use credentials_set or set RAILWAY_TOKEN env var)"],
        "audit_event": create_audit_event(
            "railway.api.blocked",
            {"provider": "railway", "operation": operation, "reason": "missing_token"},
        ),
    }


def _gql(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    token: str,
    client: httpx.Client | None = None,
    operation: str,
) -> tuple[Any, dict[str, Any]]:
    owns_client = client is None
    http_client = client or httpx.Client(timeout=30.0)

    try:
        response = http_client.post(
            RAILWAY_API_URL,
            headers=_headers(token),
            json={"query": query, "variables": variables or {}},
        )
        status_code = response.status_code
        audit_event = create_audit_event(
            "railway.api.call",
            {
                "provider": "railway",
                "operation": operation,
                "status_code": status_code,
            },
        )

        if response.is_error:
            return (
                {"error": "railway_api_error", "status_code": status_code, "response": response.text},
                audit_event,
            )

        body = response.json()
        if "errors" in body:
            return (
                {"error": "railway_graphql_error", "errors": body["errors"]},
                audit_event,
            )

        return body.get("data", {}), audit_event
    finally:
        if owns_client:
            http_client.close()


def _normalize_project(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "description": node.get("description"),
        "created_at": node.get("createdAt"),
    }


def _normalize_service(node: dict[str, Any]) -> dict[str, Any]:
    instances = [
        e["node"]
        for e in (node.get("serviceInstances") or {}).get("edges", [])
    ]
    domains: list[str] = []
    for inst in instances:
        for d in (inst.get("domains") or {}).get("serviceDomains", []):
            if d.get("domain"):
                domains.append(d["domain"])
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "created_at": node.get("createdAt"),
        "domains": domains,
        "instance_count": len(instances),
    }


def _normalize_deployment(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "status": node.get("status"),
        "url": node.get("url"),
        "created_at": node.get("createdAt"),
        "updated_at": node.get("updatedAt"),
    }


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------


def railway_validate_credentials(
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Validate Railway token using the me query."""
    resolved = _railway_token(token)
    if not resolved:
        return _missing_token_result("validate_credentials")

    data, audit_event = _gql(_Q_ME, token=resolved, client=client, operation="validate_credentials")

    if isinstance(data, dict) and data.get("error"):
        return redact({"provider": "railway", "valid": False, "errors": [data], "audit_event": audit_event})

    me = data.get("me", {})
    return redact({
        "provider": "railway",
        "valid": True,
        "user": me.get("name") or me.get("email") or me.get("id"),
        "audit_event": audit_event,
    })


def railway_list_projects(
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """List all Railway projects for the authenticated account."""
    resolved = _railway_token(token)
    if not resolved:
        return _missing_token_result("list_projects")

    data, audit_event = _gql(_Q_PROJECTS, token=resolved, client=client, operation="list_projects")

    if isinstance(data, dict) and data.get("error"):
        return redact({"provider": "railway", "ok": False, "projects": [], "errors": [data], "audit_event": audit_event})

    edges = (data.get("projects") or {}).get("edges", [])
    projects = [_normalize_project(e["node"]) for e in edges]

    return redact({
        "provider": "railway",
        "ok": True,
        "projects": projects,
        "count": len(projects),
        "audit_event": audit_event,
    })


def railway_get_project(
    project_id: str,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Get a Railway project with its services and environments."""
    resolved = _railway_token(token)
    if not resolved:
        return _missing_token_result("get_project")

    data, audit_event = _gql(
        _Q_PROJECT,
        {"id": project_id},
        token=resolved,
        client=client,
        operation="get_project",
    )

    if isinstance(data, dict) and data.get("error"):
        return redact({"provider": "railway", "ok": False, "errors": [data], "audit_event": audit_event})

    project = data.get("project") or {}
    service_edges = (project.get("services") or {}).get("edges", [])
    env_edges = (project.get("environments") or {}).get("edges", [])

    return redact({
        "provider": "railway",
        "ok": True,
        "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "services": [_normalize_service(e["node"]) for e in service_edges],
            "environments": [
                {"id": e["node"]["id"], "name": e["node"]["name"]}
                for e in env_edges
            ],
        },
        "audit_event": audit_event,
    })


def railway_list_deployments(
    service_id: str,
    environment_id: str,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """List recent deployments for a Railway service."""
    resolved = _railway_token(token)
    if not resolved:
        return _missing_token_result("list_deployments")

    data, audit_event = _gql(
        _Q_DEPLOYMENTS,
        {"serviceId": service_id, "environmentId": environment_id},
        token=resolved,
        client=client,
        operation="list_deployments",
    )

    if isinstance(data, dict) and data.get("error"):
        return redact({
            "provider": "railway",
            "ok": False,
            "deployments": [],
            "errors": [data],
            "audit_event": audit_event,
        })

    edges = (data.get("deployments") or {}).get("edges", [])
    deployments = [_normalize_deployment(e["node"]) for e in edges]

    return redact({
        "provider": "railway",
        "ok": True,
        "service_id": service_id,
        "environment_id": environment_id,
        "deployments": deployments,
        "audit_event": audit_event,
    })


def railway_deploy(
    service_id: str,
    environment_id: str,
    *,
    approval: str | bool | None = None,
    token: str | None = None,
    client: httpx.Client | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Trigger a Railway deployment after approval gate validation."""
    deploy_plan = plan or {
        "provider": "railway",
        "environment": "staging",
        "mode": "execute",
        "approval_required": True,
        "approval_required_actions": ["trigger Railway deployment"],
        "service_id": service_id,
        "environment_id": environment_id,
    }
    gate = evaluate_execution_gate(deploy_plan, approval=approval, mode="execute")
    if not gate["allowed"]:
        return redact({
            "provider": "railway",
            "triggered": False,
            "deployment_id": None,
            "gate": gate,
            "audit_event": create_audit_event(
                "railway.deploy.blocked",
                {
                    "provider": "railway",
                    "operation": "deploy",
                    "service_id": service_id,
                    "reasons": gate.get("reasons", []),
                },
            ),
        })

    resolved = _railway_token(token)
    if not resolved:
        result = _missing_token_result("deploy")
        result.update({"triggered": False, "deployment_id": None, "gate": gate})
        return redact(result)

    data, audit_event = _gql(
        _M_REDEPLOY,
        {"serviceId": service_id, "environmentId": environment_id},
        token=resolved,
        client=client,
        operation="deploy",
    )

    if isinstance(data, dict) and data.get("error"):
        return redact({
            "provider": "railway",
            "triggered": False,
            "deployment_id": None,
            "gate": gate,
            "errors": [data],
            "audit_event": audit_event,
        })

    return redact({
        "provider": "railway",
        "triggered": True,
        "deployment_id": None,
        "gate": gate,
        "audit_event": audit_event,
    })


def railway_get_deploy_status(
    deployment_id: str,
    *,
    timeout_seconds: int = 0,
    poll_interval_seconds: float = 5.0,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Read Railway deployment status, optionally polling until completion or timeout."""
    resolved = _railway_token(token)
    if not resolved:
        return _missing_token_result("get_deploy_status")

    deadline = time.monotonic() + max(timeout_seconds, 0)
    attempts = 0

    while True:
        attempts += 1
        data, audit_event = _gql(
            _Q_DEPLOYMENT,
            {"id": deployment_id},
            token=resolved,
            client=client,
            operation="get_deploy_status",
        )

        if isinstance(data, dict) and data.get("error"):
            return redact({
                "provider": "railway",
                "ok": False,
                "deployment_id": deployment_id,
                "errors": [data],
                "audit_event": audit_event,
            })

        deployment = _normalize_deployment(data.get("deployment") or {})
        status = deployment.get("status")

        if not timeout_seconds or status in FINAL_DEPLOY_STATUSES or time.monotonic() >= deadline:
            return redact({
                "provider": "railway",
                "ok": True,
                "deployment_id": deployment.get("id") or deployment_id,
                "status": status,
                "complete": status in FINAL_DEPLOY_STATUSES,
                "url": deployment.get("url"),
                "attempts": attempts,
                "deployment": deployment,
                "audit_event": audit_event,
            })

        time.sleep(max(poll_interval_seconds, 0))


def railway_healthcheck(
    url: str,
    *,
    expected_status: int = 200,
    timeout_seconds: float = 10.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Run an HTTP healthcheck against a Railway service URL."""
    if not url.startswith(("http://", "https://")):
        return {
            "provider": "railway",
            "healthy": False,
            "status_code": None,
            "errors": ["healthcheck url must start with http:// or https://"],
            "audit_event": create_audit_event(
                "railway.healthcheck.blocked",
                {"provider": "railway", "reason": "invalid_url"},
            ),
        }

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)

    try:
        response = http_client.get(url)
        healthy = response.status_code == expected_status
        return redact({
            "provider": "railway",
            "healthy": healthy,
            "status_code": response.status_code,
            "expected_status": expected_status,
            "url": url,
            "audit_event": create_audit_event(
                "railway.healthcheck.completed",
                {
                    "provider": "railway",
                    "url": url,
                    "status_code": response.status_code,
                    "healthy": healthy,
                },
            ),
        })
    except httpx.HTTPError as exc:
        return redact({
            "provider": "railway",
            "healthy": False,
            "status_code": None,
            "errors": [str(exc)],
            "url": url,
            "audit_event": create_audit_event(
                "railway.healthcheck.failed",
                {"provider": "railway", "url": url, "error": str(exc)},
            ),
        })
    finally:
        if owns_client:
            http_client.close()
