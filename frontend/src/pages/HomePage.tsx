import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, RotateCw, Upload } from 'lucide-react'

import { DataMap } from '@/components/siteline/DataMap'
import { EscalationQueue } from '@/components/siteline/EscalationQueue'
import { InboundFeed } from '@/components/siteline/InboundFeed'
import { byMoney, isOnUs, openSites, usd } from '@/components/siteline/priority-style'
import { SiteBars, SiteBarsLegend } from '@/components/siteline/SiteBars'
import { TextBubble } from '@/components/siteline/TextBubble'
import { formatClock } from '@/lib/format'
import { byArrival, hasPriorityLine } from '@/lib/sites'
import { SPONSOR, approvers } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'
import type { EscalationQueueItem } from '@/types'

const QUEUE_SHOWN = 3
const RANKED_SHOWN = 6
const FEED_SHOWN = 3

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

const today = () => new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })

function DeskHeader() {
  const { agreements, emails, queue } = useDesk()
  const waiting = (emails ?? []).filter((e) => !e.triaged).length
  const onUs = (agreements ?? []).filter((a) => isOnUs(a.status))
  const atRisk = onUs.reduce((n, a) => n + (a.priority?.moneyAtRiskPerWeek ?? 0), 0)
  const out = (queue ?? []).filter((q) => q.decision.approval.state === 'sent' || q.decision.approval.state === 'calling').length
  const news = waiting === 0 ? 'No new redlines are waiting.' : waiting === 1 ? 'One new redline is waiting.' : `${waiting} new redlines are waiting.`
  return (
    <section className="hello pt-9">
      <div className="grid items-end gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <span className="eyebrow">Protocol {SPONSOR.protocol} · {today()}</span>
          <h1>Central Contract Intelligence</h1>
          <p>
            {news}{' '}
            {atRisk > 0 ? (
              <>Sites waiting on us put about <span className="mark tabular">{usd(atRisk)} a week</span> at risk</>
            ) : (
              <>No site waiting on us has priority figures yet</>
            )}
            , and {out === 0 ? 'no escalations are' : `${plural(out, 'escalation')} ${out === 1 ? 'is' : 'are'}`} out with approvers.
          </p>
        </div>
        <img
          src="/images/lab-beakers.jpg"
          alt=""
          width={960}
          height={640}
          className="hidden h-[150px] w-full rounded-[6px] border border-line object-cover object-[50%_60%] grayscale lg:block"
        />
      </div>
      <dl className="stats">
        <div><dt>New redlines</dt><dd>{waiting}</dd></div>
        <div><dt>At risk per week</dt><dd>{atRisk > 0 ? usd(atRisk) : '—'}</dd></div>
        <div><dt>Escalations with approvers</dt><dd>{out}</dd></div>
        <div><dt>Open sites</dt><dd>{openSites(agreements ?? []).length}</dd></div>
      </dl>
    </section>
  )
}

function QueueTile({ queue }: { queue: EscalationQueueItem[] }) {
  const rest = queue.slice(QUEUE_SHOWN)
  const restSites = [...new Set(rest.map((q) => q.siteNumber))]
  return (
    <section className="tile min-[1081px]:col-span-7" aria-labelledby="q-h">
      <div className="tile-head">
        <h2 id="q-h">Escalation queue <span className="badge tabular">{queue.length}</span></h2>
      </div>
      <p className="tile-sub">Most money at risk first, then oldest question.</p>
      {queue.length === 0 ? (
        <p className="empty">Nothing is waiting on an approver.</p>
      ) : (
        <EscalationQueue items={queue.slice(0, QUEUE_SHOWN)} />
      )}
      {rest.length > 0 && (
        <div className="q-more">
          <span>{plural(rest.length, 'more')} for {restSites.map((n) => `Site ${n}`).join(', ')}</span>
          <Link to="/inbound#queue" className="btn btn-secondary btn-sm">See all <ArrowRight aria-hidden className="size-4" /></Link>
        </div>
      )}
    </section>
  )
}

