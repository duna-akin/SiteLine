# Welcome to Siteline

> **Siteline:**
> turn your past clinical trial agreements into a central intelligence playbook that adapts to each site

All contracts, sites and sponsors in this repo are fictional.

## Run it

You need [uv](https://docs.astral.sh/uv/) (Python 3.12) and Node.js 20.19+ or 22.12+.

```bash
git clone https://github.com/duna-akin/hackharvard-2026.git
cd hackharvard-2026

# Terminal 1: the API on http://127.0.0.1:8000
cd backend
cp .env.example .env        # every key is optional; see below
uv run siteline serve

# Terminal 2: the web app on http://localhost:5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api` to the backend, so both must be running.

With no keys at all the full demo still works: the Site 07 demo file ships with a stored
extraction, Word parsing runs locally, and approver texts show up on an on-screen phone.
Add `OPENAI_API_KEY` to `backend/.env` to extract new redlines with the model. The
[backend README](backend/README.md#what-runs-without-keys) lists every integration and its
fallback.

## Use it

1. **Inbound → Go to upload.** Choose **Use demo file · Site 07 (14 changes)**, or drop in
   your own redlined `.docx`, then press **Triage redline**.
2. Siteline reads each tracked change, has the model extract the facts with verbatim
   quotes, checks every quote, and applies the playbook rules. Each change is accepted,
   countered, or escalated to an approver (legal, finance or privacy). Anything
   uncertain goes to human review.
3. **Open decision list** to see every change with its rule ID, quote and precedent.
   Record approver replies here, or on the on-screen phone when no text line is set up.
4. **Export counter-proposal** downloads the agreement as Word with tracked changes and
   comments.
5. **Sites** shows every agreement by site, **Playbook** the rules and site priorities,
   and **Data** the evaluation of Siteline against an LLM-only baseline.

To start over: `cd backend && uv run siteline reset`.

## Check

```bash
cd backend && uv run pytest
cd frontend && npx tsc -b && npm run lint
```
