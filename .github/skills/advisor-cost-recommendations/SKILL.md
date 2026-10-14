---
name: advisor-cost-recommendations
description: Read and validate Azure Advisor and optimization cost recommendations before turning them into findings. Use when building advisor.json or sourcing rightsizing/commitment ideas.
---

# Advisor cost recommendations

Azure MCP exposes `advisor` (recommendation list/summary) and `optimization` (list/explain/
alternatives). Advisor is a strong, free source of cost ideas — but validate before acting.

## When to use

- Building `advisor.json`.
- Seeding the Analyser's `rightsizing` and `commitment` modes with candidates.

## Method

1. List Cost-category recommendations (`advisor recommendation list`, category = Cost).
2. For right-size/shutdown items, pull the specific resource and **validate against real
   utilization** ([idle-compute-detection](../idle-compute-detection/SKILL.md)) before trusting the
   saving — Advisor windows may differ from yours.
3. Use `optimization recommendation explain` / `alternatives` for reasoning and options.
4. Capture Advisor's `estimatedMonthlySaving` as a starting figure, re-priced via
   [price-basis-handling](../price-basis-handling/SKILL.md).

## Pitfalls

- Advisor savings are usually **list-price** and based on Advisor's own observation window — label
  the basis and re-validate rather than copying the number verbatim.
- Advisor may recommend commitments; those are **T3** (analysis only).
- Dismissed/postponed recommendations can still appear — check status.
