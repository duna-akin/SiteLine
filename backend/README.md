# Siteline backend

FastAPI service behind the Siteline frontend. It parses a site's redlined Word file,
extracts clause values with OpenAI, verifies every quote, applies the playbook rules,
texts approvers through Photon (with a voice-call fallback), and exports the
counter-proposal as Word with tracked changes and comments.

## Run

```bash
cd backend
cp .env.example .env        # fill in the keys you have; all are optional
uv run siteline serve       # http://127.0.0.1:8000, proxied by the Vite dev server at /api
```

Then start the frontend (`cd frontend && npm run dev`) and open http://localhost:5173.

Other commands:

| Command | What it does |
|---|---|
| `uv run siteline make-demo` | Rewrite `data/demo/NSO-417_CTA_Site07_redline.docx`, the clean form `data/templates/NSO-417_CTA_form.docx` and the seed extraction cache |
| `uv run siteline cache-demo` | Extract the demo file with OpenAI and save that as the demo cache (needs a key) |
| `uv run siteline make-samples` | Rewrite the nine per-clause sample redlines in `data/samples/` and their seed extractions |
| `uv run siteline parse FILE.docx` | Print a redline's tracked changes as JSON |
| `uv run siteline make-dataset` | Rewrite the labeled eval set (231 playbook changes + 12 precedent cases) |
| `uv run siteline eval [--limit N]` | Siteline vs the LLM-only baseline; writes `data/evals/latest.json` |
| `uv run siteline reset` | Clear agreements and approvals back to the seeded inbound emails |
| `uv run pytest` | Offline tests (parser, rules, quotes, export, eval set) |
| `uv run --extra chalk python -m siteline.evals.chalk_eval` | Same comparison on Chalk Agent Evals |

## What runs without keys

| Integration | Key | Without it |
|---|---|---|
| OpenAI extraction | `OPENAI_API_KEY` (optional: `SITELINE_OPENAI_MODEL`, `SITELINE_OPENAI_EFFORT` (`off` for non-reasoning models), `SITELINE_OPENAI_TIMEOUT`) | Only cached changes are extracted (the demo file ships with a hand-written seed); anything else goes to human review |
| Claude Code extraction | `SITELINE_CLAUDE_BACKEND=cli` and no `OPENAI_API_KEY`; a logged-in `claude` CLI or `CLAUDE_CODE_OAUTH_TOKEN` (optional: `SITELINE_CLAUDE_CLI_MODEL` (default `sonnet`), `SITELINE_CLAUDE_CLI_TIMEOUT`, `SITELINE_CLAUDE_CLI_CONCURRENCY` (default 3)) | Extraction runs through `claude -p` on a Claude subscription: same prompts and schema, about 2s per change, 3 at a time. Counts against the plan's usage limits, so run `siteline eval --limit N`; Chalk and Daytona still need an API key |
| Daytona parsing | `DAYTONA_API_KEY` | Local parser (same code) |
| Photon texts | `PHOTON_*` + real `APPROVER_*_PHONE` | On-screen phone in the UI |
| Voice call | `TWILIO_*` + `PUBLIC_BASE_URL` | On-screen call keypad |
| Inbound email | `IMAP_*` (optional: `SITELINE_INBOUND_ADDRESS`, which defaults to `IMAP_USER`) | Seeded inbox emails only. With a mailbox, only an email with exactly one `.docx` attached gets in, and it waits on the Inbound page for someone to triage it; any other is blocked (marked read and logged) |
| Eval | `OPENAI_API_KEY` (or the Claude Code backend) | Evals page shows "no run yet" |
| Precedent history | `DATABASE_URL` | Precedents are kept in `var/state.json` |
| Source documents | `S3_*` (Supabase Storage) | Final documents are kept in `var/documents/` |

## Canonical extraction terminology

`src/siteline/cta_terminology.json` preserves the complete supplied version
`1.1-extraction-compatible` dictionary. The clause system prompt includes its field
definitions, semantic hints, category aliases and guardrails as contextual examples.
They do not match keywords or decide negotiation outcomes. The dictionary's standalone
`extraction_prompt` remains in the source file for reference; its incompatible output
format is not sent to the model.

