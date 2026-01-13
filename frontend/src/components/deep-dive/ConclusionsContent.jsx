/**
 * Conclusions section with fit score, concerns, and attractions.
 */
import { MarkdownContent } from '../MarkdownContent'

export function ConclusionsContent({ conclusions }) {
  const { fit_score, fit_explanation, concerns, attractions, dealbreaker_check } = conclusions || {}

  return (
    <div className="space-y-3 text-sm">
      {fit_score && (
        <div>
          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
            Fit Score:{' '}
          </span>
          <FitScoreBar score={fit_score} />
        </div>
      )}

      {fit_explanation && (
        <MarkdownContent content={fit_explanation} className="deep-dive-md" />
      )}

      {concerns?.length > 0 && (
        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Concerns:</h4>
          <ul className="list-disc list-inside" style={{ color: 'var(--text-secondary)' }}>
            {concerns.map((c, i) => (
              <li key={i}>
                <MarkdownContent content={c} className="deep-dive-md" inline />
              </li>
            ))}
          </ul>
        </div>
      )}

      {attractions?.length > 0 && (
        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Attractions:</h4>
          <ul className="list-disc list-inside" style={{ color: 'var(--text-secondary)' }}>
            {attractions.map((a, i) => (
              <li key={i}>
                <MarkdownContent content={a} className="deep-dive-md" inline />
              </li>
            ))}
          </ul>
        </div>
      )}

      {dealbreaker_check && (
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Dealbreaker Check:{' '}
          {!dealbreaker_check.matrix_coordination && '✓ No matrix coordination '}
          {!dealbreaker_check.leadership_disguised && '✓ Not disguised mgmt '}
          {!dealbreaker_check.advisory_role && '✓ Not advisory'}
        </div>
      )}
    </div>
  )
}

function FitScoreBar({ score }) {
  const filled = Math.min(Math.max(score || 0, 0), 5)
  return (
    <span>
      {'█'.repeat(filled)}
      {'░'.repeat(5 - filled)}
      {' '}
      {filled}/5
    </span>
  )
}
