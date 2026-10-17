# Siteline frontend

Demo UI for Siteline: sorts a site's redlined clinical trial agreement against the sponsor playbook, routes escalations to approvers by text or call, and exports a counter-proposal.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build
npm run lint
```

- Needs the API in `../backend` (`uv run siteline serve`); Vite proxies `/api` to `http://127.0.0.1:8000`.
- `src/api/index.ts` is the API client; `src/api/events.ts` follows live server events (triage progress, approver replies, eval runs).
- `src/mocks/` now only holds static labels and the fictional playbook copy used by the editor's Reset.
- Theme tokens live in `src/styles/theme.css`. Put the Makcasa and AV Estiana `.woff2` files in `src/assets/fonts/`.

Demo path: Upload → Triage redline → Open decision list → reply on the phone (or Simulate no reply → voice call) → Export counter-proposal.
