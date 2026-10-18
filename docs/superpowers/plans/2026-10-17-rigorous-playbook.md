# Rigorous Playbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the nine one-line playbook rows into ~45 enforced positions whose thresholds live in `playbook.json` and drive `rules.py`, with sample, eval and UI coverage.

**Architecture:** `playbook.json` becomes clauses → positions (texts with `{placeholders}`, `limits`, `rules`). `playbook.py` loads, migrates, validates and renders it; `rules.py` reads every number through a `Playbook` view passed into `decide()`. Saving or resetting the playbook previews and then re-decides unconfirmed suggestions, like Priority settings.

**Tech Stack:** Python 3.12, FastAPI, pytest (uv); React 19 + TypeScript + Vite.

**Spec:** `docs/superpowers/specs/2026-10-17-rigorous-playbook-design.md` (read it: the position tables are the rule definitions).

## Global Constraints

- Outcomes: `accept | counter | escalate | human_review`. Rule IDs `CLAUSE-A#` / `-C#` / `-E#`, `…P` when widened by priority, `SYS-*` for system checks.
- Order in `decide()`: system checks (error, quote, low confidence < 0.80, conflict, cosmetic) → clause positions → novel (`SYS-NOVEL`, only over accept/counter/no verdict) → `SYS-COMMENT` / `SYS-NORULE`. Unchanged.
- Counters are fixed substitutions on the site's wording or the form's text (`change["original"]`); never new language.
- Escalate floors never move with priority; leniency widens only the three bands (start-up fee, survival, review days), capped at 0.75.
- All contract text fictional. Commits: Conventional Commits, subject only, small.
- Checks: `cd backend && uv run pytest`; `cd frontend && npx tsc -b && npm run lint`.

## Review Focus

- A limit edited so a band is inverted (e.g. `escalate_above` below `standard`) → `PUT` returns 422 with the clause and position named; nothing saved. (Task 1 test `test_validate_rejects_inverted_limits`.)
- An imported playbook missing one rule ID or adding an unknown one → 422 naming the ID. (Task 1 `test_validate_requires_exact_rule_ids`.)
- An old flat `var/playbook.json` on disk → loads as the new default with that file's owners. (Task 1 `test_old_saved_playbook_migrates_owners`.)
- Old decisions carrying `PAY-F2` etc. → playbook preview after an unrelated edit reports no change for them. (Task 3 `test_rename_is_not_a_change`.)
- A change touching two positions (overhead 28% + holdback removed) → one verdict, the stricter (counter at 25% here, ties by position order), rule text naming the other. (Task 2 `test_strictest_position_wins`.)

---

### Task 1: Playbook data and module

**Files:**
- Modify: `backend/data/playbook.json` (rewrite, spec schema)
- Modify: `backend/src/siteline/playbook.py`
- Test: `backend/tests/test_playbook.py` (new)

