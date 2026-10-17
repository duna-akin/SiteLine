export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/** "9:14 AM" */
export function formatClock(at: number | string): string {
  return new Date(at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

/** "just now", "12 min ago", "3 h ago", "6 days ago" */
export function timeAgo(at: number | string, now = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - new Date(at).getTime()) / 60_000))
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  return days === 1 ? 'yesterday' : `${days} days ago`
}

/** "9:42 AM" today, "Yesterday", or "Oct 5" for an inbound email's arrival. */
export function arrivedLabel(iso: string, now = new Date()): string {
  const d = new Date(iso)
  const days = Math.floor((new Date(now.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86_400_000)
  if (days <= 0) return formatClock(iso)
  if (days === 1) return 'Yesterday'
  return formatDate(iso)
}
