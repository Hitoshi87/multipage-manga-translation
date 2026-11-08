# Automation v2: long runs with fewer manual touches

A volume is about 200 pages and roughly 1,900 text segments. Reviewing every flagged line by hand does not scale, so the
pipeline now decides what is certain and sends a person only what is ambiguous. Everything here is deterministic or
bounded and checkpointed; none of it changes a human-approved translation.

## Typesetting (scripts/core.jsxinc, mirrored in manga_ai/layout_plan.py)

One planner chooses size, line count, line breaks and position by a single score.

| Term | Effect | Where |
|---|---|---|
| Wrap cost | Penalises breaks after an opening quote, after a bare ellipsis, inside a quotation, after function words, and a lone short word on a line | `wrapScored` |
| Fill term (`fillWeight` 5, `fillTarget` .38) | A mostly empty balloon prefers more lines, so short text stacks and fills it | `tryAt` |
| Sparse boost (`sparseFill` .18, `sparseBoost` 1.12) | A still-empty balloon may exceed the page cap slightly | end of `planLayout` |
| Optical centring | Centres the cap-height core of the first and last line, not the accent/descender ink box; Photoshop places the first baseline directly | `tryAt`, `addText` |
| Displacement | Hard limit of 5% of the width off the body centre; vertical shift limited to about 3%; the centre is the width-weighted centre of the balloon body | `tryAt` |
| Smoothing | A smaller size is accepted when it gives clearly better breaks (size penalty 1.2 per unit of relative loss) | end of `planLayout` |
| Page cap | No balloon may exceed 1.3 x the lower median fit size of the page | `pageSizeCap` |
| Leading | Default 1.05 (comic preset 1.08) | UI presets |

`tests/test_layout_plan_parity.py` runs the JS planner under Node and requires the Python mirror to agree exactly.

Balloon geometry is improved before layout:

* `manga_ai/shape_completion.py` extends a mask that stops short on one side (transparent balloons), only up to the first
  long dark stroke, and never for split children or irregular shapes.
* `split_text_groups_watershed` separates chained balloons joined by a neck; `split_text_groups_separator` separates boxes
  that share one straight ink line. Regions that still hold several confident text groups get `merged_suspect`, shown as
  `[NGHI GỘP Ô — CẦN TÁCH]` on the layer and as high priority in the draft review.

## Text conventions (manga_ai/translation/textnorm.py and `normalizeText` in core.jsxinc)

Display-only; the saved translation is never edited. Both implementations share `tests/fixtures/textnorm_cases.json`.

* Japanese brackets, full-width marks and decorative symbols (♡ ♥ ♪ ★) are replaced, because comic fonts cannot draw them.
* At most one ellipsis per bubble (at the end, or after a short interjection); none leading. A leading ellipsis moves to
  the end of the previous unfinished bubble (`normalize_page`, applied as `display` in `export_mapping`).
* The first letter of every bubble and sentence is capitalised; `upper` mode serves all-caps fonts.
* A spaced em dash used as a clause joiner becomes a comma.

## Translation (manga_ai/translation)

| Module | Job |
|---|---|
| `autopilot.py` | Retries transient errors with backoff, parks groups that keep failing, stops on systemic errors (key, 401/403), resumes, and runs in time slices (`budget_seconds`) for the Photoshop bridge. `estimate` reports ETA and cost from measured latency and usage |
| `triage.py` | Excludes banners, titles, copyright lines, page numbers and text outside any balloon before translation. Reversible; a person's restore is final; verified or hand-corrected sources and runs with translated groups are untouched |
| `shorten.py` | Estimates lettering size with the planner, sends only cramped lines (no fit, at minimum size, far below the page body size) to the model with a character budget, accepts clearly shorter clean rewrites, keeps history, never touches human-approved lines |
| `cast.py` | Infers characters and address terms from the first pages' text. Items are HINTS until confirmed; confirmed items are authoritative; rejected items are dropped; decisions survive re-analysis. Rendered into the prompt as `CAST CONTEXT` |
| `qa.py` | Deterministic warnings: `japanese_left`, `odd_symbols`, `dash_added`, `leading_ellipsis`, `ellipsis_heavy`, `long_for_bubble` |
| `providers.py` | A malformed gateway answer (missing `choices`, error object) is retried, then reported readably |

The command line runs the whole chain without time limits:

    .venv/bin/python manga_typesetter.py translate --project <project.json>
    .venv/bin/python manga_typesetter.py translate --project <project.json> --estimate-only

Photoshop calls the same steps as bridge operations: `translation_autopilot`, `translation_auto_shorten`,
`translation_auto_exclude`, `translation_estimate`, `translation_cast_analyse`, `translation_cast_confirm`,
`translation_cast_show`.

## The unattended workflow (tab "Tự động")

