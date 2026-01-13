/**
 * Insights section - basic and enhanced fit analysis.
 */
import { MarkdownContent } from '../MarkdownContent'

export function InsightsContent({ insights }) {
  const entries = Object.entries(insights || {}).filter(([, v]) => v)
  if (entries.length === 0) return <div style={{ color: 'var(--text-muted)' }}>No insights yet</div>

  return (
    <div className="space-y-3 text-sm">
      {entries.map(([key, value]) => (
        <div key={key}>
          <h4 className="font-medium capitalize mb-1" style={{ color: 'var(--text-primary)' }}>
            {key.replace(/_/g, ' ')}
          </h4>
          <MarkdownContent content={String(value)} className="deep-dive-md" />
        </div>
      ))}
    </div>
  )
}

export function EnhancedInsightsContent({ insights }) {
  const { alignment = [], concerns = [], missing_requirements = [] } = insights || {}

  if (alignment.length === 0 && concerns.length === 0 && missing_requirements.length === 0) {
    return <div style={{ color: 'var(--text-muted)' }}>No analysis yet</div>
  }

  return (
    <div className="space-y-4 text-sm">
      {alignment.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--pursue-text)' }}>
            <span>●</span> Strong Matches ({alignment.length})
          </h4>
          <ul className="space-y-2">
            {alignment.map((item, i) => (
              <li key={i} className="pl-4" style={{ color: 'var(--text-secondary)' }}>
                <div className="font-medium">
                  <MarkdownContent content={item.requirement} className="deep-dive-md" inline />
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Evidence: <MarkdownContent content={item.evidence} className="deep-dive-md" inline />
                </div>
                {item.strength !== 'strong' && (
                  <span
                    className="text-xs px-1 rounded"
                    style={{
                      backgroundColor: item.strength === 'partial' ? 'var(--maybe-bg)' : 'var(--bg-secondary)',
                      color: item.strength === 'partial' ? 'var(--maybe-text)' : 'var(--text-muted)',
                    }}
                  >
                    {item.strength}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {concerns.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--maybe-text)' }}>
            <span>◐</span> Concerns ({concerns.length})
          </h4>
          <ul className="space-y-2">
            {concerns.map((item, i) => (
              <li key={i} className="pl-4" style={{ color: 'var(--text-secondary)' }}>
                <div className="font-medium">
                  <MarkdownContent content={item.requirement} className="deep-dive-md" inline />
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Gap: <MarkdownContent content={item.gap} className="deep-dive-md" inline />
                </div>
                {item.mitigation && (
                  <div className="text-xs italic" style={{ color: 'var(--text-muted)' }}>
                    Mitigation: <MarkdownContent content={item.mitigation} className="deep-dive-md" inline />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {missing_requirements.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--skip-text)' }}>
            <span>○</span> Missing ({missing_requirements.length})
          </h4>
          <ul className="space-y-2">
            {missing_requirements.map((item, i) => (
              <li key={i} className="pl-4" style={{ color: 'var(--text-secondary)' }}>
                <div className="font-medium">
                  <MarkdownContent content={item.requirement} className="deep-dive-md" inline />
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  <MarkdownContent content={item.assessment} className="deep-dive-md" inline />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
