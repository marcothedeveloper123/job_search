/**
 * Left panel list of application preps with status indicators.
 */
export function ApplicationList({ applications, selectedId, onSelect, showArchived, onToggleArchived, onRestore, onArchive }) {
  if (applications.length === 0) {
    return (
      <div className="p-6" style={{ color: 'var(--text-muted)' }}>
        No application preps yet.
        <br />
        <span className="text-sm">
          Select a job with a completed deep dive to prepare an application.
        </span>
      </div>
    )
  }

  return (
    <div>
      <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
        <span className="font-medium" style={{ color: 'var(--text-muted)' }}>
          Applications ({applications.length})
        </span>
        <label className="flex items-center gap-1 cursor-pointer text-xs">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={onToggleArchived}
            className="w-3 h-3"
          />
          <span style={{ color: 'var(--text-muted)' }}>Archived</span>
        </label>
      </div>
      {applications.map((app) => {
        const isComplete = app.status === 'complete'
        const isError = app.status === 'error'
        const isSelected = selectedId === app.application_id
        const isArchived = app.archived

        return (
          <div
            key={app.application_id}
            onClick={() => onSelect(app.application_id)}
            className={`list-row px-4 py-3 cursor-pointer ${isArchived ? 'archived-row' : ''}`}
            style={{
              backgroundColor: isSelected ? 'var(--bg-secondary)' : 'transparent',
              borderBottom: '1px solid var(--border)',
            }}
            onMouseEnter={(e) => {
              if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isSelected ? 'var(--bg-secondary)' : 'transparent'
            }}
          >
            <div className="flex items-start gap-2 min-w-0">
              <span className="shrink-0" style={{ color: isComplete ? 'var(--pursue-text)' : isError ? 'var(--skip-text)' : 'var(--text-muted)' }}>
                {isComplete ? '●' : isError ? '✕' : '○'}
              </span>
              <div className="flex-1 min-w-0">
                <div
                  className="font-medium break-words"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {app.company}
                </div>
                <div
                  className="text-sm break-words"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {app.job_title}
                </div>
                <div className="flex items-center gap-2 mt-1 text-xs">
                  {isArchived && <span className="archived-badge">Archived</span>}
                  <StatusBadge status={app.status} />
                  {isArchived && (
                    <button
                      className="restore-btn"
                      onClick={(e) => { e.stopPropagation(); onRestore(app.application_id) }}
                    >
                      Restore
                    </button>
                  )}
                  {!isArchived && (
                    <button
                      className="archive-btn ml-auto"
                      onClick={(e) => { e.stopPropagation(); onArchive(app.application_id) }}
                    >
                      Archive
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function StatusBadge({ status }) {
  let bg = 'var(--bg-secondary)'
  let color = 'var(--text-muted)'
  let label = status

  if (status === 'complete') {
    bg = 'var(--pursue-bg)'
    color = 'var(--pursue-text)'
    label = 'Ready'
  } else if (status === 'pending') {
    bg = 'var(--maybe-bg)'
    color = 'var(--maybe-text)'
    label = 'Pending'
  } else if (status === 'error') {
    bg = 'var(--skip-bg)'
    color = 'var(--skip-text)'
    label = 'Error'
  } else if (status === 'scraping' || status === 'generating') {
    label = status === 'scraping' ? 'Scraping...' : 'Generating...'
  }

  return (
    <span
      className="px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ backgroundColor: bg, color }}
    >
      {label}
    </span>
  )
}
