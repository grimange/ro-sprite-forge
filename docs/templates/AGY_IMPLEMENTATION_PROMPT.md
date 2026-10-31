# Antigravity implementer prompt template

Role: senior Python game tooling / binary formats engineer.
Task: <ACTUAL KANEO KEY AND BOUNDED SCOPE>.
Read `GEMINI.md`, plan v1.1 relevant sections, verified Kaneo task and
`docs/workflows/ANTIGRAVITY_KANEO_PMP.md`. Use `/agy-forge-kaneo` plus applicable
`/agy-forge-codec` or `/agy-forge-requirements` skill.

Discover live MCP state; do not invent project/task IDs. Implement task scope only.
Preserve original Ragnarok data, unrelated work and existing reference bytes.
Run focused tests and record actual commands, exit codes, hashes, failures and
NOT_RUN. Produce precise evidence and transition to QA Review when reachable.
Delegate to a **different** `forge-qa-reviewer` or reviewer session; reviewer does not
edit and does not take operator art approval. If QA FAIL, fix as implementer and
request re-review. Sync only actual allowed Kaneo transition and confirm read-back.
Return task status or KANEO_SYNC_PENDING, diff, gates, evidence and next bounded gap.
