/**
 * Verdict badge showing pursue/maybe/skip status.
 */
export function VerdictBadge({ verdict, size = 'sm' }) {
  const v = verdict?.toLowerCase()
  let bg = 'var(--bg-secondary)'
  let color = size === 'sm' ? 'var(--text-muted)' : 'var(--text-primary)'

  if (v === 'pursue') {
    bg = 'var(--pursue-bg)'
    color = 'var(--pursue-text)'
  } else if (v === 'maybe') {
    bg = 'var(--maybe-bg)'
    color = 'var(--maybe-text)'
  } else if (v === 'skip') {
    bg = 'var(--skip-bg)'
    color = 'var(--skip-text)'
  }

  const sizeClasses = size === 'sm'
    ? 'px-2 py-0.5 rounded-full text-xs font-medium'
    : 'px-3 py-1 rounded text-sm font-semibold uppercase'

  return (
    <span
      className={sizeClasses}
      style={{ backgroundColor: bg, color }}
    >
      {verdict}
    </span>
  )
}
