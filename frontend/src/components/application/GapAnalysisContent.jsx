/**
 * Gap analysis showing matches, partial matches, gaps, and missing stories.
 */
export function GapAnalysisContent({ analysis }) {
  if (!analysis) {
    return <div style={{ color: 'var(--text-muted)' }}>Not yet generated</div>
  }

  const { matches = [], partial_matches = [], gaps = [], missing_stories = [] } = analysis

  const hasContent = matches.length > 0 || partial_matches.length > 0 || gaps.length > 0 || missing_stories.length > 0

  if (!hasContent) {
    return <div style={{ color: 'var(--text-muted)' }}>No analysis data</div>
  }

  return (
    <div className="space-y-4 text-sm">
      {matches.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--pursue-text)' }}>
            <span>●</span> Matches ({matches.length})
          </h4>
          <StringList items={matches} />
        </div>
      )}

      {partial_matches.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--maybe-text)' }}>
            <span>◐</span> Partial Matches ({partial_matches.length})
          </h4>
          <StringList items={partial_matches} />
        </div>
      )}

      {gaps.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--skip-text)' }}>
            <span>○</span> Gaps ({gaps.length})
          </h4>
          <StringList items={gaps} />
        </div>
      )}

      {missing_stories.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
            <span>?</span> Missing Stories ({missing_stories.length})
          </h4>
          <StringList items={missing_stories} />
        </div>
      )}
    </div>
  )
}

function StringList({ items }) {
  return (
    <ul className="space-y-1 pl-4">
      {items.map((item, i) => (
        <li key={i} style={{ color: 'var(--text-secondary)' }}>
          {item}
        </li>
      ))}
    </ul>
  )
}