The first tab is the only screen a non-technical user needs: choose the folder of pages, check the series name and mode
(fast, or quality with image reading), press Start, and leave. The older tabs remain as advanced settings.

1. **Preflight.** `manga_ai/preflight.py` picks three pages spread through the volume (about 25%, 50%, 75%). The pipeline
   runs on them in a separate project and scores what it did: how many bubbles were translated, cleaned and lettered to fit.
   * `go`: the sample is good; the full volume starts by itself.
   * `escalate`: cleaning is weak with the standard engine; the sample is repeated once with the AI redraw engine
     (`art_draft`), whose redrawn areas are flagged for review. The AI engine is already the default when its models exist.
   * `stop`: even the best engine does poorly, or translation failed (key, API, OCR). The person is told why before hours
     are spent. Thresholds (clean 80%, translated 90%, lettered 85%, at most a third of sample pages failing) are heuristics
     meant to catch clearly poor runs.
2. **Full run** (`runVolume` in `Photoshop_Typeset.jsx`, also used by the older "Chạy volume" button): scan, OCR, cast
   analysis, auto-exclude, autopilot translation, auto-shorten, then clean and typeset page by page. A failing page is
   recorded and the run continues; every page that can be exported produces a PSD.
3. **Report.** `manga_ai/report.py` writes `BAO_CAO.html` next to the draft log: counts of pages that are fine, worth a
   look, or need fixing; a card per flagged bubble with a crop of the page, the lettered line, the Japanese source and the
   reason in plain Vietnamese; then a table of all pages.
4. **Quick review** ("Rà soát nhanh trong Photoshop"). The queue (`review_queue`) lists items urgent first. For each item the
   dialog can open the PSD and select the bubble's layer, re-letter that bubble with edited text (the correction is also
   stored in the project as human approved), nudge or resize it, and mark it done. Progress is kept in
   `review_state.json`, so closing the dialog and returning later continues where it stopped.

## Layers in the PSD

* `CLEAN — từng bubble`: one layer per cleaned or redrawn bubble (`CLEAN B007`, `CLEAN AI — CẦN DUYỆT B002`), cropped to the
  painted pixels. Produced by `manga_ai/clean_layers.py`, which assigns each overlay pixel to the bubble outline that owns it;
  the pieces recombine into exactly the original overlay. Pages with more than 120 bubbles, or any failure, keep the single
  page overlay.
* `TYPESET — Tiếng Việt`: one text layer per bubble, named `[THOẠI] B007 | …`. The review dialog finds layers by these
  names (`MTA.findRegionLayers`).

## API key without environment variables

The key is read from the environment variable first, then from `~/.manga_typesetter/<NAME>.key`. The automatic tab has
three editable fields: Host, model name and API key. Host and model are remembered in `~/.manga_typesetter/easy_settings.json`;
the key is written to the key file once (permissions 600 on macOS and Linux) and cleared from the field. The key never travels in request files or
logs, and `key_status` reports only whether one exists and where it came from.

## Output: layered Adobe Photoshop PDF first

The deliverable is one Adobe Photoshop PDF per page that keeps every layer (`PDFSaveOptions` with `preserveEditing` and `layers`,
JPEG high quality, colour profile embedded). It goes to print from there, so there is no separate print export. The automatic tab
saves that file by default and saves a PSD only when "Lưu thêm file PSD" is ticked. The review dialog opens whichever file a page
produced (PDF first) and saves back to the same kind of file, so a layered PDF stays a layered PDF. Opening a Photoshop PDF that
keeps its editing data restores the layers in Photoshop; this is assumed, not verified here.

## Line spacing

Auto leading is the default: the panel's "Tự động (Auto)" box sets Photoshop's own Auto leading percentage (105% of the size) so the
spacing follows the size if someone resizes the text later, and no number is asked for. The percentage is set and read back; if
Photoshop does not honour it, the layer falls back to an explicit leading equal to the planned one so the layout is not broken.
Unticking Auto re-enables the numeric field.

## Known gaps

* Photoshop behaviour (real text metrics, baseline placement) is covered by the parity tests and by Pillow previews, not
  by a native run.
* Merging the per-page PDFs into one file is not done (and would be done by Photoshop, not an external library).
* A region that still merges two balloons is flagged, not split; typesetting does not slice its shape.
* No UI yet for confirming cast items; use `translation_cast_confirm`.
* The review dialog cannot re-clean a single bubble; it can re-letter, move, resize and mark done. It is modal, so manual
  editing happens after closing it (progress is remembered).
* Everything in the Photoshop panel is verified only by syntax checks and DOM mocks, not by a native run. Per-bubble clean
  layers add one file open per bubble, so page time rises by an amount not yet measured.
* All thresholds are heuristics tuned on five pages. Review a sample of auto-accepted lines per volume to estimate the
  real error rate before trusting them.
