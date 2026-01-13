/**
 * Recommendations section with verdict, questions, and next steps.
 */
import { VerdictBadge } from '../VerdictBadge'
import { MarkdownContent } from '../MarkdownContent'

export function RecommendationsContent({ recommendations }) {
  const { verdict, questions_to_ask, next_steps } = recommendations || {}

  return (
    <div className="space-y-3 text-sm">
      {verdict && (
        <div>
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
            Verdict:{' '}
          </span>
          <VerdictBadge verdict={verdict} size="lg" />
        </div>
      )}

      {questions_to_ask?.length > 0 && (
        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Questions to Ask:</h4>
          <ol className="list-decimal list-inside" style={{ color: 'var(--text-secondary)' }}>
            {questions_to_ask.map((q, i) => (
              <li key={i}>
                <MarkdownContent content={q} className="deep-dive-md" inline />
              </li>
            ))}
          </ol>
        </div>
      )}

      {next_steps?.length > 0 && (
        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Next Steps:</h4>
          <ul className="list-disc list-inside" style={{ color: 'var(--text-secondary)' }}>
            {next_steps.map((s, i) => (
              <li key={i}>
                <MarkdownContent content={s} className="deep-dive-md" inline />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
