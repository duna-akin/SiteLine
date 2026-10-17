import { cn } from '@/lib/utils'

export type Sponsor = 'Photon' | 'Daytona' | 'Chalk' | 'OpenAI'

/** Small "powered by" attribution shown wherever a sponsor integration is used. */
export function SponsorChip({ sponsor, label, className }: { sponsor: Sponsor; label?: string; className?: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-[4px] border border-line bg-surface px-2 py-0.5 text-xs font-medium text-muted', className)}>
      {label ?? sponsor}
    </span>
  )
}
