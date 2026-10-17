import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import * as api from '@/api'
import { RECONNECTED, useServerEvent } from '@/api/events'
import type { Agreement, EscalationQueueItem, InboundEmail } from '@/types'

/** What the desk pages share: every agreement, the inbound mailbox and the escalation queue. */
interface Desk {
  agreements: Agreement[] | null
  emails: InboundEmail[] | null
  queue: EscalationQueueItem[] | null
  imap: boolean
  /** Set when the last load failed; the data above keeps its previous value. */
  error: string | null
  refresh: () => void
}

const DeskContext = createContext<Desk | null>(null)

const REFRESH_DEBOUNCE_MS = 300

export function DeskProvider({ children }: { children: ReactNode }) {
  const [agreements, setAgreements] = useState<Agreement[] | null>(null)
  const [emails, setEmails] = useState<InboundEmail[] | null>(null)
  const [queue, setQueue] = useState<EscalationQueueItem[] | null>(null)
  const [imap, setImap] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(async () => {
    try {
      const [a, inbound, q] = await Promise.all([api.listAgreements(), api.getInboundEmails(), api.getEscalationQueue()])
      setAgreements(a)
      setEmails(inbound.emails)
      setImap(inbound.imap)
      setQueue(q)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Can’t reach the Siteline API.')
    }
  }, [])

  // Server events arrive in bursts (one decision.updated per change), so coalesce them.
  const refresh = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => void load(), REFRESH_DEBOUNCE_MS)
  }, [load])

  useEffect(() => {
    void load()
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [load])

  useServerEvent('triage.done', refresh)
  useServerEvent('agreement.updated', refresh)
  useServerEvent('decision.updated', refresh)
  useServerEvent('email.received', refresh)
  useServerEvent('email.updated', refresh)
  useServerEvent('demo.reset', refresh)
  useServerEvent(RECONNECTED, refresh) // events sent while the stream was down are gone

  const value = useMemo(() => ({ agreements, emails, queue, imap, error, refresh: () => void load() }), [agreements, emails, queue, imap, error, load])
  return <DeskContext.Provider value={value}>{children}</DeskContext.Provider>
}

export function useDesk() {
  const ctx = useContext(DeskContext)
  if (!ctx) throw new Error('useDesk must be used inside DeskProvider')
  return ctx
}
