import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'

import * as api from '@/api'
import { RECONNECTED, useServerEvent } from '@/api/events'
import { approvers, replyMeaning } from '@/mocks/playbook'
import { NO_REPLY_MS } from '@/state/decision'
import type { Agreement, ApprovalChannel, ApprovalReply, Decision, Integrations, Outcome } from '@/types'

interface Toast {
  id: number
  text: string
}

interface DemoState {
  agreement: Agreement | null
  decisions: Decision[]
  loading: boolean
  loadError: string | null
  integrations: Integrations | null
  inboundAddress: string
  localParser: boolean
  useCache: boolean
  toasts: Toast[]
}

type Action =
  | { type: 'loading' }
  | { type: 'loaded'; agreement: Agreement; decisions: Decision[] }
  | { type: 'loadFailed'; error: string }
  | { type: 'decision'; decision: Decision }
  | { type: 'agreement'; agreement: Agreement }
  | { type: 'health'; integrations: Integrations; inboundAddress: string }
  | { type: 'setFlag'; flag: 'localParser' | 'useCache'; value: boolean }
  | { type: 'toast'; toast: Toast }
  | { type: 'dismissToast'; id: number }
  | { type: 'reset' }

const initialState: DemoState = {
  agreement: null,
  decisions: [],
  loading: false,
  loadError: null,
  integrations: null,
  inboundAddress: 'redlines@siteline.demo',
  localParser: false,
  useCache: true,
  toasts: [],
}

function reducer(state: DemoState, action: Action): DemoState {
  switch (action.type) {
    case 'loading':
      return { ...state, loading: true, loadError: null }
    case 'loaded':
      return {
        ...state,
        loading: false,
        agreement: action.agreement,
        decisions: action.decisions,
      }
    case 'loadFailed':
      return { ...state, loading: false, loadError: action.error, agreement: null, decisions: [] }
    case 'decision': {
      if (!state.decisions.some((d) => d.id === action.decision.id)) return state
      return { ...state, decisions: state.decisions.map((d) => (d.id === action.decision.id ? action.decision : d)) }
    }
    case 'agreement':
      return state.agreement?.id === action.agreement.id ? { ...state, agreement: { ...state.agreement, ...action.agreement } } : state
    case 'health':
      return { ...state, integrations: action.integrations, inboundAddress: action.inboundAddress }
    case 'setFlag':
      return { ...state, [action.flag]: action.value }
    case 'toast':
      return { ...state, toasts: [...state.toasts, action.toast] }
    case 'dismissToast':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) }
    case 'reset':
      return { ...initialState, integrations: state.integrations, inboundAddress: state.inboundAddress, localParser: state.localParser, useCache: state.useCache }
  }
}

interface DemoApi extends DemoState {
  noReplyMs: number
  loadAgreement: (id: string) => Promise<void>
  /** Decision actions resolve to the error message, or null when the change was saved. */
  override: (id: string, outcome: Outcome, reason: string) => Promise<string | null>
  clearOverride: (id: string) => Promise<string | null>
  confirm: (id: string) => Promise<string | null>
  unconfirm: (id: string) => Promise<string | null>
  confirmAll: (agreementId: string) => Promise<void>
  reply: (id: string, reply: ApprovalReply, channel: ApprovalChannel) => Promise<string | null>
  callNow: (id: string) => Promise<string | null>
  setFlag: (flag: 'localParser' | 'useCache', value: boolean) => void
  notify: (text: string) => void
  dismissToast: (id: number) => void
  reset: () => void
}

const DemoContext = createContext<DemoApi | null>(null)

