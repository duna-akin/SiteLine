import { Check, TriangleAlert } from 'lucide-react'

import { SponsorChip } from '@/components/siteline/SponsorChip'
import { cn } from '@/lib/utils'
import type { SandboxPhaseEvent, SandboxPhaseId, TriageStepEvent } from '@/types'

const PHASES: { id: SandboxPhaseId; label: string; note: string }[] = [
  { id: 'create', label: 'Created', note: 'network off' },
  { id: 'upload', label: 'File in', note: '.docx copied in' },
  { id: 'parse', label: 'Parsed', note: 'inside the sandbox' },
  { id: 'output', label: 'Text out', note: 'JSON only' },
  { id: 'delete', label: 'Deleted', note: 'nothing kept' },
]

const shortId = (id: string) => (id.length > 12 ? `${id.slice(0, 4)}…${id.slice(-4)}` : id)
const secs = (s: number) => (s < 0.005 ? '<0.01 s' : `${s.toFixed(2)} s`)

/**
 * The sandbox that parses an upload, phase by phase with measured times: made for this one
 * file, network blocked, deleted at the end. "Sandbox alive" runs from created to deleted.
 */
export function SandboxStrip({ phases, step, live, elapsedMs, aliveFromMs }: {
  phases: Partial<Record<SandboxPhaseId, SandboxPhaseEvent>>
  /** The pipeline's sandbox step: skipped or failed means the file was parsed locally. */
  step?: TriageStepEvent
  /** Whether this run will use a sandbox (a key is set and the Local parser flag is off). */
  live: boolean
  elapsedMs: number
  /** Run time at which the sandbox finished being created, for the live alive clock. */
  aliveFromMs: number | null
}) {
  const local = step ? step.state === 'skipped' || step.state === 'failed' : !live
  const lastDone = PHASES.reduce((last, p, i) => (phases[p.id]?.state === 'done' ? i : last), -1)
  const deleted = phases.delete?.state === 'done' || phases.delete?.state === 'failed'
  const alive = deleted
    ? PHASES.slice(1).reduce((sum, p) => sum + (phases[p.id]?.seconds ?? 0), 0)
    : aliveFromMs !== null ? Math.max(0, elapsedMs - aliveFromMs) / 1000 : null
  const sandboxId = phases.create?.state === 'done' ? phases.create.detail : null

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="eyebrow">Step 1 of triage</span>
          <h3 className="mt-1 font-serif text-[19px] font-medium">Isolated sandbox</h3>
        </div>
        <SponsorChip sponsor="Daytona" />
      </div>
      <p className="mt-1.5 text-[13.5px] text-muted">
        {local
          ? step?.state === 'failed'
            ? `The sandbox failed, so this file was parsed locally: ${step.detail}`
            : step?.detail ?? 'The Local parser flag is on, so this run parses the file here, with no sandbox.'
          : 'A sandbox made for this one file. No internet, deleted when it’s done.'}
      </p>

      <ol aria-label="Sandbox steps" className={cn('relative mt-5 grid grid-cols-5', local && step?.state !== 'failed' && 'opacity-45')}>
        <span aria-hidden className="absolute inset-x-[10%] top-[13px] h-[2px] bg-line-strong" />
        <span
          aria-hidden
          className="absolute left-[10%] top-[13px] h-[2px] bg-ok transition-[width] duration-300 ease-brand"
          style={{ width: `${Math.max(0, lastDone) * 20}%` }}
        />
        {PHASES.map((p) => {
          const e = phases[p.id]
          const state = e?.state ?? 'waiting'
          const note = e?.state === 'done' && (p.id === 'upload' || p.id === 'output') && e.detail ? e.detail : p.note
          return (
            <li key={p.id} className="relative px-1 text-center">
              <span
                aria-hidden
                className={cn(
                  'mx-auto grid size-7 place-items-center rounded-full border-2 bg-surface transition-colors duration-200',
                  state === 'done' && 'border-ok bg-ok-bg text-ok',
                  state === 'active' && 'border-accent text-accent shadow-[0_0_0_4px_var(--accent-bg)]',
                  state === 'failed' && 'border-high bg-high-bg text-high',
                  state === 'waiting' && 'border-line-strong text-faint',
                )}
              >
                {state === 'done' && <Check className="size-3.5" strokeWidth={3} />}
                {state === 'failed' && <TriangleAlert className="size-3.5" />}
                {state === 'active' && <span className="size-2 animate-pulse rounded-full bg-accent" />}
              </span>
              <b className="mt-2 block text-[13px] font-semibold text-ink">{p.label}</b>
              <span className="mt-0.5 block text-xs leading-snug text-muted">{note}</span>
              <span className={cn('mt-1.5 block font-mono text-[12.5px] tabular', e?.seconds != null ? 'text-ink' : 'text-faint')}>
                {e?.seconds != null ? secs(e.seconds) : state === 'active' ? '…' : '—'}
              </span>
              <span className="sr-only">{state === 'waiting' ? 'not started' : state}</span>
            </li>
          )
        })}
      </ol>

      <div className="mt-5 flex items-baseline justify-between gap-3 border-t border-line pt-3.5">
        <span className="font-mono text-xs text-muted">{sandboxId ? `sandbox ${shortId(sandboxId)}` : local ? 'no sandbox' : 'sandbox not started'}</span>
        <span className="flex items-baseline gap-2">
          <span className="eyebrow">Sandbox alive</span>
          <span className={cn('font-serif text-[26px] font-medium tabular', deleted && 'text-ok')}>{alive !== null ? secs(alive) : '—'}</span>
        </span>
      </div>
    </div>
  )
}
