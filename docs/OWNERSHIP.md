# Explicit ownership and route suggestions

These v0.9 operations use explicit object IDs and new working copies. They do not infer a mechanism, change a molecular graph, or certify manually dragging an atom in ChemDraw. The original document or source file is not edited. Native validation and visual review remain separate from portable tests.

## Persistent ownership

```python
from chemdraw_macos.ownership import build_ownership, plan_move, move_document

ownership = build_ownership(
    snapshot_cdxml,
    owners=[
        {'key': 'substrate', 'fragment_ids': ['ACTUAL_FRAGMENT_ID'],
         'caption_ids': ['ACTUAL_CAPTION_ID']},
        {'key': 'product', 'fragment_ids': ['OTHER_FRAGMENT_ID'],
         'caption_ids': ['OTHER_CAPTION_ID']},
    ],
    curves=[],
)
result = move_document(
    bridge, document_id, '/absolute/existing/parent/new-move-review',
    ownership, [{'owner_key': 'substrate', 'delta': [20, 0]}],
    ownership['source_token'],
)
```

The IDs are placeholders; use actual current snapshot IDs. Every molecular fragment must have exactly one owner. Each owner has one or more fragment IDs and an explicit list of caption IDs, which may be empty. A fragment or caption cannot have two owners. Multiple fragments belonging to one compound translate together without scaling. Unassigned page captions are retained in place and listed explicitly as `stationary_caption_ids`; ownership is never guessed from proximity.

Native charge symbols, lone pairs and graphical electron dots inside a fragment move with that fragment. Their native association, geometry and supported styling are retained. This workflow does not add symbols or alter their chemical meaning.

Every existing page-level electron-flow curve needs an explicit ownership record:

```json
{
  "curve_id": "ACTUAL_CURVE_ID",
  "source": {"kind": "symbol", "id": "ACTUAL_DONOR_SYMBOL_ID"},
  "target": {"kind": "atom", "id": "ACTUAL_TARGET_ATOM_ID"}
}
```

Use a displayed donor symbol or donor bond as the source, and an atom or bond as the target. References must identify objects in an owned fragment. The ownership registry can retain legacy atom references for existing curves, but this does not authorize creating an atom-source arrow. These records declare intended ownership. They do not infer which atom a pre-existing curve chemically represents, validate its donor origin, or establish native moving attachment.

An internal curve whose endpoints have the same owner translates with that owner. A cross-owner curve can move only when both owners receive the same translation, including both staying fixed. Moving one owner independently fails explicitly. Its endpoint and two control handles are not blindly translated away from the stationary endpoint. Independent cross-owner movement and automatic rerouting during movement are not implemented; obtain and explicitly select a new route as a separate operation.

The sidecar has `schema_version: 1`, `source_token`, `owners`, `curves` and `stationary_caption_ids`. Supply 1 through 100 owners, at most 100 curve records, and 1 through 100 unique owner moves. Each delta contains two finite point values between -500 and 500; a zero move is rejected. Unknown fields and inconsistent or stale sidecars fail before creating the final copy.

When the source contains an explicit reaction `scheme`, owner translations must be horizontal. A native ChemDraw 23.0.1 regression showed that moving the SN2 reactants down 30 pt removed their `ReactionStepReactants` membership during saving, although the molecular graphs survived. Vertical scheme-relative moves therefore fail during preflight, before creating a working copy. Plain molecular sheets still support both axes. Horizontal reaction moves must retain the exact mapped source reaction roles after native saving and can still fail if ChemDraw reinterprets the arrangement. No semantic attributes are deleted, loosened or restored only in a sidecar to conceal native loss.

### Movement API and artifacts

`plan_move(cdxml, ownership, moves)` is offline and returns `(planned_cdxml, updated_ownership, plan)`. It performs positive-orientation-preserving translation only. It checks that reversing the requested translations restores the source's mapped supported chemistry, coordinates, labels, symbols and curves. Its page check uses native molecular/text bounds, calibrated symbol circles and conservative curve-control rectangles. It does not certify arrowhead ink or detect collisions caused by the requested move.

`move_document(bridge, document_id, output_dir, ownership, moves, expected_source_token, pixels=3200)` executes the native new-copy workflow. `move_file(bridge, path, output_dir, ownership, moves, expected_source_token=None, pixels=3200)` additionally freezes bounded CDXML input and remaps file IDs after native import. The ownership sidecar's token is always checked, even when the separate file argument is omitted.

The successful bundle contains `before.cdxml/svg/png`, `figure.cdxml/svg/png`, `recipe.json`, `ownership.json`, `audit.json` and `review.html`. Final `ownership.json` addresses the actual saved `figure.cdxml`, using its remapped fragment, caption, curve and endpoint IDs and its new source token. Keep those two files together. The next tool move must use the updated sidecar; manual changes make an old token stale.

Final native CDXML is exported after SVG/PNG rendering and compared with the planned geometry and graph. Source content, document metadata and available disk hashes are checked; file input also rechecks its original bytes. Determinate failures close only newly owned copies. Uncertain native outcomes stop without retry or automatic cleanup, including uncertainty during cleanup itself. The final successful working copy stays open. Existing output paths are refused, and PNG longest side remains 256 through 8192 pixels.