The dictionary covers the original 34 canonical fields. The live `FIELDS` registry
also retains the 16 fields added for the expanded playbook (50 total), plus the expanded
`institution_is_public` description for agreement context and public-records terms.
The full live registry determines supported names; the dictionary is a semantic subset.
The strict response remains unchanged:
`clause_type`, `values[{field,value,quote}]`, `novel_issue`, `confidence`, `rationale`.
Values remain strings and quotes must be verbatim. Missing fields are omitted, never
filled with false or null. Ambiguous or conditional facts that cannot fit one canonical
value are omitted and explained in `rationale`, with confidence below 0.8 for human
review. A concept outside all supported live fields is identified as `Proposed field: <concept>` in
`novel_issue`; this does not extend the schema or rules. A field without a playbook rule
(such as the existing ML-training field) is not automatically a proposed new field.

The pipeline still supplies one change plus the first twelve paragraphs of agreement
context. Definitions or cross-references outside that context may remain unresolved;
the prompt asks the model to flag that uncertainty. Investigator-initiated arrangements
require resolving Institution, Sponsor-Investigator, Company and Funding Agency by
contractual duties before assigning sponsor-directed values.

Live clause entries now use `clause-v2-` keys based on the actual system and user prompts,
including terminology, current playbook context, party context and tracked edits. Old
unversioned **runtime** clause entries are ignored, retained on disk, and regenerated
when a live backend is available. Without one, an uncached change goes to human review.
The committed demo/sample seeds keep their original keys and content as an explicit
fallback; stale runtime entries cannot override them. Thus cached demos still demonstrate
the old hand-written extractions, not the expanded prompt. A fresh versioned live result
takes precedence over a matching seed. `use_cache=False` bypasses both kinds of reads
and writes only to the runtime cache. Document-figure extraction and its cache are
unchanged. `siteline cache-demo` still explicitly replaces demo seeds; it is not required
for this integration and was not run.

Run focused offline tests from `backend/`:

```bash
uv run python -X utf8 -m pytest tests/test_extraction.py tests/test_extraction_semantics.py tests/test_extraction_cache.py -q
uv run python -X utf8 -m pytest -q
```

UTF-8 mode avoids the existing state writer's Windows default-encoding limitation.
The tests verify terminology delivery, schema compatibility, quoted evidence, cache
behavior and scripted extraction-to-rule outcomes across synonyms, negations and
conditions. Scripted model responses do **not** verify LLM interpretation. Live validation
must exercise those language cases with cache reads disabled, including party-role
resolution, silence, conditional inventions/notice periods and publication timelines.
The existing broader live eval is `uv run siteline eval --limit N` and requires a model
backend; it does not replace a review of these new semantic cases.

This terminology integration preserves the expanded negotiation rules and playbook,
cost-of-delay priority scoring, and document-figure extraction. Public-records disclosure
terms retain their confidentiality classification wherever they occur in the agreement.
Existing policy limits still need a separate review before any rule changes: mutual
publication extensions need contextual interpretation; public-institution governing-law
handling is broader than the playbook's home-state wording; missing refundability or
non-cancellable-cost facts can still conservatively escalate; and some canonical fields
have no dedicated decision rule. These are not resolved by adding vocabulary.

## Postgres (precedent history)

Precedents live in one `precedents` table (created on first use) with two queries:

- **Read, at upload:** the accepted terms on record for the uploading institution (matched on its
  normalized name). The rules run first; a matching acceptance can turn an escalation into
  `PREC-A1`.
- **Write, at confirmation:** **Confirm agreement** on the export page (`POST
  /api/agreements/{id}/complete`, refused while anything is pending) keeps the final document
  under `{agreementId}/…_final.docx` (bucket or `var/documents/`), saves every accepted term with that key and its
  section and quote, and marks the agreement executed. Approver replies alone write nothing.

Without `DATABASE_URL` the same two operations use `var/state.json`.

The final document goes to the S3 bucket set by `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY` and `S3_BUCKET` (Supabase: Storage → Settings → S3 Connection). It is
uploaded before any precedent is written, so a precedent never cites a missing file. The UI
opens it through `GET /api/sources?key=…`: each precedent on a decision card links to it, and the
export page links to the agreement's own final document once confirmed.

```bash
createdb siteline                                         # local Postgres (e.g. brew services start postgresql@16)
echo 'DATABASE_URL=postgresql://localhost/siteline' >> .env
```

To move to Supabase, replace `DATABASE_URL` with the project's connection string (Connect →
Session pooler, ending in `?sslmode=require`). No code changes. `siteline reset` and the demo
reset clear agreements and approvals but leave Postgres precedents alone. Tests never touch a
database unless `SITELINE_TEST_DATABASE_URL` points at a throwaway local one.

## Photon setup notes

