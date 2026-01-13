/**
 * Interview prep content with what to say, what not to say, questions, and red flags.
 */
export function InterviewPrepContent({ prep }) {
  if (!prep) {
    return <div style={{ color: 'var(--text-muted)' }}>Not yet generated</div>
  }

  const { what_to_say = [], what_not_to_say = [], questions_to_ask = [], red_flags = [] } = prep

  const hasContent = what_to_say.length > 0 || what_not_to_say.length > 0 || questions_to_ask.length > 0 || red_flags.length > 0

  if (!hasContent) {
    return <div style={{ color: 'var(--text-muted)' }}>No prep data</div>
  }

  return (
    <div className="space-y-4 text-sm">
      {what_to_say.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--pursue-text)' }}>
            What to Say
          </h4>
          <ul className="space-y-2">
            {what_to_say.map((item, i) => (
              <li key={i} className="pl-4" style={{ color: 'var(--text-secondary)' }}>
                <div className="font-medium">{item.question}</div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {item.answer}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {what_not_to_say.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--skip-text)' }}>
            What NOT to Say
          </h4>
          <ul className="list-disc list-inside space-y-1" style={{ color: 'var(--text-secondary)' }}>
            {what_not_to_say.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {questions_to_ask.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
            Questions to Ask
          </h4>
          <ol className="list-decimal list-inside space-y-1" style={{ color: 'var(--text-secondary)' }}>
            {questions_to_ask.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </div>
      )}

      {red_flags.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--maybe-text)' }}>
            Red Flags to Watch
          </h4>
          <ul className="list-disc list-inside space-y-1" style={{ color: 'var(--text-secondary)' }}>
            {red_flags.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
