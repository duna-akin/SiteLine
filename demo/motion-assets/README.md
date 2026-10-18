# Siteline demo video assets

Upload this folder to [Motion](https://motion.so) and paste the prompt at the bottom.
Every screenshot is 3840×2160 (1920×1080 at 2×, 16:9) from the running app. All sites, sponsors
and contract text are fictional.

## Files

### `screens/` (one per scene)

| File | Shows |
|---|---|
| `01-home.png` | Home: one new redline, $104,308/week at risk, 6 escalations with approvers |
| `02-inbound.png` | Inbound: the agent mailbox, redlines emailed by sites, the escalation queue |
| `03-upload-idle.png` | Upload, before a run: the Isolated sandbox strip (Daytona) |
| `04-upload-sandbox-done.png` | Upload, after a run: all five sandbox steps with measured times |
| `05-upload-triage-complete.png` | "14 changes triaged in 2.2 s · under target": 7 accept, 2 counter, 2 escalate, 3 human review |
| `06-review.png` | Review: the whole agreement, each redlined paragraph tinted by its outcome |
| `07-review-escalation.png` | An escalation opened: rule `IND-E2`, the extracted value, the verbatim quote, the Legal approver |
| `08-review-counter.png` | A counter opened: rule `IND-C1`, the carve-out narrowed to gross negligence, and the counter wording Siteline sends back |
| `09-review-human-review.png` | A new term no playbook rule covers (a ban on training models on study data): rule `SYS-NOVEL` sends it to the Privacy approver |
| `10-export-counter-proposal.png` | The counter-proposal as a Word file: tracked changes, one comment per decision |
| `11-sites.png` | Sites: money at risk per week per site, days open, stuck clauses |
| `12-data-eval-results.png` | Siteline vs an LLM-only baseline: 0% unsafe accepts vs 2.6% |
| `13-data-confusion-matrix.png` | Confusion matrix: no labeled escalation accepted or countered |
| `14-data-where-data-lives.png` | Where data lives: Daytona sandbox, Postgres, S3, all live |
| `15-playbook.png` | The playbook: standard, counter and escalate for each clause, with rule IDs |

### `sandbox-frames/` (the Daytona moment, frame by frame)

One Site 07 upload, captured each time the sandbox moved to its next step. Play them in order for
the strip filling left to right: `01-ready`, `02-creating-sandbox`, `03-copying-file-in`,
`04-parsing`, `05-deleting-sandbox`, `06-sandbox-deleted`. Times on screen are measured, not staged.

### `full-page/` (for slow scrolls)

`home.png`, `review-site-07.png` (the whole agreement), `data.png` (the whole eval page).

### `brand/`

| File | Use |
|---|---|
| `logo-mark.svg`, `logo-mark-1024.png` | The mark on its own (same as the app's tab icon) |
| `wordmark-on-light.png` | Mark + "Siteline" for light backgrounds (transparent PNG) |
| `wordmark-on-dark.png` | Mark + white "Siteline" for dark backgrounds (transparent PNG) |

## Brand

- **Fonts:** IBM Plex Serif (headings, wordmark, big numbers), IBM Plex Sans (body), IBM Plex Mono (logs, IDs).
- **Colours:**

| Role | Hex |
|---|---|
| Page background | `#F5F5F5` |
| Surface (cards) | `#FFFFFF` |
| Ink (text) | `#212121` |
| Ink 2 (buttons, logo square) | `#424242` |
| Muted text | `#616161` |
| Lines | `#E0E0E0` |
| Accent (links, focus) | `#4C5B6B` |
| Accept / OK green | `#4D6A58` on `#E7EDE9` |
| Counter gold | `#755E2E` |
| Escalate red | `#8C4A4A` on `#F2E9E9` |

- **Tone:** calm and institutional. Neutral greys with muted outcome colours; no gradients, no neon.

## Numbers to quote (exact)

From the committed eval run (`backend/data/evals/latest.json`, run `eval-20261018-034325`, model
`gpt-5`, 243 labeled changes, 77 of which should escalate, parsed in 12 parallel Daytona sandboxes):

| | Siteline | LLM-only baseline |
|---|---|---|
| Unsafe accept rate | **0%** | 2.6% (2 of 77) |
| Triage accuracy | 93.8% | 90.1% |
| Quote pass rate | 99.6% | 96.3% |
| Escalation recall | 92.2% | 97.4% |

The 6 escalations Siteline didn't escalate went to human review, not to accept.

Site 07 demo: 14 changes triaged in 2.2 s (target 30 s). Sandbox steps: created 1.13 s (network
off), file in 0.29 s, parsed 0.20 s, text out <0.01 s (50 KB JSON), deleted 0.06 s.

## Say it right

- The model is OpenAI `gpt-5`. It only extracts values with a verbatim quote; deterministic rules
  decide, each with a rule ID. Don't say the app runs on Claude.
- Daytona: each file gets its own sandbox with the network blocked; only parsed text comes out,
  then the sandbox is deleted. Say "built the way a HIPAA / SOC 2 environment expects", not
  "HIPAA compliant": clinical trial agreements rarely hold patient data.
- Approvals go out as texts; in these screenshots texting was off, so they read "simulated".

## Suggested storyboard (about 60 s)

1. **Problem (0–8 s):** `01-home.png`. "Every site that's still negotiating its contract costs a sponsor money each week. $104,308 a week, here."
2. **Intake (8–14 s):** `02-inbound.png`. "Sites email their redlines straight to Siteline."
3. **Daytona (14–26 s):** `sandbox-frames/01…06`, then `04-upload-sandbox-done.png`. "Each contract opens in its own Daytona sandbox: no internet, deleted 0.55 seconds later. Only text reaches the model."
4. **Decisions (26–40 s):** `05-upload-triage-complete.png`, `07-review-escalation.png`. "14 changes in 2.2 seconds. The model quotes the contract; the playbook's rules decide, and anything uncertain goes to a person."
5. **Approvals and export (40–48 s):** `10-export-counter-proposal.png`. "Approvers answer by text; Siteline writes the counter-proposal back as a Word file."
6. **Proof (48–58 s):** `12-data-eval-results.png`, `13-data-confusion-matrix.png`. "Against an LLM-only baseline on 243 labeled changes: zero unsafe accepts."
7. **Close (58–60 s):** `brand/wordmark-on-light.png`. "Siteline." (Add a tagline if you have one; the app doesn't use one.)

## Prompt for Motion

> A 60-second, 16:9 product demo for Siteline, a tool that triages a clinical trial site's
> redlined contract against the sponsor's playbook. Use the uploaded screenshots as the product
> footage, in the storyboard order from README.md, with slow pans and zooms on the part each
> line talks about. Style: calm, institutional; IBM Plex Serif headings, IBM Plex Sans body;
> background #F5F5F5, ink #212121, accent #4C5B6B, green #4D6A58 for "safe", red #8C4A4A for
> "escalate"; no gradients. Highlight the Daytona sandbox strip filling step by step, and end on
> the headline number: 0% unsafe accepts vs 2.6% for an LLM-only baseline. Calm voiceover,
> soft music, captions on.
