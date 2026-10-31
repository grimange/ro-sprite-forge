# RSF-17 interactive assignment and playback

The local workbench uses `service/workbench.py` as an adapter to the accepted
contracts, ledger, coverage, timeline, animation inspector and comparison engine.
It adds no JavaScript assignment, timing or graphics engine.

`GET /api/projects/{id}/workspace` returns the immutable requirement identities,
resolved ledger, coverage, exact resource inventories and source catalog. Read
routes tolerate unavailable blobs so the operator can inspect missing evidence.
Content reads still verify SHA-256; saving and mutation retain integrity checks.

Protected POST operations are `target`, `import-pair`, `assign`, `preview`,
`source-preview` and `compare`. Mutations require the current project revision.
Assignments use exact requirement/source revisions and canonical ledger validation;
the whole proposed batch is validated before a single atomic project save. Reuse
preserves dependency revisions and ordered recipes. No operation grants approval.

Pair import records original ACT/SPR hashes and a computed inventory. Source tray
image identities retain pool/index and inventory provenance. Decoded PNG hashes
identify previewable image content separately from original SPR representation.
Original indexed bytes remain in immutable blob storage. Missing source bytes do
not become implicit reference assignments.

Manual selections, stepping and timed seeks call the Python timeline. Playback
requests include explicit external context, speed and elapsed milliseconds; Python
calculates the frame. A resume frame is converted to a supported timeline position
in Python and checked against canonical seek semantics. Unsupported timing stops
playback with a diagnostic while manual stepping remains available. Action changes
preserve the selected evidenced view where it exists; invalid slots never fall back.

Animation frames and comparisons come from the accepted compositor and comparison
APIs. The assignment inspector separately shows effective source previews and
executed horizontal mirror reuse. Other valid ledger recipes remain explicitly
`TRANSFORMATION_NOT_EXECUTED` on this bounded path. The animation panel presents
explicit imported resource selections; it does not compile a modified animation
from the ledger. Fidelity remains PARTIAL where the accepted renderer says so.

The source tray and exact mapping confirmation support individual assignment and
an ordered batch mapping editor. Save/reopen retains canonical ledger identities;
concurrent stale saves return HTTP 409. Work-order and coverage views retain the
separate structural, assignment, technical, review and native dimensions.

Browser acceptance is exercised through Playwright MCP against an installed wheel.
The reusable MCP journey is `tests/browser/rsf17-mcp.js`; the optional audited
fixture journey is `tests/browser/rsf17-private-mcp.js`. Comprehensive automation
uses an explicit confirmation shim; native modal confirmation is also tested using
MCP click/handle-dialog operations. Private resources and private captures are not
included in distribution artifacts.
