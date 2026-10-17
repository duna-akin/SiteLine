import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, AtSign, Copy, RotateCw, Upload } from 'lucide-react'

import { EscalationQueue } from '@/components/siteline/EscalationQueue'
import { InboundFeed } from '@/components/siteline/InboundFeed'
import { openSites } from '@/components/siteline/priority-style'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { useHashScroll } from '@/hooks/useHashScroll'
import { byArrival } from '@/lib/sites'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'

const TARGET_DAYS = 90

function median(values: number[]) {
  const s = [...values].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="tile py-5">
      <p className="eyebrow">{label}</p>
      <p className="mt-1 font-display text-4xl font-semibold tabular">{value}</p>
      {note && <p className="mt-1 text-sm text-muted">{note}</p>}
    </div>
  )
}

export function InboundPage() {
  const { notify, inboundAddress } = useDemo()
  const { agreements, emails, queue, imap, error, refresh } = useDesk()
  const navigate = useNavigate()
  const [over, setOver] = useState(false)
  const ready = Boolean(agreements && emails && queue)
  useHashScroll(ready)

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(inboundAddress)
      notify('Inbound address copied')
    } catch {
      notify(inboundAddress)
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) navigate('/upload', { state: { file } })
  }

  if (error && !ready) {
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

  const open = openSites(agreements ?? [])
  const waiting = (emails ?? []).filter((e) => !e.triaged).length

  return (
    <div className="wrap pb-12">
      <section className="hello pt-7 pb-6">
        <h1>Inbound</h1>
        <p>
          Redlines that sites emailed or you uploaded, and every escalation still out with an approver.
          {ready && (waiting === 0 ? ' Nothing is waiting for triage.' : ` ${waiting} ${waiting === 1 ? 'redline is' : 'redlines are'} waiting for triage.`)}
        </p>
      </section>

      <div className="grid gap-[18px] sm:grid-cols-3">
        <Kpi label="Open agreements" value={ready ? String(open.length) : '–'} />
        <Kpi label="Median days open" value={ready && open.length ? `${median(open.map((a) => a.daysOpen))} d` : '–'} note={`Target ${TARGET_DAYS} d`} />
        <Kpi label="Escalations waiting" value={ready ? String(queue!.length) : '–'} note="Out with approvers, unanswered" />
      </div>

      <div className="mt-[18px] grid grid-cols-1 gap-[18px] min-[1081px]:grid-cols-12">
        <section className="tile min-[1081px]:col-span-7" aria-labelledby="mail-h">
          <div className="tile-head">
            <h2 id="mail-h">Mailbox</h2>
            <span className="pill p-peach">Agent inbox</span>
          </div>
          <p className="tile-sub">
            Sites email a redline straight to the agent and it lands here.{' '}
            {imap ? 'The mailbox is checked every 30 s.' : 'No mailbox is connected (IMAP), so these are the seeded emails.'}
          </p>
          <div className="mb-4 flex items-center gap-2 rounded-[20px] bg-bg py-1.5 pr-1.5 pl-4">
            <AtSign aria-hidden className="size-4 shrink-0 text-tangerine-ink" />
            <code className="min-w-0 flex-1 truncate text-sm font-bold">{inboundAddress}</code>
            <button type="button" className="btn btn-soft size-11 p-0" onClick={copyAddress} aria-label="Copy inbound address">
              <Copy aria-hidden className="size-4" />
            </button>
          </div>
          {!ready ? (
            <div className="flex flex-col gap-2.5" aria-hidden>
              {[0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-[20px] bg-bg" />)}
            </div>
          ) : emails!.length === 0 ? (
            <p className="rounded-[20px] bg-bg px-4 py-5 text-muted">No redlines have come in yet.</p>
          ) : (
            <InboundFeed emails={byArrival(emails!)} />
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <SponsorChip sponsor="Daytona" label="Parsed in Daytona" />
            <SponsorChip sponsor="Anthropic Claude" label="Extracted by OpenAI" />
          </div>
        </section>

        <section className="tile bg-peach min-[1081px]:col-span-5" aria-labelledby="up-h">
          <div className="tile-head"><h2 id="up-h">Upload a redline</h2></div>
          <p className="tile-sub">A Word file with tracked changes and comments. Siteline hands back one decision per change.</p>
          <Link
            to="/upload"
            className="drop min-h-40 flex-col justify-center bg-card text-center"
            data-over={over}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }}
            onDragLeave={() => setOver(false)}
            onDrop={onDrop}
          >
            <Upload aria-hidden className="size-8 text-tangerine-ink" />
            <span className="font-extrabold text-ink">Drop a .docx here, or choose a file</span>
            <span>The Site 07 demo file is one click away on the upload page.</span>
          </Link>
          <Link to="/upload" className="btn btn-orange mt-4 w-full">Go to upload <ArrowRight aria-hidden className="size-4" /></Link>
        </section>

        <section id="queue" className="tile scroll-mt-6 bg-butter min-[1081px]:col-span-12" aria-labelledby="queue-h">
          <div className="tile-head">
            <h2 id="queue-h">Escalation queue <span className="badge tabular">{queue?.length ?? 0}</span></h2>
          </div>
          <p className="tile-sub">Most money at risk first, then oldest question. An approver’s bare “1”, “2” or “3” still answers the oldest text they got.</p>
          {!ready ? (
            <div className="h-24 animate-pulse rounded-[20px] bg-card" aria-hidden />
          ) : queue!.length === 0 ? (
            <p className="rounded-[20px] bg-card px-4 py-5 text-muted">Nothing is waiting on an approver.</p>
          ) : (
            <EscalationQueue items={queue!} />
          )}
        </section>
      </div>
    </div>
  )
}
