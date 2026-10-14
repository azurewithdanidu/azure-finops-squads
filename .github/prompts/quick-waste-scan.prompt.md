---
description: Fast, read-only sweep for obvious waste (orphaned disks, unassociated public IPs, idle VMs) without a full audit.
---

# Quick waste scan

A lightweight, read-only check for low-risk waste. No remediation.

1. Invoke **finops-analyser** in `waste` mode directly against the in-scope subscriptions.
2. Focus on fast wins: unattached managed disks, unassociated public IPs, and clearly idle VMs
   (use [orphaned-resource-detection](../skills/orphaned-resource-detection/SKILL.md) and
   [idle-compute-detection](../skills/idle-compute-detection/SKILL.md)).
3. Emit schema-valid findings to `findings/waste.json` with evidence, tier, saving + basis, and
   `iacMatch`. Set `status: proposed`.
4. Print a short ranked table of findings. Do not open PRs.

Validate: `python scripts/validate-findings.py .finops/runs/<id>/findings/`.
