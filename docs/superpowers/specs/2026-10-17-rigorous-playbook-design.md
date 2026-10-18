# A rigorous, enforced playbook — design

## Intent

Siteline's playbook today is nine one-line rows (standard, fallback, escalate-when). It reads as a
toy next to a real sponsor CTA playbook, and it is not what decides: the thresholds live in
`rules.py`, and editing the playbook text changes only the extraction prompt and clause owners.
Judges and sponsor legal teams will read the Playbook page as the policy Siteline enforces, so it
must be both realistic and true.

Goal: each of the nine clause types becomes a set of **positions** (negotiable issues), each with
the sponsor's standard, a counter (fallback position), an escalation trigger, a rationale and
talking points, and **every position is enforced** by deterministic rules whose numbers come from
the playbook itself.

## Goals

- Nine clauses → ~45 positions, written the way a sponsor's contracts team writes a playbook.
- One source of truth: numeric thresholds live in `playbook.json` (`limits`), `rules.py` reads
  them. The Playbook page shows exactly what decides, and editing a limit changes decisions.
- Every rule ID the engine can return (except `SYS-*`) belongs to exactly one position, and every
  position lists the rule IDs that enforce it. A test fails on any mismatch in either direction.
- New positions are enforced end to end: extraction fields, rules, sample redline coverage with
  seed extractions, and labeled eval rows.

## Non-goals

- No new clause types (insurance, limitation of liability, records and audit stay out of scope;
  changes there still go to human review via `SYS-NORULE` / `SYS-NOVEL`).
- No drafting of new legal language. Counters stay fixed substitutions on the site's own wording
  or a return to the form's text (PRD non-goal).
- No change to the design rules: Claude extracts facts with verbatim quotes; rules decide; anything
  uncertain goes to human review; precedent never downgrades a novel term.

## Anti-goals

- A playbook page that describes positions the engine does not enforce.
- Rule text and playbook text that disagree on a number.
- Losing coverage of any `SYS-*` check in the samples.

## Data model (`backend/data/playbook.json`)

```jsonc
{
  "name": "Northstar Oncology CTA negotiation playbook — NSO-417 (fictional)",
  "clauses": [
    {
      "clauseType": "payment_terms",
      "label": "Payment Terms",
      "owner": "finance",
      "summary": "One paragraph: what the sponsor protects in this clause and why.",
      "positions": [
        {
          "id": "start_up_fee",            // anchors the Playbook page: #payment_terms.start_up_fee
          "issue": "Start-up fee",
          "form": "§6.3",
          "fields": ["start_up_fee_pct", "start_up_fee_refundable"],
          "standard": "A non-refundable start-up fee of up to {standard}% of the study budget.",
          "counter": "Above {standard}%: counter at {standard}%, refundable pro rata if no subject enrolls.",
          "escalate": "A non-refundable fee above {escalate_above}%.",
          "rationale": "Why the sponsor holds this line.",
          "talkingPoints": ["What a negotiator says to the site.", "..."],
          "limits": {
            "standard": {"value": 10, "unit": "%", "label": "Standard fee"},
            "escalate_above": {"value": 20, "unit": "%", "label": "Escalate above"}
          },
          "rules": [
            {"id": "PAY-A3", "outcome": "accept", "when": "Fee at or under {standard}%."},
            {"id": "PAY-A3P", "outcome": "accept", "when": "Fee within the band site priority widens."},
            {"id": "PAY-C2", "outcome": "counter", "when": "Fee above {standard}%, up to {escalate_above}% or refundable."},
            {"id": "PAY-E2", "outcome": "escalate", "when": "Non-refundable fee above {escalate_above}%."}
          ]
        }
      ]
    }
  ]
}
```

