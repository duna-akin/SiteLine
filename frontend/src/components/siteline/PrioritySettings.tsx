import { useCallback, useEffect, useId, useState } from 'react'
import { Eye, LoaderCircle, RotateCcw, Save } from 'lucide-react'

import * as api from '@/api'
import { priorityPill, priorityShort, usd } from '@/components/siteline/priority-style'
import { cn } from '@/lib/utils'
import { useDemo } from '@/state/demo'
import type { CostOfDelay, PriorityBand, PriorityConfig, PrioritySettings as Settings, RedecidedChange } from '@/types'

const LEVELS = ['high', 'elevated', 'standard'] as const

const pct = (share: number) => `${Math.round(share * 100)}%`

/** Risk-adjusted, discounted sales lost per trial day, and the whole day with trial costs (mirrors priority.assess). */
function trialDay(c: CostOfDelay) {
  const sales = (c.probabilityOfApproval * c.salesPerDayUsd) / (1 + c.discountRate) ** c.yearsToLaunch
  return { sales, total: sales + c.trialCostPerDayUsd }
}

/** The accept line a share of the gap gives this band (mirrors rules.band_limit). */
const bandLimit = (b: PriorityBand, share: number) => Math.round((b.standard + share * (b.floor - b.standard)) * 100) / 100

function Field({ label, hint, value, was, onChange, min, max, step = 1, prefix, suffix, slider }: {
  label: string
  hint?: string
  value: number
  was?: string
  onChange: (v: number) => void
  min: number
  max: number
  step?: number
  prefix?: string
  suffix?: string
  /** Range of the slider beside the number, when it differs from the field's limits. */
  slider?: [number, number]
}) {
  const id = useId()
  return (
    <div className={cn('grid items-center gap-3 rounded-[8px] px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,180px)]', was ? 'border border-line border-l-[3px] border-l-elevated bg-subtle' : 'border border-line bg-subtle')}>
      <label htmlFor={id} className="font-semibold">
        {label}
        {hint && <small className="block text-xs font-semibold text-muted">{hint}</small>}
      </label>
      <div>
        <div className="flex items-center gap-1.5 rounded-[6px] bg-surface px-3 border border-line-strong focus-within:outline-2 focus-within:outline-accent">
          {prefix && <span className="text-muted">{prefix}</span>}
          <input
            id={id}
            type="number"
            inputMode="numeric"
            className="min-h-11 w-24 bg-transparent font-semibold tabular outline-none"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          {suffix && <span className="shrink-0 text-sm text-muted">{suffix}</span>}
        </div>
        {was && <p className="mt-1 text-xs font-medium text-elevated">was {was}</p>}
      </div>
      <input
        type="range"
        aria-label={`${label} slider`}
        min={slider?.[0] ?? min}
        max={slider?.[1] ?? max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--ink-2)]"
      />
    </div>
  )
}