function PhoneTile({ queue }: { queue: EscalationQueueItem[] }) {
  const top = queue.find((q) => q.decision.approval.state !== 'none' && q.decision.approval.text)
  const a = top?.decision.approval
  const text = a && a.state !== 'none' ? a.text ?? '' : ''
  const title = top ? approvers[top.decision.owner].title : null
  return (
    <section className="tile min-[1081px]:col-span-5" aria-labelledby="ph-h">
      <div className="tile-head"><h2 id="ph-h">{title ? `What the ${title.toLowerCase()} sees` : 'What approvers see'}</h2></div>
      <p className="tile-sub">{hasPriorityLine(text) ? 'Each escalation text carries one priority line.' : 'The text sent for the top escalation.'}</p>
      {a && a.state !== 'none' ? (
        <>
          <div className="phone" role="img" aria-label={`Text message to the ${title?.toLowerCase()}: ${text.replace(/\n+/g, ' ')}`}>
            <div className="phone-top"><span><b>Siteline</b> · Text message</span><span className="tabular">{formatClock(a.sentAt)}</span></div>
            <TextBubble text={text} />
          </div>
          <p className="phone-note">A bare “1”, “2” or “3” still answers the oldest question that approver was sent.</p>
        </>
      ) : (
        <p className="empty">No approver has an open text right now.</p>
      )}
    </section>
  )
}

function SitesTile() {
  const { agreements } = useDesk()
  const sites = openSites(agreements ?? [])
  const ranked = byMoney(sites).slice(0, RANKED_SHOWN)
  return (
    <section className="tile min-[1081px]:col-span-7" aria-labelledby="r-h">
      <div className="tile-head">
        <h2 id="r-h">Open sites <span className="badge tabular">{sites.length}</span></h2>
        <Link to="/sites" className="link">See all sites <ArrowRight aria-hidden className="size-4" /></Link>
      </div>
      {ranked.length ? (
        <>
          <SiteBars sites={ranked} label="Open sites by money at risk" />
          <SiteBarsLegend />
        </>
      ) : (
        <p className="empty">No open sites yet. Triage a redline to add one.</p>
      )}
    </section>
  )
}

function InboundTile() {
  const { emails } = useDesk()
  const { inboundAddress } = useDemo()
  const navigate = useNavigate()
  const [over, setOver] = useState(false)

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) navigate('/upload', { state: { file } })
  }

  return (
    <section className="tile min-[1081px]:col-span-5" aria-labelledby="inb-h">
      <div className="tile-head">
        <h2 id="inb-h">Inbound</h2>
        <Link to="/inbound" className="link">All <ArrowRight aria-hidden className="size-4" /></Link>
      </div>
      {(emails ?? []).length === 0 ? (
        <p className="empty">No redlines have come in yet.</p>
      ) : (
        <InboundFeed emails={byArrival(emails ?? []).slice(0, FEED_SHOWN)} />
      )}
      <Link
        to="/upload"
        className="drop"
        data-over={over}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <Upload aria-hidden className="size-5 shrink-0" />
        <span>Drop a .docx here, or have sites email <code>{inboundAddress}</code></span>
      </Link>
    </section>
  )
}

function DataTile() {
  const { integrations } = useDemo()
  const { agreements } = useDesk()
  return (
    <section className="tile min-[1081px]:col-span-12" aria-labelledby="data-h">
      <div className="tile-head">
        <h2 id="data-h">Where your data lives</h2>
        <Link to="/data" className="link">Data and evals <ArrowRight aria-hidden className="size-4" /></Link>
      </div>
      <DataMap integrations={integrations} agreements={agreements ?? []} />
    </section>
  )
}

export function HomePage() {
  const { agreements, queue, error, refresh } = useDesk()

  if (error && !agreements) {
    return (
      <div className="wrap py-16">
        <div className="tile mx-auto max-w-xl text-center" role="alert">
          <h1 className="text-[26px]">Can’t reach the Siteline API</h1>
          <p className="mt-3 text-muted">{error}</p>
          <button type="button" className="btn btn-primary mt-5" onClick={refresh}><RotateCw aria-hidden className="size-4" /> Try again</button>
        </div>
      </div>
    )
  }

  if (!agreements || !queue) {
    return (
      <div className="wrap pb-12" role="status" aria-label="Loading your desk">
        <div className="hello pt-9 pb-6"><div className="h-12 w-2/3 animate-pulse rounded-[6px] bg-sunken" /></div>
        <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-12">
          {['min-[1081px]:col-span-7', 'min-[1081px]:col-span-5', 'min-[1081px]:col-span-7', 'min-[1081px]:col-span-5', 'min-[1081px]:col-span-12'].map((span, i) => (
            <div key={i} className={`tile h-64 animate-pulse ${span}`} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="wrap">
      <DeskHeader />
      {error && (
        <p role="alert" className="alert mb-6">
          Couldn’t refresh: {error} <button type="button" className="link ml-2 min-h-0" onClick={refresh}>Try again</button>
        </p>
      )}
      <div className="grid grid-cols-1 gap-6 pb-4 min-[1081px]:grid-cols-12">
        <QueueTile queue={queue} />
        <PhoneTile queue={queue} />
        <SitesTile />
        <InboundTile />
        <DataTile />
      </div>
    </div>
  )
}
