import { useEffect, useState } from 'react'
import { Box, FlaskConical, LoaderCircle, Play, ShieldCheck } from 'lucide-react'
import { motion } from 'motion/react'

import * as api from '@/api'
import { useServerEvent } from '@/api/events'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { AnimatedCircularProgressBar } from '@/components/ui/animated-circular-progress-bar'
import { BlurFade } from '@/components/ui/blur-fade'
import { BorderBeam } from '@/components/ui/border-beam'
import { NumberTicker } from '@/components/ui/number-ticker'
import { cn } from '@/lib/utils'
import { outcomeLabel, outcomeOrder } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import type { EvalMetric, EvalResults } from '@/types'

const PLANNED_SANDBOXES = 12

function better(m: EvalMetric) {
  return m.lowerIsBetter ? m.siteline <= m.baseline : m.siteline >= m.baseline
}

function MetricCard({ m, highlight }: { m: EvalMetric; highlight?: boolean }) {
  const max = m.unit === '%' ? 100 : Math.max(m.siteline, m.baseline, 30)
  const rows = [
    { name: 'Siteline', value: m.siteline, color: 'var(--mint)' },
    { name: 'LLM-only baseline', value: m.baseline, color: 'var(--blue-l)' },
  ]
  return (
    <article className={cn('panel relative overflow-hidden p-5', highlight && 'border-mint/60')}>
      {highlight && <BorderBeam size={100} duration={8} colorFrom="var(--mint)" colorTo="var(--yellow)" />}
      <p className="eyebrow">{m.label}</p>
      <p className="mt-1 text-sm text-muted">{m.description}</p>
      <p className="mt-3 text-5xl font-bold tabular">
        {m.siteline === 0 ? '0' : <NumberTicker value={m.siteline} decimalPlaces={1} className="text-text" />}
        <span className="text-2xl text-muted">{m.unit === '%' ? '%' : ' s'}</span>
      </p>
      <div className="mt-4 flex flex-col gap-2">
        {rows.map((r) => (
          <div key={r.name}>
            <div className="flex justify-between text-xs">
              <span className="font-bold">{r.name}</span>
              <span className="tabular text-muted">{r.value.toFixed(1)}{m.unit === '%' ? '%' : ' s'}</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-space">
              <motion.div
                className="h-full rounded-full"
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
      <p className="mt-3 flex items-center justify-between text-xs text-muted">
        <span>Target: {m.target}</span>
        <span className={cn('font-bold', better(m) ? 'text-mint' : 'text-butter')}>
          {better(m) ? 'Siteline ahead' : 'Baseline ahead'}
        </span>
      </p>
    </article>
  )
}

export function EvalsPage() {
  const { integrations } = useDemo()
  const [latest, setLatest] = useState<api.EvalLatest | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [parsed, setParsed] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  useEffect(() => {
    api.getEvalResults().then(
      (r) => {
        setLatest(r)
        setRunning(r.status.running)
      },
      (e: Error) => setLoadError(e.message),
    )
  }, [])

  useServerEvent<{ total: number }>('eval.started', ({ total }) => {
    setRunning(true)
    setParsed(false)
    setProgress({ done: 0, total })
  })
  useServerEvent<{ line: string }>('eval.log', ({ line }) => {
    if (line.startsWith('parsed')) setParsed(true)
  })
  useServerEvent<{ done: number; total: number }>('eval.progress', (p) => setProgress(p))
  useServerEvent<{ result: EvalResults }>('eval.done', ({ result }) => {
    setLatest((l) => ({ available: true, result, status: l?.status ?? { running: false, runId: result.runId, error: null } }))
    setRunning(false)
  })
  useServerEvent<{ error: string }>('eval.failed', ({ error }) => {
    setRunError(error)
    setRunning(false)
  })

  async function run() {
    setRunError(null)
    setParsed(false)
    try {
      await api.startEvalRun()
      setRunning(true)
    } catch (e) {
      setRunError(e instanceof Error ? e.message : 'Could not start the eval')
    }
  }

  if (loadError) {
    return <div className="wrap py-16"><p role="alert" className="panel p-6">{loadError}</p></div>
  }
  if (!latest) {
    return (
      <div className="wrap py-16 text-muted" role="status">
        <LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading eval results…
      </div>
    )
  }

  const sandboxCount = latest.available && latest.result.parallelSandboxes > 0 ? latest.result.parallelSandboxes : PLANNED_SANDBOXES
  const runPanel = (
    <section aria-labelledby="run-heading" className="panel h-fit p-5 sm:p-6">
      <h2 id="run-heading" className="flex items-center gap-2 text-2xl"><FlaskConical aria-hidden className="size-5 text-butter" /> Eval run</h2>
      <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
        <dt className="text-muted">Harness</dt><dd className="font-bold">{latest.available ? latest.result.harness : 'Siteline eval harness'}</dd>
        <dt className="text-muted">Dataset</dt><dd className="font-bold break-all">{latest.available ? latest.result.datasetName : latest.dataset.name}</dd>
        {latest.available && <><dt className="text-muted">Run</dt><dd className="font-bold break-all">{latest.result.runId}</dd></>}
        {latest.available && latest.result.model && <><dt className="text-muted">Model</dt><dd className="font-bold break-all">{latest.result.model}</dd></>}
        <dt className="text-muted">Parsing</dt>
        <dd className="font-bold">{integrations?.daytona ? `${sandboxCount} Daytona sandboxes in parallel` : 'Local parser (no Daytona key)'}</dd>
      </dl>
      {integrations?.daytona && (
        <div className="mt-4 grid grid-cols-6 gap-2" aria-label={running ? (parsed ? 'Sandboxes finished parsing' : 'Sandboxes parsing') : 'Sandboxes idle'} role="img">
          {Array.from({ length: sandboxCount }, (_, i) => (
            <motion.span
              key={i}
              animate={running && !parsed ? { opacity: [0.35, 1, 0.35] } : { opacity: 1 }}
              transition={running && !parsed ? { repeat: Infinity, duration: 1.2, delay: i * 0.05 } : { duration: 0.2 }}
              className={cn(
                'flex aspect-square items-center justify-center rounded-lg border',
                parsed || !running ? 'border-mint/60 bg-mint/10 text-mint' : 'border-line text-muted',
              )}
            >
              <Box aria-hidden className="size-4" />
            </motion.span>
          ))}
        </div>
      )}
      {running && progress.total > 0 && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-muted"><span>Claude calls</span><span className="tabular">{progress.done}/{progress.total}</span></div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-space">
            <div className="h-full rounded-full bg-mint transition-[width]" style={{ width: `${(progress.done / progress.total) * 100}%` }} />
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
      {(runError || latest.status.error) && <p role="alert" className="mt-2 text-sm font-bold text-butter">{runError ?? latest.status.error}</p>}
    </section>
  )

  if (!latest.available) {
    return (
      <div className="wrap py-10 sm:py-14">
        <BlurFade>
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">Safety eval</p>
            <SponsorChip sponsor="Daytona" label="Parallel Daytona sandboxes" />
          </div>
          <h1 className="mt-3 max-w-4xl text-4xl sm:text-6xl">
            Siteline vs an <span className="text-yellow">LLM-only</span> baseline
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-muted">
            {latest.dataset.labeledChanges} labeled changes, {latest.dataset.shouldEscalate} of which should escalate. No run yet: start one to get real numbers.
          </p>
        </BlurFade>
        <div className="mt-8 max-w-md">{runPanel}</div>
      </div>
    )
  }

  const results = latest.result
  const metric = (k: string) => results.metrics.find((m) => m.key === k)!
  const recall = metric('recall')
  const accuracy = metric('accuracy')

  return (
    <div className="wrap py-10 sm:py-14">
      <BlurFade>
        <div className="flex flex-wrap items-center gap-2">
          <p className="eyebrow">Safety eval</p>
          {results.harness.includes('Chalk') && <SponsorChip sponsor="Chalk" label={results.harness} />}
          {results.parallelSandboxes > 0 && <SponsorChip sponsor="Daytona" label={`${results.parallelSandboxes} parallel Daytona sandboxes`} />}
        </div>
        <h1 className="mt-3 max-w-4xl text-4xl sm:text-6xl">
          Siteline vs an <span className="text-yellow">LLM-only</span> baseline
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted">
          {results.labeledChanges} labeled changes, {results.shouldEscalate} of which should escalate. The number that matters most: how often a change that needed an approver slipped through.
        </p>
        <p className="mt-2 text-sm text-muted">Run {results.runId} · finished {new Date(results.finishedAt).toLocaleString()}</p>
      </BlurFade>

      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <section aria-labelledby="unsafe-heading" className="panel relative overflow-hidden p-6 sm:p-8">
          <div className="nova -right-24 -bottom-24 size-72 opacity-40" aria-hidden />
          <h2 id="unsafe-heading" className="eyebrow">Unsafe accept rate</h2>
          <div className="relative mt-4 flex flex-wrap items-end gap-x-10 gap-y-4">
            <div>
              <p className={cn('text-8xl leading-none font-bold tabular', metric('unsafe').siteline === 0 ? 'text-mint' : 'text-butter')}>
                {metric('unsafe').siteline.toFixed(metric('unsafe').siteline % 1 ? 1 : 0)}<span className="text-4xl">%</span>
              </p>
              <p className="mt-2 flex items-center gap-1.5 font-bold"><ShieldCheck aria-hidden className="size-4 text-mint" /> Siteline · target 0</p>
            </div>
            <div>
              <p className="text-5xl leading-none font-bold text-blue-l tabular">
                <NumberTicker value={metric('unsafe').baseline} decimalPlaces={1} className="text-blue-l" />%
              </p>
              <p className="mt-2 text-sm text-muted">LLM-only baseline: {Math.round((metric('unsafe').baseline / 100) * results.shouldEscalate)} of {results.shouldEscalate} escalations accepted or countered</p>
            </div>
          </div>
        </section>

        <section aria-labelledby="gauges-heading" className="panel p-6">
          <h2 id="gauges-heading" className="eyebrow">Siteline at a glance</h2>
          <div className="mt-4 grid grid-cols-2 gap-4">
            {[recall, accuracy].map((m) => (
              <div key={m.key} className="flex flex-col items-center text-center">
                <AnimatedCircularProgressBar
                  value={m.siteline}
                  gaugePrimaryColor="var(--mint)"
                  gaugeSecondaryColor="var(--line)"
                  className="size-28 text-xl text-text sm:size-32"
                />
                <p className="mt-2 text-sm font-bold">{m.label}</p>
                <p className="text-xs text-muted">baseline {m.baseline.toFixed(1)}%</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {['recall', 'accuracy', 'quotes', 'latency'].map((k) => (
          <BlurFade key={k} inView>
            <MetricCard m={metric(k)} highlight={k === 'quotes'} />
          </BlurFade>
        ))}
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section aria-labelledby="matrix-heading" className="panel p-5 sm:p-6">
          <h2 id="matrix-heading" className="text-2xl">Siteline confusion matrix</h2>
          <p className="mt-1 text-sm text-muted">Rows: labeled outcome. Columns: what Siteline chose.</p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[520px] text-center text-sm">
              <thead>
                <tr>
                  <th scope="col" className="p-2 text-left text-xs text-muted">Label ↓ / Siteline →</th>
                  {outcomeOrder.map((o) => (
                    <th key={o} scope="col" className="p-2 text-xs font-bold">{outcomeLabel[o]}</th>
                  ))}
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
                        const unsafe = row === 'escalate' && (col === 'accept' || col === 'fallback')
                        return (
                          <td key={col} className="p-1">
                            <span
                              className={cn(
                                'flex h-11 items-center justify-center rounded-lg font-bold tabular',
                                row === col ? 'text-ink' : 'text-text',
                                unsafe && 'ring-1 ring-red',
                              )}
                              style={{
                                background: row === col
                                  ? `color-mix(in oklab, var(--mint) ${30 + (total ? n / total : 0) * 70}%, var(--space-2))`
                                  : n > 0 ? 'color-mix(in oklab, var(--butter) 18%, var(--space))' : 'var(--space)',
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
            Red-outlined cells are unsafe accepts: labeled escalations that Siteline accepted or countered
            ({results.confusion.escalate.accept + results.confusion.escalate.fallback} in this run).
          </p>
        </section>

        {runPanel}
      </div>
    </div>
  )
}
