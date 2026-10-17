import type { Change } from '@/types'

const isWord = (ch: string | undefined) => ch !== undefined && /\S/.test(ch)

/** Split a replacement into shared prefix, removed middle, added middle and shared suffix, snapped to word edges. */
function wordDiff(a: string, b: string) {
  let p = 0
  while (p < a.length && p < b.length && a[p] === b[p]) p++
  // Don't cut a word in half: back off to the previous space when both sides continue mid-word.
  if (p < a.length && p < b.length) while (p > 0 && isWord(a[p - 1]) && isWord(a[p])) p--
  let s = 0
  while (s < a.length - p && s < b.length - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++
  while (s > 0 && isWord(a[a.length - s]) && isWord(a[a.length - s - 1]) && a.length - s > p) s--
  return {
    prefix: a.slice(0, p),
    removed: a.slice(p, a.length - s),
    added: b.slice(p, b.length - s),
    suffix: a.slice(a.length - s),
  }
}

const del = 'rounded bg-rose px-0.5 text-rose-ink line-through decoration-rose-ink decoration-2'
const ins = 'rounded bg-mint px-0.5 text-mint-ink underline decoration-mint-ink decoration-2 underline-offset-4'

export function RedlineDiff({ change }: { change: Change }) {
  if (change.kind === 'insertion' && !change.original) {
    return (
      <p className="leading-relaxed">
        <ins className={ins}>{change.revised}</ins>
      </p>
    )
  }
  if (change.kind === 'deletion') {
    return (
      <p className="leading-relaxed">
        <del className={del}>{change.original}</del>
      </p>
    )
  }
  if (change.kind === 'comment') {
    return <p className="leading-relaxed text-ink">{change.original}</p>
  }
  const d = wordDiff(change.original, change.revised)
  return (
    <p className="leading-relaxed text-ink">
      {d.prefix}
      {d.removed && <del className={del}>{d.removed}</del>}
      {d.added && <ins className={d.removed ? `${ins} ml-1` : ins}>{d.added}</ins>}
      {d.suffix}
    </p>
  )
}
