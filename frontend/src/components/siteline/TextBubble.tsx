import { PRIORITY_LINE } from '@/lib/sites'
import { cn } from '@/lib/utils'

/** An incoming text as the approver's phone shows it, with the priority line picked out. */
export function TextBubble({ text, className }: { text: string; className?: string }) {
  const lines = text.split('\n')
  const k = lines.findIndex((l) => PRIORITY_LINE.test(l))
  return (
    <div className={cn('bubble', className)}>
      {k >= 0 ? (
        <>
          {lines.slice(0, k).join('\n')}
          <span className="new">{lines[k]}</span>
          {lines.slice(k + 1).join('\n')}
        </>
      ) : (
        text
      )}
    </div>
  )
}
