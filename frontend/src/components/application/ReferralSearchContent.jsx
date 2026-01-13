/**
 * Referral search showing contacts and channel priority.
 */
export function ReferralSearchContent({ search }) {
  if (!search) {
    return <div style={{ color: 'var(--text-muted)' }}>Not yet researched</div>
  }

  const { contacts = [], channel_priority = [] } = search

  const hasContent = contacts.length > 0 || channel_priority.length > 0

  if (!hasContent) {
    return <div style={{ color: 'var(--text-muted)' }}>No referral data</div>
  }

  return (
    <div className="space-y-4 text-sm">
      {contacts.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
            Contacts
          </h4>
          <ul className="list-disc list-inside space-y-1" style={{ color: 'var(--text-secondary)' }}>
            {contacts.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {channel_priority.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
            Channel Priority
          </h4>
          <ol className="list-decimal list-inside space-y-1" style={{ color: 'var(--text-secondary)' }}>
            {channel_priority.map((ch, i) => (
              <li key={i}>{ch}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
