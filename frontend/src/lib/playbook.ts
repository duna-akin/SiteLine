import { useEffect, useState } from 'react'

import * as api from '@/api'
import type { ClauseType, Playbook, PlaybookLimit } from '@/types'

const PLACEHOLDER = /\{(\w+)\}/g

/** A limit's number as the server writes it (playbook._fmt): no exponent, up to 4 decimals. */
export const formatNumber = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/\.?0+$/, ''))

export const formatLimit = (l: PlaybookLimit) => `${formatNumber(l.value)}${l.unit}`

/** A playbook text with its {placeholders} filled from the position's limits (mirrors playbook.render). */
export function fill(text: string, limits: Record<string, PlaybookLimit>): string {
  return text.replace(PLACEHOLDER, (m, name: string) => (limits[name] ? formatLimit(limits[name]) : m))
}

/** Templates only, the shape the API accepts: drops the *Text keys the server renders. */
export function templatesOnly(pb: Playbook): Playbook {
  const strip = <T extends object>(o: T): T => Object.fromEntries(Object.entries(o).filter(([k]) => !k.endsWith('Text'))) as T
  return {
    name: pb.name,
    clauses: pb.clauses.map((c) => ({ ...c, positions: c.positions.map((p) => ({ ...strip(p), rules: p.rules.map(strip) })) })),
  }
}

export const positionAnchor = (clause: ClauseType, position: string) => `${clause}.${position}`

export interface RulePosition {
  clauseType: ClauseType
  positionId: string
  issue: string
}

let index: Promise<Record<string, RulePosition>> | null = null

/** Rule ID (or an old alias of it) → the playbook position that enforces it; fetched once. */
export function useRulePositions(): Record<string, RulePosition> {
  const [map, setMap] = useState<Record<string, RulePosition>>({})
  useEffect(() => {
    index ??= api.getPlaybook().then(({ playbook, aliases }) => {
      const out: Record<string, RulePosition> = {}
      for (const c of playbook.clauses)
        for (const p of c.positions)
          for (const r of p.rules) out[r.id] = { clauseType: c.clauseType, positionId: p.id, issue: p.issue }
      for (const [old, now] of Object.entries(aliases)) if (out[now]) out[old] = out[now]
      return out
    }).catch(() => {
      index = null
      return {}
    })
    let live = true
    void index.then((m) => live && setMap(m))
    return () => {
      live = false
    }
  }, [])
  return map
}

/** After a save the cached index is stale (owners and wording may have moved). */
export const forgetRulePositions = () => {
  index = null
}