export function PrioritySettings() {
  const { notify } = useDemo()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [draft, setDraft] = useState<PriorityConfig | null>(null)
  const [preview, setPreview] = useState<RedecidedChange[] | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.getPrioritySettings().then(
      (s) => {
        setSettings(s)
        setDraft(s.config)
      },
      (e: Error) => setErrors([e.message]),
    )
  }, [])
  useEffect(load, [load])

  if (!settings || !draft) {
    return (
      <div className="tile text-muted" role="status">
        {errors.length ? errors.join(' ') : <><LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading priority settings…</>}
      </div>
    )
  }

  const saved = settings.config
  const edit = (next: PriorityConfig) => {
    setDraft(next)
    setPreview(null)
    setErrors([])
  }
  const [first, second] = draft.daysBuckets
  const buckets = [`0–${first} days`, `${first + 1}–${second} days`, `Over ${second} days`]
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved)

  async function run(kind: 'preview' | 'save') {
    if (!draft) return
    setBusy(true)
    setErrors([])
    try {
      if (kind === 'preview') {
        setPreview((await api.previewPriorityConfig(draft)).changes)
      } else {
        const res = await api.savePriorityConfig(draft)
        setSettings(res)
        setDraft(res.config)
        setPreview(null)
        notify(`Priority settings saved · ${res.changes.length} open suggestion${res.changes.length === 1 ? '' : 's'} re-decided`)
      }
    } catch (e) {
      setErrors(e instanceof api.ApiError && e.details ? e.details : [e instanceof Error ? e.message : 'Request failed'])
    } finally {
      setBusy(false)
    }
  }

  const sites = preview ? new Set(preview.map((c) => c.agreementId)).size : 0
  const cost = draft.costOfDelay
  const day = trialDay(cost)
  const setCost = (key: keyof CostOfDelay, v: number) => edit({ ...draft, costOfDelay: { ...cost, [key]: v } })
  const wasCost = (key: keyof CostOfDelay, fmt: (v: number) => string) =>
    cost[key] !== saved.costOfDelay[key] ? fmt(saved.costOfDelay[key]) : undefined
  const pctOf = (v: number) => `${Math.round(v * 1000) / 10}%`

  return (
    <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-12">
      <div className="flex flex-col gap-6 min-[1081px]:col-span-8">
        <section aria-labelledby="levels-h" className="tile">
          <div className="tile-head"><h3 id="levels-h" className="text-[19px]">Priority levels</h3></div>
          <p className="tile-sub">
            Money at risk per week = trial days lost while this site waits × the value of a trial day (below). A site enrolling 10% of
            the study’s patients per month delays the trial about 0.7 days for each week it waits. A site without usable enrollment
            figures is “unknown” and treated as standard.
          </p>
          <div className="flex flex-col gap-2.5">
            <Field label="High" hint="at or above, per week" prefix="$" suffix="/ week" min={1} max={10_000_000} step={1000} slider={[0, 300_000]}
              value={draft.thresholds.high} was={draft.thresholds.high !== saved.thresholds.high ? usd(saved.thresholds.high) : undefined}
              onChange={(v) => edit({ ...draft, thresholds: { ...draft.thresholds, high: v } })} />
            <Field label="Elevated" hint="at or above, per week" prefix="$" suffix="/ week" min={1} max={10_000_000} step={1000} slider={[0, 300_000]}
              value={draft.thresholds.elevated} was={draft.thresholds.elevated !== saved.thresholds.elevated ? usd(saved.thresholds.elevated) : undefined}
              onChange={(v) => edit({ ...draft, thresholds: { ...draft.thresholds, elevated: v } })} />
            <Field label="Planned enrollment" hint="patients across the study" suffix="patients" min={1} max={100_000} slider={[1, 2_000]}
              value={draft.plannedEnrollment} was={draft.plannedEnrollment !== saved.plannedEnrollment ? String(saved.plannedEnrollment) : undefined}
              onChange={(v) => edit({ ...draft, plannedEnrollment: v })} />
            <Field label="Study enrollment period" hint={settings.costSources.trialEnrollmentMonths} suffix="months" min={1} max={240} slider={[6, 60]}
              value={cost.trialEnrollmentMonths} was={wasCost('trialEnrollmentMonths', (v) => `${v} months`)}
              onChange={(v) => setCost('trialEnrollmentMonths', v)} />
          </div>
        </section>

        <section aria-labelledby="cod-h" className="tile">
          <div className="tile-head"><h3 id="cod-h" className="text-[19px]">Value of a trial day</h3></div>
          <p className="tile-sub">
            A later finish with a fixed patent expiry loses a day of sales at launch. That day is weighted by the chance of approval and
            discounted back to today; the trial’s own running cost is added undiscounted. With these inputs a trial day is
            worth <b className="text-ink tabular">≈{usd(day.total)}</b> ({usd(day.sales)} in sales + {usd(cost.trialCostPerDayUsd)} in trial costs).
          </p>
          <div className="flex flex-col gap-2.5">
            <Field label="Sales per day" hint={settings.costSources.salesPerDayUsd} prefix="$" suffix="/ day" min={0} max={100_000_000} step={10_000} slider={[0, 3_000_000]}
              value={cost.salesPerDayUsd} was={wasCost('salesPerDayUsd', usd)} onChange={(v) => setCost('salesPerDayUsd', v)} />
            <Field label="Chance of approval" hint={settings.costSources.probabilityOfApproval} suffix="%" min={0.1} max={100} step={0.1} slider={[1, 100]}
              value={Math.round(cost.probabilityOfApproval * 1000) / 10} was={wasCost('probabilityOfApproval', pctOf)}
              onChange={(v) => setCost('probabilityOfApproval', v / 100)} />
            <Field label="Years to launch" hint={settings.costSources.yearsToLaunch} suffix="years" min={0} max={30} step={0.1} slider={[0, 15]}
              value={cost.yearsToLaunch} was={wasCost('yearsToLaunch', (v) => `${v} years`)} onChange={(v) => setCost('yearsToLaunch', v)} />
            <Field label="Discount rate" hint={settings.costSources.discountRate} suffix="% a year" min={0} max={100} step={0.5} slider={[0, 25]}
              value={Math.round(cost.discountRate * 1000) / 10} was={wasCost('discountRate', pctOf)}
              onChange={(v) => setCost('discountRate', v / 100)} />
            <Field label="Trial cost per day" hint={settings.costSources.trialCostPerDayUsd} prefix="$" suffix="/ day" min={0} max={10_000_000} step={500} slider={[0, 100_000]}
              value={cost.trialCostPerDayUsd} was={wasCost('trialCostPerDayUsd', usd)} onChange={(v) => setCost('trialCostPerDayUsd', v)} />
          </div>
        </section>

        <section aria-labelledby="days-h" className="tile">
          <div className="tile-head"><h3 id="days-h" className="text-[19px]">Days waiting</h3></div>
          <p className="tile-sub">Days since the site’s current redline arrived. Each level gets more leeway the longer a site waits.</p>
          <div className="flex flex-col gap-2.5">
            <Field label="First bucket ends" suffix="days" min={1} max={3650} slider={[1, Math.max(second - 1, 1)]}
              value={first} was={first !== saved.daysBuckets[0] ? `${saved.daysBuckets[0]} days` : undefined}
              onChange={(v) => edit({ ...draft, daysBuckets: [v, second] })} />
            <Field label="Second bucket ends" suffix="days" min={2} max={3650} slider={[first + 1, 365]}
              value={second} was={second !== saved.daysBuckets[1] ? `${saved.daysBuckets[1]} days` : undefined}
              onChange={(v) => edit({ ...draft, daysBuckets: [first, v] })} />
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs font-semibold text-muted" aria-hidden>
            {buckets.map((b) => <span key={b} className="rounded-[4px] border border-line bg-subtle px-2 py-1">{b}</span>)}
          </div>
        </section>

        <section aria-labelledby="matrix-h" className="tile">
          <div className="tile-head"><h3 id="matrix-h" className="text-[19px]">Leniency</h3></div>
          <p className="tile-sub">
            Share of the gap between the playbook standard and the escalate floor that Siteline may accept without asking. Each cell is capped at {pct(settings.maxShare)}; the bars fill toward that cap.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-3"><span className="sr-only">Priority</span></th>
                  {buckets.map((b) => <th key={b} scope="col" className="px-2 py-2 font-semibold">{b}</th>)}
                </tr>
              </thead>
              <tbody>
                {LEVELS.map((level) => (
                  <tr key={level}>
                    <th scope="row" className="py-2 pr-3"><span className={`pill ${priorityPill[level]}`}>{priorityShort[level]}</span></th>
                    {draft.leniency[level].map((share, i) => (
                      <td key={i} className="px-2 py-2">
                        <div className="rounded-[6px] border border-line bg-subtle p-2">
                          <div className="flex items-center gap-1 rounded-[6px] bg-surface px-2 border border-line-strong focus-within:outline-2 focus-within:outline-accent">
                            <input
                              type="number"
                              min={0}
                              max={Math.round(settings.maxShare * 100)}
                              step={5}
                              value={Math.round(share * 100)}
                              aria-label={`${priorityShort[level]}, ${buckets[i]}: share of the gap in percent`}
                              className="min-h-10 w-full min-w-0 bg-transparent font-semibold tabular outline-none"
                              onChange={(e) => {
                                const row = [...draft.leniency[level]] as [number, number, number]
                                row[i] = Number(e.target.value) / 100
                                edit({ ...draft, leniency: { ...draft.leniency, [level]: row } })
                              }}
                            />
                            <span className="text-muted">%</span>
                          </div>
                          <div className="mt-2 h-1 overflow-hidden rounded-[2px] bg-line" aria-hidden>
                            <span className="block h-full bg-ink-2" style={{ width: `${Math.min(100, (share / settings.maxShare) * 100)}%` }} />
                          </div>
                        </div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="bands-h" className="tile">
          <div className="tile-head"><h3 id="bands-h" className="text-[19px]">What a high-priority site gets</h3></div>
          <p className="tile-sub">Accept lines under the high row above. Standards and escalate floors are fixed in the rules engine and never move.</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="text-muted">
                <tr className="border-b-2 border-line">
                  <th scope="col" className="py-2 pr-3 font-semibold">Band</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Standard</th>
                  {buckets.map((b) => <th key={b} scope="col" className="px-3 py-2 font-semibold">{b}</th>)}
                  <th scope="col" className="px-3 py-2 font-semibold">Escalate floor</th>
                </tr>
              </thead>
              <tbody>
                {settings.bands.map((b) => (
                  <tr key={b.field} className="border-b border-line last:border-0">
                    <th scope="row" className="py-3 pr-3 font-semibold">{b.label} <code className="chip ml-1 text-xs">{b.ruleId}</code></th>
                    <td className="px-3 py-3 tabular">{b.standard}{b.unit}</td>
                    {draft.leniency.high.map((share, i) => <td key={i} className="px-3 py-3 font-semibold tabular">{bandLimit(b, share)}{b.unit}</td>)}
                    <td className="px-3 py-3 font-semibold text-high tabular">{b.floor}{b.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <aside className="flex h-fit flex-col gap-6 min-[1081px]:sticky min-[1081px]:top-6 min-[1081px]:col-span-4">
        <section aria-labelledby="apply-h" className="tile">
          <div className="tile-head">
            <h3 id="apply-h" className="text-[19px]">
              {preview ? `${preview.length} open decision${preview.length === 1 ? '' : 's'} across ${sites} site${sites === 1 ? '' : 's'} would change` : 'Apply changes'}
            </h3>
          </div>
          <p className="tile-sub">Only unconfirmed suggestions change; confirmed ones stay as they are.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-secondary btn-sm" disabled={busy || !dirty} onClick={() => void run('preview')}><Eye aria-hidden className="size-4" /> Preview</button>
            <button type="button" className="btn btn-primary btn-sm" disabled={busy || !dirty} onClick={() => void run('save')}>
              {busy ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Save aria-hidden className="size-4" />} Save changes
            </button>
            <button type="button" className="btn btn-secondary btn-sm" disabled={busy || !dirty} onClick={() => edit(saved)}><RotateCcw aria-hidden className="size-4" /> Discard</button>
          </div>
          {errors.length > 0 && (
            <ul role="alert" className="alert mt-3">
              {errors.map((e) => <li key={e}>{e}</li>)}
            </ul>
          )}
          {preview && (
            <ul className="mt-4 flex flex-col gap-2 text-sm" aria-live="polite">
              {preview.length === 0 && <li className="rounded-[6px] border border-line bg-surface px-3 py-2 text-muted">No open decision changes.</li>}
              {preview.map((c) => (
                <li key={c.changeId} className="rounded-[6px] border border-line bg-surface px-3 py-2">
                  <b>{c.agreementId.replace(/^site-/, 'Site ')} · {c.section}</b>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
                    <code className="chip">{c.from.ruleId}</code> → <code className="chip">{c.to.ruleId}</code>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="log-h" className="tile">
          <div className="tile-head"><h3 id="log-h" className="text-[19px]">Change log</h3></div>
          <p className="tile-sub">Who changed what, newest first.</p>
          {settings.log.length === 0 ? (
            <p className="text-sm text-muted">No changes yet. Defaults come from backend/data/priority_config.json.</p>
          ) : (
            <ul className="flex flex-col gap-3 text-sm">
              {settings.log.map((entry) => (
                <li key={entry.at} className="flex gap-3">
                  <span aria-hidden className="rank size-9 shrink-0 text-xs">{entry.by.split(' ').map((p) => p[0]).join('').slice(0, 3)}</span>
                  <div className="min-w-0">
                    <p className="font-semibold">
                      High {usd(entry.old.thresholds.high)} → {usd(entry.new.thresholds.high)} · elevated {usd(entry.old.thresholds.elevated)} → {usd(entry.new.thresholds.elevated)}
                      {JSON.stringify(entry.old.leniency) !== JSON.stringify(entry.new.leniency) && ' · leniency matrix changed'}
                      {JSON.stringify(entry.old.daysBuckets) !== JSON.stringify(entry.new.daysBuckets) && ` · buckets ${entry.old.daysBuckets.join('/')} → ${entry.new.daysBuckets.join('/')}`}
                      {JSON.stringify(entry.old.costOfDelay) !== JSON.stringify(entry.new.costOfDelay) && ' · cost-of-delay inputs changed'}
                    </p>
                    <p className="text-xs text-muted">{entry.by} · {new Date(entry.at).toLocaleString()}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </div>
  )
}
