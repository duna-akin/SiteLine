import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, AtSign, Copy, FileUp, LoaderCircle, Mail, Paperclip } from 'lucide-react'

import * as api from '@/api'
import { useServerEvent } from '@/api/events'
import { outcomeVar } from '@/components/siteline/outcome-style'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { AnimatedList } from '@/components/ui/animated-list'
import { BlurFade } from '@/components/ui/blur-fade'
import { MagicCard } from '@/components/ui/magic-card'
import { NumberTicker } from '@/components/ui/number-ticker'
import { formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import { outcomeLabel, outcomeOrder } from '@/mocks/playbook'
import { statusLabel } from '@/mocks/portfolio'
import { useDemo } from '@/state/demo'
import type { Agreement, AgreementStatus, InboundEmail } from '@/types'

const statusTone: Record<AgreementStatus, string> = {
  triaging: 'var(--blue-l)',
  awaiting_approval: 'var(--red)',
  ready_to_export: 'var(--butter)',
  sent_to_site: 'var(--magenta)',
  executed: 'var(--mint)',
}

function median(values: number[]) {
  const s = [...values].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

function OutcomeMix({ mix }: { mix: Agreement['outcomeMix'] }) {
  const total = outcomeOrder.reduce((n, o) => n + mix[o], 0)
  if (total === 0) return <span className="text-xs text-muted">Not triaged yet</span>
  return (
    <div
      className="flex h-2 w-full overflow-hidden rounded-full bg-space"
      role="img"
      aria-label={outcomeOrder.map((o) => `${mix[o]} ${outcomeLabel[o]}`).join(', ')}
    >
      {outcomeOrder.map((o) => (
        <span key={o} style={{ width: `${(mix[o] / total) * 100}%`, background: outcomeVar[o] }} />
      ))}
    </div>
  )
}

export function InboxPage() {
  const { notify, inboundAddress, integrations } = useDemo()
  const navigate = useNavigate()
  const [agreements, setAgreements] = useState<Agreement[] | null>(null)
  const [emails, setEmails] = useState<InboundEmail[]>([])
  const [triaging, setTriaging] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    api.listAgreements().then(setAgreements, (e: Error) => setError(e.message))
    api.getInboundEmails().then((r) => setEmails(r.emails), (e: Error) => setError(e.message))
  }, [])
  useEffect(refresh, [refresh])
  useServerEvent('triage.done', refresh)
  useServerEvent('agreement.updated', refresh)
  useServerEvent('email.received', refresh)
  useServerEvent('demo.reset', refresh)

  async function triageEmail(e: InboundEmail) {
    setTriaging(e.id)
    try {
      const { agreement } = await api.triageEmail(e.id)
      notify(`Triaged ${e.attachment}: ${agreement.changes} changes`)
      refresh()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Triage failed')
    } finally {
      setTriaging(null)
    }
  }

  const open = agreements?.filter((a) => a.status !== 'executed') ?? []
  const waiting = open.reduce((n, a) => n + (a.status === 'awaiting_approval' ? a.outcomeMix.escalate : 0), 0)

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(inboundAddress)
      notify('Inbound address copied')
    } catch {
      notify(inboundAddress)
    }
  }

  return (
    <div>
      <section className="relative overflow-hidden">
        <div className="nova top-6 right-[-120px] size-[300px] sm:right-[4%] sm:size-[380px]" aria-hidden />
        <div className="wrap relative py-12 sm:py-20">
          <BlurFade>
            <p className="eyebrow">Agreement inbox · NSO-417</p>
            <h1 className="mt-4 max-w-4xl text-5xl leading-[1.02] sm:text-7xl">
              Every site redline, <span className="text-yellow">triaged</span> before your coffee cools.
            </h1>
            <p className="mt-5 max-w-2xl text-lg text-muted">
              Siteline checks a site’s redlined clinical trial agreement against your playbook, texts approvers only what needs them, and drafts the counter-proposal.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/upload" className="btn btn-primary"><FileUp aria-hidden className="size-4" /> Upload a redline</Link>
              <Link to="/portfolio" className="btn btn-ghost">See portfolio radar <ArrowRight aria-hidden className="size-4" /></Link>
            </div>
          </BlurFade>
        </div>
      </section>

      <div className="wrap">
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { label: 'Open agreements', value: open.length, suffix: '' },
            { label: 'Median days open', value: open.length ? median(open.map((a) => a.daysOpen)) : 0, suffix: ' d', note: 'Target 90 d' },
            { label: 'Escalations waiting', value: waiting, suffix: '' },
          ].map((k, i) => (
            <BlurFade key={k.label} delay={0.05 * i} className="h-full">
              <MagicCard className="h-full rounded-[20px]" gradientFrom="var(--magenta)" gradientTo="var(--yellow)" gradientColor="var(--space-2)">
                <div className="p-5">
                  <p className="eyebrow">{k.label}</p>
                  <p className="mt-2 text-4xl font-bold tabular">
                    {k.value === 0 ? '0' : <NumberTicker value={k.value} className="text-text" />}
                    <span className="text-2xl text-muted">{k.suffix}</span>
                  </p>
                  {k.note && <p className="mt-1 text-sm text-muted">{k.note}</p>}
                </div>
              </MagicCard>
            </BlurFade>
          ))}
        </div>

        <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          <section aria-labelledby="agreements-heading">
            <h2 id="agreements-heading" className="text-3xl">Agreements</h2>
            {error && <p role="alert" className="mt-3 rounded-2xl border border-red/50 bg-red/10 px-4 py-3 text-sm">{error}</p>}
            <ul className="mt-4 flex flex-col gap-3">
              {!agreements &&
                Array.from({ length: 4 }, (_, i) => <li key={i} className="panel h-24 animate-pulse" aria-hidden />)}
              {agreements?.map((a) => {
                const isLive = Boolean(a.fileName)
                const body = (
                  <>
                    <div className="flex min-w-0 flex-1 flex-col gap-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-serif text-xl text-yellow">Site {a.siteNumber}</span>
                        <span className="truncate font-bold">{a.siteName}</span>
                        {a.source === 'email' && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs text-muted">
                            <Mail aria-hidden className="size-3" /> via email
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted">{a.city} · received {formatDate(a.receivedAt)} · {a.changes} changes</p>
                      <div className="mt-1 max-w-sm"><OutcomeMix mix={a.outcomeMix} /></div>
                    </div>
                    <div className="flex shrink-0 items-center gap-4 sm:flex-col sm:items-end sm:gap-1">
                      <span
                        className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-bold"
                        style={{ borderColor: statusTone[a.status] }}
                      >
                        <span aria-hidden className="size-1.5 rounded-full" style={{ background: statusTone[a.status] }} />
                        {statusLabel[a.status]}
                      </span>
                      <span className={cn('tabular text-sm', a.daysOpen > 90 ? 'font-bold text-butter' : 'text-muted')}>
                        {a.daysOpen} days open
                      </span>
                    </div>
                  </>
                )
                return (
                  <li key={a.id}>
                    {isLive ? (
                      <Link
                        to={`/review/${a.id}`}
                        className="panel flex flex-col gap-3 p-4 transition-colors duration-200 hover:border-yellow sm:flex-row sm:items-center sm:p-5"
                        aria-label={`Open Site ${a.siteNumber}, ${a.siteName}`}
                      >
                        {body}
                        <ArrowRight aria-hidden className="hidden size-5 text-yellow sm:block" />
                      </Link>
                    ) : (
                      <div className="panel flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:p-5">{body}</div>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>

          <section aria-labelledby="email-heading" className="panel h-fit p-5">
            <div className="flex items-center justify-between gap-2">
              <h2 id="email-heading" className="text-2xl">Inbound email</h2>
              <span className="rounded-full bg-magenta/15 px-2.5 py-0.5 text-xs font-bold text-text">Agent mailbox</span>
            </div>
            <p className="mt-2 text-sm text-muted">
              Sites can email a redline straight to the agent. It lands here and joins the inbox.
              {integrations && (integrations.imap ? ' The mailbox is checked every 30 s.' : ' No mailbox is connected (IMAP), so this shows the seeded emails.')}
            </p>
            <div className="mt-4 flex items-center gap-2 rounded-2xl border border-line bg-space px-3 py-2">
              <AtSign aria-hidden className="size-4 text-butter" />
              <code className="flex-1 truncate text-sm">{inboundAddress}</code>
              <button type="button" className="btn btn-ghost size-11 p-0" onClick={copyAddress} aria-label="Copy inbound address">
                <Copy className="size-4" />
              </button>
            </div>
            <AnimatedList delay={900} className="mt-4 items-stretch gap-3">
              {emails.map((e) => (
                <div key={e.id} className="w-full rounded-2xl border border-line bg-space-2 p-3">
                  <div className="flex items-center justify-between gap-2 text-xs text-muted">
                    <span className="truncate">{e.from}</span>
                    <span className="shrink-0">{formatDate(e.receivedAt)}</span>
                  </div>
                  <p className="mt-1 font-bold">{e.subject}</p>
                  <p className="text-sm text-muted">{e.siteName}</p>
                  <p className="mt-2 flex items-center gap-1.5 text-xs"><Paperclip aria-hidden className="size-3.5" /> {e.attachment}</p>
                  <div className="mt-3 flex items-center justify-between">
                    <span className={cn('text-xs font-bold', e.triaged ? 'text-mint' : 'text-butter')}>
                      {e.triaged ? 'Triaged' : 'Queued for triage'}
                    </span>
                    {!e.triaged && (
                      <button type="button" className="btn btn-ghost min-h-9 px-3 py-1 text-xs" disabled={triaging !== null} onClick={() => void triageEmail(e)}>
                        {triaging === e.id && <LoaderCircle aria-hidden className="size-3.5 animate-spin" />} Triage now
                      </button>
                    )}
                    {e.triaged && e.agreementId && (
                      <button type="button" className="btn btn-ghost min-h-9 px-3 py-1 text-xs" onClick={() => navigate(`/review/${e.agreementId}`)}>
                        Open <ArrowRight aria-hidden className="size-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </AnimatedList>
            <div className="mt-4 flex flex-wrap gap-2">
              <SponsorChip sponsor="Daytona" label="Parsed in Daytona" />
              <SponsorChip sponsor="Anthropic Claude" label="Extracted by Claude" />
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
