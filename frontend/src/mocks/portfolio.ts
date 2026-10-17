import type { AgreementStatus } from '@/types'

export const statusLabel: Record<AgreementStatus, string> = {
  triaging: 'Triaging',
  awaiting_approval: 'Awaiting approval',
  ready_to_export: 'Ready to export',
  sent_to_site: 'Sent to site',
  executed: 'Executed',
}
