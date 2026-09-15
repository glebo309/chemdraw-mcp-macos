# Complete scope jobs

A scope job combines an offline proposal, explicit candidate acceptance, shared-scaffold drawing, measured category rows, headings, and optional native framing in one callable workflow. It creates new documents and leaves pre-existing documents unchanged.

```python
from chemdraw_macos.scope_job import plan_scope_job, build_scope_job

plan = plan_scope_job(job)  # offline; returns proposal and grouping plan
result = build_scope_job(bridge, job, "/absolute/new-output-directory")
```

The complete acetophenone example is [scope-job.json](../examples/scope-job.json). It explicitly accepts all 14 unique standard candidates and assigns three ordered bands: Reference / donors, Withdrawers, and Bulky / positional. The reference is explicitly included with donors to avoid a separate mostly empty row. These are supplied display categories, not predictions of experimental performance.

## Approval and grouping

The job requires `parent_smiles`, `handle_atom_map`, and an ordered `groups` list. Each group has exactly `label` and `categories`. Supported categories are the standard proposal's `reference`, `electron_donating`, `electron_withdrawing`, `halogen`, `steric`, and `positional` memberships. Labels are unique single-line text of at most 80 characters.

To preview, omit both acceptance fields. `plan_scope_job` returns the complete proposal with `selection_required: true` and no selected structures. Native building rejects that job before creating anything. To approve, provide exactly one of:

- `"accept_all": true`, accepting the entire deterministic proposal.
- `"selected_candidate_ids": ["candidate ID from proposal", "another candidate ID"]`, accepting only those unique known IDs.

The checked-in example already contains explicit `accept_all`; running it is approval to draw its entire proposal. Remove that field when starting an unapproved review. Unknown, duplicate, empty or ungrouped selections fail. Both acceptance keys together fail, including `accept_all: false`.

Each graph appears once, in its first matching group. Proposal order is retained inside each group, regardless of selection-list order. Empty groups are omitted. The plan retains every original category plus `primary_category`, `secondary_categories` and `assigned_group`. Short numeric compound IDs are display bindings only; `selected_candidates` retains their stable graph candidate IDs. Every candidate yield remains `null`; no yield field is accepted and no yield is invented.

## Style and measured layout

Optional fields are `schema_version` (1), `columns` (1 through 24, default 4), `preset` (built-in name or validated numerical custom preset), `layout`, `frame`, `separators`, and `pixels` (256 through 8192, default 3200). Frame and separators default to true. Headings use the supplied nonblank group labels.

| Layout field | Default, pt | Meaning |
| --- | ---: | --- |
| `h_gap` | 18 | Horizontal gap between measured cells |
| `v_gap` | 24 | Gap between rows within a group |
| `label_gap` | 10 | Gap from structure ink to compound caption |
| `margin` | 48 | Inset of the grid's usable page region |

Gaps must be finite numbers from 4 through 144 pt; margin must be 24 through 144 pt. Booleans, unknown layout keys and nonfinite values fail. These values are passed to both initial native drawing and final grouped arrangement. Inter-group heading space is reserved separately using the actual document caption size, with a minimum group gap of caption size plus 28 pt, or `v_gap` if larger.

The example uses compact explicit spacing: 24 pt margin, 12 pt horizontal gap, 16 pt row gap, and 8 pt caption gap. The workflow never shrinks molecules to force a fit. Different fonts, scale, captions, group counts or page dimensions may require different explicit spacing or fewer selected compounds. Page overflow fails; there is no automatic pagination.

The map-free parent is passed as an explicit shared scaffold to native drawing. Final arrangement translates aligned structures and their owned captions together. Each group starts fresh rows; a partially filled row is not shared with the next group. Headings, dotted separators and the rounded shadow frame use the measured native objects through [scope decoration](SCOPE_DECORATION.md). There is no chemistry-based reclassification or relabeling of a mixed grid.

## Outputs and verification

The returned object contains `document`, `output_dir`, `review`, `audit`, and `plan`. The output directory must be new, absolute, and have an existing parent. It contains:

- `review.html`: the native preview and editable/export links.
- `figure/figure.cdxml`, `figure/figure.svg`, `figure/figure.png`: final native-decorated outputs.
- `job.json`, `proposal.json`, `plan.json`: supplied job, complete proposal, acceptance and group bindings.
- `group-layout.json`, `grouped-planned.cdxml`, `grouped-native.cdxml`: measured group placement and native round trip.
- `audit.json` and child drawing/decoration audits: chemical, positional, style, ownership and source-preservation checks.

Successful completion leaves only the final owned document open. Checks preserve native chemical graphs, stereochemistry, scaffold orientation, compound/caption bindings, page fit, nonoverlap and all pre-existing document content. Native decoration verification compares retained geometry, text and style. Machine success does not replace visual review: `visual_review` remains `required`.

After any uncertain native operation there is no retry or automatic close. The audit records uncertainty and owned IDs known to that stage; child audits retain more specific recovery context. Inspect the native document inventory before deciding recovery.

## Limits

This first job API uses the bounded [standard proposal](STANDARD_SCOPE_DESIGN.md), not arbitrary substituent attachments or custom mapped scans. [Custom scopes](SCOPE_EXPANDED.md) remain available separately. It does not infer reaction products, yields, feasibility, category order, acceptance, or a reaction mechanism. Layout supports one physical page, at most the standard proposal's 14 candidates, and existing native drawing/decoration restrictions. Custom font families must pass actual installed-family checks; see [style import](STYLE_IMPORT.md).
