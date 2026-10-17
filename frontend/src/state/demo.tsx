import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'

import * as api from '@/api'
import { approvers } from '@/mocks/playbook'
import { NO_REPLY_MS } from '@/state/decision'
import type { ApprovalChannel, ApprovalReply, Change, Decision, Outcome } from '@/types'

interface Toast {
  id: number
  text: string
}

interface DemoState {
  decisions: Decision[]
  triageSeconds: number | null
  localParser: boolean
  useCache: boolean
  activeEscalationId: string | null
  toasts: Toast[]
}

type Action =
  | { type: 'loaded'; changes: Change[]; triageSeconds: number }
  | { type: 'override'; id: string; outcome: Outcome; reason: string; at: number }
  | { type: 'clearOverride'; id: string }
  | { type: 'sent'; id: string; at: number }
  | { type: 'calling'; id: string; at: number }
  | { type: 'answered'; id: string; reply: ApprovalReply; channel: ApprovalChannel; at: number }
  | { type: 'setFlag'; flag: 'localParser' | 'useCache'; value: boolean }
  | { type: 'focusEscalation'; id: string | null }
  | { type: 'toast'; toast: Toast }
  | { type: 'dismissToast'; id: number }
  | { type: 'reset' }

const initialState: DemoState = {
  decisions: [],
  triageSeconds: null,
  localParser: false,
  useCache: true,
  activeEscalationId: null,
  toasts: [],
}

function update(state: DemoState, id: string, fn: (d: Decision) => Decision): DemoState {
  return { ...state, decisions: state.decisions.map((d) => (d.id === id ? fn(d) : d)) }
}

function reducer(state: DemoState, action: Action): DemoState {
  switch (action.type) {
    case 'loaded': {
      const decisions = action.changes.map<Decision>((c) => ({ ...c, approval: { state: 'none' } }))
      return {
        ...state,
        decisions,
        triageSeconds: action.triageSeconds,
        activeEscalationId: decisions.find((d) => d.outcome === 'escalate')?.id ?? null,
      }
    }
    case 'override':
      return update(state, action.id, (d) => ({
        ...d,
        override: { outcome: action.outcome, reason: action.reason, at: action.at },
      }))
    case 'clearOverride':
      return update(state, action.id, (d) => ({ ...d, override: undefined }))
    case 'sent':
      return update(state, action.id, (d) =>
        d.approval.state === 'none' ? { ...d, approval: { state: 'sent', sentAt: action.at } } : d,
      )
    case 'calling':
      return update(state, action.id, (d) =>
        d.approval.state === 'sent'
          ? { ...d, approval: { state: 'calling', sentAt: d.approval.sentAt, callStartedAt: action.at } }
          : d,
      )
    case 'answered':
      return update(state, action.id, (d) =>
        d.approval.state === 'sent' || d.approval.state === 'calling'
          ? {
              ...d,
              approval: {
                state: 'answered',
                sentAt: d.approval.sentAt,
                reply: action.reply,
                channel: action.channel,
                answeredAt: action.at,
              },
            }
          : d,
      )
    case 'setFlag':
      return { ...state, [action.flag]: action.value }
    case 'focusEscalation':
      return { ...state, activeEscalationId: action.id }
    case 'toast':
      return { ...state, toasts: [...state.toasts, action.toast] }
    case 'dismissToast':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) }
    case 'reset':
      return { ...initialState, localParser: state.localParser, useCache: state.useCache }
  }
}

interface DemoApi extends DemoState {
  loadSite07: (triageSeconds: number) => Promise<void>
  override: (id: string, outcome: Outcome, reason: string) => Promise<void>
  clearOverride: (id: string) => void
  reply: (id: string, reply: ApprovalReply, channel: ApprovalChannel) => Promise<void>
  callNow: (id: string) => Promise<void>
  setFlag: (flag: 'localParser' | 'useCache', value: boolean) => void
  focusEscalation: (id: string | null) => void
  notify: (text: string) => void
  dismissToast: (id: number) => void
  reset: () => void
}

const DemoContext = createContext<DemoApi | null>(null)

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const toastId = useRef(0)
  const callTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  const notify = useCallback((text: string) => {
    const id = ++toastId.current
    dispatch({ type: 'toast', toast: { id, text } })
    setTimeout(() => dispatch({ type: 'dismissToast', id }), 4000)
  }, [])

  const callNow = useCallback(async (id: string) => {
    const decision = state.decisions.find((d) => d.id === id)
    if (!decision || decision.approval.state !== 'sent') return
    clearTimeout(callTimers.current.get(id))
    callTimers.current.delete(id)
    const res = await api.placeApprovalCall(id, approvers[decision.owner].phone)
    dispatch({ type: 'calling', id, at: res.startedAt })
    dispatch({ type: 'focusEscalation', id })
  }, [state.decisions])

  // Arm a no-reply timer for each text that is waiting; the voice agent calls when it fires.
  const callNowRef = useRef(callNow)
  useEffect(() => {
    callNowRef.current = callNow
  }, [callNow])
  useEffect(() => {
    for (const d of state.decisions) {
      if (d.approval.state === 'sent' && !callTimers.current.has(d.id)) {
        const remaining = Math.max(0, d.approval.sentAt + NO_REPLY_MS - Date.now())
        callTimers.current.set(d.id, setTimeout(() => void callNowRef.current(d.id), remaining))
      }
    }
  }, [state.decisions])
  useEffect(() => {
    const timers = callTimers.current
    return () => timers.forEach((t) => clearTimeout(t))
  }, [])

  const loadSite07 = useCallback(async (triageSeconds: number) => {
    const changes = await api.getDecisions('site-07')
    dispatch({ type: 'loaded', changes, triageSeconds })
    // One Photon text per escalation, sent as soon as triage finishes.
    for (const c of changes.filter((c) => c.outcome === 'escalate')) {
      const res = await api.sendApprovalText(c.id, approvers[c.owner].phone)
      dispatch({ type: 'sent', id: c.id, at: res.sentAt })
    }
  }, [])

  const override = useCallback(async (id: string, outcome: Outcome, reason: string) => {
    const res = await api.overrideDecision(id, outcome, reason)
    dispatch({ type: 'override', id, outcome: res.outcome, reason: res.reason, at: res.at })
    notify('Override saved with reason')
  }, [notify])

  const reply = useCallback(async (id: string, value: ApprovalReply, channel: ApprovalChannel) => {
    clearTimeout(callTimers.current.get(id))
    const res = await api.recordApprovalReply(id, value, channel)
    dispatch({ type: 'answered', id, reply: res.reply, channel: res.channel, at: res.answeredAt })
  }, [])

  const value = useMemo<DemoApi>(
    () => ({
      ...state,
      loadSite07,
      override,
      clearOverride: (id) => dispatch({ type: 'clearOverride', id }),
      reply,
      callNow,
      setFlag: (flag, v) => dispatch({ type: 'setFlag', flag, value: v }),
      focusEscalation: (id) => dispatch({ type: 'focusEscalation', id }),
      notify,
      dismissToast: (id) => dispatch({ type: 'dismissToast', id }),
      reset: () => {
        callTimers.current.forEach((t) => clearTimeout(t))
        callTimers.current.clear()
        dispatch({ type: 'reset' })
      },
    }),
    [state, loadSite07, override, reply, callNow, notify],
  )

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>
}

export function useDemo() {
  const ctx = useContext(DemoContext)
  if (!ctx) throw new Error('useDemo must be used inside DemoProvider')
  return ctx
}
