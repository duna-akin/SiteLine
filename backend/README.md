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
| `uv run siteline make-dataset` | Rewrite the 150-change labeled eval set |
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
- `approvals.py`, `photon.py`, `voice.py`: texts, replies, no-reply timer, calls
- `export.py`, `docx_writer.py`: the Word counter-proposal
- `evals/`: labeled set, harness, Chalk runner
- `data/`: playbook, demo redline, seed cache, seed portfolio (fictional). Runtime state goes to `var/` (git-ignored).