**Interfaces:**
- Produces (in `playbook.py`):
  - `load_playbook() -> dict` — saved copy if present (old flat list → `migrate(old) -> dict`: default with old owners), else default.
  - `default_playbook() -> dict`; `save_playbook(pb: dict, by: str) -> None` (logs `{at, by, summary}`); `reset_playbook(by: str) -> None` (deletes saved copy, logs); `playbook_log() -> list[dict]`.
  - `class Playbook` built from a playbook dict: `Playbook(pb).limit(clause: str, position: str, key: str) -> float`, `.owner(clause) -> str`, `.positions(clause) -> list[dict]` (playbook order).
  - `render(pb: dict) -> dict` — deep copy where each position gains `standardText`, `counterText`, `escalateText`, and each rule `whenText`, placeholders filled (`{standard}` → `10%` using the limit's unit; integers print without `.0`).
  - `validate_playbook(pb: dict, rule_ids: set[str]) -> list[str]` — errors as strings.
  - `playbook_text(pb: dict | None = None) -> str` — clause → positions (issue, rendered standard/counter/escalate) for prompts.
  - `owner_for(clause_type: str, pb: dict | None = None) -> str` (signature keeps working for `pipeline.py`).
- Content: every position in the spec tables, with `id` (snake_case, unique within clause), `issue`, `form`, `fields`, `standard`, `counter`, `escalate` (use "—" text such as "No escalation: …" where the table has none), `rationale`, `talkingPoints` (2–3), `limits`, `rules`. Limit keys used by Task 2 (exact):
  - payment_terms: `net_days{standard:45, accept_min:30}`, `start_up_fee{standard:10, escalate_above:20}`, `overhead{standard:25, escalate_above:30}`, `holdback{standard:10, accept_min:5}`, `screen_failures{standard:0.33, escalate_above:0.5}`
  - confidentiality: `survival{standard:7, accept_min:5, escalate_below:3}`, `trade_secrets{}`, `affiliates{}`, `marking{}`, `public_records{}`
  - indemnification: `carve_out{}`, `mutual{}`, `claim_notice{accept_max:30}`, `defense{}`, `additional_insured{}`
  - subject_injury: `covered_costs{}`, `coordination{}`, `cap{}`, `exclusions{}`
  - publication: `review{standard:60, escalate_below:30}`, `patent_delay{standard:60}`, `multisite{standard:18, accept_min:12}`
  - intellectual_property: `inventions{}`, `research_license{}`, `background_ip{}`, `patent_prosecution{}`
  - data_privacy: `baa{}`, `secondary_research{}`, `data_use_addendum{}`, `incident_notice{standard:10, accept_min:5}`, `data_transfer{}`
  - termination: `site_notice{standard:30, accept_max:60, escalate_below:30}`, `convenience{}`, `sponsor_notice{standard:30, accept_max:60}`
  - governing_law: `choice_of_law{}`, `venue{}`, `arbitration{}`
- Ordering checks in validation (by key presence): `accept_min ≤ standard`; `standard ≤ escalate_above`; `escalate_below ≤ accept_min` when both; `escalate_below ≤ standard`; `standard ≤ accept_max`.

- [ ] **Step 1: Write failing tests** in `test_playbook.py`:
  - `test_default_is_valid`: `validate_playbook(default_playbook(), RULE_IDS) == []` (import `RULE_IDS` from `siteline.rules`; this passes only after Task 2 — mark it with the other Task 2 tests if running Task 1 alone).
  - `test_render_fills_placeholders`: rendered `payment_terms.start_up_fee.standardText` contains `"10%"`; no rendered text anywhere contains `"{"`.
  - `test_validate_rejects_inverted_limits`: set `start_up_fee.escalate_above.value = 5` → an error mentioning `"payment_terms"` and `"start_up_fee"`.
  - `test_validate_rejects_unknown_placeholder`: standard `"Up to {nope}"` → error mentioning `"{nope}"`.
  - `test_validate_requires_exact_rule_ids`: drop `PAY-C2` → error mentioning `PAY-C2`; add `PAY-Z9` → error mentioning `PAY-Z9`.
  - `test_old_saved_playbook_migrates_owners`: write a flat list (old schema, `payment_terms` owner `legal`) to `SAVED_PATH` (monkeypatched to tmp) → `load_playbook()` is a dict with clauses and `Playbook(...).owner("payment_terms") == "legal"`.
  - `test_save_and_reset_log`: `save_playbook(pb, "Test")` then `reset_playbook("Test")` → `playbook_log()` has 2 entries and `load_playbook() == default_playbook()`.
- [ ] **Step 2: Run** `uv run pytest tests/test_playbook.py -v` → FAIL (import errors).
- [ ] **Step 3: Write `playbook.json`** (all positions, fictional sponsor-side prose) **and implement `playbook.py`** per Interfaces. `CLAUSE_TYPES`, `OWNERS`, `SPONSOR`, `APPROVERS`, `approvers()` stay.
- [ ] **Step 4: Run** `uv run pytest tests/test_playbook.py -v` → PASS except `test_default_is_valid` (needs Task 2).
- [ ] **Step 5: Commit** `feat(backend): structure the playbook as positions with limits`

### Task 2: Rules engine on playbook limits, new positions

**Files:**
- Modify: `backend/src/siteline/rules.py`, `backend/src/siteline/extraction.py` (FIELDS), `backend/src/siteline/priority.py` (docstring only), `backend/src/siteline/api.py` (`bands` in priority settings)
- Test: `backend/tests/test_rules.py` (new); update `backend/tests/test_priority.py`, `test_precedent.py`, `test_pipeline.py` for `PAY-F2`→`PAY-C2` etc.

**Interfaces:**
- Consumes: `Playbook`, `load_playbook` (Task 1).
- Produces (in `rules.py`):
  - `decide(change: dict, extraction: dict, quotes_ok: bool, lenient: dict | None = None, playbook: dict | None = None) -> Verdict` (default `load_playbook()`).
  - `RULE_IDS: frozenset[str]` — every non-`SYS` rule ID the engine can return (incl. `…P`).
  - `RULE_ALIASES: dict[str, str]` — `{"PAY-F2": "PAY-C2", "CONF-F1": "CONF-C1", "IND-F1": "IND-C1", "PUB-F1": "PUB-C1", "TERM-F1": "TERM-C1", "GOV-F1": "GOV-C1", "PUB-A2": "PUB-A1"}`.
  - `bands(pb: dict | None = None) -> dict[str, dict]` — the three widened bands, `standard`/`floor` from limits: start-up fee `start_up_fee.standard` / `escalate_above`; survival `survival.accept_min` / `escalate_below` (leniency widens the 5-year accept line, as today); review `review.standard` / `escalate_below`; `band_limit(field, share, pb=None)`.
  - `WIDENED_CLAUSES = {"payment_terms", "confidentiality", "publication"}`.
- New fields in `extraction.FIELDS` (exact names/formats): `overhead_pct` (percent of direct costs, number), `holdback_pct` (percent withheld, number; 0 when deleted), `screen_failures_per_enrolled` (screen failures paid per enrolled subject, decimal e.g. 0.33, or `uncapped`), `discloses_to_affiliates` (true/false), `marking_required` (true/false), `public_records_disclosure` (true/false), `public_records_notice` (true/false: Sponsor gets notice before disclosure), `claim_notice_days` (integer), `sponsor_controls_defense` (true/false), `additional_insured` (true/false), `removes_injury_exclusions` (true/false), `multisite_wait_months` (integer), `site_may_file_patents` (true/false), `incident_notice_days` (integer business days), `restricts_data_transfer` (true/false), `arbitration_domestic` (true/false). `institution_is_public` stays, described as usable for governing law and confidentiality.
- Rule semantics: the spec tables. Notes the tables leave implicit:
  - Each clause function evaluates all its positions and returns the strictest (`escalate > counter > accept`), ties by playbook position order; the winner's `rule_text` gets `" Also: <id> <text>"` for each other position that fired.
  - `PUB-A1` covers review ≥ `review.standard`; `PUB-A2` is gone.
  - `screen_failures_per_enrolled == "uncapped"` → `PAY-E4`.
  - `CONF-A4` needs `public_records_disclosure` true, `institution_is_public` true and `public_records_notice` true; `CONF-E3` when disclosure is true and either is false; missing → no verdict from this position.
  - `TERM-A2`: `termination_for_convenience` true and `pays_noncancellable_costs` true.
  - Counters with `[form text]` in the spec use `change["original"]`; `[substitute]` uses `_replace_quantity` / `_replace_percent` with the limit written as words-and-digits (`_words(n)` → `"thirty (30)"`, reuse `verify._words` or add `_qty(n)`).

- [ ] **Step 1: Write failing tests** in `test_rules.py` — a helper `v(clause, **values)` building an extraction with confidence 0.95 and a change with `original`/`revised` text containing the number; then one parametrized table test `test_position_rules` with rows `(clause, values, expected_rule_id)` covering every rule ID in the spec tables at and around each limit, e.g. `("payment_terms", {"overhead_pct": "25"}, "PAY-A4")`, `({"overhead_pct": "28"}, "PAY-C3")`, `({"overhead_pct": "31"}, "PAY-E3")`, `({"holdback_pct": "0"}, "PAY-C4")`, `({"screen_failures_per_enrolled": "uncapped"}, "PAY-E4")`, `("publication", {"review_days": "90"}, "PUB-A1")`, `("confidentiality", {"public_records_disclosure": "true", "institution_is_public": "true", "public_records_notice": "false"}, "CONF-E3")`, …; plus:
  - `test_every_rule_id_is_in_the_playbook`: `{r["id"] for c in default_playbook()["clauses"] for p in c["positions"] for r in p["rules"]} == RULE_IDS`, and the set of IDs found by regex in `rules.py` source (excluding `SYS-`) equals `RULE_IDS`.
  - `test_limits_drive_decisions`: copy the default, set `overhead.standard=30, escalate_above=35`, `decide(..., playbook=copy)` on 28% → `PAY-A4`.
  - `test_strictest_position_wins`: payment extraction `{"overhead_pct": "28", "holdback_pct": "0"}` → `PAY-C3` (tie → overhead listed first), `"PAY-C4"` in `rule_text`; `{"net_days": "20", "overhead_pct": "28"}` → `PAY-E1`.
  - `test_counter_never_drafts`: for every counter verdict in the table rows, `counter_text` is `None`, the change's `original`, or the `revised` text with only a quantity/percent/phrase changed (assert it shares the revised text's first 10 characters).
