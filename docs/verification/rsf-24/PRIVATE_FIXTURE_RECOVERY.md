# Audited private fixture recovery

The Orc fixtures were initially absent. The coordinator recovered only the two requested
entries from the existing private GRF; source archive, external code and original resources
were read only. No art, encrypted payload or external decoder code is included in Forge.
No native playback was performed by this recovery.

Archive: `/home/ra/Documents/lwr-m1b-workspace/gravity-data/kro-210607/data.grf`.
Actual SHA-256: `fa3b7bbdbd650c3468eca5e978a44e7a848d533f2735e6f5af2b668e1d1dc3b6`.
The GRF 2.0 header/table were read using Python `struct`/`zlib`. Only matching basename
entries were read, with bounded decoded sizes. Duplicate SPR entries contained the same
compressed metadata. Original files were not written.

| Entry | Compressed / aligned / decoded bytes | Flags | Processing |
|---|---|---|---|
| orc_skeleton.act | 8179 / 8184 / 87004 | 5 | decodeHeader then zlib inflate |
| orc_skeleton.spr | 25423 / 25424 / 119327 | 3 | decodeFull(data, aligned size, 25423) then zlib inflate |

Existing read-only extraction utility:
`/home/ra/Documents/lwr-m1b-workspace/src/roBrowserLegacy/src/Loaders/GameFileDecrypt.js`.
Repository revision `b6ee6af55cf95caaafca61d88ecc58093dd0a838`;
actual file SHA-256 `5057933b3870328362e168c4ce92e3d4ad487272eec40255e505e1bd494a9d87`.
Repository LICENSE is GPL-3.0, SHA-256
`1ca220990c29c68bfcdbd4dba0ab4594ffb3baa324d258ecda2407d90e2d4db1`.
Node 22.23.4 loaded that existing module in memory and used its exported decoder.
This is tool execution provenance, not incorporation of its code into Forge.
Initial attempts refused encrypted flags before invoking the existing decoder; no malformed
fixture was accepted. Node/Python recovery completed with exact audited hash comparisons.

Outputs remain private under `/tmp/ro-sprite-forge-audit-e1/`, with exclusive creation and
existing-content comparison rather than overwrite:

- ACT SHA-256 `31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2`.
- SPR SHA-256 `a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f`.

Both match the independently audited `AUDITED_HASHES` constants in the private fixture hook.
Rerun `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` against
these private outputs; public CI and distributions do not depend on them.
