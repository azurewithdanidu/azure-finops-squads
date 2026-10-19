"""Read-only tools for hosted finops-squad agents.

Azure access uses the agent's managed identity (Reader, Cost Management Reader, Monitoring Reader).
Only GET requests, Resource Graph and Cost Management queries are exposed -- nothing here can
create, update or delete a resource.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Annotated, Any

import httpx
from agent_framework import tool
from azure.identity import DefaultAzureCredential
from finops_store import BlobBackend, RunStore, list_runs

ARM = "https://management.azure.com"
os.environ.setdefault("FINOPS_SCHEMA_DIR", str(Path(__file__).resolve().parent / "schemas"))
_credential = DefaultAzureCredential()
_SUB = r"[0-9a-fA-F-]{36}"
_SCOPE_RE = re.compile(rf"^/subscriptions/{_SUB}(/resourceGroups/[\w.()-]+)?$")
_GET_ALLOWED = (
    "microsoft.advisor/",
    "microsoft.insights/metrics",
    "microsoft.insights/metricdefinitions",
    "microsoft.insights/diagnosticsettings",
    "microsoft.costmanagement/budgets",
    "microsoft.consumption/",
    "microsoft.compute/reservations",
    "microsoft.capacity/",
    "microsoft.billingbenefits/",
)


def _token() -> str:
    return _credential.get_token(f"{ARM}/.default").token


def _request(method: str, url: str, **kw) -> dict:
    headers = {"Authorization": f"Bearer {_token()}"}
    for attempt in range(4):
        r = httpx.request(method, url, headers=headers, timeout=120, **kw)
        if r.status_code == 429:
            time.sleep(min(int(r.headers.get("Retry-After", 5)), 60))
            continue
        break
    if r.status_code >= 400:
        return {"error": True, "status": r.status_code, "body": r.text[:2000]}
    return r.json()


@tool
def resource_graph_query(
    query: Annotated[str, "Azure Resource Graph KQL query"],
    subscription_ids: Annotated[list[str], "Subscription IDs to query"],
) -> str:
    """Run a read-only Azure Resource Graph query (inventory, orphans, tag coverage)."""
    if not subscription_ids or not all(re.fullmatch(_SUB, s) for s in subscription_ids):
        return json.dumps({"error": True, "body": "subscription_ids must be GUIDs"})
    url = f"{ARM}/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01"
    body = {"subscriptions": subscription_ids, "query": query, "options": {"resultFormat": "objectArray", "$top": 1000}}
    return json.dumps(_request("POST", url, json=body))[:60000]


@tool
def cost_query(
    scope: Annotated[str, "/subscriptions/<id> or /subscriptions/<id>/resourceGroups/<rg>"],
    query_body: Annotated[str, "Cost Management query JSON (type, timeframe/timePeriod, dataset)"],
) -> str:
    """Query actual cost via the Cost Management Query API. Needs Cost Management Reader."""
    if not _SCOPE_RE.match(scope):
        return json.dumps({"error": True, "body": "scope must be a subscription or resource group"})
    url = f"{ARM}{scope}/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    return json.dumps(_request("POST", url, json=json.loads(query_body)))[:60000]


@tool
def arm_get(
    path: Annotated[str, "ARM path starting with /subscriptions/, e.g. /subscriptions/<id>/providers/Microsoft.Advisor/recommendations"],
    api_version: Annotated[str, "API version, e.g. 2023-01-01"],
    query: Annotated[str, "Extra query string without leading ?, optional"] = "",
) -> str:
    """Read-only ARM GET for Advisor, Monitor metrics, budgets and reservations."""
    if not path.startswith("/subscriptions/") or ".." in path:
        return json.dumps({"error": True, "body": "path must start with /subscriptions/"})
    low = path.lower()
    if not any(a in low for a in _GET_ALLOWED):
        return json.dumps({"error": True, "body": f"path not in read-only allowlist: {_GET_ALLOWED}"})
    url = f"{ARM}{path}?api-version={api_version}" + (f"&{query}" if query else "")
    return json.dumps(_request("GET", url))[:60000]


@tool
def retail_price(
    odata_filter: Annotated[str, "OData $filter, e.g. serviceName eq 'Virtual Machines' and armSkuName eq 'Standard_D4s_v5' and armRegionName eq 'eastus'"],
) -> str:
    """Query the public Azure Retail Prices API (list price)."""
    r = httpx.get("https://prices.azure.com/api/retail/prices", params={"$filter": odata_filter}, timeout=60)
    return r.text[:30000]


def _backend() -> BlobBackend:
    return BlobBackend(os.environ["FINOPS_STORAGE_ACCOUNT_URL"], os.environ.get("FINOPS_STORAGE_CONTAINER", "finops"), _credential)


@tool
def save_artifact(
    subscription_id: Annotated[str, "Subscription GUID the artifact belongs to"],
    run_id: Annotated[str, "Run id, yyyymmdd-hhmm"],
    path: Annotated[str, "Relative path, e.g. inventory.json or findings/waste.json"],
    content: Annotated[Any, "File content: a JSON object/array (or JSON string) for *.json, text otherwise"],
) -> str:
    """Write a run artifact to storage. Findings and verification files are schema-validated."""
    store = RunStore(_backend(), subscription_id, run_id)
    try:
        if path.endswith(".json"):
            doc = json.loads(content) if isinstance(content, str) else content
            key = store.write_json(path, doc)
        else:
            key = store.write_text(path, content if isinstance(content, str) else json.dumps(content))
    except Exception as e:  # report validation errors to the model so it can fix and retry
        return json.dumps({"error": True, "body": str(e)[:2000]})
    return json.dumps({"saved": key})


@tool
def read_artifact(
    subscription_id: Annotated[str, "Subscription GUID"],
    run_id: Annotated[str, "Run id"],
    path: Annotated[str, "Relative path inside the run"],
) -> str:
    """Read a run artifact from storage."""
    store = RunStore(_backend(), subscription_id, run_id)
    try:
        return store.read_text(path)[:60000]
    except Exception as e:
        return json.dumps({"error": True, "body": str(e)[:500]})


@tool
def list_run_artifacts(
    subscription_id: Annotated[str, "Subscription GUID"],
    run_id: Annotated[str, "Run id; empty to list run ids"] = "",
) -> str:
    """List runs for a subscription, or the artifacts within one run."""
    b = _backend()
    if not run_id:
        return json.dumps(list_runs(b, subscription_id))
    return json.dumps(RunStore(b, subscription_id, run_id).list())


COMMON_TOOLS = [save_artifact, read_artifact, list_run_artifacts]
READ_TOOLS = [resource_graph_query, cost_query, arm_get, retail_price]


@tool
def build_reports(
    subscription_id: Annotated[str, "Subscription GUID"],
    run_id: Annotated[str, "Run id"],
) -> str:
    """Generate reports/savings-ledger.json and reports/kpis.json from the run's stored artifacts."""
    import tempfile
    from pathlib import Path

    import kpis
    import ledger

    b = _backend()
    with tempfile.TemporaryDirectory() as tmp:
        runs_dir = Path(tmp) / ".finops" / "runs"
        for rid in list_runs(b, subscription_id):
            for rel in RunStore(b, subscription_id, rid).list():
                dest = runs_dir / rid / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b.read(f"{subscription_id}/runs/{rid}/{rel}"))
        folder = runs_dir / run_id
        if not folder.is_dir():
            return json.dumps({"error": True, "body": f"run {run_id} not found"})
        store = RunStore(b, subscription_id, run_id)
        led = ledger.build_ledger(folder)
        store.write_json("reports/savings-ledger.json", led)
        store.write_json("reports/kpis.json", kpis.build_kpis(folder, runs_dir))
    return json.dumps({"saved": ["reports/savings-ledger.json", "reports/kpis.json"], "mixedCurrencies": led.get("mixedCurrencies")})


DISCOVERY_TOOLS = [*READ_TOOLS, *COMMON_TOOLS]
ANALYSER_TOOLS = [*READ_TOOLS, *COMMON_TOOLS]
VISUALIZER_TOOLS = [*COMMON_TOOLS, build_reports]
IMPLEMENTER_TOOLS = [*COMMON_TOOLS]