- [ ] **Step 2: Run** `uv run pytest tests/test_rules.py -v` → FAIL.
- [ ] **Step 3: Implement** per Interfaces; rename `F#` IDs in code and existing tests; `api.py` priority settings uses `bands()`.
- [ ] **Step 4: Run** `uv run pytest tests/test_rules.py tests/test_playbook.py tests/test_priority.py tests/test_precedent.py -v` → PASS. (`test_samples.py` and `test_evals.py` may fail until Tasks 4–5.)
- [ ] **Step 5: Commit** `feat(backend): decide every playbook position from its limits`

### Task 3: Re-decide on playbook edits, playbook API

**Files:**
- Modify: `backend/src/siteline/pipeline.py`, `backend/src/siteline/api.py`, `backend/src/siteline/evals/harness.py` (pass playbook through, unchanged behaviour)
- Test: `backend/tests/test_playbook_api.py` (new)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - `pipeline.redecide_open(agreement_id: str, lenient: dict, dry_run: bool = False, playbook: dict | None = None, clauses: set[str] | None = None) -> list[dict]` — `clauses=None` means every clause; priority callers pass `WIDENED_CLAUSES`. Compares `RULE_ALIASES.get(d["ruleId"], d["ruleId"])` to the new rule ID. Owner is re-read from the playbook when it changes and is reported in the change dict as `owner`.
  - `pipeline.replay_playbook(pb: dict, dry_run: bool = False) -> list[dict]` — like `reprioritize_all` over live agreements, every clause.
  - API: `GET /api/playbook` → `{"playbook": render(load_playbook()), "log": playbook_log()}`; `POST /api/playbook/preview` body `{"playbook": {...}}` → `{"changes": [...]}` or 422 `{"errors": [...]}`; `PUT /api/playbook` body `{"playbook": {...}, "by": "Reviewer"}` → validate, save, replay, publish `decision.updated` / `agreement.updated`, return `{"playbook", "log", "changes"}`; `DELETE /api/playbook?by=Reviewer` → reset, replay, same response.
  - Templates only on input: `PUT`/preview strip `*Text` keys before validating.

