import { useMemo } from 'react'

import { Particles } from '@/components/ui/particles'
import { token } from '@/lib/tokens'

/** Fixed deep-space backdrop: drifting stars plus two soft novas. */
export function StarField() {
  const star = useMemo(() => token('--glow') || undefined, [])
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-space">
      <div className="nova -top-40 -right-32 size-[420px] opacity-30 sm:size-[560px]" />
      <div
        className="absolute -bottom-48 -left-40 size-[520px] rounded-full opacity-40"
        style={{ background: 'radial-gradient(circle, var(--blue) 0%, var(--space-2) 45%, transparent 70%)' }}
      />
      <Particles className="absolute inset-0" quantity={90} staticity={60} ease={70} size={0.5} color={star} />
    </div>
  )
}
