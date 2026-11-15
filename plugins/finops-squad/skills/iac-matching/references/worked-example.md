# Worked example — search procedure

Resource: `/subscriptions/<id>/resourceGroups/rg-dev/providers/Microsoft.Compute/disks/disk-orphan-01`.

1. Search the IaC repo for the literal name `disk-orphan-01` — no hit (name is likely built from a
   parameterized expression).
2. Search for the resource type `Microsoft.Compute/disks'` combined with the resource group name
   `rg-dev` — finds `modules/disks/dev.bicep`, which declares a `for` loop over a `diskNames` array
   parameter.
3. Check `diskNames` in the matching `.bicepparam` file for `rg-dev` — confirms `disk-orphan-01` is
   one of the array entries, with the symbolic name `disks[2]`.
4. Record `iacMatch: { "status": "found", "repo": "infra", "path": "modules/disks/dev.bicep" }` and
   tell the Implementer the specific array entry/index, not just the file — the module loops.

If step 2 had found two candidate modules that could plausibly own the resource (e.g. two parameter
files targeting the same resource group), the correct call is `not-found`, not a guess — ambiguity
between two owners is exactly the case this skill exists to catch before a PR edits the wrong file.
