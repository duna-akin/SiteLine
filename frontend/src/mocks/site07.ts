import type { ParseStepId } from '@/types'

// The Site 07 demo redline lives in the backend (backend/src/siteline/demo.py) as a real Word file.
export const DEMO_FILE_NAME = 'NSO-417_CTA_Site07_redline.docx'

export const stepLabels: Record<ParseStepId, string> = {
  upload: 'Upload received',
  sandbox: 'Fresh sandbox',
  parse: 'Tracked changes parsed',
  extract: 'Clause values extracted',
  verify: 'Quotes verified',
  rules: 'Rules engine',
  teardown: 'Sandbox deleted',
}
