import { outcomeBg, outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { cn } from '@/lib/utils'
import { outcomeLabel } from '@/mocks/playbook'
import type { Outcome } from '@/types'

export function OutcomeBadge({ outcome, size = 'md', className }: { outcome: Outcome; size?: 'sm' | 'md'; className?: string }) {
  const Icon = outcomeIcon[outcome]
  return (
    <span
      className={cn('pill', size === 'sm' ? 'px-1.5 py-0 text-[11.5px]' : '', className)}
      style={{ background: outcomeBg[outcome], color: outcomeVar[outcome] }}
    >
      <Icon aria-hidden className={size === 'sm' ? 'size-3.5' : 'size-4'} />
      {outcomeLabel[outcome]}
    </span>
  )
}
