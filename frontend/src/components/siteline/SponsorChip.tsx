import { cn } from '@/lib/utils'

export type Sponsor = 'Photon' | 'Daytona' | 'Chalk' | 'Anthropic Claude'

const sponsorDot: Record<Sponsor, string> = {
  Photon: 'var(--lime)',
  Daytona: 'var(--blue-l)',
  Chalk: 'var(--cream)',
  'Anthropic Claude': 'var(--butter)',
}

/** Small "powered by" attribution shown wherever a sponsor integration is used. */
export function SponsorChip({ sponsor, label, className }: { sponsor: Sponsor; label?: string; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-line bg-space/60 px-2.5 py-0.5 text-xs font-medium text-muted',
        className,
      )}
    >
      <span aria-hidden className="size-1.5 rounded-full" style={{ background: sponsorDot[sponsor] }} />
      {label ?? sponsor}
    </span>
  )
}
