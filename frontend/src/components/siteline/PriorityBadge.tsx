import { priorityLabel, priorityPill, usd } from '@/components/siteline/priority-style'
import { cn } from '@/lib/utils'
import type { SitePriority } from '@/types'

/** Level pill plus "≈$X/week at risk"; `detail` adds the reason and the quoted figures. */
export function PriorityBadge({ priority, detail = false, className }: { priority?: SitePriority; detail?: boolean; className?: string }) {
  if (!priority) return null
  const quotes = [...new Set(priority.figures.map((f) => f.quote))]
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`pill ${priorityPill[priority.level]}`}>{priorityLabel[priority.level]}</span>
        {priority.moneyAtRiskPerWeek !== null && (
          <span className="text-sm font-extrabold tabular">≈{usd(priority.moneyAtRiskPerWeek)}/week at risk</span>
        )}
      </div>
      {detail && (
        <>
          <p className="text-sm text-muted">{priority.reason}</p>
          {quotes.map((q) => (
            <p key={q} className="text-xs text-muted">
              <span className="font-extrabold text-ink">{priority.source === 'study plan' ? 'Study plan' : 'Contract'}:</span> “{q}”
            </p>
          ))}
        </>
      )}
    </div>
  )
}
