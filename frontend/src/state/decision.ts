import type { Decision, Outcome } from '@/types'

/** How long an approver has to reply to the text before the voice agent calls. */
export const NO_REPLY_MS = 45_000

/** The outcome shown on the card, after any human override. */
export function effectiveOutcome(d: Decision): Outcome {
  return d.override?.outcome ?? d.outcome
}

/** Blocked on an approver's reply or a reviewer's decision (mirrors store.is_waiting). */
export function isWaiting(d: Decision): boolean {
  const o = effectiveOutcome(d)
  return (o === 'escalate' && d.approval.state !== 'answered') || ((o === 'human_review' || o === 'novel') && !d.override)
}

/** A person signed off: confirmed it, overrode it, or answered its escalation (mirrors store.is_confirmed). */
export function isConfirmed(d: Decision): boolean {
  if (d.confirmation || d.override) return true
  return effectiveOutcome(d) === 'escalate' && d.approval.state === 'answered'
}
