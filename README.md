# Welcome to Siteline

> **Siteline:**
> turn your past clinical trial agreements into a central intelligence playbook that adapts to each site

## Run it

You need Python 3.12 with [uv](https://docs.astral.sh/uv/) and Node.js with npm.

**Backend** (http://127.0.0.1:8000):

```bash
cd backend
cp .env.example .env        # first run only; fill in the keys you have, all are optional
uv run siteline serve
```

**Frontend** (http://localhost:5173, proxies `/api` to the backend), in a second terminal:

```bash
cd frontend
npm install                 # first run only
npm run dev
```

Then open http://localhost:5173.

See `backend/README.md` for the other commands and what works without keys.
