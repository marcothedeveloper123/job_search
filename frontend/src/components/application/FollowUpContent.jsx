/**
 * Follow-up timeline showing milestones and backup contacts.
 */
export function FollowUpContent({ followUp }) {
  if (!followUp) {
    return <div style={{ color: 'var(--text-muted)' }}>Not yet planned</div>
  }

  const { milestones = [], backup_contacts = [] } = followUp

  const hasContent = milestones.length > 0 || backup_contacts.length > 0

  if (!hasContent) {
    return <div style={{ color: 'var(--text-muted)' }}>No follow-up data</div>
  }

  return (
    <div className="space-y-4 text-sm">
      {milestones.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
            Milestones
          </h4>
          <ul className="list-disc list-inside space-y-1" style={{ color: 'var(--text-secondary)' }}>
            {milestones.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {backup_contacts.length > 0 && (
        <div>
          <h4 className="font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
            Backup Contacts
          </h4>
          <ul className="list-disc list-inside space-y-1" style={{ color: 'var(--text-secondary)' }}>
            {backup_contacts.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