`checks_passed` is not collision approval. The audit records visual review as required and `native_manual_drag_attachment: "not_verified"`.

## Geometry-only route suggestions

```python
from chemdraw_macos.route_suggestions import (
    suggest_routes, select_route, annotate_selected_route_document,
)

proposal = suggest_routes(
    snapshot_cdxml,
    source={'kind': 'symbol', 'id': 'ACTUAL_DONOR_SYMBOL_ID'},
    target={'kind': 'atom', 'id': 'ACTUAL_TARGET_ATOM_ID'},
    electrons=2,
)
# Review candidate geometry and explicitly choose one returned candidate_id.
chosen_arrow = select_route(proposal, chosen_candidate_id, snapshot_cdxml)
result = annotate_selected_route_document(
    bridge, document_id, '/absolute/existing/parent/new-route-review',
    proposal, chosen_candidate_id,
)
```

The source and target each require exactly `kind` and `id`, without manual offsets or controls. The source must be a displayed donor symbol or donor bond; the target must be an atom or bond. Bare atom sources are rejected, so a neutral atom donor needs an explicitly displayed lone pair first. Existing negative charges and lone pairs require two electrons; a graphical electron requires one. Positive-charge donors and symbol targets are rejected. `electrons` is explicitly 1 or 2. `fishhook_side` may be `left` or `right` for one-electron arrows; its default is left.

The planner tests 24 deterministic cubic candidates with different offsets and bends. Atom-target offsets are bounded at 36 pt and avoid the measured atom-label box; controls use the annotation workflow's existing 200 pt coordinate bound. Symbol sources use its calibrated visible-edge rule, and bond sources use the explicit donor bond's midpoint. Endpoint separation is limited to 1 through 600 pt. There is no atom, donor, acceptor or reaction inference.

The collision model includes native measured atom/caption rectangles, atom circles, calibrated symbol circles, conservative bond capsules using effective widths and multiple-bond spacing, existing curve-control/reaction-arrow boxes and the native page box. All text needs native measured bounds. At most 2,000 obstacles are accepted. Each cubic is approximated by 64 line segments with an additional error allowance derived from its maximum second derivative: `6 * max(norm(P0 - 2*P1 + P2), norm(P1 - 2*P2 + P3)) / (8 * 64**2)`. Segment distances include this allowance and half the requested curve width, rather than checking isolated sample points only.

Intended donor-symbol/bond contact, or target-bond contact, is an explicit exception near that endpoint only: at most the first/last 4 of 64 segments, with both segment endpoints within 12 pt of the intended contact. Other objects are still checked in those regions. Exempted contact clearances are not included in the reported minimum. Native arrowhead ink, font substitution, chemical plausibility and every version-specific rendered detail remain uncertified. The planner can reject a visually feasible route.

`line_width` defaults to 0.9 pt, permitted 0.2 through 3. `clearance` defaults to 2 pt, permitted 1 through 12. `max_candidates` defaults to 5, permitted 1 through 10. Candidates rank by approximate length, then clearance and deterministic ID. Each carries a complete ordinary annotation recipe, minimum modeled clearance, obstacle counts, approximation error bound and contact exceptions. The report exposes evaluated/rejected/feasible/omitted counts. No feasible route produces `status: "no_route"` and an empty list, not an overlapping fallback.

`selected_candidate` remains null and `selection_required` true even when only one route is returned. `select_route` checks the source token, regenerates the bounded proposals, and rejects changed candidate geometry. No native operation occurs until an explicit candidate ID is selected.

`annotate_selected_route_file(bridge, path, output_dir, suggestions, candidate_id, pixels=3200)` is the corresponding file entry point. Both selected-route wrappers call the existing annotation workflow. They retain `route-suggestions.json` and audit the original selected recipe, native planned recipe, final mapped curve ID and accompanying source/final snapshot names. No route selection silently changes a molecule or another existing arrow.

## Native grouping research boundary

`plan_native_groups(cdxml, ownership)` prepares a separate, offline native compatibility probe. It serializes one nonnested `group` per owner with exactly `id`, `BoundingBox` and `Integral="yes"`. Owned fragments, selected captions and same-owner curves become its direct children. Cross-owner curves stay at page level. Child IDs, geometry and chemistry are not regenerated.

This serialization follows installed ChemDraw 23.0.1 `BioDrawResources/GS_DNA_4.cdxml` and `GS_Replication.cdxml`, inspected read-only. Both contain integral groups with fragment/curve children. The archived vendor [Group reference](https://chemapps.stolaf.edu/iupac/cdx/sdk/Group.htm) describes the container; [Integral](https://chemapps.stolaf.edu/iupac/cdx/sdk/properties/Group_Integral.htm) describes group-level selection behavior. No sample artwork is copied.

The plan returns `status: "native_probe_required"` and does not run inside `move_document`. The ordinary supported parser still rejects grouped drawings. A successful format plan alone does not demonstrate that manual dragging in the installed application moves the intended members or updates a cross-owner arrow. Native save/group/move behavior must be tested serially on owned copies before any such claim or integration.