- [ ] **Step 1: Write failing tests** in `test_playbook_api.py` (fixture: fresh state + Site 07 demo triaged from the seed cache, as `test_samples.py`'s `upload` does):
  - `test_get_returns_templates_and_text`: `standard` contains `"{standard}"`, `standardText` contains `"10%"`.
  - `test_preview_lists_changes_without_saving`: lower `start_up_fee.standard` to 5 → preview lists Site 07's §6.3 change `{"from": {"ruleId": "PAY-A3P"...}}` → anything with a different ID; `load_playbook() == default_playbook()` afterwards.
  - `test_put_redecides_only_unconfirmed`: confirm one decision first; PUT a stricter limit → that decision unchanged, an unconfirmed one changed; `playbook_log()` has 1 entry.
  - `test_put_rejects_invalid`: inverted limit → 422, errors non-empty, nothing saved.
  - `test_delete_resets`: PUT a change, DELETE → `load_playbook() == default_playbook()`.
  - `test_rename_is_not_a_change`: set a Site 07 decision's `ruleId` to `"PAY-F2"` where the engine now says `"PAY-C2"`; preview of the unchanged default → no change listed for it.
- [ ] **Step 2: Run** `uv run pytest tests/test_playbook_api.py -v` → FAIL.
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** `uv run pytest tests/test_playbook_api.py tests/test_priority.py -v` → PASS.
- [ ] **Step 5: Commit** `feat(backend): preview and re-decide open work on playbook edits`

### Task 4: Sample redline coverage (parallel with 5 and 6)

**Files:**
- Modify: `backend/src/siteline/samples.py`; regenerate `backend/data/samples/*.docx`, `backend/data/extraction_cache.json` (`uv run siteline make-samples`, then `uv run siteline make-demo`, then restore unchanged-content demo/template `.docx` files with `git checkout` if only timestamps differ)
- Modify: `backend/README.md` (samples table)
- Test: existing `backend/tests/test_samples.py`

**Interfaces:**
- Consumes: `RULE_IDS`, new FIELDS (Task 2).
- Rules: every ID in `RULE_IDS` (except `…P` other than `PAY-A3P`) and every `SYS-*` except `SYS-ERROR` is the expected rule of at least one sample change. Move the spec's listed changes to their new rules (§6.5 → PAY-C4, §9.6 → IND-A3, §9.7 → IND-A4, §10.5 → SI-A3, §12.4 → PUB-A4, §13.5 → IP-C1, §11.7 → DP-C1, §17.5 → CONF-A4 with clause `confidentiality`); expected IDs renamed `F#`→`C#`; Site 22 §12.1 70 days → `PUB-A1`. Add new changes (one per section, section number's article in the form, `§N.N Title`) for the remaining new IDs and one `SYS-NORULE`. Each new change: segments, hand-written seed values with verbatim quotes, `expect`, `rationale`; wording fictional, in the form's style.
- Update `test_samples_reach_every_rule_and_outcome` to use `RULE_IDS` instead of regex if simpler; keep the assertion that every outcome and priority level is reached.

