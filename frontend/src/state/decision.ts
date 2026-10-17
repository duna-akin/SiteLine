import type { Decision, Outcome } from '@/types'

/** How long an approver has to reply to the text before the voice agent calls. */
export const NO_REPLY_MS = 45_000

/** The outcome shown on the card, after any human override. */
export function effectiveOutcome(d: Decision): Outcome {
  return d.override?.outcome ?? d.outcome
}
