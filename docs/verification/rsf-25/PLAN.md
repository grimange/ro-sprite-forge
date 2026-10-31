# RSF-25 implementation plan

Live task `udjjt7jp22k3owbo05s8mnf8`, Codex account
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`; dependency RSF-24 Accepted.
Verified transitions: assigned → Ready → In Progress.

1. Extend the accepted compiler with a canonical, sealed build section containing
   semantic inputs, approved pre-build composition, toolchain pins, remapping and
   output hashes. Keep invocation IDs, output names and verification evidence outside it.
2. Derive production eligibility from full-profile coverage, complete replacement
   selection and actual decoding; reject stale review projections. Mark bounded output
   PARTIAL_DIAGNOSTIC and preserve separate declared/full completeness states.
3. Stage and fsync complete bundles, then publish by a Linux no-replace atomic directory
   rename. Add an immutable, verified content-addressed cache; never reuse cached approvals.
4. Test separate-process builds at different paths/times, numeric/order contracts,
   production rejection/acceptance, review invalidation, interrupted publication and cache
   corruption. Run existing public/private/schema/Rust/distribution regressions.
5. Hand off to a separate read-only forge_qa_reviewer; correct reproducible findings and
   obtain independent retest before synchronizing acceptance. Keep M5-N UNVERIFIED.

No native run, artwork approval, new codec, commits, pushes or unrelated source edits.
Pre-edit snapshots are in `/tmp/rsf25-before`; durable hashes/diff follow at QA handoff.
