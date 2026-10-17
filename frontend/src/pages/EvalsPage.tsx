import { useEffect, useState } from 'react'
import { Box, FlaskConical, LoaderCircle, Play, ShieldCheck } from 'lucide-react'
import { motion } from 'motion/react'

import * as api from '@/api'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { AnimatedCircularProgressBar } from '@/components/ui/animated-circular-progress-bar'
import { BlurFade } from '@/components/ui/blur-fade'
import { BorderBeam } from '@/components/ui/border-beam'
import { NumberTicker } from '@/components/ui/number-ticker'
import { cn } from '@/lib/utils'
import { outcomeLabel, outcomeOrder } from '@/mocks/playbook'
import type { EvalMetric, EvalResults } from '@/types'

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
  const [results, setResults] = useState<EvalResults | null>(null)
  const [running, setRunning] = useState(false)
  const [finished, setFinished] = useState(0)

  useEffect(() => {
    void api.getEvalResults().then(setResults)
  }, [])

  async function run() {
    if (!results) return
    setRunning(true)
    setFinished(0)
    await api.startEvalRun()
    for (let i = 1; i <= results.parallelSandboxes; i++) {
      await new Promise((r) => setTimeout(r, 180 + Math.random() * 220))
      setFinished(i)
    }
    setResults(await api.getEvalResults())
    setRunning(false)
  }

  if (!results) {
    return (
      <div className="wrap py-16 text-muted" role="status">
        <LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading eval results…
      </div>
    )
  }

  const metric = (k: string) => results.metrics.find((m) => m.key === k)!
  const recall = metric('recall')
  const accuracy = metric('accuracy')

  return (
    <div className="wrap py-10 sm:py-14">
      <BlurFade>
        <div className="flex flex-wrap items-center gap-2">
          <p className="eyebrow">Safety eval</p>
          <SponsorChip sponsor="Chalk" label={results.harness} />
          <SponsorChip sponsor="Daytona" label="Parallel Daytona sandboxes" />
        </div>
        <h1 className="mt-3 max-w-4xl text-4xl sm:text-6xl">
          Siteline vs an <span className="text-yellow">LLM-only</span> baseline
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted">
          {results.labeledChanges} labeled changes, {results.shouldEscalate} of which should escalate. The number that matters most: how often a change that needed an approver slipped through.
        </p>
        <p className="mt-2 text-sm text-butter">Placeholder numbers for the UI. They get replaced when the eval harness runs.</p>
      </BlurFade>

      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <section aria-labelledby="unsafe-heading" className="panel relative overflow-hidden p-6 sm:p-8">
          <div className="nova -right-24 -bottom-24 size-72 opacity-40" aria-hidden />
          <h2 id="unsafe-heading" className="eyebrow">Unsafe accept rate</h2>
          <div className="relative mt-4 flex flex-wrap items-end gap-x-10 gap-y-4">
            <div>
              <p className="text-8xl leading-none font-bold text-mint tabular">0<span className="text-4xl">%</span></p>
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
        {['recall', 'accuracy', 'quote', 'latency'].map((k) => (
          <BlurFade key={k} inView>
            <MetricCard m={metric(k)} highlight={k === 'quote'} />
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
                                  ? `color-mix(in oklab, var(--mint) ${30 + (n / total) * 70}%, var(--space-2))`
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
          <p className="mt-3 text-xs text-muted">Red-outlined cells are unsafe accepts: labeled escalations that Siteline accepted or countered. Both are 0.</p>
        </section>

        <section aria-labelledby="run-heading" className="panel h-fit p-5 sm:p-6">
          <h2 id="run-heading" className="flex items-center gap-2 text-2xl"><FlaskConical aria-hidden className="size-5 text-butter" /> Eval run</h2>
          <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-muted">Harness</dt><dd className="font-bold">{results.harness}</dd>
            <dt className="text-muted">Dataset</dt><dd className="font-bold break-all">{results.datasetName}</dd>
            <dt className="text-muted">Run</dt><dd className="font-bold break-all">{results.runId}</dd>
            <dt className="text-muted">Sandboxes</dt><dd className="font-bold">{results.parallelSandboxes} in parallel</dd>
          </dl>
          <div className="mt-4 grid grid-cols-6 gap-2" aria-label={`${finished} of ${results.parallelSandboxes} sandboxes finished`} role="img">
            {Array.from({ length: results.parallelSandboxes }, (_, i) => (
              <motion.span
                key={i}
                animate={running && i >= finished ? { opacity: [0.35, 1, 0.35] } : { opacity: 1 }}
                transition={running && i >= finished ? { repeat: Infinity, duration: 1.2, delay: i * 0.05 } : { duration: 0.2 }}
                className={cn(
                  'flex aspect-square items-center justify-center rounded-lg border',
                  i < finished || !running ? 'border-mint/60 bg-mint/10 text-mint' : 'border-line text-muted',
                )}
              >
                <Box aria-hidden className="size-4" />
              </motion.span>
            ))}
          </div>
          <button type="button" className="btn btn-primary mt-5 w-full" onClick={run} disabled={running}>
            {running ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Play aria-hidden className="size-4" />}
            {running ? `Running… ${finished}/${results.parallelSandboxes}` : 'Re-run eval'}
          </button>
          <p className="mt-2 text-xs text-muted">Stubbed: replays the stored results.</p>
        </section>
      </div>
    </div>
  )
}
