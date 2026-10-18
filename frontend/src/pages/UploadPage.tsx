import { useEffect, useRef, useState, type DragEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Box, Check, CircleSlash, Download, FileSearch, FileText, Gavel, ListChecks, LoaderCircle, Play, TriangleAlert, UploadCloud } from 'lucide-react'

import * as api from '@/api'
import { runTriage } from '@/api/events'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { cn } from '@/lib/utils'
import { outcomeOrder } from '@/mocks/playbook'
import { DEMO_FILE_NAME, stepLabels } from '@/mocks/site07'
import { useDemo } from '@/state/demo'
import type { ParseStepId, StepState, TriageStepEvent } from '@/types'

const TARGET_SECONDS = 30
const STEP_ORDER: ParseStepId[] = ['upload', 'sandbox', 'parse', 'extract', 'verify', 'rules', 'teardown']

type RunState = 'idle' | 'running' | 'done'
type NodeState = 'waiting' | 'active' | 'done' | 'skipped'

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
        <label htmlFor={id} className="font-medium">{label}</label>
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
          'relative mt-1 inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors duration-150 disabled:opacity-45',
          checked ? 'border-ink-2 bg-ink-2' : 'border-line-strong bg-sunken',
        )}
      >
        <span className={cn('inline-block size-[18px] rounded-full bg-surface shadow-[0_1px_2px_rgba(33,33,33,.2)] transition-transform duration-150 ease-brand', checked ? 'translate-x-[22px]' : 'translate-x-[2px]')} />
      </button>
    </div>
  )
}

const nodeTone: Record<NodeState, string> = {
  done: 'border-ok text-ok',
  active: 'border-ink-2 text-ink shadow-[0_0_0_3px_var(--sunken)]',
  waiting: 'border-line text-faint',
  skipped: 'border-dashed border-line-strong text-faint opacity-60',
}

function Node({ icon, label, state }: {
  icon: ReactNode
  label: string
  state: NodeState
}) {
  return (
    <div className="z-10 flex w-[4.5rem] flex-col items-center gap-2 text-center sm:w-24">
      <div className={cn('flex size-12 items-center justify-center rounded-[6px] border bg-surface transition-colors duration-200 sm:size-14', nodeTone[state])}>
        {icon}
      </div>
      <span className="text-xs leading-tight font-medium">{label}</span>
    </div>
  )
}

