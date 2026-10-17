import type { Decision, Outcome } from '@/types'

/** How long an approver has to reply to the text before the voice agent calls. */
export const NO_REPLY_MS = 45_000

/** The outcome shown on the card, after any human override. */
export function effectiveOutcome(d: Decision): Outcome {
  return d.override?.outcome ?? d.outcome
}

const unresolved = (o: Outcome) => o === 'human_review' || o === 'novel'

/** Blocked on an approver's reply or a reviewer's decision (mirrors store.is_waiting). Human review
 * and novel stay waiting even when an override chose them: export can't act on either. */
export function isWaiting(d: Decision): boolean {
  const o = effectiveOutcome(d)
  return (o === 'escalate' && d.approval.state !== 'answered') || unresolved(o)
}

/** A person signed off: confirmed it, overrode it to an outcome export can act on, or answered its
 * escalation (mirrors store.is_confirmed). */
export function isConfirmed(d: Decision): boolean {
  const o = effectiveOutcome(d)
  if (unresolved(o)) return false
  if (d.confirmation || d.override) return true
  return o === 'escalate' && d.approval.state === 'answered'
}
