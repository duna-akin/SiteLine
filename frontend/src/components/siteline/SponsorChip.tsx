import { cn } from '@/lib/utils'

export type Sponsor = 'Photon' | 'Daytona' | 'Chalk' | 'OpenAI'

const sponsorDot: Record<Sponsor, string> = {
  Photon: 'var(--radar-ok)',
  Daytona: 'var(--blue)',
  Chalk: 'var(--radar-warn)',
  OpenAI: 'var(--tangerine)',
}

/** Small "powered by" attribution shown wherever a sponsor integration is used. */
export function SponsorChip({ sponsor, label, className }: { sponsor: Sponsor; label?: string; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full bg-card px-2.5 py-0.5 text-xs font-bold text-muted shadow-[inset_0_0_0_1.5px_var(--line)]', className)}>
      <span aria-hidden className="size-1.5 rounded-full" style={{ background: sponsorDot[sponsor] }} />
      {label ?? sponsor}
    </span>
  )
}
