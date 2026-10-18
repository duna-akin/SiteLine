import { useEffect, useState } from 'react'
import { Box, FlaskConical, LoaderCircle, Play, RotateCw, ShieldCheck } from 'lucide-react'
import { motion } from 'motion/react'

import * as api from '@/api'
import { useServerEvent } from '@/api/events'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { AnimatedCircularProgressBar } from '@/components/ui/animated-circular-progress-bar'
import { cn } from '@/lib/utils'
import { outcomeLabel, outcomeOrder } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import type { EvalMetric, EvalResults as EvalResult } from '@/types'

const PLANNED_SANDBOXES = 12

const better = (m: EvalMetric) => (m.lowerIsBetter ? m.siteline <= m.baseline : m.siteline >= m.baseline)
const unit = (m: EvalMetric) => (m.unit === '%' ? '%' : ' s')

function MetricCard({ m }: { m: EvalMetric }) {
  const max = m.unit === '%' ? 100 : Math.max(m.siteline, m.baseline, 30)
  const rows = [
    { name: 'Siteline', value: m.siteline, color: 'var(--ink-2)' },
    { name: 'LLM-only baseline', value: m.baseline, color: 'var(--accent)' },
  ]
  return (
    <article className="tile flex flex-col">
      <p className="eyebrow">{m.label}</p>
      <p className="mt-1 text-sm text-muted">{m.description}</p>
      <p className="mt-3 font-serif text-[34px] leading-tight font-medium tabular">
        {m.siteline.toFixed(m.siteline % 1 ? 1 : 0)}<span className="text-lg text-muted">{unit(m)}</span>
      </p>
      <div className="mt-4 flex flex-col gap-2">
        {rows.map((r) => (
          <div key={r.name}>
            <div className="flex justify-between text-xs">
              <span className="font-medium">{r.name}</span>
              <span className="text-muted tabular">{r.value.toFixed(1)}{unit(m)}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-[2px] bg-sunken">
              <motion.div
                className="h-full"
                style={{ background: r.color }}
                initial={{ width: 0 }}
                whileInView={{ width: `${Math.max(1.5, (r.value / max) * 100)}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-auto flex items-center justify-between pt-3 text-xs text-muted">
        <span>Target: {m.target}</span>
        <span className={cn('pill', better(m) ? 's-ok' : 's-elevated')}>{better(m) ? 'Siteline ahead' : 'Baseline ahead'}</span>
      </p>
    </article>
  )
}

function Confusion({ results }: { results: EvalResult }) {
  return (
    <section aria-labelledby="matrix-heading" className="tile min-w-0">
      <div className="tile-head"><h2 id="matrix-heading">Siteline confusion matrix</h2></div>
      <p className="tile-sub">Rows: labeled outcome. Columns: what Siteline chose.</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-center text-sm">
          <thead>
            <tr>
              <th scope="col" className="p-2 text-left text-xs text-muted">Label ↓ / Siteline →</th>
              {outcomeOrder.map((o) => <th key={o} scope="col" className="p-2 text-xs font-semibold">{outcomeLabel[o]}</th>)}
            </tr>
          </thead>
          <tbody>
            {outcomeOrder.map((row) => {
              const total = outcomeOrder.reduce((n, c) => n + results.confusion[row][c], 0)
              return (
                <tr key={row}>
                  <th scope="row" className="p-2 text-left"><OutcomeBadge outcome={row} size="sm" /></th>
                  {outcomeOrder.map((col) => {
                    const n = results.confusion[row][col]
                    const unsafe = row === 'escalate' && (col === 'accept' || col === 'counter')
                    return (
                      <td key={col} className="p-1">
                        <span
                          className={cn('flex h-11 items-center justify-center rounded-[6px] font-semibold tabular', unsafe && n > 0 && 'shadow-[inset_0_0_0_1px_var(--high)]')}
                          style={{
                            background: row === col
                              ? `color-mix(in oklab, var(--stuck-none) ${20 + (total ? n / total : 0) * 50}%, var(--surface))`
                              : n > 0 ? 'var(--elevated-bg)' : 'var(--page)',
                          }}
                        >
                          {n}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted">
        Outlined cells are unsafe accepts: labeled escalations that Siteline accepted or countered
        ({results.confusion.escalate.accept + results.confusion.escalate.counter} in this run).
      </p>
    </section>
  )
}

/** Siteline vs an LLM-only baseline on the labeled set: latest results and the run control. */
export function EvalResults() {
  const { integrations } = useDemo()
  const [latest, setLatest] = useState<api.EvalLatest | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [parsed, setParsed] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const load = () => {
    api.getEvalResults().then(
      (r) => {
        setLoadError(null)
        setLatest(r)
        setRunning(r.status.running)
      },
      (e: Error) => setLoadError(e.message),
    )
  }
  useEffect(load, [])

  // A finished or newly started run makes any earlier failure stale.
  const clearStoredError = () => setLatest((l) => (l ? { ...l, status: { ...l.status, error: null } } : l))
  useServerEvent<{ total: number }>('eval.started', ({ total }) => {
    setRunning(true)
    setParsed(false)
    setRunError(null)
    clearStoredError()
    setProgress({ done: 0, total })
  })
  useServerEvent<{ line: string }>('eval.log', ({ line }) => {
    if (line.startsWith('parsed')) setParsed(true)
  })
  useServerEvent<{ done: number; total: number }>('eval.progress', (p) => setProgress(p))
  useServerEvent<{ result: EvalResult }>('eval.done', ({ result }) => {
    setLatest({ available: true, result, status: { running: false, runId: result.runId, error: null } })
    setRunError(null)
    setRunning(false)
  })
  useServerEvent<{ error: string }>('eval.failed', ({ error }) => {
    setRunError(error)
    setRunning(false)
  })

  async function run() {
    setRunError(null)
    clearStoredError()
    setParsed(false)
    try {
      await api.startEvalRun()
      setRunning(true)
    } catch (e) {
      setRunError(e instanceof Error ? e.message : 'Could not start the eval')
    }
  }

  if (loadError) {
    return (
      <div className="tile text-center" role="alert">
        <p className="font-semibold">Couldn’t load the eval results.</p>
        <p className="mt-1 text-sm text-muted">{loadError}</p>
        <button type="button" className="btn btn-primary mt-4" onClick={load}><RotateCw aria-hidden className="size-4" /> Try again</button>
      </div>
    )
  }
  if (!latest) {
    return (
      <div className="tile text-muted" role="status">
        <LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading eval results…
      </div>
    )
  }

  const error = runError ?? latest.status.error
  const sandboxCount = latest.available && latest.result.parallelSandboxes > 0 ? latest.result.parallelSandboxes : PLANNED_SANDBOXES
  const runPanel = (
    <section aria-labelledby="run-heading" className="tile h-fit">
      <div className="tile-head"><h2 id="run-heading"><FlaskConical aria-hidden className="size-5 text-faint" /> Eval run</h2></div>
      <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted">Harness</dt><dd className="font-semibold">{latest.available ? latest.result.harness : 'Siteline eval harness'}</dd>
        <dt className="text-muted">Dataset</dt><dd className="font-semibold break-all">{latest.available ? latest.result.datasetName : latest.dataset.name}</dd>
        {latest.available && <><dt className="text-muted">Run</dt><dd className="font-semibold break-all">{latest.result.runId}</dd></>}
        {latest.available && latest.result.model && <><dt className="text-muted">Model</dt><dd className="font-semibold break-all">{latest.result.model}</dd></>}
        <dt className="text-muted">Parsing</dt>
        <dd className="font-semibold">{integrations?.daytona ? `${sandboxCount} Daytona sandboxes in parallel` : 'Local parser (no Daytona key)'}</dd>
      </dl>
      {integrations?.daytona && (
        <div className="mt-4 grid grid-cols-6 gap-2" aria-label={running ? (parsed ? 'Sandboxes finished parsing' : 'Sandboxes parsing') : 'Sandboxes idle'} role="img">
          {Array.from({ length: sandboxCount }, (_, i) => (
            <motion.span
              key={i}
              animate={running && !parsed ? { opacity: [0.35, 1, 0.35] } : { opacity: 1 }}
              transition={running && !parsed ? { repeat: Infinity, duration: 1.2, delay: i * 0.05 } : { duration: 0.2 }}
              className={cn('flex aspect-square items-center justify-center rounded-[6px]', parsed || !running ? 'border border-line bg-surface text-ok' : 'border border-line bg-surface text-faint')}
            >
              <Box aria-hidden className="size-4" />
            </motion.span>
          ))}
        </div>
      )}
      {running && progress.total > 0 && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-muted"><span>Model calls</span><span className="tabular">{progress.done}/{progress.total}</span></div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-[2px] bg-sunken">
            <div className="h-full bg-ink-2 transition-[width]" style={{ width: `${(progress.done / progress.total) * 100}%` }} />
          </div>
        </div>
      )}
      <button type="button" className="btn btn-primary mt-5 w-full" onClick={run} disabled={running || !integrations?.claude}>
        {running ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Play aria-hidden className="size-4" />}
        {running ? 'Running…' : latest.available ? 'Re-run eval' : 'Run eval'}
      </button>
      <p className="mt-2 text-xs text-muted">
        {integrations?.claude
          ? 'Runs Siteline and the LLM-only baseline on every labeled change (about 300 OpenAI calls).'
          : 'Needs an OpenAI API key on the server (OPENAI_API_KEY).'}
      </p>
      {error && <p role="alert" className="alert mt-2">{error}</p>}
    </section>
  )

  if (!latest.available) {
    return (
      <div className="grid gap-6 min-[1081px]:grid-cols-12">
        <div className="tile min-[1081px]:col-span-7">
          <h3 className="text-[20px]">No run yet</h3>
          <p className="mt-2 text-muted">
            {latest.dataset.labeledChanges} labeled changes, {latest.dataset.shouldEscalate} of which should escalate. Start a run to get real numbers.
          </p>
        </div>
        <div className="min-[1081px]:col-span-5">{runPanel}</div>
      </div>
    )
  }

  const results = latest.result
  const metric = (k: string) => results.metrics.find((m) => m.key === k)!
  const unsafe = metric('unsafe')

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted">
        {results.labeledChanges} labeled changes, {results.shouldEscalate} of which should escalate · run {results.runId} · finished {new Date(results.finishedAt).toLocaleString()}
        <span className="ml-2 inline-flex flex-wrap gap-2 align-middle">
          {results.harness.includes('Chalk') && <SponsorChip sponsor="Chalk" label={results.harness} />}
          {results.parallelSandboxes > 0 && <SponsorChip sponsor="Daytona" label={`${results.parallelSandboxes} parallel Daytona sandboxes`} />}
        </span>
      </p>

      <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-12">
        <section aria-labelledby="unsafe-heading" className="tile min-[1081px]:col-span-7">
          <h3 id="unsafe-heading" className="eyebrow">Unsafe accept rate</h3>
          <p className="mt-1 text-sm text-ink">How often a change that needed an approver slipped through.</p>
          <div className="mt-4 flex flex-wrap items-end gap-x-10 gap-y-4">
            <div>
              <p className={cn('font-serif text-[64px] leading-none font-medium tabular', unsafe.siteline === 0 ? 'text-ok' : 'text-elevated')}>
                {unsafe.siteline.toFixed(unsafe.siteline % 1 ? 1 : 0)}<span className="text-[28px]">%</span>
              </p>
              <p className="mt-2 flex items-center gap-1.5 font-medium"><ShieldCheck aria-hidden className="size-4 text-ok" /> Siteline · target 0</p>
            </div>
            <div>
              <p className="font-serif text-[34px] leading-none font-medium text-accent tabular">{unsafe.baseline.toFixed(1)}%</p>
              <p className="mt-2 text-sm text-ink">LLM-only baseline: {Math.round((unsafe.baseline / 100) * results.shouldEscalate)} of {results.shouldEscalate} escalations accepted or countered</p>
            </div>
          </div>
        </section>

        <section aria-labelledby="gauges-heading" className="tile min-[1081px]:col-span-5">
          <h3 id="gauges-heading" className="eyebrow">Siteline at a glance</h3>
          <div className="mt-4 grid grid-cols-2 gap-4">
            {[metric('recall'), metric('accuracy')].map((m) => (
              <div key={m.key} className="flex flex-col items-center text-center">
                <AnimatedCircularProgressBar value={m.siteline} gaugePrimaryColor="var(--ink-2)" gaugeSecondaryColor="var(--line)" className="size-28 text-xl text-ink sm:size-32" />
                <p className="mt-2 text-sm font-medium">{m.label}</p>
                <p className="text-xs text-muted">baseline {m.baseline.toFixed(1)}%</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        {['recall', 'accuracy', 'quotes', 'latency'].map((k) => <MetricCard key={k} m={metric(k)} />)}
      </div>

      <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-[minmax(0,1fr)_380px]">
        <Confusion results={results} />
        {runPanel}
      </div>
    </div>
  )
}
