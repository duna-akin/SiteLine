# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] · Email inbox

### Changed

- **One redline per email:** the mailbox poller only accepts an email with exactly one attachment, and that attachment must be a non-empty `.docx`. Anything else (no attachment, several attachments, a PDF) is blocked: marked read, logged with the reason, and never recorded or triaged. Inline signature images don't count as attachments.
- **Emails wait for a person:** an accepted email lands on the Inbound page untriaged, with its Triage now button, instead of being triaged as soon as it arrives. The same goes for `/api/inbound-emails/simulate`.
- **The address on screen is the real mailbox:** with IMAP connected and no `SITELINE_INBOUND_ADDRESS`, the Inbound and Home pages show `IMAP_USER` instead of the placeholder `redlines@siteline.demo`.

## [Unreleased] · Four outcomes

### Changed

- **Novel is now part of Human review.** A change that adds a term no playbook rule covers is decided by a person on the Review page, the same as an unclear reading, so the two are one outcome: Accept, Fallback, Escalate, Human review. The reason is in the rule: `SYS-NOVEL` (with the new term described) next to `SYS-QUOTE`, `SYS-LOWCONF`, `SYS-ERROR`, `SYS-CONFLICT`, `SYS-NORULE` and `SYS-COMMENT`. A term that is new and also trips an escalation still escalates, and precedent never downgrades it.
- Everywhere: the rules engine, the override form and API, the Word export, the eval labels (16 rows relabeled) and the LLM-only baseline's prompt, the samples' expected outcomes, and the outcome bar and tags on Review. Saved state from before loads with its novel decisions as human review.
- A Human review redline no longer also carries a "Needs your decision" pill; the tag already says it.

## [Unreleased] · A full form agreement

### Changed

- **Every generated redline is a whole contract.** A new fictional form CTA for NSO-417 (`cta_base.py`) has key terms, recitals, seventeen articles (definitions, study conduct, investigator, regulatory and safety, study drug, payment, records and audit, confidentiality, indemnification, subject injury, data protection, publication, IP, term and termination, insurance, compliance, general), a signature page and two exhibits (study summary, budget and payment schedule), about 2,900 words. The Site 07 demo, the nine sample redlines and the seeded inbound emails' attachments are that form with one site's tracked changes applied.
- **Clean template:** `backend/data/templates/NSO-417_CTA_form.docx` is the form with no tracked changes and placeholders for the site's details, for reading or opening in Word. `uv run siteline make-demo` rewrites it from `cta_base.py`, and a test fails if the committed copy drifts from the code.
- The seeded inbound attachments make at most one change per section, in document order, with the rest of the agreement unchanged around it (they used to be twelve redlined paragraphs alone, with repeated and conflicting sections out of order).
- Changed paragraphs keep their exact headings and wording, so seed extractions, quote checks and every expected outcome and rule ID are unchanged; the priority figures' seeds were regenerated for the new text and the stale ones dropped.

## [Unreleased] · The contract is the review screen

### Changed

- **Review shows the whole agreement**, as the site sent it back: title, parties and every article and clause in order, in the document typeface. Each redlined paragraph sits in place, tinted by Siteline's outcome, with deletions struck through, insertions underlined, the site's comment beneath it and what still needs a person (to confirm, needs your decision, awaiting approver, signed off). Clicking a redline opens its decision in a panel beside the contract that stays in view while it scrolls (rule, extracted values, verified quote, precedent, counter text, owner, Confirm, Override and the escalation status), so a change is always judged with the clauses around it. The panel steps to the previous or next change and scrolls the contract with it; on narrow screens the decision opens under its paragraph instead. Links to `#change-…` open the one they name.
- A sticky bar counts the changes per outcome; clicking a count jumps to the next redline with that outcome instead of hiding the rest of the contract. Priority, days waiting, escalations answered and sign-offs share one line under the header.
- Agreements triaged before the full text was stored show their redlined paragraphs alone, with a note.
- **Sites** shows how the selected site's changes were sorted and an "Open contract" link instead of its own redline excerpt.

