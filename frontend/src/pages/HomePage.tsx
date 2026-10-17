import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, RotateCw, Upload } from 'lucide-react'

import { DataMap } from '@/components/siteline/DataMap'
import { EscalationQueue } from '@/components/siteline/EscalationQueue'
import { InboundFeed } from '@/components/siteline/InboundFeed'
import { byMoney, isOnUs, openSites, usd, usdK } from '@/components/siteline/priority-style'
import { RadarLegend, SiteRadar } from '@/components/siteline/SiteRadar'
import { TextBubble } from '@/components/siteline/TextBubble'
import { formatClock } from '@/lib/format'
import { agreementPath, byArrival, hasPriorityLine, notTriaged } from '@/lib/sites'
import { approvers } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'
import type { EscalationQueueItem } from '@/types'

const QUEUE_SHOWN = 3
const RANKED_SHOWN = 6
const FEED_SHOWN = 3

function greeting(hour = new Date().getHours()) {
  return hour < 12 ? 'Good morning!' : hour < 18 ? 'Good afternoon!' : 'Good evening!'
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

function Greeting() {
  const { agreements, emails, queue } = useDesk()
  const waiting = (emails ?? []).filter((e) => !e.triaged).length
  const onUs = (agreements ?? []).filter((a) => isOnUs(a.status))
  const atRisk = onUs.reduce((n, a) => n + (a.priority?.moneyAtRiskPerWeek ?? 0), 0)
  const out = (queue ?? []).filter((q) => q.decision.approval.state === 'sent' || q.decision.approval.state === 'calling').length
  const news = waiting === 0 ? 'No new redlines are waiting.' : waiting === 1 ? 'One new redline is waiting.' : `${waiting} new redlines are waiting.`
  return (
    <section className="hello pt-7 pb-6">
      <h1>{greeting()} Here’s your desk.</h1>
      <p>
        {news}{' '}
        {atRisk > 0 ? (
          <>Sites waiting on us put about <span className="mark tabular">{usd(atRisk)} a week</span> at risk</>
        ) : (
          <>No site waiting on us has priority figures yet</>
        )}
        , and {out === 0 ? 'no escalations are' : `${plural(out, 'escalation')} ${out === 1 ? 'is' : 'are'}`} out with approvers.
      </p>
    </section>
  )
}

function QueueTile({ queue }: { queue: EscalationQueueItem[] }) {
  const rest = queue.slice(QUEUE_SHOWN)
  const restSites = [...new Set(rest.map((q) => q.siteNumber))]
  return (
    <section className="tile bg-butter min-[1081px]:col-span-7" aria-labelledby="q-h">
      <div className="tile-head">
        <h2 id="q-h">Escalation queue <span className="badge tabular">{queue.length}</span></h2>
      </div>
      <p className="tile-sub">Most money at risk first, then oldest question.</p>
      {queue.length === 0 ? (
        <p className="rounded-[20px] bg-card px-4 py-5 text-muted">Nothing is waiting on an approver.</p>
      ) : (
        <EscalationQueue items={queue.slice(0, QUEUE_SHOWN)} />
      )}
      {rest.length > 0 && (
        <div className="q-more">
          <span>{plural(rest.length, 'more')} for {restSites.map((n) => `Site ${n}`).join(', ')}</span>
          <Link to="/inbound#queue" className="btn btn-soft btn-sm">See all <ArrowRight aria-hidden className="size-4" /></Link>
        </div>
      )}
    </section>
  )
}

function PhoneTile({ queue }: { queue: EscalationQueueItem[] }) {
  const top = queue.find((q) => q.decision.approval.state !== 'none' && q.decision.approval.text)
  const a = top?.decision.approval
  const text = a && a.state !== 'none' ? a.text ?? '' : ''
  const name = top ? approvers[top.decision.owner].name : null
  const first = name?.split(' ')[0]
  return (
    <section className="tile bg-peach min-[1081px]:col-span-5" aria-labelledby="ph-h">
      <div className="tile-head"><h2 id="ph-h">{first ? `What ${first} sees` : 'What approvers see'}</h2></div>
      <p className="tile-sub">{hasPriorityLine(text) ? 'Each escalation text carries one priority line.' : 'The text sent for the top escalation.'}</p>
      {a && a.state !== 'none' ? (
        <>
          <div className="phone" role="img" aria-label={`Text message to ${name}: ${text.replace(/\n+/g, ' ')}`}>
            <div className="phone-top"><b>Siteline</b> · Text message · {formatClock(a.sentAt)}</div>
            <TextBubble text={text} />
          </div>
          <p className="phone-note">A bare “1”, “2” or “3” still answers the oldest question {first} was sent.</p>
        </>
      ) : (
        <p className="rounded-[20px] bg-card px-4 py-5 text-muted">No approver has an open text right now.</p>
      )}
    </section>
  )
}

function RadarTile() {
  const { agreements } = useDesk()
  const sites = openSites(agreements ?? [])
  const ranked = byMoney(sites).slice(0, RANKED_SHOWN)
  return (
    <section className="tile min-[1081px]:col-span-7" aria-labelledby="r-h">
      <div className="tile-head">
        <h2 id="r-h">Open sites <span className="badge tabular">{sites.length}</span></h2>
        <Link to="/sites" className="link">See all sites <ArrowRight aria-hidden className="size-4" /></Link>
      </div>
      <div className="grid items-center gap-5 sm:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <SiteRadar sites={sites} />
        <ol className="rank-list" aria-label="Open sites by money at risk">
          {ranked.map((a) => (
            <li key={a.id}>
              <Link to={agreementPath(a)}>
                <span className="n">{a.siteNumber}</span>
                <span className="nm">{a.siteName} · {a.daysOpen} d</span>
                {notTriaged(a) ? (
                  <span className="pill p-sky">Not triaged</span>
                ) : a.priority?.moneyAtRiskPerWeek != null ? (
                  <b className="tabular">{usdK(a.priority.moneyAtRiskPerWeek)}/wk</b>
                ) : (
                  <span className="pill p-cream">Unknown</span>
                )}
              </Link>
            </li>
          ))}
        </ol>
      </div>
      <RadarLegend />
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
        <p className="rounded-[20px] bg-bg px-4 py-5 text-muted">No redlines have come in yet.</p>
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
    <section className="tile bg-sky min-[1081px]:col-span-12" aria-labelledby="data-h">
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
          <h1 className="text-3xl">Can’t reach the Siteline API</h1>
          <p className="mt-3 text-muted">{error}</p>
          <button type="button" className="btn btn-orange mt-5" onClick={refresh}><RotateCw aria-hidden className="size-4" /> Try again</button>
        </div>
      </div>
    )
  }

  if (!agreements || !queue) {
    return (
      <div className="wrap pb-12" role="status" aria-label="Loading your desk">
        <div className="hello pt-7 pb-6"><div className="h-12 w-2/3 animate-pulse rounded-2xl bg-card" /></div>
        <div className="grid grid-cols-1 gap-[18px] min-[1081px]:grid-cols-12">
          {['min-[1081px]:col-span-7', 'min-[1081px]:col-span-5', 'min-[1081px]:col-span-7', 'min-[1081px]:col-span-5', 'min-[1081px]:col-span-12'].map((span, i) => (
            <div key={i} className={`tile h-64 animate-pulse ${span}`} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="wrap">
      <Greeting />
      {error && (
        <p role="alert" className="mb-4 rounded-[20px] bg-rose px-4 py-3 text-sm font-bold text-rose-ink">
          Couldn’t refresh: {error} <button type="button" className="link ml-2 min-h-0" onClick={refresh}>Try again</button>
        </p>
      )}
      <div className="grid grid-cols-1 gap-[18px] pb-12 min-[1081px]:grid-cols-12">
        <QueueTile queue={queue} />
        <PhoneTile queue={queue} />
        <RadarTile />
        <InboundTile />
        <DataTile />
      </div>
    </div>
  )
}