- [ ] **Step 1:** Edit `samples.py` per Rules.
- [ ] **Step 2: Run** `uv run siteline make-samples && uv run pytest tests/test_samples.py -v` → PASS.
- [ ] **Step 3: Commit** `test(backend): cover every playbook rule in the sample redlines`

### Task 5: Eval set rows (parallel with 4 and 6)

**Files:**
- Modify: `backend/src/siteline/evals/dataset.py`; regenerate `backend/data/evals/labeled_changes.jsonl` (`uv run siteline make-dataset`)
- Test: `backend/tests/test_evals.py`

**Interfaces:**
- Consumes: the spec tables (labels follow the playbook, not `rules.py`).
- Add ~4 labeled rows per new position (at, just inside and just outside each limit, plus wording variants), raise the row cap so none of the existing 150 are cut; `§18.11 Data Residency` becomes `escalate` (DP-E3); keep the 12 precedent items last. Update the module docstring's counts.

- [ ] **Step 1:** Edit `dataset.py`.
- [ ] **Step 2: Run** `uv run siteline make-dataset && uv run pytest tests/test_evals.py -v` → PASS.
- [ ] **Step 3: Commit** `test(backend): label eval rows for the new playbook positions`

### Task 6: Playbook page, decision link

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/api/index.ts`, `frontend/src/pages/PlaybookPage.tsx`, `frontend/src/mocks/playbook.ts` (drop the `playbook` array; keep `SPONSOR`, a static `clauseLabel`, `ownerLabel`, `outcomeLabel`, `outcomeOrder`, `approvers`, `replyMeaning`), `frontend/src/components/siteline/DecisionDetail.tsx`

**Interfaces:**
- Consumes: Task 3 API.
- Produces: types `PlaybookLimit {value: number; unit: string; label: string}`, `PlaybookRule {id: string; outcome: Outcome; when: string; whenText?: string}`, `PlaybookPosition {id, issue, form, fields: string[], standard, counter, escalate, standardText?, counterText?, escalateText?, rationale, talkingPoints: string[], limits: Record<string, PlaybookLimit>, rules: PlaybookRule[]}`, `PlaybookClause {clauseType: ClauseType; label; owner: Owner; summary; positions: PlaybookPosition[]}`, `Playbook {name: string; clauses: PlaybookClause[]}`, `PlaybookChange` (Task 3 change dict), `PlaybookLogEntry {at: number; by: string; summary: string}`; API `getPlaybook()`, `previewPlaybook(pb)`, `savePlaybook(pb, by)`, `resetPlaybook(by)`.
- Page: per clause a section (`id={clauseType}`) with label, owner select, summary; per position a block (`id={`${clauseType}.${position.id}`}`) with issue, form section, the three rendered texts in outcome-coloured columns (click Edit to edit templates), limits as number inputs, rule chips (`whenText` on hover), and a `<details>` for rationale and talking points. Save: preview first ("Saving changes N open suggestions"), then PUT. Reset: DELETE. Load/Export JSON carry templates (strip `*Text`). A log list under the playbook.
- Decision panel: the rule chip links to `/playbook#<clause>.<position>` when the rule ID (or its alias) is in the playbook; position issue shown next to it.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Run** `cd frontend && npx tsc -b && npm run lint` → clean (4 existing warnings).
- [ ] **Step 3: Check in a browser** on an isolated preview backend (blank phones and keys): edit a limit, see the preview count, save, see a decision change on Review; click a rule link from Review.
- [ ] **Step 4: Commit** `feat(frontend): show and edit the playbook as enforced positions`

### Task 7: Docs

**Files:** `CHANGELOG.md`, `backend/README.md`, `CLAUDE.md` (only if a project fact changed)

- [ ] **Step 1:** Changelog entry "A rigorous playbook" (positions, limits drive rules, re-decide on edits, rule renames, coverage); README module list and Playbook mention.
- [ ] **Step 2: Run** full checks (backend pytest, frontend tsc + lint) → pass.
- [ ] **Step 3: Commit** `docs: describe the enforced playbook`
