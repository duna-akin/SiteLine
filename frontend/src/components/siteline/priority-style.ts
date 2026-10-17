import type { PriorityLevel, SitePriority } from '@/types'

export const priorityTone: Record<PriorityLevel, string> = {
  high: 'var(--red)',
  elevated: 'var(--butter)',
  standard: 'var(--blue-l)',
  unknown: 'var(--line)',
}

export const priorityLabel: Record<PriorityLevel, string> = {
  high: 'High priority',
  elevated: 'Elevated priority',
  standard: 'Standard priority',
  unknown: 'Priority unknown',
}

export const usd = (n: number) => `$${Math.round(n).toLocaleString('en-US')}`

/** Waiting on us first, by money at risk then days open; everything else keeps its order after. */
export function byPriority<T extends { status: string; daysOpen: number; priority?: SitePriority }>(rows: T[]): T[] {
  const onUs = (s: string) => s === 'awaiting_approval' || s === 'ready_to_export' || s === 'triaging'
  return rows
    .map((r, i) => ({ r, i }))
    .sort((a, b) => {
      const ua = onUs(a.r.status), ub = onUs(b.r.status)
      if (ua !== ub) return ua ? -1 : 1
      if (!ua) return a.i - b.i
      const ma = a.r.priority?.moneyAtRiskPerWeek ?? 0, mb = b.r.priority?.moneyAtRiskPerWeek ?? 0
      return mb - ma || b.r.daysOpen - a.r.daysOpen
    })
    .map(({ r }) => r)
}