Siteline uses **Photon 2.0** (dashboard at https://app.beta.photon.codes, REST API at
`https://api.photon.codes/v1`). The Photon CLI (`@photon-ai/cli`) and `create-spectrum-project`
only reach classic Photon, so they are not used. The API's schema is at
https://api.photon.codes/openapi.json.

- **Credentials:** `PHOTON_API_KEY` is the project key (`pho_sk_…`, valid only under its own
  project); `PHOTON_PROJECT_ID` is `pho_prj_…`. A wrong project ID returns 403.
- **Approvers:** add each phone under iMessage → "Add someone to the line". Photon assigns every
  person one of the project's **shared lines**, and different people can land on different
  lines. Siteline looks up each approver's line (`GET …/platforms/imessage/assignments`) and
  sends from it. A shared line only sends to someone who has messaged it since their
  assignment, so each approver texts **their own assigned line** once before the demo.
- **Webhook:** one destination for `message.received` (API version `2026-07-01`) pointing at
  `$PUBLIC_BASE_URL/api/webhooks/photon`. It can be created and updated with the project key
  (`POST`/`PATCH …/webhooks/destinations`; writes need an `Idempotency-Key` header). The
  `signingSecret` is returned once on create; it goes in `PHOTON_WEBHOOK_SECRET`.
- **Voice:** calls run on the project's SMS number (`PHOTON_NUMBER`), not the iMessage line:
  set up a voice profile on it with SIP to Twilio. Carrier campaign registration is only needed
  for sending SMS texts, which Siteline does not do.
- A reply of `1`, `2` or `3` answers that approver's oldest open escalation; `C04 2` picks one.
- With all three approver phones set, **every upload texts real people**. Blank the
  `APPROVER_*_PHONE` lines to rehearse with simulated texts, answered from the Review page.

## Public URL (ngrok)

Photon and Twilio callbacks need a public HTTPS URL. The team uses ngrok's free static dev
domain, so the URL and the Photon webhook never change:

```bash
ngrok http --url=https://sudden-playlist-untimely.ngrok-free.dev 8000
```

Set `PUBLIC_BASE_URL` to that URL. A Cloudflare quick tunnel also works, but its URL changes on
every restart (then update the webhook and `.env`); a named Cloudflare tunnel needs a domain on
Cloudflare. ngrok's browser warning page does not affect server-to-server webhooks.

## Site priority: value lost per week of delay

Each site's "money at risk per week" is the risk-adjusted present value of the trial delay
caused by one more week without that site. It is computed in `priority.assess` from two
figures quoted verbatim from the site's contract (subjects to enroll, enrollment months) and
the study inputs in `data/priority_config.json`, which can be edited on the Priority page.

```
site share of enrollment  s = (site subjects / site months) / (planned subjects / study months)   capped at 1
trial delay per site-week d = 7 × s days
value of one trial day    V = p × S / (1 + r)^L  +  C
money at risk per week      = d × V
```

| Input | Default | Source |
|---|---|---|
| S, sales per day on the market | $840,000 | Tufts CSDD 2024 (Smith, DiMasi, Getz), median for oncology, 2023 US$ |
| p, chance of approval | 9.3% | BIO/Informa/QLS, *Clinical Development Success Rates 2011–2020*: Phase II, solid tumors |
| L, years to launch | 7.6 | Same report, oncology: Phase II 3.7 + Phase III 3.1 + review 0.8 years |
| r, discount rate | 10.5% | DiMasi, Grabowski, Hansen 2016 (*J Health Econ* 47): real cost of capital |
| C, direct trial cost per day | $23,737 | Tufts CSDD 2024: Phase II, 2023 US$ |
| Planned enrollment / study months | 340 / 24 | Fictional NSO-417 study plan |