- `{name}` placeholders in text fields resolve from the position's `limits`. Text is stored and
  edited as the template; `GET /api/playbook` returns each text field both as the template and
  rendered (`standard` / `standardText`, and so on), the extraction prompt uses the rendered text,
  `PUT` and Load JSON accept templates only, and Export writes templates. A placeholder with no
  limit fails validation. *(Builder's call.)*
- The saved copy (`var/playbook.json`, from the editor) takes precedence, as today. A saved copy in
  the old flat format is replaced by the new default on load, keeping its per-clause owners.
  *(Builder's call.)*
- Validation (`validate_playbook`): all nine clause types once; owners valid; every position has
  id, issue, standard, counter, escalate, rationale, rules; limits numeric and ≥ 0; per-position
  ordering checks where a position defines them (e.g. `accept_min ≤ standard`); every placeholder
  resolves; the set of rule IDs equals the engine's (`rules.RULE_IDS`), so an import cannot drop a
  rule or invent one.

## Rule IDs

`CLAUSE-A#` accept, `CLAUSE-C#` counter, `CLAUSE-E#` escalate, `…P` widened by site priority.
The six counter rules currently named `…-F#` become `…-C#` (`PAY-F2` → `PAY-C2`, `CONF-F1` →
`CONF-C1`, `IND-F1` → `IND-C1`, `PUB-F1` → `PUB-C1`, `TERM-F1` → `TERM-C1`, `GOV-F1` → `GOV-C1`).
Saved state keeps the old IDs on old decisions; an alias map (`PAY-F2` → `PAY-C2`, …) resolves them
to their position for the decision-panel link and for comparisons in the re-decide preview, so the
rename never shows up as a decision change. *(Builder's call.)*

## One verdict per change

A change can touch several positions of one clause (overhead and holdback in one §6 edit, say).
Every position's rules run; the strictest outcome wins (escalate > counter > accept), ties go to
the position listed first in the playbook, the winner's counter text is used, and its rule text
ends with what else fired ("Also: PAY-A5 holdback within the fallback."). Human review checks still
run first and win outright. This replaces today's first-match order outside payment.
*(Builder's call.)*

## Editing the playbook re-decides open work

Saving the playbook (a limit, owner or text) or resetting it to the default behaves like Priority
settings today *(decided with the user)*:

- `POST /api/playbook/preview` (dry run) returns the open suggestions that would change, from →
  to, per agreement, without saving.
- `PUT /api/playbook` / `DELETE /api/playbook` save, then re-decide only suggestions no person has
  confirmed. Confirmed decisions, overrides and answered escalations never move. Every clause is
  re-decided, not only the bands priority widens (`pipeline.redecide_open` grows to cover this).
- Each save is logged (when, what changed, how many decisions moved), next to the priority change
  log.
- The Playbook page shows the preview before saving ("Saving changes 3 open suggestions") and the
  log after.

## Positions

Existing positions keep their behaviour; numbers move into `limits`. **New** marks new rules,
fields and coverage. Counter mechanics in brackets.

### Payment Terms (finance, form §6)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Invoice payment terms | Net 45 | — (Net 30–44 accepted as the fallback) | Under Net 30 | PAY-A1, PAY-A2, PAY-E1 | net_days |
| Start-up fee | ≤ 10%, non-refundable | > 10%: 10%, refundable pro rata [substitute %] | Non-refundable > 20% | PAY-A3, PAY-A3P, PAY-C2, PAY-E2 | start_up_fee_pct, start_up_fee_refundable |
| **Institutional overhead** | ≤ 25% of direct costs | 26–30%: counter at 25% [substitute %] | > 30% | PAY-A4, PAY-C3, PAY-E3 | overhead_pct |
| **Holdback** | 10% withheld until database lock | Under 5% or deleted: restore the form [form text] | — | PAY-A5, PAY-C4 | holdback_pct |
| **Screen failures** | Paid up to 1 per 3 enrolled | Up to 1 per 2: hold 1 per 3 [form text] | More than 1 per 2, or uncapped | PAY-A6, PAY-C5, PAY-E4 | screen_failures_per_enrolled |

### Confidentiality (legal, §8)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Survival | 7 years (5 accepted) | 3–5 years: counter at 5 [substitute] | Under 3 years | CONF-A1, CONF-A2, CONF-A2P, CONF-C1, CONF-E1 | survival_years |
| Trade secrets | Protected without end date | — | Perpetual protection removed | **CONF-A3**, CONF-E2 | trade_secrets_perpetual |
| **Disclosure to affiliates** | Employees and agents who need to know | Disclosure widened to affiliates or collaborators: restore the form [form text] | — | CONF-C2 | discloses_to_affiliates |
| **Marking requirement** | Oral and written information protected | Protection limited to marked information: restore the form [form text] | — | CONF-C3 | marking_required |
| **Public records** | — | — | Public-records disclosure claimed by a private institution, or without notice to Sponsor | CONF-A4 (public institution, with notice), CONF-E3 | public_records_disclosure, public_records_notice, institution_is_public |

### Indemnification (legal, §9)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Carve-out | Site negligence excluded (gross negligence accepted) | Gross negligence "as finally adjudicated": strike the qualifier | Carve-out removed | IND-A1, IND-A2, IND-C1, IND-E1 | carve_out_standard, adjudication_required |
| Mutual indemnity | One-way, sponsor to site | — | Made mutual | IND-E2 | mutual_indemnity |
| **Notice of claims** | Prompt written notice | Over 30 days: counter at 30 [substitute] | — | IND-A3, IND-C2 | claim_notice_days |
| **Control of defense** | Sponsor controls defense and settlement | — | Control taken from Sponsor | IND-E3 | sponsor_controls_defense |
| **Additional insured** | — | — | — | IND-A4 (naming the site as additional insured is accepted) | additional_insured |

### Subject Injury (finance, §10)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Covered costs | Reasonable medical costs | — | Lost wages or pain and suffering | SI-E1, **SI-A3** (reasonable travel for treatment accepted) | covers_lost_wages, covers_pain_and_suffering, covers_travel |
| Coordination with insurance | Net of insurance (sponsor-pays-first accepted) | — | — | SI-A1, SI-A2 | coordination_with_insurance |
| Cap | Capped at reasonable and necessary | — | Uncapped | SI-E2 | reimbursement_cap |
| **Exclusions** | Underlying disease, standard of care and protocol deviations excluded | — | Exclusions deleted | SI-E3 | removes_injury_exclusions |

### Publication (legal, §12)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Review window | 60 days or longer | 30–59 days: counter at 60 [substitute] | Under 30 days, or open-ended | PUB-A1, PUB-A2P, PUB-C1, PUB-E2, PUB-E3 | review_days, review_window_open_ended |
| Patent delay | Up to 60 extra days | — | Removed | PUB-A3, PUB-E1 | patent_delay, patent_delay_days |
| **Multi-site first publication** | 18 months (12 accepted) | Under 12 months: counter at 18 [substitute] | — | PUB-A4, PUB-C2 | multisite_wait_months |

### Intellectual Property (legal, §13)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Study inventions | Sponsor owns | — | Joint or institution ownership | IP-A1, IP-E1 | invention_ownership |
| Research license | — (accepted) | — | — | IP-A2 | site_research_license |
| Background IP | Each party keeps its own | — | — | IP-A3 | background_ip_retained |
| **Patent prosecution** | Sponsor controls filings | Site step-in right: restore the form [form text] | — | IP-C1 | site_may_file_patents |

### Data Protection (privacy, §11)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| BAA | Not required (research disclosure under authorization) | — | Required | DP-E1 | requires_baa |
| Secondary research | Allowed within consent | — | Blocked | DP-E2 | blocks_secondary_research |
| Data-use addendum | — (accepted) | — | — | DP-A2 | data_use_addendum |
| **Security-incident notice** | 10 business days (5 accepted) | Under 5: counter at 5 [substitute] | — | DP-A3, DP-C1 | incident_notice_days |
| **Data transfer** | Coded data may leave the site's country | — | Transfer or storage restricted to one place | DP-E3 | restricts_data_transfer |

(AI-training restrictions stay unruled on purpose: `SYS-NOVEL`, the demo's novel term.)

Public records *(builder's call)*: public-records language is classified as confidentiality wherever
it sits. `institution_is_public` may be quoted from the change or the agreement's preamble (the
quote check already accepts the preamble as context). Accept only when the institution is public
and the change gives Sponsor notice before disclosure; a private institution, or no notice,
escalates; a missing fact means no rule fires (human review).

Publication *(builder's call)*: the 75-day line goes. A longer sponsor review never hurts the
sponsor, so anything from 60 days up is PUB-A1; `PUB-A2` is retired (the Site 22 sample's 70 days
becomes PUB-A1) and the old `openQuestion` field is dropped from the schema.

### Termination (legal, §14)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Site notice | 30 days (to 60 accepted) | Over 60: counter at 60 [substitute] | Under 30 | TERM-A0, TERM-A1, TERM-C1, TERM-E2 | site_notice_days |
| Termination for convenience | — | — | Without paying non-cancellable costs | **TERM-A2** (with those costs paid), TERM-E1 | termination_for_convenience, pays_noncancellable_costs |
| **Sponsor notice** | 30 days (to 60 accepted) | Over 60: counter at 60 [substitute] | — | TERM-A3, TERM-C2 | sponsor_notice_days |

### Governing Law (legal, §17)

| Position | Standard | Counter | Escalate | Rules | Fields |
|---|---|---|---|---|---|
| Choice of law | Sponsor's home state (a public site's own state accepted) | — | Another state's law for a private site | GOV-A1, GOV-A2, GOV-E2 | governing_law_state, institution_is_public |
| Venue | Sponsor's courts or silent | Site's courts: counter silent on venue [strip phrase] | — | GOV-C1 | venue |
| Arbitration and immunity | Courts; no immunity terms | **Domestic arbitration: restore the form [form text]** | Arbitration abroad or a sovereign-immunity demand | **GOV-C2**, GOV-E1 | arbitration_domestic, arbitration_abroad, sovereign_immunity_waiver_required |

## Changes by part

- **`playbook.json` / `playbook.py`:** new schema and content; `limit(clause, position, key)`;
  rendering of placeholders; validation as above; `playbook_text()` renders clauses → positions →
  limits for the extraction and baseline prompts.
- **`rules.py`:** reads every threshold through `limit()`; `BANDS` takes standard and floor from the
  playbook; 29 new rules (and `PUB-A2` retired); `F#` → `C#`; `RULE_IDS` lists every non-system rule ID.
- **`extraction.py`:** the new fields in `FIELDS`.
- **Samples (`samples.py`):** every new rule reached by a sample change with a seed extraction.
  Existing no-rule changes that a new position now covers move to that rule (§6.5 Holdback →
  PAY-C4, §9.6 → IND-A3, §9.7 → IND-A4, §10.5 → SI-A3, §12.4 → PUB-A4, §13.5 → IP-C1, §11.7 →
  DP-C1, §17.5 → CONF-A4). One new change keeps `SYS-NORULE` covered; every other `SYS-*` check
  keeps its sample.
- **Eval set (`evals/dataset.py`):** labeled rows for each new position around its thresholds
  (about four per position); the row cap grows to fit; labels follow the playbook.
- **API:** `GET /api/playbook` (templates and rendered text), `POST /api/playbook/preview`, `PUT`
  (validate, save, re-decide), `DELETE` (reset to the default, re-decide), and the change log. The
  frontend's duplicate copy of the playbook goes; Reset uses the server default.
- **Frontend Playbook page:** per clause, a summary and its positions: issue, form section,
  standard / counter / escalate shown rendered and editable as templates, limits as number inputs,
  rule IDs, and a collapsible rationale and talking points. Owner selectable per clause. Save (with
  the re-decide preview), Reset (server default), Load/Export JSON, and the change log.
- **Decision panel:** the rule ID names its position and links to it on the Playbook page.

## Left to the builder

Exact wording of summaries, rationales and talking points (fictional, sponsor-side, plain legal
English); exact eval rows; which sample hosts each new change, within the one-change-per-section
and form-article constraints.
