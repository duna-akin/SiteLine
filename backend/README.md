# Siteline backend

FastAPI service behind the Siteline frontend. It parses a site's redlined Word file,
extracts clause values with Claude, verifies every quote, applies the playbook rules,
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
| `uv run siteline make-demo` | Rewrite `data/demo/NSO-417_CTA_Site07_redline.docx` and its seed extraction cache |
| `uv run siteline cache-demo` | Extract the demo file with Claude and save that as the demo cache (needs a key) |
| `uv run siteline parse FILE.docx` | Print a redline's tracked changes as JSON |
| `uv run siteline make-dataset` | Rewrite the labeled eval set (150 playbook changes + 12 precedent cases) |
| `uv run siteline eval [--limit N]` | Siteline vs the LLM-only baseline; writes `data/evals/latest.json` |
| `uv run siteline reset` | Clear agreements and approvals back to the seed portfolio |
| `uv run pytest` | Offline tests (parser, rules, quotes, export, eval set) |
| `uv run --extra chalk python -m siteline.evals.chalk_eval` | Same comparison on Chalk Agent Evals |

## What runs without keys

| Integration | Key | Without it |
|---|---|---|
| Claude extraction | `ANTHROPIC_API_KEY` | Only cached changes are extracted (the demo file ships with a hand-written seed); anything else goes to human review |
| Daytona parsing | `DAYTONA_API_KEY` | Local parser (same code) |
| Photon texts | `PHOTON_*` + real `APPROVER_*_PHONE` | On-screen phone in the UI |
| Voice call | `TWILIO_*` + `PUBLIC_BASE_URL` | On-screen call keypad |
| Inbound email | `IMAP_*` | Seeded inbox emails only |
| Eval | `ANTHROPIC_API_KEY` | Evals page shows "no run yet" |
| Precedent history | `DATABASE_URL` | Precedents are kept in `var/state.json` |
| Source documents | `S3_*` (Supabase Storage) | Final documents are kept in `var/documents/` |

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

- A shared Photon iMessage line only sends to someone who has messaged that line since
  their assignment. Have each approver text the Siteline line once before the demo.
- Create a webhook destination for `message.received` pointing at
  `$PUBLIC_BASE_URL/api/webhooks/photon`, and put its signing secret in `PHOTON_WEBHOOK_SECRET`.
- A reply of `1`, `2` or `3` answers that approver's oldest open escalation; `C04 2` picks one.

## Layout

- `src/siteline/docx_redline.py`: stdlib-only parser (also uploaded into the Daytona sandbox)
- `extraction.py` → `verify.py` → `rules.py`: Claude reads, quotes are checked, rules decide
- `pipeline.py`: the triage job and its live progress events
- `precedent.py`: after the rules, checks what the sponsor already agreed with this institution; builds the precedents a confirmed agreement contributes
- `db.py`: the `precedents` table and its two queries (read by site, write on confirmation) when `DATABASE_URL` is set
- `storage.py`: final agreed documents in the S3 bucket (or `var/documents/`), served back as precedent sources
- `approvals.py`, `photon.py`, `voice.py`: texts, replies, no-reply timer, calls
- `export.py`, `docx_writer.py`: the Word counter-proposal
- `evals/`: labeled set, harness, Chalk runner
- `data/`: playbook, demo redline, seed cache, seed portfolio (fictional). Runtime state goes to `var/` (git-ignored).
