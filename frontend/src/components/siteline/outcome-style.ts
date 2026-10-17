import { ArrowLeftRight, CircleCheck, Eye, Siren, Sparkles, type LucideIcon } from 'lucide-react'

import type { Outcome } from '@/types'

export const outcomeIcon: Record<Outcome, LucideIcon> = {
  accept: CircleCheck,
  fallback: ArrowLeftRight,
  escalate: Siren,
  human_review: Eye,
  novel: Sparkles,
}

/** CSS variable holding each outcome's colour (see index.css). */
export const outcomeVar: Record<Outcome, string> = {
  accept: 'var(--outcome-accept)',
  fallback: 'var(--outcome-fallback)',
  escalate: 'var(--outcome-escalate)',
  human_review: 'var(--outcome-human)',
  novel: 'var(--outcome-novel)',
}
