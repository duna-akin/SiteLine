import type { Agreement, PriorityLevel, SitePriority } from '@/types'

/** Dot colour per level. */
export const priorityTone: Record<PriorityLevel, string> = {
  high: 'var(--high)',
  elevated: 'var(--elevated)',
  standard: 'var(--accent)',
  unknown: 'var(--muted)',
}

/** Status badge per level. */
export const priorityPill: Record<PriorityLevel, string> = {
  high: 's-high',
  elevated: 's-elevated',
  standard: 's-info',
  unknown: 's-neutral',
}

export const priorityShort: Record<PriorityLevel, string> = {
  high: 'High',
  elevated: 'Elevated',
  standard: 'Standard',
  unknown: 'Unknown',
}

export const priorityLabel: Record<PriorityLevel, string> = {
  high: 'High priority',
  elevated: 'Elevated priority',
  standard: 'Standard priority',
  unknown: 'Priority unknown',
}

export const usd = (n: number) => `$${Math.round(n).toLocaleString('en-US')}`

/** "$11.2k" (under $1,000 stays exact). */
export const usdK = (n: number) => (n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : usd(n))

/** Waiting on us: the sponsor owes the site an answer. */
export const isOnUs = (status: string) => status === 'awaiting_approval' || status === 'ready_to_export' || status === 'triaging'

/** Waiting on us first, by money at risk then days open; everything else keeps its order after. */
export function byPriority<T extends { status: string; daysOpen: number; priority?: SitePriority }>(rows: T[]): T[] {
  return rows
    .map((r, i) => ({ r, i }))
    .sort((a, b) => {
      const ua = isOnUs(a.r.status), ub = isOnUs(b.r.status)
      if (ua !== ub) return ua ? -1 : 1
      if (!ua) return a.i - b.i
      const ma = a.r.priority?.moneyAtRiskPerWeek ?? 0, mb = b.r.priority?.moneyAtRiskPerWeek ?? 0
      return mb - ma || b.r.daysOpen - a.r.daysOpen
    })
    .map(({ r }) => r)
}

/** Open sites (the portfolio): every agreement not yet executed. */
export const openSites = (agreements: Agreement[]) => agreements.filter((a) => a.status !== 'executed')

/** Most money at risk first, then longest open: the open-sites bar list. */
export const byMoney = (sites: Agreement[]) =>
  [...sites].sort((a, b) => (b.priority?.moneyAtRiskPerWeek ?? -1) - (a.priority?.moneyAtRiskPerWeek ?? -1) || b.daysOpen - a.daysOpen)
