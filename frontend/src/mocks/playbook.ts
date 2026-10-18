import type { Approver, ClauseType, Outcome, Owner } from '@/types'

// Fictional sponsor details written for the demo. Not real contract language.
export const SPONSOR = {
  name: 'Northstar Oncology',
  protocol: 'NSO-417',
  study: 'Phase II study of NSO-417 in relapsed solid tumors',
}

// Clause names for labels across the app; the playbook itself (positions, limits, rules) is served by
// the API from backend/data/playbook.json.
export const clauseLabel: Record<ClauseType, string> = {
  indemnification: 'Indemnification',
  subject_injury: 'Subject Injury',
  publication: 'Publication',
  confidentiality: 'Confidentiality',
  intellectual_property: 'Intellectual Property',
  data_privacy: 'Data Protection',
  payment_terms: 'Payment Terms',
  termination: 'Termination',
  governing_law: 'Governing Law',
}

export const outcomeLabel: Record<Outcome, string> = {
  accept: 'Accept',
  counter: 'Counter',
  escalate: 'Escalate',
  human_review: 'Human review',
}

export const outcomeOrder: Outcome[] = ['accept', 'counter', 'escalate', 'human_review']

export const ownerLabel: Record<Owner, string> = {
  legal: 'Legal',
  finance: 'Finance',
  privacy: 'Privacy',
}

export const approvers: Record<Owner, Approver> = {
  legal: { owner: 'legal', title: 'Legal approver', role: 'Contracts counsel' },
  finance: { owner: 'finance', title: 'Finance approver', role: 'Clinical finance' },
  privacy: { owner: 'privacy', title: 'Privacy approver', role: 'Privacy officer' },
}

export const replyMeaning: Record<1 | 2 | 3, string> = {
  1: 'Approve the site’s language',
  2: 'Counter with the playbook fallback',
  3: 'Reject and hold the standard',
}
