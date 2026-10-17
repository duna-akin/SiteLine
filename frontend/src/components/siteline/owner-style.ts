import { Landmark, Lock, Scale, type LucideIcon } from 'lucide-react'

import type { Owner } from '@/types'

/** A role mark per approver, used where a person's photo or initials would otherwise go. */
export const ownerIcon: Record<Owner, LucideIcon> = {
  legal: Scale,
  finance: Landmark,
  privacy: Lock,
}
