import { useEffect, useRef, useState, type DragEvent, type ReactNode, type RefObject } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Check, FileText, Gavel, ListChecks, LoaderCircle, Sparkles, UploadCloud } from 'lucide-react'

import * as api from '@/api'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { AnimatedBeam } from '@/components/ui/animated-beam'
import { BlurFade } from '@/components/ui/blur-fade'
import { BorderBeam } from '@/components/ui/border-beam'
import { ShimmerButton } from '@/components/ui/shimmer-button'
import { AnimatedSpan, Terminal } from '@/components/ui/terminal'
import { cn } from '@/lib/utils'
import { outcomeOrder } from '@/mocks/playbook'
import { SITE07, parseSteps, site07Changes } from '@/mocks/site07'
import { useDemo } from '@/state/demo'
import type { ParseStep, ParseStepId } from '@/types'

const TARGET_SECONDS = 30
/** Extra time a live (uncached) Claude extraction takes in the simulation. */
const UNCACHED_EXTRA_MS = 5200

type RunState = 'idle' | 'running' | 'done'

function Toggle({ id, label, hint, checked, onChange, disabled }: {
  id: string
  label: string
  hint: string
  checked: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div>
        <label htmlFor={id} className="font-bold text-text">{label}</label>
        <p id={`${id}-hint`} className="text-sm text-muted">{hint}</p>
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={`${id}-hint`}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative mt-1 inline-flex h-7 w-12 shrink-0 items-center rounded-full border border-line transition-colors duration-200 disabled:opacity-45',
          checked ? 'bg-yellow' : 'bg-space',
        )}
      >
        <span
          className={cn(
            'inline-block size-5 rounded-full shadow transition-transform duration-200 ease-brand',
            checked ? 'translate-x-6 bg-ink' : 'translate-x-1 bg-muted',
          )}
        />
      </button>
    </div>
  )
}

function Node({ nodeRef, icon, label, state, sponsor }: {
  nodeRef: RefObject<HTMLDivElement | null>
  icon: ReactNode
  label: string
  state: 'waiting' | 'active' | 'done' | 'skipped'
  sponsor?: string
}) {
  return (
    <div className="z-10 flex w-20 flex-col items-center gap-2 text-center sm:w-24">
      <div
        ref={nodeRef}
        className={cn(
          'flex size-14 items-center justify-center rounded-2xl border bg-space-2 transition-all duration-300 sm:size-16',
          state === 'done' && 'border-mint text-mint',
          state === 'active' && 'border-yellow text-yellow shadow-[0_0_28px_-6px_var(--yellow)]',
          state === 'waiting' && 'border-line text-muted',
          state === 'skipped' && 'border-dashed border-line text-muted opacity-60',
        )}
      >
        {icon}
      </div>
      <span className="text-xs leading-tight font-bold text-text">{label}</span>
      {sponsor && <span className="text-[11px] leading-tight text-muted">{sponsor}</span>}
    </div>
  )
}

