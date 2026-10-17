# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
