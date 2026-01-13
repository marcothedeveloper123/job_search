/**
 * Filter bar for job list - free text search, AI focus, archived toggle.
 */
import { useState } from 'react'

export function Filters({ filters, onFiltersChange, selectedCount, totalCount }) {
  const [searchInput, setSearchInput] = useState(filters.search || '')

  const handleSearchChange = (e) => {
    setSearchInput(e.target.value)
    onFiltersChange({ ...filters, search: e.target.value })
  }

  return (
    <div
      className="flex flex-wrap items-center gap-4 px-6 py-3 border-b text-sm"
      style={{ borderColor: 'var(--border)' }}
    >
      {/* Free text search */}
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-muted)' }}>Search:</span>
        <input
          type="text"
          value={searchInput}
          onChange={handleSearchChange}
          placeholder="title, company, location..."
          title="Search by title, company, location, or source (LI, JO, SJ)"
          className="px-2 py-1 rounded text-sm w-48"
          style={{
            backgroundColor: 'var(--white)',
            border: '1px solid var(--border-strong)',
            color: 'var(--text-primary)',
          }}
        />
      </div>

      {/* Checkboxes */}
      <label className="flex items-center gap-1 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.showArchived}
          onChange={() => onFiltersChange({ ...filters, showArchived: !filters.showArchived })}
          className="w-4 h-4"
        />
        <span style={{ color: 'var(--text-muted)' }}>Show Archived</span>
      </label>

      {/* Selection count - clickable to filter */}
      <button
        onClick={() => onFiltersChange({ ...filters, showSelectedOnly: !filters.showSelectedOnly })}
        className="ml-auto cursor-pointer"
        style={{
          color: filters.showSelectedOnly ? 'var(--text-primary)' : 'var(--text-muted)',
          background: 'none',
          border: 'none',
          font: 'inherit',
        }}
      >
        {filters.showSelectedOnly ? `${selectedCount} selected ✓` : `${selectedCount} of ${totalCount} selected`}
      </button>
    </div>
  )
}
