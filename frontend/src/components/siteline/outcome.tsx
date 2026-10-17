import { outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { cn } from '@/lib/utils'
import { outcomeLabel } from '@/mocks/playbook'
import type { Outcome } from '@/types'

export function OutcomeBadge({ outcome, size = 'md', className }: { outcome: Outcome; size?: 'sm' | 'md'; className?: string }) {
  const Icon = outcomeIcon[outcome]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-bold whitespace-nowrap text-text',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        className,
      )}
      style={{
        borderColor: outcomeVar[outcome],
        background: `color-mix(in oklab, ${outcomeVar[outcome]} 18%, transparent)`,
      }}
    >
      <Icon aria-hidden className={size === 'sm' ? 'size-3.5' : 'size-4'} style={{ color: outcomeVar[outcome] }} />
      {outcomeLabel[outcome]}
    </span>
  )
}
