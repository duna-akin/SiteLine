import type { Approver, ClauseType, Outcome, Owner, PlaybookRule } from '@/types'

// Fictional sponsor playbook written for the demo. Not real contract language.
// The server copy (backend/data/playbook.json) is the source of truth; this one backs the editor's Reset.
export const SPONSOR = {
  name: 'Northstar Oncology',
  protocol: 'NSO-417',
  study: 'Phase II study of NSO-417 in relapsed solid tumors',
}

export const playbook: PlaybookRule[] = [
  {
    clauseType: 'indemnification',
    label: 'Indemnification',
    owner: 'legal',
    standard: 'Sponsor indemnifies site for claims arising from the study drug or protocol, except site negligence or protocol deviation.',
    fallback: 'Carve-out narrowed to gross negligence or willful misconduct.',
    escalateWhen: 'Site removes the negligence carve-out or adds mutual indemnity.',
  },
  {
    clauseType: 'subject_injury',
    label: 'Subject Injury',
    owner: 'finance',
    standard: 'Sponsor reimburses reasonable medical costs for study-related injury, net of subject insurance.',
    fallback: 'Sponsor pays first, without coordinating with subject insurance.',
    escalateWhen: 'Site adds lost wages, pain and suffering, or an uncapped reimbursement.',
  },
  {
    clauseType: 'publication',
    label: 'Publication',
    owner: 'legal',
    standard: 'Site may publish after multi-site publication or 18 months; sponsor reviews drafts for 60 days.',
    fallback: 'Review window up to 75 days, including a patent delay.',
    escalateWhen: 'Site shortens the review below 30 days or removes the patent delay.',
    openQuestion: 'Is the 75-day fallback reversed? Confirm with legal before the demo.',
  },
  {
    clauseType: 'confidentiality',
    label: 'Confidentiality',
    owner: 'legal',
    standard: 'Confidentiality survives 7 years after study close.',
    fallback: '5-year survival term.',
    escalateWhen: 'Term under 3 years, or trade secrets lose perpetual protection.',
  },
  {
    clauseType: 'intellectual_property',
    label: 'Intellectual Property',
    owner: 'legal',
    standard: 'Inventions arising from the protocol or study drug belong to sponsor.',
    fallback: 'Site keeps a non-exclusive research license to study inventions.',
    escalateWhen: 'Site claims ownership or joint ownership of protocol inventions.',
  },
  {
    clauseType: 'data_privacy',
    label: 'Data Protection',
    owner: 'privacy',
    standard: 'Coded data only; site handles HIPAA authorization; sponsor follows applicable privacy law.',
    fallback: 'Sponsor signs a limited data-use addendum.',
    escalateWhen: 'Site requires a business associate agreement or blocks secondary research use.',
  },
  {
    clauseType: 'payment_terms',
    label: 'Payment Terms',
    owner: 'finance',
    standard: 'Net 45 from invoice; quarterly reconciliation; start-up fee up to 10% of budget.',
    fallback: 'Net 30; a start-up fee above 10% is countered at 10%, refundable pro rata if no subject enrolls.',
    escalateWhen: 'Net under 30, or a non-refundable start-up fee above 20% of budget.',
  },
  {
    clauseType: 'termination',
    label: 'Termination',
    owner: 'legal',
    standard: 'Either party may terminate on 30 days’ notice; sponsor pays for completed work.',
    fallback: '60 days’ notice for the site.',
    escalateWhen: 'Site adds termination for convenience without paying non-cancellable costs.',
  },
  {
    clauseType: 'governing_law',
    label: 'Governing Law',
    owner: 'legal',
    standard: 'Law of the sponsor’s home state; venue in its courts.',
    fallback: 'Silent on venue, or the site’s state for public institutions.',
    escalateWhen: 'Mandatory arbitration abroad, or a sovereign immunity waiver demand.',
  },
]

export const clauseLabel: Record<ClauseType, string> = Object.fromEntries(
  playbook.map((r) => [r.clauseType, r.label]),
) as Record<ClauseType, string>

export const outcomeLabel: Record<Outcome, string> = {
  accept: 'Accept',
  fallback: 'Fallback',
  escalate: 'Escalate',
  human_review: 'Human review',
  novel: 'Novel',
}

export const outcomeOrder: Outcome[] = ['accept', 'fallback', 'escalate', 'human_review', 'novel']

export const ownerLabel: Record<Owner, string> = {
  legal: 'Legal',
  finance: 'Finance',
  privacy: 'Privacy',
}

export const approvers: Record<Owner, Approver> = {
  legal: { owner: 'legal', name: 'Tuna Akin', role: 'Contracts counsel', phone: '+1 (555) 010-4417' },
  finance: { owner: 'finance', name: 'Brian Soon', role: 'Clinical finance', phone: '+1 (555) 010-2290' },
  privacy: { owner: 'privacy', name: 'Michael Boneta', role: 'Privacy officer', phone: '+1 (555) 010-7731' },
}

export const replyMeaning: Record<1 | 2 | 3, string> = {
  1: 'Approve the site’s language',
  2: 'Counter with the playbook fallback',
  3: 'Reject and hold the standard',
}
