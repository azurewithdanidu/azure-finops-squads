"""Storage backends and the schema-validating RunStore."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Protocol

SUBSCRIPTION_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
RUN_ID_RE = re.compile(r"^\d{8}-\d{4}$")


class StoreError(Exception):
    """Invalid key, missing artifact or backend failure."""


class ValidationError(StoreError):
    """An artifact failed schema validation and was not written."""


class Backend(Protocol):
    def read(self, key: str) -> bytes: ...
    def write(self, key: str, data: bytes) -> None: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str) -> list[str]: ...


class LocalBackend:
    """Folder-backed store, for local development and tests."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise StoreError(f"key escapes store root: {key}")
        return path

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StoreError(f"not found: {key}")
        return path.read_bytes()

    def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix) if prefix else self.root
        if not base.exists():
            return []
        return sorted(
            p.relative_to(self.root).as_posix() for p in base.rglob("*") if p.is_file()
        )


class BlobBackend:
    """Azure Blob container backend using Microsoft Entra ID (no keys).

    ``credential`` defaults to ``DefaultAzureCredential``: the managed identity in Azure,
    the developer sign-in locally.
    """

    def __init__(self, account_url: str, container: str = "finops", credential: Any = None) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import ContainerClient

        self._container = ContainerClient(
            account_url, container, credential=credential or DefaultAzureCredential()
        )

    def read(self, key: str) -> bytes:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._container.download_blob(key).readall()
        except ResourceNotFoundError as exc:
            raise StoreError(f"not found: {key}") from exc

    def write(self, key: str, data: bytes) -> None:
        self._container.upload_blob(key, data, overwrite=True)

    def exists(self, key: str) -> bool:
        return self._container.get_blob_client(key).exists()

    def list(self, prefix: str) -> list[str]:
        return sorted(b.name for b in self._container.list_blobs(name_starts_with=prefix))


def _schema_dir() -> Path:
    override = os.environ.get("FINOPS_SCHEMA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "schemas"


def _schema_for(rel: str) -> str | None:
    parts = PurePosixPath(rel).parts
    if "findings" in parts[:-1] and rel.endswith(".json"):
        return "finding.schema.json"
    if "verification" in parts[:-1] and rel.endswith(".json"):
        return "verification.schema.json"
    return None


def _items(doc: Any) -> Iterator[Any]:
    if isinstance(doc, list):
        yield from doc
    elif isinstance(doc, dict) and isinstance(doc.get("findings"), list):
        yield from doc["findings"]
    else:
        yield doc


def _clean_rel(rel: str) -> str:
    if not rel or rel.startswith(("/", "\\")) or "\\" in rel:
        raise StoreError(f"invalid relative path: {rel!r}")
    parts = PurePosixPath(rel).parts
    if any(p in ("", ".", "..") for p in parts) or re.match(r"^[A-Za-z]:", rel):
        raise StoreError(f"invalid relative path: {rel!r}")
    return "/".join(parts)


class RunStore:
    """Reads and writes the artifacts of one run for one subscription."""

    def __init__(self, backend: Backend, subscription_id: str, run_id: str) -> None:
        if not SUBSCRIPTION_RE.match(subscription_id):
            raise StoreError(f"invalid subscription id: {subscription_id!r}")
        if not RUN_ID_RE.match(run_id):
            raise StoreError(f"invalid run id (expected yyyymmdd-hhmm): {run_id!r}")
        self.backend = backend
        self.subscription_id = subscription_id.lower()
        self.run_id = run_id
        self.prefix = f"{self.subscription_id}/runs/{run_id}"

    def key(self, rel: str) -> str:
        return f"{self.prefix}/{_clean_rel(rel)}"

    def _validate(self, rel: str, doc: Any) -> None:
        schema_name = _schema_for(rel)
        if schema_name is None:
            return
        import jsonschema

        schema = json.loads((_schema_dir() / schema_name).read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)
        errors = []
        for idx, item in enumerate(_items(doc)):
            for err in sorted(validator.iter_errors(item), key=lambda e: list(e.path)):
                loc = "/".join(str(p) for p in err.path) or "(root)"
                errors.append(f"[item {idx}] {loc}: {err.message}")
        if errors:
            raise ValidationError(f"{rel} failed {schema_name}: " + "; ".join(errors))

    def write_json(self, rel: str, doc: Any) -> str:
        key = self.key(rel)
        self._validate(_clean_rel(rel), doc)
        self.backend.write(key, json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8"))
        return key

    def write_text(self, rel: str, text: str) -> str:
        key = self.key(rel)
        self.backend.write(key, text.encode("utf-8"))
        return key

    def read_json(self, rel: str) -> Any:
        return json.loads(self.backend.read(self.key(rel)).decode("utf-8"))

    def read_text(self, rel: str) -> str:
        return self.backend.read(self.key(rel)).decode("utf-8")

    def exists(self, rel: str) -> bool:
        return self.backend.exists(self.key(rel))

    def list(self, rel_prefix: str = "") -> list[str]:
        """Artifact paths relative to the run folder."""
        prefix = self.prefix + "/" + (_clean_rel(rel_prefix) if rel_prefix else "")
        cut = len(self.prefix) + 1
        return [k[cut:] for k in self.backend.list(prefix)]


def list_subscriptions(backend: Backend) -> list[str]:
    return sorted({k.split("/", 1)[0] for k in backend.list("") if "/runs/" in k})


def list_runs(backend: Backend, subscription_id: str) -> list[str]:
    """Run IDs for a subscription, newest first."""
    if not SUBSCRIPTION_RE.match(subscription_id):
        raise StoreError(f"invalid subscription id: {subscription_id!r}")
    prefix = f"{subscription_id.lower()}/runs/"
    runs = {k[len(prefix):].split("/", 1)[0] for k in backend.list(prefix)}
    return sorted((r for r in runs if RUN_ID_RE.match(r)), reverse=True)
