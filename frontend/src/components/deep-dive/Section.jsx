/**
 * Wrapper section with title for deep dive content blocks.
 */
export function Section({ title, children }) {
  return (
    <div
      className="mb-6 p-4 rounded-lg"
      style={{
        backgroundColor: 'var(--white)',
        border: '1px solid var(--border)',
      }}
    >
      <h2
        className="text-xs font-semibold tracking-wider mb-3"
        style={{ color: 'var(--text-muted)' }}
      >
        {title}
      </h2>
      {children}
    </div>
  )
}
