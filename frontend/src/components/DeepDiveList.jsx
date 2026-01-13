/**
 * Left panel list of deep dives with status indicators.
 */
import { VerdictBadge } from './VerdictBadge'

export function DeepDiveList({ jobs, deepDives, selectedJobId, onSelect, showArchived, onToggleArchived, onRestore, onArchive }) {
  // Map jobs by job_id for lookup
  const jobMap = {}
  jobs.forEach((j) => {
    jobMap[j.job_id] = j
  })

  if (deepDives.length === 0) {
    return (
      <div className="p-6" style={{ color: 'var(--text-muted)' }}>
        No deep dives yet.
      </div>
    )
  }

  return (
    <div>
      <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
        <span className="font-medium" style={{ color: 'var(--text-muted)' }}>
          Deep Dives ({deepDives.length})
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
      {deepDives.map((dive) => {
        const job = jobMap[dive.job_id]
        const isComplete = dive.status === 'complete'
        const verdict = dive.recommendations?.verdict
        const isSelected = selectedJobId === dive.job_id
        const isArchived = dive.archived

        return (
          <div
            key={dive.job_id}
            onClick={() => onSelect(dive.job_id)}
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
              <span className="shrink-0" style={{ color: isComplete ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                {isComplete ? '●' : '○'}
              </span>
              <div className="flex-1 min-w-0">
                <div
                  className="font-medium break-words"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {job?.company || 'Unknown Company'}
                </div>
                <div
                  className="text-sm break-words"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {job?.title || 'Unknown Role'}
                </div>
                <div className="flex items-center gap-2 mt-1 text-xs min-w-0">
                  <span className="truncate flex-1" style={{ color: 'var(--text-muted)' }}>
                    {job?.location || 'Remote'}
                  </span>
                  {isArchived && <span className="archived-badge">Archived</span>}
                  {verdict && <VerdictBadge verdict={verdict} />}
                  {!isComplete && !isArchived && (
                    <span className="shrink-0" style={{ color: 'var(--text-muted)' }}>⏳</span>
                  )}
                  {isArchived && (
                    <button
                      className="restore-btn"
                      onClick={(e) => { e.stopPropagation(); onRestore(dive.job_id) }}
                    >
                      Restore
                    </button>
                  )}
                  {!isArchived && (
                    <button
                      className="archive-btn ml-auto"
                      onClick={(e) => { e.stopPropagation(); onArchive(dive.job_id) }}
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
