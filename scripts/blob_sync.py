"""Read-only mirror of finops run artifacts from Blob Storage into the local `.finops/runs` layout.

The dashboard reads plain files, so for the App Service deployment we mirror
`<subscription>/runs/<run-id>/**` from the container into
`<cache>/<subscription>/runs/<run-id>/**`. Auth is Microsoft Entra ID only
(managed identity in Azure, developer sign-in locally); this module never writes to storage.
"""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

SUBSCRIPTION_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
RUN_ID_RE = re.compile(r"^\d{8}-\d{4}$")


def _container(account_url: str, container: str):
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import ContainerClient

    return ContainerClient(account_url, container, credential=DefaultAzureCredential())


def list_subscriptions(account_url: str, container: str = "finops") -> list[str]:
    c = _container(account_url, container)
    subs = {b.name.split("/", 1)[0] for b in c.list_blobs() if "/" in b.name}
    return sorted(s for s in subs if SUBSCRIPTION_RE.match(s))


def sync_subscription(account_url: str, subscription_id: str, cache_dir: Path, container: str = "finops") -> Path:
    """Mirror one subscription's runs; returns the local runs directory. Unchanged files are skipped."""
    if not SUBSCRIPTION_RE.match(subscription_id):
        raise ValueError("invalid subscription id")
    c = _container(account_url, container)
    runs_dir = (cache_dir / subscription_id / "runs").resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)
    for blob in c.list_blobs(name_starts_with=f"{subscription_id}/runs/"):
        parts = PurePosixPath(blob.name).parts
        if len(parts) < 4 or not RUN_ID_RE.match(parts[2]) or ".." in parts:
            continue
        dest = (runs_dir.joinpath(*parts[2:])).resolve()
        if runs_dir not in dest.parents:
            continue
        if dest.is_file() and dest.stat().st_size == blob.size and dest.stat().st_mtime >= blob.last_modified.timestamp():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(c.download_blob(blob.name).readall())
    return runs_dir
