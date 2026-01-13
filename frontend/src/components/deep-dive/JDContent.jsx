/**
 * Job description content with scrape status indicator.
 */
export function JDContent({ jd }) {
  const statusIcon = {
    complete: '✓',
    partial: '⚠',
    failed: '✗',
    manual: '📋',
  }[jd.scrape_status] || '?'

  const statusColor = {
    complete: 'var(--pursue-text)',
    partial: 'var(--maybe-text)',
    failed: 'var(--skip-text)',
    manual: 'var(--text-muted)',
  }[jd.scrape_status] || 'var(--text-muted)'

  return (
    <div className="text-sm">
      <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--text-muted)' }}>
        <span style={{ color: statusColor }}>{statusIcon}</span>
        <span>
          {jd.scrape_status === 'complete' && 'Scraped'}
          {jd.scrape_status === 'partial' && 'Partial scrape'}
          {jd.scrape_status === 'failed' && 'Scrape failed'}
          {jd.scrape_status === 'manual' && 'Manual entry'}
        </span>
        {jd.scraped_at && (
          <span className="text-xs">
            • {new Date(jd.scraped_at).toLocaleDateString()}
          </span>
        )}
      </div>
      <pre
        className="whitespace-pre-wrap font-sans text-sm max-h-64 overflow-y-auto p-3 rounded"
        style={{
          color: 'var(--text-secondary)',
          backgroundColor: 'var(--bg-tertiary)',
        }}
      >
        {jd.raw_text}
      </pre>
    </div>
  )
}
