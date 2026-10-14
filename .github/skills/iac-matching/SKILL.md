---
name: iac-matching
description: Locate the Bicep source for a live Azure resource so a fix can be a PR, not a manual change. Use before the Implementer acts on any finding.
---

# IaC matching

The Implementer only opens a PR when it can find the resource in IaC. This skill sets
`iacMatch.status` on a finding.

## Statuses

- `found` — the resource is declared in the IaC repo; record `repo` and `path`. Implementer can PR.
- `not-found` — the resource type is managed by IaC but this instance isn't located. Implementer
  refuses (don't guess the file).
- `unmanaged` — the resource isn't in IaC at all. Implementer produces a **manual change request**.

## Method

1. Resolve the IaC repo + path from `.finops/config.json`.
2. Search the repo for the resource by: name, resource type, tags, and resource-id fragments
   (e.g. the resource group + name). Bicep symbolic names and `name:` properties are good anchors.
3. Prefer an exact match on `name` + type. If several modules could own it, mark `not-found` rather
   than risk editing the wrong file.
4. Record `repo` and `path` precisely so the Implementer edits the right module.

## Pitfalls

- Looping/`for` constructs and parameterized names make text search miss matches — check module
  parameters and naming conventions.
- A resource created by a module instance may live in the module, not the caller.
- Terraform is out of scope for v0.1; if the repo is Terraform, mark `unmanaged` and note it.