With these inputs a trial day is worth about $60,300 ($36,600 in sales, $23,700 in trial
costs). Site 07 (48 subjects over 18 months, 19% of the study's enrollment rate) delays the
trial 1.3 days per week it waits: about $79,500 a week. Levels: high at $75,000 a week or
more, elevated at $45,000 or more.

Why the terms are there:

- **Enrollment is the critical path.** The study ends when planned enrollment is reached. A
  week without this site's patients pushes the end out by the time the rest of the study takes
  to enroll them, which is 7 days times the site's share of the enrollment rate.
- **A fixed patent expiry turns delay into lost sales.** A later launch doesn't defer the sales
  window, it shortens it. A day of delay removes a day of sales at launch, L years away.
- **Risk and time.** Those sales only happen if the drug is approved (p) and are worth less
  today (discounted at r over L years). Trial costs are paid now and in full, so they are
  neither weighted nor discounted.

Assumptions and limits:

- Sales per day is a lifetime average (total sales divided by days on market), so the model
  treats sales as flat. It values sales, not profit.
- Other sites keep their pace and don't absorb this site's patients. Under competitive
  enrollment, the real delay is smaller.
- The site enrolls at its contracted rate from activation. Ramp-up and screen failures are ignored.
- The per-patient amount is still read and shown, but it doesn't change the value lost.
- Missing or unverified enrollment figures give priority "unknown", treated as standard.

## Sample redlines

Every generated redline (the Site 07 demo, these samples and the seeded inbound emails' attachments)
is the same fictional form agreement, `cta_base.py`, with one site's tracked changes applied: key
terms, recitals, seventeen articles, the signature page and two exhibits, so each one reads as a
whole contract on the Review page. The clean form itself, with placeholders for the site's details
and no tracked changes, is `data/templates/NSO-417_CTA_form.docx`.

`data/samples/` holds nine fictional CTAs (Sites 21–29), one per playbook clause, for demos and
tests. Upload any of them on the Inbound page. They triage from seed extractions, so no key is
needed, and each change lands on the rule ID listed in `samples.py`.

| Site | Clause | What to look for |
|---|---|---|
| 21 Copperline | Payment | Net 20 escalates; the 14% fee is accepted only because the site is high priority (`PAY-A3P`); deleted holdback and 28% overhead are countered; uncapped screen failures escalate |
| 22 Halvorsen | Confidentiality | 2-year survival, trade-secret cap and a private site's public-records clause escalate; affiliates and marking are countered; a site comment and a low-confidence read go to review |
| 23 Marrowgate | Indemnification | Carve-out removed, mutual indemnity, site-controlled defense, 35% overhead and deleted injury exclusions escalate; "as finally adjudicated" and 60-day claim notice are countered; the damages-waiver edit has no rule (`SYS-NORULE`) |
| 24 Saltmarsh | Subject injury | Pain and suffering and an uncapped reimbursement escalate to Finance; travel costs accepted; arbitration in Georgia countered |
| 25 Thornbury | Publication | 21-day review, patent delay removed, open-ended thesis review escalate; 12-month multi-site wait and 5% holdback accepted; public-institution law accepted |
| 26 Ashgrove | Intellectual property | Institution and joint ownership escalate; the research license is pre-approved; the site's own patent filings, 6-month multi-site wait and one-in-two screen failures are countered |
| 27 Kestrel Valley | Data protection | BAA, blocked secondary use and Washington-only data escalate to Privacy; 2-day breach notice countered; AI-training limit goes to human review (`SYS-NOVEL`) |
| 28 Brightwater | Termination | 10-day notice and convenience termination escalate; 90-day sponsor notice countered; conflicting notice and a failed quote go to review |
| 29 Cardinal Plains | Governing law | Sovereign immunity and arbitration abroad escalate; county venue is countered; public-records disclosure after notice and paid convenience termination accepted |

## Layout

- `src/siteline/docx_redline.py`: stdlib-only parser (also uploaded into the Daytona sandbox)
- `extraction.py` → `verify.py` → `rules.py`: the model reads, quotes are checked, rules decide
- `playbook.py` + `data/playbook.json`: the playbook, 9 clauses and 37 positions. Each position's `limits` are the numbers `rules.py` decides by, and its `rules` list the rule IDs that enforce it (a test keeps the two in step). Saving it from the Playbook page (`PUT /api/playbook`, after a `preview`) re-decides open suggestions; `var/playbook.json` holds the saved copy and `var/playbook_log.json` the change log
- `pipeline.py`: the triage job and its live progress events
- `precedent.py`: after the rules, checks what the sponsor already agreed with this institution; builds the precedents a confirmed agreement contributes
- `db.py`: the `precedents` table and its two queries (read by site, write on confirmation) when `DATABASE_URL` is set
- `storage.py`: final agreed documents in the S3 bucket (or `var/documents/`), served back as precedent sources
- `approvals.py`, `photon.py`, `voice.py`: texts, replies, no-reply timer, calls
- `export.py`, `docx_writer.py`: the Word counter-proposal
- `cta_base.py`: the sponsor's full form agreement that every generated redline is built on
- `samples.py`: the nine per-clause sample redlines, their seed extractions and expected rule IDs
- `evals/`: labeled set, harness, Chalk runner
- `data/`: playbook, demo redline, clean form agreement, seed cache, seeded inbound emails (fictional). Runtime state goes to `var/` (git-ignored).