export function UploadPage() {
  const navigate = useNavigate()
  const { localParser, useCache, setFlag, loadSite07, reset } = useDemo()
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [run, setRun] = useState<RunState>('idle')
  const [completed, setCompleted] = useState<ParseStepId[]>([])
  const [activeStep, setActiveStep] = useState<ParseStepId | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [fileError, setFileError] = useState<string | null>(null)
  const startedAt = useRef(0)

  const container = useRef<HTMLDivElement>(null)
  const nDoc = useRef<HTMLDivElement>(null)
  const nBox = useRef<HTMLDivElement>(null)
  const nClaude = useRef<HTMLDivElement>(null)
  const nRules = useRef<HTMLDivElement>(null)
  const nList = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (run !== 'running') return
    const t = setInterval(() => setElapsed(performance.now() - startedAt.current), 100)
    return () => clearInterval(t)
  }, [run])

  const steps: ParseStep[] = parseSteps.map((s) => {
    if (localParser && s.sponsor === 'Daytona') {
      if (s.id === 'parse') return { ...s, detail: s.detail.replace('→ JSON', '→ JSON (local parser)'), sponsor: undefined, ms: 900 }
      return { ...s, label: s.id === 'sandbox' ? 'Sandbox skipped' : 'No sandbox to delete', detail: 'Local parser flag is on', sponsor: undefined, ms: 150 }
    }
    if (s.id === 'extract' && useCache) return { ...s, detail: 'Cached extraction for the demo file · quotes still verified', ms: 700 }
    if (s.id === 'extract') return { ...s, ms: s.ms + UNCACHED_EXTRA_MS }
    return s
  })

  function pick(f: File | null) {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.docx')) {
      setFileError('That file isn’t a Word document. Upload a .docx with tracked changes.')
      return
    }
    setFileError(null)
    setFile(f)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files?.[0] ?? null)
  }

  async function start() {
    reset()
    setRun('running')
    setCompleted([])
    setElapsed(0)
    startedAt.current = performance.now()
    await api.uploadRedline(file, { localParser, useCache })
    for (const step of steps) {
      setActiveStep(step.id)
      await new Promise((r) => setTimeout(r, step.ms))
      setCompleted((c) => [...c, step.id])
    }
    const seconds = (performance.now() - startedAt.current) / 1000
    setElapsed(seconds * 1000)
    setActiveStep(null)
    await loadSite07(Number(seconds.toFixed(1)))
    setRun('done')
  }

  const nodeState = (ids: ParseStepId[], skip = false): 'waiting' | 'active' | 'done' | 'skipped' => {
    if (skip) return 'skipped'
    if (ids.every((id) => completed.includes(id))) return 'done'
    if (activeStep && ids.includes(activeStep)) return 'active'
    return 'waiting'
  }

  const seconds = elapsed / 1000
  const counts = outcomeOrder.map((o) => [o, site07Changes.filter((c) => c.outcome === o).length] as const)

  return (
    <div className="wrap py-10 sm:py-14">
      <BlurFade>
        <p className="eyebrow">Step 1 · Upload</p>
        <h1 className="mt-3 max-w-3xl text-4xl sm:text-6xl">
          Drop a redline. <span className="text-yellow">Get decisions</span> in under 30 seconds.
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted">
          Siteline reads every tracked insertion, deletion and comment, checks each one against the playbook, and hands back one decision per change.
        </p>
      </BlurFade>

      <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <section aria-labelledby="file-heading" className="panel relative overflow-hidden p-5 sm:p-7">
          <h2 id="file-heading" className="text-2xl">Agreement file</h2>
          <label
            htmlFor="redline-file"
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              'mt-5 flex min-h-48 flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-6 text-center transition-colors duration-200',
              dragging ? 'border-yellow bg-yellow/5' : 'border-line hover:border-muted',
            )}
          >
            <UploadCloud aria-hidden className="size-10 text-butter" />
            <span className="text-lg font-bold">{file ? file.name : 'Drag a .docx here, or browse'}</span>
            <span className="text-sm text-muted">Word files with tracked changes and comments</span>
            <input
              id="redline-file"
              type="file"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="sr-only"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />
          </label>
          {fileError && <p role="alert" className="mt-3 text-sm font-bold text-butter">{fileError}</p>}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" className="btn btn-ghost" onClick={() => { setFile(null); setFileError(null) }}>
              <FileText aria-hidden className="size-4" /> Use demo file · Site 07 (14 changes)
            </button>
            {useCache && <span className="rounded-full bg-butter/15 px-3 py-1 text-xs font-bold text-butter">Cached extraction</span>}
          </div>
          <p className="mt-3 text-sm text-muted">
            {file ? 'Your file is shown for the demo; triage runs on the Site 07 sample.' : `Selected: ${SITE07.fileName}`}
          </p>

          <div className="mt-6 divide-y divide-line border-t border-line">
            <Toggle
              id="flag-local"
              label="Local parser"
              hint="Fallback flag: parse here instead of in a fresh Daytona sandbox."
              checked={localParser}
              onChange={(v) => setFlag('localParser', v)}
              disabled={run === 'running'}
            />
            <Toggle
              id="flag-cache"
              label="Cached extraction"
              hint="Reuse the stored Claude extraction for the demo file. Quotes are still verified."
              checked={useCache}
              onChange={(v) => setFlag('useCache', v)}
              disabled={run === 'running'}
            />
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <button type="button" className="btn btn-primary" onClick={start} disabled={run === 'running'}>
              {run === 'running' ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Sparkles aria-hidden className="size-4" />}
              {run === 'running' ? 'Triaging…' : run === 'done' ? 'Run again' : 'Triage redline'}
            </button>
            <span className="text-sm text-muted">Target: under {TARGET_SECONDS} s for a 14-change file</span>
          </div>
          {run === 'running' && <BorderBeam size={120} duration={6} colorFrom="var(--yellow)" colorTo="var(--magenta)" />}
        </section>

        <section aria-labelledby="pipeline-heading" className="panel p-5 sm:p-7">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="pipeline-heading" className="text-2xl">Parse pipeline</h2>
            <div className="flex flex-wrap gap-2">
              {!localParser && <SponsorChip sponsor="Daytona" />}
              <SponsorChip sponsor="Anthropic Claude" />
            </div>
          </div>

          <div ref={container} className="relative mt-6 flex items-start justify-between gap-1 overflow-hidden py-2">
            <Node nodeRef={nDoc} icon={<FileText className="size-6" />} label=".docx" state={nodeState(['upload'])} />
            <Node nodeRef={nBox} icon={<Box className="size-6" />} label={localParser ? 'Local parser' : 'Sandbox'} sponsor={localParser ? undefined : 'Daytona'} state={nodeState(['sandbox', 'parse'])} />
            <Node nodeRef={nClaude} icon={<Sparkles className="size-6" />} label="Extract + verify" sponsor="Claude" state={nodeState(['extract', 'verify'])} />
            <Node nodeRef={nRules} icon={<Gavel className="size-6" />} label="Rules" state={nodeState(['rules'])} />
            <Node nodeRef={nList} icon={<ListChecks className="size-6" />} label="Decisions" state={nodeState(['teardown'])} />
            {run !== 'idle' && (
              <>
                <AnimatedBeam containerRef={container} fromRef={nDoc} toRef={nBox} duration={3} pathColor="var(--line)" gradientStartColor="var(--yellow)" gradientStopColor="var(--magenta)" />
                <AnimatedBeam containerRef={container} fromRef={nBox} toRef={nClaude} duration={3} delay={0.4} pathColor="var(--line)" gradientStartColor="var(--yellow)" gradientStopColor="var(--magenta)" />
                <AnimatedBeam containerRef={container} fromRef={nClaude} toRef={nRules} duration={3} delay={0.8} pathColor="var(--line)" gradientStartColor="var(--yellow)" gradientStopColor="var(--magenta)" />
                <AnimatedBeam containerRef={container} fromRef={nRules} toRef={nList} duration={3} delay={1.2} pathColor="var(--line)" gradientStartColor="var(--yellow)" gradientStopColor="var(--magenta)" />
              </>
            )}
          </div>

          <div className="mt-6">
            <div className="flex items-baseline justify-between">
              <span className="eyebrow">Elapsed</span>
              <span className="tabular text-2xl font-bold" aria-live="polite">
                {seconds.toFixed(1)} s <span className="text-base font-normal text-muted">/ {TARGET_SECONDS} s</span>
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-space" role="progressbar" aria-label="Time against 30 second target" aria-valuemin={0} aria-valuemax={TARGET_SECONDS} aria-valuenow={Number(seconds.toFixed(1))}>
              <div
                className="h-full rounded-full transition-[width] duration-100"
                style={{ width: `${Math.min(100, (seconds / TARGET_SECONDS) * 100)}%`, background: 'linear-gradient(90deg, var(--mint), var(--butter))' }}
              />
            </div>
          </div>

          <Terminal sequence={false} className="mt-6 h-auto max-w-none bg-space [&_pre]:whitespace-pre-wrap [&_pre]:break-words">
            <span className="text-muted">$ siteline triage {SITE07.fileName}</span>
            {steps.filter((s) => completed.includes(s.id)).map((s) => (
              <AnimatedSpan key={s.id} className="block text-mint">
                <span>
                  <Check aria-hidden className="mr-1 inline size-3.5" />
                  {s.label} <span className="text-muted">· {s.detail}</span>
                </span>
              </AnimatedSpan>
            ))}
            {activeStep && (
              <span className="text-butter">
                <LoaderCircle aria-hidden className="mr-1 inline size-3.5 animate-spin" />
                {steps.find((s) => s.id === activeStep)?.label}…
              </span>
            )}
          </Terminal>
        </section>
      </div>

      {run === 'done' && (
        <BlurFade className="panel mt-6 flex flex-col gap-5 p-5 sm:p-7 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="eyebrow">Triage complete</p>
            <p className="mt-2 text-2xl font-bold">
              14 changes triaged in <span className="tabular text-mint">{seconds.toFixed(1)} s</span>
              {seconds < TARGET_SECONDS && <span className="text-muted"> · under target</span>}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {counts.map(([o, n]) => (
                <span key={o} className="inline-flex items-center gap-1.5">
                  <OutcomeBadge outcome={o} size="sm" /> <span className="tabular text-sm font-bold">{n}</span>
                </span>
              ))}
            </div>
            <p className="mt-3 text-sm text-muted">4 escalation texts sent to approvers by Photon.</p>
          </div>
          <ShimmerButton
            onClick={() => navigate('/review/site-07')}
            background="var(--wine)"
            shimmerColor="var(--magenta)"
            className="min-h-12 font-bold text-text"
          >
            Open decision list →
          </ShimmerButton>
        </BlurFade>
      )}
    </div>
  )
}
