/**
 * Job list table with checkboxes, sorting, selection state, and exit animations.
 */
import { useState, useEffect, useRef } from 'react'
import FlipMove from 'react-flip-move'

function formatAge(daysAgo) {
  if (daysAgo === null || daysAgo === undefined) return '—'
  if (daysAgo === 0) return 'Today'
  if (daysAgo === 1) return '1 day'
  return `${daysAgo} days`
}

function formatSource(source) {
  if (!source) return '—'
  if (source === 'linkedin') return 'LI'
  if (source === 'jobs.cz') return 'JO'
  if (source === 'startupjobs.cz') return 'SJ'
  return source.slice(0, 2).toUpperCase()
}

export function JobList({ jobs, selectedIds, onSelectionChange, onRestore, onReorder }) {
  const [sortKey, setSortKey] = useState(null) // null = manual order from backend
  const [sortAsc, setSortAsc] = useState(true)
  const [exitingIds, setExitingIds] = useState(new Set())
  const [enteringIds, setEnteringIds] = useState(new Set())
  const prevJobsRef = useRef(jobs)
  const exitingJobsDataRef = useRef(new Map())

  // Drag state
  const [draggedId, setDraggedId] = useState(null)
  const [dragOverId, setDragOverId] = useState(null)
  const [dragDirection, setDragDirection] = useState(null) // 'up' or 'down'
  const [settledIds, setSettledIds] = useState(new Set())

  // Clear stale exitingIds and exitingJobsDataRef
  useEffect(() => {
    // Clear exitingIds that no longer have data
    setExitingIds((prev) => {
      const valid = [...prev].filter((id) => exitingJobsDataRef.current.has(id))
      return valid.length === prev.size ? prev : new Set(valid)
    })
    // Clear orphaned data from exitingJobsDataRef (cleanup race condition)
    const currentIds = new Set(jobs.map((j) => j.job_id))
    for (const id of exitingJobsDataRef.current.keys()) {
      if (!currentIds.has(id) && !exitingIds.has(id)) {
        exitingJobsDataRef.current.delete(id)
      }
    }
  }, [jobs, exitingIds])

  // Detect added/removed jobs and trigger animations
  useEffect(() => {
    const prevIds = new Set(prevJobsRef.current.map((j) => j.job_id))
    const currentIds = new Set(jobs.map((j) => j.job_id))

    // Find jobs that were removed (exit animation)
    const removed = [...prevIds].filter((id) => !currentIds.has(id))

    // Skip exit animation for bulk removals (filter toggle) - only animate 1-3 jobs
    if (removed.length > 3) {
      // Bulk removal - clear any stale exit animation data
      setExitingIds(new Set())
      exitingJobsDataRef.current.clear()
    } else if (removed.length > 0) {
      // Save job data BEFORE we lose it (fixes race condition)
      removed.forEach((id) => {
        const job = prevJobsRef.current.find((j) => j.job_id === id)
        if (job) exitingJobsDataRef.current.set(id, job)
      })

      setExitingIds((prev) => new Set([...prev, ...removed]))

      // Clean up after animation completes
      const timeoutId = setTimeout(() => {
        removed.forEach((id) => exitingJobsDataRef.current.delete(id))
        setExitingIds((prev) => {
          const next = new Set(prev)
          removed.forEach((id) => next.delete(id))
          return next
        })
      }, 650)

      return () => clearTimeout(timeoutId)
    }

    // Find jobs that were added (entrance animation)
    const added = [...currentIds].filter((id) => !prevIds.has(id))

    if (added.length > 0 && prevJobsRef.current.length > 0) {
      // Only animate if we had jobs before (skip initial load)
      setEnteringIds(new Set(added))
      setTimeout(() => setEnteringIds(new Set()), 500)
    }

    // Detect reordered jobs (same IDs, different positions)
    if (removed.length === 0 && added.length === 0 && prevJobsRef.current.length > 0) {
      const prevOrder = prevJobsRef.current.map((j) => j.job_id)
      const currentOrder = jobs.map((j) => j.job_id)

      // Find the job that moved the most (likely the one user/API moved)
      let maxMove = 0
      let primaryMovedId = null
      currentOrder.forEach((id, newIdx) => {
        const oldIdx = prevOrder.indexOf(id)
        const distance = Math.abs(newIdx - oldIdx)
        if (distance > maxMove) {
          maxMove = distance
          primaryMovedId = id
        }
      })

      // Find all jobs that changed position
      const moved = currentOrder.filter((id, idx) => prevOrder[idx] !== id)

      if (moved.length > 0) {
        setSettledIds(new Set(moved))
        setTimeout(() => setSettledIds(new Set()), 450)

        // Scroll to the primary moved job after animation
        if (primaryMovedId) {
          setTimeout(() => {
            const row = document.querySelector(`tr[data-job-id="${primaryMovedId}"]`)
            if (row) {
              row.scrollIntoView({ behavior: 'smooth', block: 'center' })
            }
          }, 350) // Slightly before animation ends for smooth feel
        }
      }
    }

    prevJobsRef.current = jobs
  }, [jobs])

  const handleSort = (key) => {
    if (sortKey === key) {
      if (!sortAsc) {
        // Third click: reset to manual order
        setSortKey(null)
        setSortAsc(true)
      } else {
        setSortAsc(false)
      }
    } else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  // Combine current jobs with exiting jobs (to keep them in DOM during animation)
  const exitingJobs = [...exitingIds]
    .map((id) => exitingJobsDataRef.current.get(id))
    .filter(Boolean)
  const allJobs = [...jobs, ...exitingJobs]

  const sortedJobs = [...allJobs].sort((a, b) => {
    // Keep exiting jobs at their original position (end)
    const aExiting = exitingIds.has(a.job_id)
    const bExiting = exitingIds.has(b.job_id)
    if (aExiting && !bExiting) return 1
    if (!aExiting && bExiting) return -1
    if (aExiting && bExiting) return 0

    // null sortKey = manual order (respect order from props/backend)
    if (sortKey === null) return 0

    const aVal = a[sortKey]
    const bVal = b[sortKey]

    // Numeric comparison for days_ago
    if (sortKey === 'days_ago') {
      const aNum = aVal ?? Infinity
      const bNum = bVal ?? Infinity
      const cmp = aNum - bNum
      return sortAsc ? cmp : -cmp
    }

    // String comparison for other fields
    const cmp = String(aVal || '').localeCompare(String(bVal || ''))
    return sortAsc ? cmp : -cmp
  })

  const toggleSelection = (jobId) => {
    const newIds = selectedIds.includes(jobId)
      ? selectedIds.filter((id) => id !== jobId)
      : [...selectedIds, jobId]
    onSelectionChange(newIds)
  }

  const handleRowClick = (job, e) => {
    // Don't open link if clicking checkbox, drag handle, or if exiting
    if (e.target.type === 'checkbox') return
    if (e.target.closest('.drag-handle')) return
    if (exitingIds.has(job.job_id)) return
    window.open(job.url, '_blank')
  }

  // Drag handlers
  const handleDragStart = (e, jobId) => {
    setDraggedId(jobId)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', jobId)
  }

  const handleDragOver = (e, jobId) => {
    e.preventDefault()
    e.stopPropagation()
    const newOverId = jobId === draggedId ? null : jobId
    if (dragOverId !== newOverId) {
      setDragOverId(newOverId)
      // Calculate direction based on position in displayed list
      if (newOverId && draggedId) {
        const displayedJobs = sortedJobs.filter((j) => !exitingIds.has(j.job_id))
        const fromIdx = displayedJobs.findIndex((j) => j.job_id === draggedId)
        const toIdx = displayedJobs.findIndex((j) => j.job_id === newOverId)
        setDragDirection(toIdx > fromIdx ? 'down' : 'up')
      } else {
        setDragDirection(null)
      }
    }
  }

  const handleDrop = (e, targetId) => {
    e.preventDefault()
    if (draggedId && draggedId !== targetId && onReorder) {
      // Use displayed order (sortedJobs minus exiting jobs)
      const displayedJobs = sortedJobs.filter((j) => !exitingIds.has(j.job_id))
      const ids = displayedJobs.map((j) => j.job_id)
      const fromIdx = ids.indexOf(draggedId)
      const toIdx = ids.indexOf(targetId)
      if (fromIdx !== -1 && toIdx !== -1) {
        ids.splice(fromIdx, 1)
        ids.splice(toIdx, 0, draggedId)
        onReorder(ids)
        // Reset to manual order after drag
        setSortKey(null)
        // Trigger settle animation on dragged item
        setSettledIds(new Set([draggedId]))
        setTimeout(() => setSettledIds(new Set()), 450)
      }
    }
    setDraggedId(null)
    setDragOverId(null)
    setDragDirection(null)
  }

  const handleDragEnd = () => {
    setDraggedId(null)
    setDragOverId(null)
    setDragDirection(null)
  }

  if (jobs.length === 0 && exitingIds.size === 0) {
    return (
      <div className="p-6 text-center" style={{ color: 'var(--text-muted)' }}>
        No search results yet. Waiting for Claude to trigger a search.
      </div>
    )
  }

  const handleTableDragLeave = (e) => {
    // Clear highlight when leaving the table entirely
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setDragOverId(null)
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" onDragLeave={handleTableDragLeave}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th className="w-6"></th>
            <th className="p-3 w-10"></th>
            <SortHeader label="Title" sortKey="title" current={sortKey} asc={sortAsc} onClick={handleSort} />
            <SortHeader label="Company" sortKey="company" current={sortKey} asc={sortAsc} onClick={handleSort} />
            <SortHeader label="Location" sortKey="location" current={sortKey} asc={sortAsc} onClick={handleSort} />
            <SortHeader label="Src" sortKey="source" current={sortKey} asc={sortAsc} onClick={handleSort} />
            <SortHeader label="Age" sortKey="days_ago" current={sortKey} asc={sortAsc} onClick={handleSort} />
            <th className="p-3 w-20"></th>
          </tr>
        </thead>
        <FlipMove typeName="tbody" duration={300} easing="ease-out" enterAnimation="fade" leaveAnimation={false}>
          {sortedJobs.map((job) => {
            const isSelected = selectedIds.includes(job.job_id)
            const isExiting = exitingIds.has(job.job_id)
            const isEntering = enteringIds.has(job.job_id)
            const isArchived = job.archived
            const isDragging = draggedId === job.job_id
            const isDragOver = dragOverId === job.job_id
            const isSettled = settledIds.has(job.job_id)
            return (
              <tr
                key={job.job_id}
                data-job-id={job.job_id}
                onClick={(e) => handleRowClick(job, e)}
                onDragOver={(e) => handleDragOver(e, job.job_id)}
                onDrop={(e) => handleDrop(e, job.job_id)}
                className={`cursor-pointer ${isExiting ? 'job-row-exiting' : ''} ${isEntering ? 'job-row-entering' : ''} ${isArchived ? 'archived-row' : ''} ${isDragging ? 'dragging' : ''} ${isDragOver ? `drag-over drag-${dragDirection}` : ''} ${isSelected ? 'selected' : ''} ${isSettled ? 'job-row-settled' : ''}`}
                style={{
                  borderBottom: '1px solid var(--border)',
                  pointerEvents: isExiting ? 'none' : 'auto',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected && !isExiting && !isDragOver && !isDragging && !isSettled) e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'
                }}
                onMouseLeave={(e) => {
                  if (!isExiting && !isDragOver && !isDragging && !isSettled) e.currentTarget.style.backgroundColor = isSelected ? 'var(--bg-secondary)' : ''
                }}
              >
                <td
                  className="drag-handle pl-2"
                  draggable={!isExiting}
                  onDragStart={(e) => handleDragStart(e, job.job_id)}
                  onDragEnd={handleDragEnd}
                >
                  <span style={{ color: 'var(--text-muted)', cursor: isExiting ? 'default' : 'grab' }}>⠿</span>
                </td>
                <td className="p-3">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleSelection(job.job_id)}
                    className="w-4 h-4 cursor-pointer"
                    disabled={isExiting}
                    style={{
                      accentColor: 'var(--bg-inverse)',
                      opacity: isExiting ? 0.5 : 1,
                    }}
                  />
                </td>
                <td className="p-3">
                  <div style={{ color: 'var(--text-primary)' }}>{job.title}</div>
                  {job.ai_focus && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        backgroundColor: 'var(--pursue-bg)',
                        color: 'var(--pursue-text)',
                      }}
                    >
                      AI
                    </span>
                  )}
                </td>
                <td className="p-3" style={{ color: 'var(--text-secondary)' }}>
                  {job.company}
                </td>
                <td className="p-3" style={{ color: 'var(--text-secondary)' }}>
                  {job.location || '—'}
                </td>
                <td className="p-3" style={{ color: 'var(--text-muted)' }} title={job.source}>
                  {formatSource(job.source)}
                </td>
                <td
                  className="p-3"
                  style={{ color: 'var(--text-secondary)' }}
                  title={job.posted || undefined}
                >
                  {formatAge(job.days_ago)}
                </td>
                <td className="p-3">
                  {isArchived && (
                    <button
                      className="restore-btn"
                      onClick={(e) => { e.stopPropagation(); onRestore(job.job_id) }}
                    >
                      Restore
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </FlipMove>
      </table>
    </div>
  )
}

function SortHeader({ label, sortKey, current, asc, onClick }) {
  const isActive = current === sortKey
  return (
    <th
      className="p-3 text-left font-medium cursor-pointer select-none"
      style={{ color: 'var(--text-muted)' }}
      onClick={() => onClick(sortKey)}
    >
      {label}
      {isActive && (
        <span className="ml-1">{asc ? '↑' : '↓'}</span>
      )}
    </th>
  )
}
