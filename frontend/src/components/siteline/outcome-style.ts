import { ArrowLeftRight, CircleCheck, Eye, Siren, Sparkles, type LucideIcon } from 'lucide-react'

import type { Outcome } from '@/types'

export const outcomeIcon: Record<Outcome, LucideIcon> = {
  accept: CircleCheck,
  fallback: ArrowLeftRight,
  escalate: Siren,
  human_review: Eye,
  novel: Sparkles,
}

/** Ink colour per outcome (see index.css): text, icons, edges. */
export const outcomeVar: Record<Outcome, string> = {
  accept: 'var(--outcome-accept)',
  fallback: 'var(--outcome-fallback)',
  escalate: 'var(--outcome-escalate)',
  human_review: 'var(--outcome-human)',
  novel: 'var(--outcome-novel)',
}

/** Pastel fill per outcome, paired with outcomeVar for text on it. */
export const outcomeBg: Record<Outcome, string> = {
  accept: 'var(--outcome-accept-bg)',
  fallback: 'var(--outcome-fallback-bg)',
  escalate: 'var(--outcome-escalate-bg)',
  human_review: 'var(--outcome-human-bg)',
  novel: 'var(--outcome-novel-bg)',
}
