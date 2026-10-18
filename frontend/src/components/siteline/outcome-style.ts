import { ArrowLeftRight, CircleAlert, CircleCheck, Eye, type LucideIcon } from 'lucide-react'

import type { Outcome } from '@/types'

export const outcomeIcon: Record<Outcome, LucideIcon> = {
  accept: CircleCheck,
  counter: ArrowLeftRight,
  escalate: CircleAlert,
  human_review: Eye,
}

/** Ink colour per outcome (see index.css): text, icons, edges. */
export const outcomeVar: Record<Outcome, string> = {
  accept: 'var(--outcome-accept)',
  counter: 'var(--outcome-counter)',
  escalate: 'var(--outcome-escalate)',
  human_review: 'var(--outcome-human)',
}

/** Muted fill per outcome, paired with outcomeVar for text on it. */
export const outcomeBg: Record<Outcome, string> = {
  accept: 'var(--outcome-accept-bg)',
  counter: 'var(--outcome-counter-bg)',
  escalate: 'var(--outcome-escalate-bg)',
  human_review: 'var(--outcome-human-bg)',
}
