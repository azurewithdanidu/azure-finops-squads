---
title: Security model
description: Canonical security and approval contracts shipped with the FinOps squad plugin.
---

## Packaged contracts

The maintained [security model](../plugins/finops-squad/skills/finops-squad/references/security-model.md)
and [safety contract](../plugins/finops-squad/skills/finops-squad/references/safety-contract.md)
ship with the plugin. Every phase loads these rules in the consumer workspace.

Instructions and deterministic approval flags are not security boundaries. Azure access requires
a human-confirmed identity without effective write access, including inherited and activated
permissions. No agent deploys or mutates Azure.