const message = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong')

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const toastId = useRef(0)
  const agreementId = useRef<string | null>(null)

  const notify = useCallback((text: string) => {
    const id = ++toastId.current
    dispatch({ type: 'toast', toast: { id, text } })
    setTimeout(() => dispatch({ type: 'dismissToast', id }), 4500)
  }, [])

  useEffect(() => {
    api
      .getHealth()
      .then((h) => dispatch({ type: 'health', integrations: h.integrations, inboundAddress: h.inboundAddress }))
      .catch((e: unknown) => notify(message(e)))
  }, [notify])

  const loadAgreement = useCallback(async (id: string) => {
    agreementId.current = id
    dispatch({ type: 'loading' })
    try {
      const res = await api.getAgreement(id)
      if (agreementId.current === id) dispatch({ type: 'loaded', agreement: res.agreement, decisions: res.decisions })
    } catch (e) {
      if (agreementId.current === id) dispatch({ type: 'loadFailed', error: message(e) })
    }
  }, [])

  // Live updates: approver replies (Photon webhook or recorded on Review), calls, overrides.
  const decisionsRef = useRef(state.decisions)
  useEffect(() => {
    decisionsRef.current = state.decisions
  })
  useServerEvent<{ agreementId: string; decision: Decision }>('decision.updated', ({ agreementId: aid, decision }) => {
    if (aid !== agreementId.current) return
    const before = decisionsRef.current.find((d) => d.id === decision.id)
    if (decision.approval.state === 'answered' && before && before.approval.state !== 'answered') {
      const who = `The ${approvers[decision.owner].title.toLowerCase()}`
      notify(`${who} replied ${decision.approval.reply} by ${decision.approval.channel === 'voice' ? 'phone' : 'text'}: ${replyMeaning[decision.approval.reply]}`)
    }
    dispatch({ type: 'decision', decision })
  })
  useServerEvent<{ agreement: Agreement }>('agreement.updated', ({ agreement }) => {
    if (agreement) dispatch({ type: 'agreement', agreement })
  })
  // Replies and calls sent while the stream was down were missed: reload the open agreement quietly.
  useServerEvent(RECONNECTED, () => {
    const id = agreementId.current
    if (!id) return
    api.getAgreement(id).then(
      (res) => agreementId.current === id && dispatch({ type: 'loaded', agreement: res.agreement, decisions: res.decisions }),
      () => undefined,
    )
  })
  useServerEvent('demo.reset', () => {
    agreementId.current = null
    dispatch({ type: 'reset' })
  })

  const run = useCallback(
    async (fn: () => Promise<Decision>, done?: string): Promise<string | null> => {
      try {
        dispatch({ type: 'decision', decision: await fn() })
        if (done) notify(done)
        return null
      } catch (e) {
        notify(message(e))
        return message(e)
      }
    },
    [notify],
  )

  const value = useMemo<DemoApi>(
    () => ({
      ...state,
      noReplyMs: state.integrations ? state.integrations.noReplySeconds * 1000 : NO_REPLY_MS,
      loadAgreement,
      override: (id, outcome, reason) => run(() => api.overrideDecision(id, outcome, reason), 'Override saved with reason'),
      clearOverride: (id) => run(() => api.clearOverride(id), 'Override removed'),
      confirm: (id) => run(() => api.confirmDecision(id), 'Confirmed'),
      unconfirm: (id) => run(() => api.unconfirmDecision(id), 'Confirmation removed'),
      confirmAll: async (aid) => {
        try {
          const r = await api.confirmAllSuggested(aid)
          dispatch({ type: 'agreement', agreement: r.agreement })
          notify(`Confirmed ${r.confirmed} suggestion${r.confirmed === 1 ? '' : 's'}` +
            (r.needOwnConfirm ? `; ${r.needOwnConfirm} with a precedent need their own confirm` : ''))
        } catch (e) {
          notify(message(e))
        }
      },
      reply: (id, r, channel) => run(() => api.recordApprovalReply(id, r, channel)),
      callNow: (id) => run(() => api.placeApprovalCall(id)),
      setFlag: (flag, v) => dispatch({ type: 'setFlag', flag, value: v }),
      notify,
      dismissToast: (id) => dispatch({ type: 'dismissToast', id }),
      reset: () => {
        agreementId.current = null
        dispatch({ type: 'reset' })
      },
    }),
    [state, loadAgreement, run, notify],
  )

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>
}

export function useDemo() {
  const ctx = useContext(DemoContext)
  if (!ctx) throw new Error('useDemo must be used inside DemoProvider')
  return ctx
}
