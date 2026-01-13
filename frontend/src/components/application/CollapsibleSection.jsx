/**
 * Collapsible section with status indicator.
 */
import { useState } from 'react'

const STATUS_COMPLETE = '#788c5d'
const STATUS_MISSING = '#d97757'

export function CollapsibleSection({ title, hasContent, defaultOpen, action, children }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div
      className="mb-4 rounded-lg overflow-hidden"
      style={{
        backgroundColor: 'var(--white)',
        border: '1px solid var(--border)',
      }}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 p-4 text-left"
        style={{ color: 'var(--text-muted)' }}
      >
        <span
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: hasContent ? STATUS_COMPLETE : STATUS_MISSING }}
        />
        <span className="text-xs font-semibold tracking-wider">{title}</span>
        {action && <span onClick={e => e.stopPropagation()}>{action}</span>}
        <span className="ml-auto">{isOpen ? '▼' : '▶'}</span>
      </button>
      {isOpen && (
        <div className="px-4 pb-4">
          {children}
        </div>
      )}
    </div>
  )
}
