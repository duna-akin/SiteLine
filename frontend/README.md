# Siteline frontend

Demo UI for Siteline: sorts a site's redlined clinical trial agreement against the sponsor playbook, routes escalations to approvers by text or call, and exports a counter-proposal.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build
npm run lint
```

- All data is fictional mock data in `src/mocks/`.
- `src/api/index.ts` holds stub endpoints. None of them make network requests; each `TODO` names the intended HTTP method and path.
- Theme tokens live in `src/styles/theme.css`. Put the Makcasa and AV Estiana `.woff2` files in `src/assets/fonts/`.

Demo path: Upload → Triage redline → Open decision list → reply on the phone (or Simulate no reply → voice call) → Export counter-proposal.