### Added

- `GET /api/agreements/{id}/document`: every parsed paragraph of the redline, changed or not (404 when none was stored).

### Removed

- The separate decision cards and outcome filter tiles on Review, and the on-screen approver phone. When escalations aren't going out by Photon, the approver's reply (1 approve, 2 counter, 3 reject) is recorded from the escalation's status line in the unfolded decision.

## [Unreleased] · Redline on Sites

### Added

- **Redline in the Sites panel:** choosing a triaged site shows its changed paragraphs in document order, as the site marked them up: deleted wording struck through in place and new wording underlined after it, with the author on hover, site comments, and Siteline's outcome per paragraph. Seed sites without a redline keep their empty state.
- **Override from Sites:** paragraphs marked Human review or Novel show the rule that sent them there and an Override button that opens the same reasoned override form as the Review page (accept, fallback or escalate), with Undo. Overriding to escalate texts the approver, as it does on Review.

### Changed

- **Start from the inbox only:** the seed no longer includes the seven pre-filled site agreements, so the app opens with just the two inbound demo emails. Sites appear once a redline is triaged or uploaded; Home and Sites show empty states until then.

## [Unreleased] · Institutional frontend

### Changed

- **Institutional redesign** of the whole frontend, keeping the calming-neutral palette (#F5F5F5 page, #757575 secondary greys, charcoal text) with one blue-gray accent and muted status tones. IBM Plex Serif headings over IBM Plex Sans body, 1.5px line icons, white panels with hairline borders and 6–8px radii, and restrained buttons.
- **Shell:** a white header with a serif wordmark, plain navigation with an underline for the current page, a rectangular search box and a neutral footer.
- **Pages:** every page opens with an eyebrow, a serif title and a hairline rule. Home, Inbound and Sites carry a row of summary figures. Sites uses a proper data table. Export reads as a document, with serif text, struck-through deletions, underlined insertions and margin comments. Decision cards and redlines use the same redline convention.
- **Approvers by role:** the UI shows approvers by role ("Legal approver", with a scale, landmark or lock mark) and never by name or initials.
- **Quieter motion:** no confetti, no animated beams and no pop-in effects. Transitions are short fades.
- **Imagery:** one greyscale laboratory photo (Unsplash licence) in the Home header.

## [Unreleased] · Sample redlines

### Added

- **Nine sample redlines** (`backend/data/samples/`, Sites 21–29), one fictional CTA per playbook clause. Each one's tracked changes center on that clause's issues, with a few edits elsewhere. Every change has a hand-written seed extraction, so the samples triage without an API key, and an expected outcome and rule ID. Together they reach every clause rule and system check and all three priority levels. `uv run siteline make-samples` rewrites them and their seeds.
- `tests/test_samples.py` uploads each sample through the API and checks the whole path: site and priority read from the contract, the outcome and rule ID of every change, owner routing and simulated texts, the export guard, an approver reply, confirm-all and the Word counter-proposal.

## [Unreleased] · Claude Code extraction fallback

### Added

- **`claude -p` extraction backend** (issue #4): with `SITELINE_CLAUDE_BACKEND=cli` and no `OPENAI_API_KEY`, clause and document extraction run through Claude Code in headless mode on a Claude subscription. Same prompts and JSON schema (`--json-schema`, no tools, no project settings) and the same output shape, so quote checks, rules, cache and UI don't change. At most 3 calls at a time (`SITELINE_CLAUDE_CLI_CONCURRENCY`), a timeout (`SITELINE_CLAUDE_CLI_TIMEOUT`), and the extraction cache still applies. Invalid JSON, a missing structured answer, a usage limit, a timeout or a missing `claude` binary sends the change to human review (`SYS-ERROR`). The Data page shows the model as `claude -p (sonnet)`.

## [Unreleased] · Sunday Morning frontend

### Changed

- **New design** (`mockups/b-sunday-morning.html`): cream, tangerine and trust-blue palette, Fredoka and Nunito, pastel bento tiles. Top bar with Home, Inbound, Sites, Data and Playbook tabs, a search over sites and files, and the Upload button.
- **Home** shows the escalation queue, the text the top approver received (with its priority line), an open-sites radar and ranked list, the inbound feed and where each agreement's data lives, all from the live API.
- **Pages moved:** the inbox became Inbound (mailbox, upload, full escalation queue), the portfolio became Sites, evals moved under Data, and priority settings moved under Playbook. `/portfolio`, `/evals` and `/priority` redirect.
- The extraction step and sponsor chips credit OpenAI.

### Fixed

- The live event stream reconnects (with backoff) after the API restarts, goes quiet, or is unreachable at page load, then refetches what it missed; a triage fails with a message instead of hanging on "Triaging…". The stream closes when the page is hidden, so cached pages no longer use up the browser's connections.
- An override to Human review or Novel no longer looks finished: it stays waiting (backend and UI agree), and the override form offers only Accept, Fallback and Escalate.
- "Escalations waiting" counts only unanswered escalations; queue links scroll to their change; Review and Sites show load errors with a retry; a failed override keeps the form and the typed reason; a successful eval run clears the old error; Export never shows the previous agreement; precedent source rows have unique keys.

## [Unreleased] · Backend fixes from the full code review

### Fixed

- **No unsafe auto-accepts:** a precedent covers an ask only when both have the same fields, and never downgrades an escalation that carries a novel issue. The payment rule checks net days and the start-up fee together and keeps the stricter verdict. Governing law with no governing-law facts is `SYS-NORULE`. Conflicting values for one field go to human review (`SYS-CONFLICT`), and a numeric value must be stated in its own quote.
- **OpenAI migration finished:** `extract_document` uses the OpenAI client (it still called the removed Anthropic one and failed every upload without cached figures). `complete_json` checks every answer (refusal, cut off, content filter, empty, invalid JSON), so the eval baseline records a row error instead of aborting the run. `SITELINE_OPENAI_EFFORT=off` leaves `reasoning_effort` out for non-reasoning models; `SITELINE_OPENAI_TIMEOUT` (default 180s); timeouts say so; one client per event loop for the Chalk tasks. A leftover `ANTHROPIC_API_KEY` logs a warning.
- **Approver replies:** a reply naming a code that is not open (or open on two sites) is never applied to another escalation; the approver gets one clarification text and can answer "Site 12 C04 1". Approvers sharing a phone can answer each other's escalations. Photon webhook redeliveries are applied once.
- **Calls:** a reply recorded while a call is being placed is kept, the timer and "Call now" place one call, and an override cancels (or resumes) the no-reply call. Photon and Twilio network errors are caught, and a failing timer call is logged.
- **Rounds:** a new redline from a site whose agreement was executed starts round 2 under the same agreement ID, keeps the signed round in `previousRounds`, applies the site's earlier precedents, and stores its precedents and final document under round-tagged IDs and keys. A failed precedent save returns 503 instead of marking the agreement executed.
- Export filenames are ASCII (no 500 when the site number is unknown), author names with quotes no longer corrupt the Word file, and one failing inbound email no longer drops the rest of the IMAP batch.
- The Chalk evaluation installs `psycopg`, runs the same precedent step as the local harness (`siteline_verdict`), and scores a row with no output as unsafe.

### Changed

- **Faster eval:** each labeled change runs its extraction and baseline calls together, and 16 changes run at once (was 8, one call after the other). Set it with `siteline eval --concurrency` or `POST /api/evals/run?concurrency=`.

## [Unreleased] · Site priority and cost of delay (issue #2)

### Added

- **Priority from the contract** (`priority.py`, `extraction.extract_document`): one whole-agreement Claude pass reads the site's enrollment target, enrollment period and per-patient amount, each with a verbatim quote checked against the document. Code computes money at risk per week (patients per week × per-patient amount, 52/12 weeks a month) and a level: high, elevated, standard, or unknown (missing, unverified or low-confidence figures; treated as standard). Seeded sites carry study-plan figures.
- **Leniency from priority and days waiting**: a share of the gap between a band's standard and its escalate floor, from a level × days-waiting matrix (defaults: high 50/50/75%, elevated 25/25/50%, standard 0/0/25%; capped at 75%). Only three accept lines widen: start-up fee (10% → up to 17.5%), confidentiality survival (5 → down to 3.5 years) and publication review (60 → down to 37.5 days). New rule IDs `PAY-A3P`, `CONF-A2P`, `PUB-A2P` state the level, money at risk, days waiting and band. Escalate floors and every fail-safe are unchanged.
- **Human confirmation of every suggestion**: accept and fallback outcomes need a person's confirm (per decision, or "Confirm all suggested") before export or completion; a suggestion with a precedent needs its own confirm. Overrides and answered escalations count as confirmed.
- **Editable metrics** in `backend/data/priority_config.json` (UI edits saved to `var/`, with a change log), `GET/PUT /api/priority-config`, a dry-run `POST /api/priority-config/preview`, and a Priority settings page. Saving re-decides only unconfirmed suggestions.
- Priority badge and money-at-risk line in the inbox, review header and radar (blip size = money at risk); inbox and radar table sorted by money at risk, then days open; `GET /api/escalations` queue sorted the same way (reply matching stays oldest-first); approver texts and calls add "Site 07 = high priority, ≈$11,200/week at risk (14% of planned enrollment)."
- Eval harness also decides every row for a high-priority site at the widest leniency and reports its unsafe-accept rate next to the standard one.
- `tests/test_priority.py`: money math, thresholds, unknown cases, a sweep showing no leniency ever lifts an escalation, key vs standard outcomes, the confirmation gate, config bounds and re-deciding.

### Changed

- The Site 07 demo redline and the seeded email attachments state enrollment and per-patient figures (Site 07: 48 subjects over 18 months, USD 18,200 per subject → ≈$11,200/week, high). With high priority, its 15% start-up fee and 4-year confidentiality are accepted (`PAY-A3P`, `CONF-A2P`) instead of countered.
- Tests never text a real approver phone.

## [Unreleased] · Backend

The product now runs end to end. A new `backend/` (Python, FastAPI) replaces every stub in `frontend/src/api/index.ts`.

### Added

- **`backend/`** (uv project, package `siteline`): API on :8000. See `backend/README.md`.
  - Word parsing (`docx_redline.py`, stdlib only): reads tracked insertions, deletions, moves, paragraph-mark changes and comments from a `.docx`.
  - Daytona (`sandbox.py`): each upload is parsed in a fresh ephemeral sandbox with network blocked; only JSON comes back, then the sandbox is deleted. Falls back to the local parser.
  - Claude extraction (`extraction.py`): one call per change, in parallel, with JSON-schema output (clause type, typed values, one verbatim quote per value, confidence, novel issue). Model `claude-opus-5-5` with server-side refusal fallback. Results are cached per change.
  - Quote verification (`verify.py`) and a rules engine (`rules.py`) with a rule ID on every outcome. Failed quotes, confidence under 0.80 and extraction errors go to human review. Counter text comes from fixed substitutions on the site's wording, not generated language.
  - Approvals (`approvals.py`, `photon.py`, `voice.py`): one Photon iMessage per escalation; replies `1`/`2`/`3` come back through a signed Photon webhook; a server-side no-reply timer places a Twilio call through Photon's SIP line and reads the keypad digit. Without credentials, texts and calls go to the on-screen phone.
  - Word export (`export.py`, `docx_writer.py`): accepted site edits folded in, sponsor counters and holds as tracked changes, one comment per decision, pending items left as the site sent them.
  - Inbound email (`inbound_email.py`): IMAP poller that triages `.docx` attachments; the two seeded inbox emails carry generated fictional redlines.
  - Eval (`evals/`): 150 labeled fictional changes (48 should escalate, plus cosmetic, ambiguous and novel cases), a harness that parses them in up to 12 parallel Daytona sandboxes and compares Siteline with an LLM-only baseline, and a Chalk Agent Evals runner.
  - Site 07 demo redline as a real Word file (`data/demo/`), with a hand-written seed extraction so the demo runs offline. `siteline cache-demo` replaces it with live Claude output.
  - Live progress over Server-Sent Events (`/api/events`), state saved to `backend/var/`.
  - 8 offline tests (`uv run pytest`).
- `frontend/src/api/events.ts`: shared EventSource and a triage runner.

### Changed

- Frontend calls the real API: upload shows the pipeline's actual steps and timings; review, export and the approver phone work for any triaged agreement (`/review/:agreementId`); the phone shows whether a text went out through Photon or only on screen; the inbox triages emails; the evals page shows the last real run or an empty state, and runs the eval; playbook saves are validated server-side.
- Payment Terms playbook row: the start-up fee thresholds are now explicit (counter above 10%, escalate above 20% non-refundable) so the rules and the demo agree.
- `vite.config.ts`: `/api` proxy to the backend; `import.meta.dirname` instead of `__dirname`.
- `.chalkignore`: excludes `backend/` and `frontend/` from `chalk apply`.

### Removed

- Mock agreements, emails and eval numbers from `frontend/src/mocks/` (now served by the backend; the eval no longer shows placeholder numbers).

### Fixed

- Photon: texts go out from each approver's own assigned shared iMessage line (looked up from Photon), not one fixed line. People on the same project can be assigned different lines.
- Config: a blank value in `.env` (e.g. `APPROVER_FINANCE_PHONE=`) now counts as unset, so it falls back to the fictional number instead of an empty "real" phone.

### Verified live

- Photon 2.0 iMessage: escalation texts reach real approver phones, and a reply comes back through the signed webhook (via an ngrok static domain), updates the decision, and gets a confirmation text.

### Not yet verified

- Live Claude, Daytona, Twilio voice, IMAP and Chalk calls: no credentials yet (tracked in issue #3). Each path is written against the provider's current API and falls back safely.

## Frontend prototype

Initial Siteline frontend, built from `PRD.docx` (the only product source for this work). The Chalk scaffold files (`CLAUDE.md`, `README.md`, `chalk.yaml`, `pyproject.toml`, `uv.lock`, `.claude/skills/*`) were not used or modified.

### Added

- **`frontend/`**: React 19 + Vite 8 + TypeScript + Tailwind CSS v4 app (`npm create vite` react-ts template).
  - `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`: Tailwind plugin and `@/*` path alias.
  - `components.json`: shadcn config with the `@magicui` registry.
  - Dependencies: `react-router-dom`, `motion`, `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority`; Magic UI peers pulled in by the registry (`canvas-confetti`, `radix-ui`, `next-themes`); dev: `@types/node`.
- **Styling**
  - `src/styles/theme.css`: the provided `@font-face` rules and `:root` palette, verbatim.
  - `src/index.css`: Tailwind tokens mapped onto the palette (`bg-space`, `text-yellow`, `font-serif`…), shadcn semantic tokens, outcome colors (accept = mint, fallback = butter, escalate = red, human review = blue-l, novel = magenta), base styles (focus rings, 44px targets), `prefers-reduced-motion` handling, and Magic UI keyframes.
  - `src/assets/fonts/.gitkeep`: font folder. **The Makcasa and AV Estiana `.woff2` files are not in the repo yet**; the `@font-face` rules are in place and the fallbacks render until the files are added.
- **Magic UI components** (`src/components/ui/`, added via the magicui registry): iPhone, Animated List, Number Ticker, Border Beam, Magic Card, Terminal, Animated Beam, Orbiting Circles, Particles, Animated Circular Progress Bar, Confetti, Shimmer Button, Blur Fade, Ripple, plus shadcn Button.
- **Domain and data**
  - `src/types.ts`: outcomes, 9 clause types, changes, decisions, approvals, agreements, eval results.
  - `src/mocks/playbook.ts`: a fictional sponsor (Northstar Oncology, NSO-417), the 9-clause playbook (standard / fallback / escalate, owner), and approvers for legal, finance and privacy.
  - `src/mocks/site07.ts`: the Site 07 demo redline with 14 changes (3 accept, 4 fallback, 4 escalate, 2 human review, 1 novel) and the parse pipeline steps.
  - `src/mocks/portfolio.ts`: 10 fictional sites, inbound emails, and placeholder eval results (150 labeled changes).
- **Stub API**: `src/api/index.ts`. Typed functions for every backend action. They make **no real GET or POST**; each returns mock data after a short delay and carries a `// TODO: wire to backend` comment naming the intended method and path.
- **State**: `src/state/demo.tsx` and `src/state/decision.ts`. A shared demo store: decisions, overrides, one Photon text per escalation, a 45 s no-reply timer that falls back to a voice call, live reply updates, and toasts.
- **Shell**: `src/components/siteline/AppShell.tsx` (wordmark, desktop nav, mobile menu, skip link, focus on route change, sponsor footer, toasts), `StarField.tsx` (particles and nova backdrop), `SponsorChip.tsx`.
- **Screens** (`src/pages/`, route-level code splitting in `src/App.tsx`):
  - `/`: `InboxPage`, the agreement inbox with KPIs, outcome-mix bars, and an inbound email panel.
  - `/upload`: `UploadPage`, with drag-and-drop `.docx`, the demo file, Local parser and Cached extraction flags, an animated pipeline (Daytona sandbox → Claude extraction → quote verification → rules → sandbox deleted), a sandbox log, and a 30 s target timer.
  - `/review/site-07`: `ReviewPage`, with outcome filters, decision cards (`DecisionCard.tsx`, `RedlineDiff.tsx`, `outcome.tsx`), the on-screen approver iPhone (`ApproverPhone.tsx`) with an iMessage thread, 1/2/3 replies, a voice-call fallback with keypad, and confetti when every escalation is approved.
  - `/review/site-07/export`: `ExportPage`, a Word-style counter-proposal preview with tracked changes, one comment per decision, a pending warning, and a `.docx` download stub.
  - `/portfolio`: `PortfolioPage`, a radar of days open and stuck clauses with a 90-day target ring, site detail, and an accessible table.
  - `/evals`: `EvalsPage`, Siteline vs the LLM-only baseline: unsafe accept rate, escalation recall, triage accuracy, quote pass rate, latency, a confusion matrix, and a Chalk Agent Evals run panel with 12 parallel Daytona sandboxes.
  - `/playbook`: `PlaybookPage`, an editor for the 9 clause types (owner, standard, fallback, escalate) with load/export JSON, validation, reset, and a save stub. The Publication row flags the open 75-day fallback question.
- `src/hooks/useNow.ts`, `src/lib/format.ts`, `src/lib/tokens.ts`, `src/lib/utils.ts`: small helpers.
- `public/favicon.svg`: Siteline nova icon. `index.html`: title, description, dark class.

### Changed

- `frontend/README.md`: replaced the Vite template text with run instructions.
- `src/components/ui/button.tsx`: fixed the registry import of `cn` (`"cn"` → `"@/lib/utils"`).
- `src/components/ui/particles.tsx`: replaced the `NodeJS.Timeout` type with `ReturnType<typeof setTimeout>` so it typechecks in the browser build.

### Removed

- Vite template boilerplate created during scaffolding: `src/App.css`, `src/assets/react.svg`, `src/assets/vite.svg`, `src/assets/hero.png`, `public/icons.svg`.
- A stray `cn` npm package that the shadcn CLI added.

### Fixed

- Horizontal overflow at 375px on Upload and Evals: grids now default to `grid-cols-1` and use `minmax(0, …)` columns.
- Sandbox log lines were clipped: the terminal now wraps lines and sizes to its content.
- Radar: sites with few days open no longer pile up on the center point.

### Verified

- `npx tsc --noEmit -p tsconfig.app.json` and `npm run build`: 0 errors. The build warns that the font files are missing, which is expected until they are added.
- `npm run lint` (oxlint): 0 errors. The remaining warnings are in Magic UI registry files, plus the standard provider-and-hook pattern in `state/demo.tsx`.
- A headless Chromium run of 32 checks passed: every route at 375px and 1440px with no horizontal scroll and no console errors; the demo path (upload → 14 cards → 4 texts → reply "1" updates the card → no reply triggers a voice call → press "2" → override needs a reason → export lists 14 decisions → download stub); the playbook shows 9 rules with the open question; eval re-run; no requests leave the dev server.

### PRD coverage

| PRD requirement | Priority | Screen / component | Status |
|---|---|---|---|
| Parse a Word file's tracked insertions, deletions and comments | P0 | `/upload`, pipeline step "Tracked changes parsed"; `RedlineDiff` | Done (UI; parsing is stubbed) |
| Map each change to one of 9 playbook clause types | P0 | Card eyebrow; `mocks/playbook.ts` | Done |
| Extract values with Claude, verbatim quote, verify the quote | P0 | Card "Extracted values" and "Quote verified / failed verification"; pipeline step | Done |
| Rules engine assigns one outcome per change and logs the rule | P0 | Card "Rule fired" with rule ID | Done |
| Review screen: outcome, rule, quote, owner, override with reason | P0 | `/review/site-07` · `DecisionCard` | Done |
| Approval by Photon text; reply updates the card live | P0 | `ApproverPhone` iMessage thread, 1/2/3 replies | Done |
| Eval: Siteline vs LLM-only baseline, ~150 labeled changes | P0 | `/evals` | Done (placeholder numbers) |
| Demo file Site 07 (14 changes), playbook, labeled set | P0 | `mocks/site07.ts`, `mocks/playbook.ts`, `mocks/portfolio.ts` | Done |
| Parse each upload in a Daytona sandbox | P1 | `/upload` pipeline (create → parse → JSON → delete) | Done (UI) |
| Voice call if the text gets no reply | P1 | 45 s timer → `CallScreen` with keypad; "Simulate no reply" | Done |
| Export counter-proposal as Word with comments | P1 | `/review/site-07/export` | Done (download stubbed) |
| Agreement inbox and portfolio radar | P1 | `/` and `/portfolio` | Done |
| Chalk Agent Evals for the eval run | P2 | `/evals` run panel | Done (UI) |
| Inbound email: a site emails its redline | P2 | Inbox "Inbound email" panel | Done (UI) |
| Playbook editor (else load from JSON) | P2 | `/playbook` | Done |
| Upload to decision list < 30 s | Metric | `/upload` timer and target bar; review header | Done |
| Unsafe accept rate, escalation recall, triage accuracy, quote pass rate | Metric | `/evals` cards and confusion matrix | Done |
| Approve escalations from a phone in under a minute | Goal | Card shows reply time | Done |
| Low confidence goes to human review | Risk | Changes 09 and 12 | Done |
| Local parser flag; cached extraction for the demo file | Fallback | `/upload` toggles and badge | Done |
| Teammate iPhone or on-screen phone | Fallback | On-screen iPhone | Done |
| Sponsor attribution (Photon, Daytona, Chalk, Claude) | Sponsors | `SponsorChip` on each screen and the footer | Done |
| Clean room: no real contract or Merck material | Non-goal | All mock content is fictional; footer note | Done |
| Publication 75-day fallback open question | Open question | Flagged on the Publication playbook row | Done |
