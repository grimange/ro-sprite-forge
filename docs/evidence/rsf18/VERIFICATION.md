# RSF-18 verification

Result: **RSF-18_IMPLEMENTED_AND_QA_PASSED**. Python 3.14.4, Pillow 12.1.1,
jsonschema 4.19.2, Linux. Authoritative plan SHA-256 remains
`5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`.

## Implementation and policy

`core/review.py` extends the existing ledger composition basis and dependency
authority. It seals immutable `rsf.review-event/v1` events, evaluates currentness,
retains stale/rejected history and projects current decisions into existing ledger
and coverage rules without changing assignment revisions. Project/v1 accepts the
optional history; existing projects remain compatible.

The service reconstructs exact proposals from persisted inputs, validates all
members before publication, and uses existing optimistic atomic persistence.
Generic saves cannot inject review history or overwrite ledger/target state.
The workbench presents exact layer/frame/view/action/batch IDs, actual executable
source previews, hashes, lineage, frame facts and explicit limitations before a
decision. Unexecuted recipes cannot be approved or exempted.

This is **provisional ordered source-layer inspection**. It does not certify fully
composed replacement animation, unexecuted transformations, native pixel parity or
artistic suitability. APPROVED remains bound to that explicit policy. Availability,
technical execution, authored replacement coverage and native evidence stay separate;
export_ready remains false. NOT_REQUIRED requires explicit unchanged-reference,
structural-only policy, with no reuse or transforms. Automation used synthetic art only.

## Executed checks

All commands below exited 0:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_review.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q
.venv/bin/python scripts/check_contract_schemas.py
.venv/bin/python scripts/check_ledger_schema.py
.venv/bin/python scripts/check_coverage_schema.py
.venv/bin/python scripts/check_animation_schema.py
.venv/bin/python scripts/check_comparison_schema.py
.venv/bin/python scripts/check_review_schema.py
node --check src/ro_sprite_forge/static/workbench.js
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14
```

Focused **19**, public **318**, private **36** PASS. Installed isolated wheel:
318 collected, OK with two optional-dependency skips (Pillow-free branch and
optional jsonschema test); mandatory schema checking ran separately. Offline
repeated wheel builds, stdlib-only core, installed import isolation and distribution
private-asset exclusions passed. Private fixture tests preserve Novice body/head
separation, Novice body 456 motions/110 identities/108 contents, Orc 512 motions/
1776 visible layers/55 of57 identities. No private approval or screenshot generated.

Final distribution log SHA-256:
`0d33f6dc1efc9719615f490dc63ac3b87ffedfd154eb533901f3f01181ffda58`.
Reproducible sdist-derived wheel SHA-256:
`a4cb1f7d5a9d411c3d6d0fe93cbafb4614892919b8a5abb1f01878235e81e0ea`.
Source distribution SHA-256:
`b9b8d5eeaf5038b72fca6ccc3436c778c4bd10a48de0d0fa05a9743967c425bd`.
Separately built final installed browser wheel SHA-256:
`d7c46473d8acae0cfb0b66be25e685b488337b59bf45420fd99f0948edeaba9c`.
These are separate build routes; no cross-route binary identity is claimed.

## Browser reproduction and results

Use Playwright MCP `browser_run_code_unsafe` with absolute filename
`tests/browser/rsf18-mcp.js` against installed local service on 127.0.0.1:8182.
Prepare isolated synthetic inputs, without private resources:

```sh
PYTHONPATH=src:tests .venv/bin/python - <<'PY'
from pathlib import Path
from test_inventory import resources
p=Path('/tmp/rsf17-synthetic'); p.mkdir(exist_ok=True)
a,s=resources(slots=40,frames=6)
(p/'body.act').write_bytes(a); (p/'body.spr').write_bytes(s)
PY
ro-sprite-forge serve --port 8182 --projects-dir /tmp/rsf18-browser-projects
```

Fixture builder illustrates equivalent synthetic structure; original executed
synthetic fixture SPR hash is recorded in browser result JSON. The suite creates a
fresh project per run; timestamps identify isolated test projects only, not canonical
composition inputs. Long prior assignment confirmations use a test confirmation
shim; actual approval dialog controls are clicked. Existing native confirmation
behavior was separately established in RSF-17.

Coordinator and reviewer both executed the real browser through **Playwright MCP**,
Chromium156.0.8078.73. Individual approval/reopen, rejection, batch exactness,
dependency staleness, independent D preservation, separate-context conflict,
unsupported-transform block and prior assignment/timeline/comparison all passed.
Final coordinator run used the final installed wheel; full results and requirement
IDs are in `browser-release-results.json`. Zero unexpected console errors or network
failures. Deliberate missing candidate/stale operations returned422/409/409.

Separate coordinator missing-source test temporarily moved only a synthetic blob,
observed approval become STALE and review proposal fail, then restored exact bytes.
See `browser-results.json`. No original private files changed. Reviewer independently
executed the main browser suite; see `QA_REVIEW.md` for precise build distinction.

## Determinism and preservation

`determinism.json` records byte-equal repeated workspace output and exact event/
member hashes. Four approved synthetic assignments become A/B/C STALE, D APPROVED
after A revision changes, with export_ready=false. Unrelated display metadata and
save/reopen retain applicability; future build hashes are absent from composition
inputs. Invalid batch and concurrent review tests publish no partial event.

Accepted baseline:386 files, no missing files. Baseline manifest SHA-256
`44486e33e0133c07477ee05e161b7f0abd692c29915388e7ccc5eb69c64a3747`.
Archive `/tmp/rsf18-accepted-source.tar.gz` SHA-256
`9ba396b536f300b758c2de55d30d9ff77363a3cb9473c114abc1bb72beca9241`.
Git HEAD remains `472b1d3f9e29630b505fc2b3b7315f6b4e00beba`;
accepted/new project files remain uncommitted. No commit/push, cleanup or permissions
change. Exact changed/new paths and hashes: `implementation-manifest.json`.

Python3.12/3.13 and cross-platform tests NOT_RUN (unavailable). Full native runtime
NOT_RUN for this task; no affected codec/runtime path. Existing M0/M2 evidence retained.
