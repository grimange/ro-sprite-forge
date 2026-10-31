# Definition of Done — scoped engineering tasks

A normal engineering task is ready for independent QA when:

1. Its *existing live Kaneo task* and v1.1 milestone criteria were read; no scope creep.
2. Code behavior is reproducible, constrained to approved files, and regression-tested.
3. Exact test commands, exit codes, skipped tests and changes are recorded.
4. Format changes have relevant malformed-input, inventory and preservation checks.
5. Approval state, layer topology, unknown mappings, classic fallback and native status
   are represented truthfully and separately wherever relevant.
6. Provenance and licenses are documented; no private art, secrets or GRF committed.
7. The implementation is handed to an independent reviewer, not self-accepted.

`QA_PASS` is a claim about the *reviewed slice*, not the overall milestone. For M0:
`M0-S`, `M0-I`, `M0-N` must be explicitly separate. Only all three can yield `M0_PASS`.
For modified animations, native proof must establish exact requested/resolved slots.
A human alone approves artistic output; preview and runtime evidence never silently
constitute this approval. If a gate is not run, say why and stop at its supported status.