export function UploadPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { localParser, useCache, setFlag, loadAgreement, reset, decisions, agreement, integrations, notify } = useDemo()
  // A .docx dropped on Home or Inbound arrives here in the navigation state.
  const [file, setFile] = useState<File | null>(() => {
    const handed = (location.state as { file?: unknown } | null)?.file
    return handed instanceof File && handed.name.toLowerCase().endsWith('.docx') ? handed : null
  })
  const [dragging, setDragging] = useState(false)
  const [run, setRun] = useState<RunState>('idle')
  const [steps, setSteps] = useState<Partial<Record<ParseStepId, TriageStepEvent>>>({})
  const [logLines, setLogLines] = useState<string[]>([])
  const [elapsed, setElapsed] = useState(0)
  const [fileError, setFileError] = useState<string | null>(() => {
    const handed = (location.state as { file?: unknown } | null)?.file
    return handed instanceof File && !handed.name.toLowerCase().endsWith('.docx') ? 'That file isn’t a Word document. Upload a .docx with tracked changes.' : null
  })
  const [runError, setRunError] = useState<string | null>(null)
  const [resultId, setResultId] = useState<string | null>(null)
  const startedAt = useRef(0)

  useEffect(() => {
    if (run !== 'running') return
    const t = setInterval(() => setElapsed(performance.now() - startedAt.current), 100)
    return () => clearInterval(t)
  }, [run])

  const daytonaLive = !!integrations?.daytona && !localParser
  const fileName = file?.name ?? DEMO_FILE_NAME

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
    setSteps({})
    setLogLines([])
    setRunError(null)
    setResultId(null)
    setElapsed(0)
    startedAt.current = performance.now()
    try {
      const result = await runTriage(
        file,
        { localParser, useCache },
        (e) => setSteps((s) => ({ ...s, [e.step]: e })),
        (line) => setLogLines((l) => [...l, line]),
      )
      setElapsed(performance.now() - startedAt.current)
      await loadAgreement(result.agreementId)
      setResultId(result.agreementId)
      setRun('done')
    } catch (e) {
      setElapsed(performance.now() - startedAt.current)
      setRunError(e instanceof Error ? e.message : 'Triage failed')
      setRun('idle')
      notify('Triage failed')
    }
  }

  const stepState = (id: ParseStepId): StepState | 'waiting' => steps[id]?.state ?? 'waiting'
  const nodeState = (ids: ParseStepId[]): NodeState => {
    const states = ids.map(stepState)
    if (states.every((s) => s === 'skipped')) return 'skipped'
    if (states.some((s) => s === 'active')) return 'active'
    if (states.every((s) => s === 'done' || s === 'skipped' || s === 'failed')) return 'done'
    return run === 'running' && states.some((s) => s !== 'waiting') ? 'active' : 'waiting'
  }
  const activeStep = STEP_ORDER.find((id) => steps[id]?.state === 'active') ?? null
  const finished = STEP_ORDER.filter((id) => steps[id] && steps[id]!.state !== 'active')

  const seconds = elapsed / 1000
  const ready = run === 'done' && resultId !== null && agreement?.id === resultId
  const counts = outcomeOrder.map((o) => [o, decisions.filter((d) => d.outcome === o).length] as const)
  const escalations = decisions.filter((d) => d.outcome === 'escalate')
  const viaPhoton = escalations.filter((d) => d.approval.state !== 'none' && d.approval.delivery === 'photon').length

  return (
    <div className="wrap pb-12">
      <Link to="/inbound" className="link"><ArrowRight aria-hidden className="size-4 rotate-180" /> Inbound</Link>
      <section className="hello pt-2 pb-6">
        <span className="eyebrow">Intake · Upload</span>
        <h1>Upload a redline</h1>
        <p>Siteline reads every tracked insertion, deletion and comment, checks each one against the playbook, and hands back one decision per change, in under {TARGET_SECONDS} seconds.</p>
      </section>

      <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-12">
        <section aria-labelledby="file-heading" className="tile min-[1081px]:col-span-6">
          <div className="tile-head"><h2 id="file-heading">Agreement file</h2></div>
          <label
            htmlFor="redline-file"
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            data-over={dragging}
            className="drop mt-2 min-h-48 cursor-pointer flex-col justify-center text-center"
          >
            <UploadCloud aria-hidden className="size-8 text-faint" />
            <span className="text-base font-medium text-ink">{file ? file.name : 'Drag a .docx here, or browse'}</span>
            <span>Word files with tracked changes and comments</span>
            <input
              id="redline-file"
              type="file"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="sr-only"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />
          </label>
          {fileError && <p role="alert" className="alert mt-3">{fileError}</p>}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setFile(null); setFileError(null) }}>
              <FileText aria-hidden className="size-4" /> Use demo file · Site 07 (14 changes)
            </button>
            <a href={api.demoFileUrl} className="btn btn-secondary btn-sm" download>
              <Download aria-hidden className="size-4" /> Download demo .docx
            </a>
          </div>
          <p className="mt-3 text-sm text-muted">Selected: <span className="font-medium text-ink">{fileName}</span></p>

          <div className="mt-4 divide-y divide-line border-t border-line">
            <Toggle
              id="flag-local"
              label="Local parser"
              hint={integrations && !integrations.daytona ? 'No sandbox is set up on the server, so parsing runs locally.' : 'Fallback flag: parse here instead of in a fresh sandbox.'}
              checked={localParser || (!!integrations && !integrations.daytona)}
              onChange={(v) => setFlag('localParser', v)}
              disabled={run === 'running' || (!!integrations && !integrations.daytona)}
            />
            <Toggle
              id="flag-cache"
              label="Cached extraction"
              hint={integrations && !integrations.claude ? 'Extraction is off on the server: only cached changes are extracted; others go to human review.' : 'Reuse a stored extraction when the change was seen before. Quotes are still verified.'}
              checked={useCache}
              onChange={(v) => setFlag('useCache', v)}
              disabled={run === 'running'}
            />
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-4">
            <button type="button" className="btn btn-primary" onClick={start} disabled={run === 'running'}>
              {run === 'running' ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Play aria-hidden className="size-4" />}
              {run === 'running' ? 'Triaging…' : run === 'done' ? 'Run again' : 'Triage redline'}
            </button>
            <span className="text-sm text-muted">Target: under {TARGET_SECONDS} s for a 14-change file</span>
          </div>
          {runError && (
            <p role="alert" className="alert mt-4 flex items-start gap-2">
              <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-high" /> {runError}
            </p>
          )}
        </section>

        <section aria-labelledby="pipeline-heading" className="tile min-[1081px]:col-span-6">
          <div className="tile-head"><h2 id="pipeline-heading">Parse pipeline</h2></div>

          <div className="well relative mt-4 flex items-start justify-between gap-1 overflow-hidden px-2 py-4">
            {/* A static rule behind the steps; each step's border shows its state */}
            <span aria-hidden className="absolute inset-x-10 top-[calc(1rem+24px)] h-px bg-line-strong sm:top-[calc(1rem+28px)]" />
            <Node icon={<FileText className="size-5" />} label=".docx" state={nodeState(['upload'])} />
            <Node icon={<Box className="size-5" />} label={daytonaLive ? 'Sandbox' : 'Local parser'} state={nodeState(['sandbox', 'parse'])} />
            <Node icon={<FileSearch className="size-5" />} label="Extract + verify" state={nodeState(['extract', 'verify'])} />
            <Node icon={<Gavel className="size-5" />} label="Rules" state={nodeState(['rules'])} />
            <Node icon={<ListChecks className="size-5" />} label="Decisions" state={nodeState(['teardown'])} />
          </div>

          <div className="mt-5">
            <div className="flex items-baseline justify-between">
              <span className="eyebrow">Elapsed</span>
              <span className="font-serif text-2xl font-medium tabular" aria-live="polite">
                {seconds.toFixed(1)} s <span className="font-sans text-base font-normal text-muted">/ {TARGET_SECONDS} s</span>
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-[2px] bg-sunken" role="progressbar" aria-label={`Time against ${TARGET_SECONDS} second target`} aria-valuemin={0} aria-valuemax={TARGET_SECONDS} aria-valuenow={Number(seconds.toFixed(1))}>
              <div className="h-full bg-ink-2 transition-[width] duration-100" style={{ width: `${Math.min(100, (seconds / TARGET_SECONDS) * 100)}%` }} />
            </div>
          </div>

          <div role="log" aria-label="Triage log" className="well mt-5 flex min-h-32 flex-col gap-1 p-4 font-mono text-[12.5px] leading-relaxed break-words">
            <span className="text-muted">$ siteline triage {fileName}</span>
            {finished.map((id) => {
              const s = steps[id]!
              const skipped = s.state === 'skipped'
              const failed = s.state === 'failed'
              return (
                <span key={id} className={cn(skipped ? 'text-muted' : failed ? 'text-high' : 'text-ok')}>
                  {skipped ? <CircleSlash aria-hidden className="mr-1 inline size-3.5" /> : failed ? <TriangleAlert aria-hidden className="mr-1 inline size-3.5" /> : <Check aria-hidden className="mr-1 inline size-3.5" />}
                  {stepLabels[id]} <span className="text-muted">· {s.detail}</span>
                </span>
              )
            })}
            {logLines.map((line, i) => (
              <span key={`log-${i}`} className="pl-4 text-xs text-muted">{line}</span>
            ))}
            {activeStep && (
              <span className="text-elevated">
                <LoaderCircle aria-hidden className="mr-1 inline size-3.5 animate-spin" />
                {stepLabels[activeStep]}… <span className="text-muted">{steps[activeStep]?.detail}</span>
              </span>
            )}
          </div>
        </section>

        {ready && agreement && (
          <section aria-labelledby="done-heading" className="tile flex flex-col gap-5 min-[1081px]:col-span-12 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="eyebrow text-ok">Triage complete · Site {agreement.siteNumber}, {agreement.siteName}</p>
              <h2 id="done-heading" className="mt-2 text-[24px]">
                {decisions.length} changes triaged in <span className="tabular">{seconds.toFixed(1)} s</span>
                {seconds < TARGET_SECONDS && <span className="font-sans text-base font-medium text-ok"> · under target</span>}
              </h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {counts.map(([o, n]) => (
                  <span key={o} className="inline-flex items-center gap-1.5">
                    <OutcomeBadge outcome={o} size="sm" /> <span className="text-sm font-semibold tabular">{n}</span>
                  </span>
                ))}
              </div>
              <p className="mt-3 text-sm text-ink">
                {escalations.length === 0
                  ? 'No escalations: nothing to text.'
                  : viaPhoton > 0
                    ? `${viaPhoton} of ${escalations.length} escalation texts sent to approvers.`
                    : `${escalations.length} escalation texts simulated: no text line is set up, so record replies on Review.`}
              </p>
            </div>
            <button type="button" className="btn btn-primary" onClick={() => navigate(`/review/${agreement.id}`)}>
              Open decision list <ArrowRight aria-hidden className="size-4" />
            </button>
          </section>
        )}
      </div>
    </div>
  )
}
