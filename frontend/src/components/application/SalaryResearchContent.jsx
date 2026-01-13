/**
 * Salary research showing range, sources, and anchoring strategy.
 */
export function SalaryResearchContent({ research }) {
  if (!research) {
    return <div style={{ color: 'var(--text-muted)' }}>Not yet researched</div>
  }

  const { range, glassdoor, levels_fyi, blind, anchoring_strategy } = research

  const hasContent = range || glassdoor || levels_fyi || blind || anchoring_strategy

  if (!hasContent) {
    return <div style={{ color: 'var(--text-muted)' }}>No salary data</div>
  }

  return (
    <div className="space-y-3 text-sm">
      {range && (
        <div>
          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>Range: </span>
          <span style={{ color: 'var(--pursue-text)' }}>{range}</span>
        </div>
      )}

      <div className="space-y-1">
        {glassdoor && (
          <div style={{ color: 'var(--text-secondary)' }}>
            <span className="font-medium">Glassdoor:</span> {glassdoor}
          </div>
        )}
        {levels_fyi && (
          <div style={{ color: 'var(--text-secondary)' }}>
            <span className="font-medium">Levels.fyi:</span> {levels_fyi}
          </div>
        )}
        {blind && (
          <div style={{ color: 'var(--text-secondary)' }}>
            <span className="font-medium">Blind:</span> {blind}
          </div>
        )}
      </div>

      {anchoring_strategy && (
        <div className="pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>Strategy: </span>
          <span style={{ color: 'var(--text-secondary)' }}>{anchoring_strategy}</span>
        </div>
      )}
    </div>
  )
}
