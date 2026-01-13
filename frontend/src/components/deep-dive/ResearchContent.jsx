/**
 * Research section showing company, role, compensation, and research notes.
 */
import { useState } from 'react'
import { MarkdownContent } from '../MarkdownContent'

export function ResearchContent({ research, researchNotes }) {
  const { company, role, sentiment, context, compensation } = research || {}
  const hasNotes = researchNotes && (
    researchNotes.employee?.length > 0 ||
    researchNotes.customer?.length > 0 ||
    researchNotes.company?.length > 0
  )
  const hasSentiment = sentiment && (
    sentiment.employee?.length > 0 ||
    sentiment.customer?.length > 0
  )
  const hasContext = context && (
    context.market?.length > 0 ||
    context.interview_process?.length > 0 ||
    context.remote_reality?.length > 0
  )

  return (
    <div className="space-y-4 text-sm">
      {hasNotes && <ResearchNotesSection notes={researchNotes} />}
      {company && (
        <div>
          <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Company</h3>
          <FieldList fields={company} />
        </div>
      )}
      {role && (
        <div>
          <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Role</h3>
          <FieldList fields={role} />
        </div>
      )}
      {hasSentiment && (
        <div>
          <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Sentiment</h3>
          <ItemizedSection data={sentiment} labels={{ employee: 'Employee', customer: 'Customer' }} />
        </div>
      )}
      {hasContext && (
        <div>
          <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Context</h3>
          <ItemizedSection data={context} labels={{ market: 'Market', interview_process: 'Interview Process', remote_reality: 'Remote Reality' }} />
        </div>
      )}
      {compensation && (
        <div>
          <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Compensation</h3>
          {compensation.estimate && (
            <MarkdownContent content={compensation.estimate} className="deep-dive-md" />
          )}
          {compensation.notes && (
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              <MarkdownContent content={compensation.notes} className="deep-dive-md" inline />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ResearchNotesSection({ notes }) {
  const categories = [
    { key: 'employee', label: 'Employee', items: notes.employee || [] },
    { key: 'customer', label: 'Customer', items: notes.customer || [] },
    { key: 'company', label: 'Company', items: notes.company || [] },
  ].filter(c => c.items.length > 0)

  return (
    <div className="space-y-2">
      <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Research Notes</h3>
      <div className="space-y-2">
        {categories.map(cat => (
          <ResearchCategory key={cat.key} label={cat.label} items={cat.items} />
        ))}
      </div>
    </div>
  )
}

function ResearchCategory({ label, items }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs font-medium"
        style={{ color: 'var(--text-secondary)' }}
      >
        <span style={{ width: '1em', display: 'inline-block' }}>{expanded ? '▼' : '▶'}</span>
        {label} ({items.length})
      </button>
      {expanded && (
        <div className="ml-4 mt-1 space-y-1">
          {items.map((item, idx) => (
            <ResearchItem key={idx} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

function ResearchItem({ item }) {
  const sentimentIcon = {
    positive: '✓',
    negative: '✗',
    neutral: '○',
  }[item.sentiment] || '○'

  const sentimentColor = {
    positive: 'var(--success)',
    negative: 'var(--danger)',
    neutral: 'var(--text-muted)',
  }[item.sentiment] || 'var(--text-muted)'

  return (
    <div className="flex items-start gap-2 text-xs">
      <span style={{ color: sentimentColor, flexShrink: 0 }}>{sentimentIcon}</span>
      <MarkdownContent content={item.finding} className="deep-dive-md" inline />
    </div>
  )
}

function FieldList({ fields }) {
  const entries = Object.entries(fields || {}).filter(([k, v]) => v && k !== 'found')
  if (entries.length === 0) return <div style={{ color: 'var(--text-muted)' }}>—</div>

  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key}>
          <span className="capitalize font-medium" style={{ color: 'var(--text-primary)' }}>
            {key.replace(/_/g, ' ')}:
          </span>
          <MarkdownContent content={String(value)} className="deep-dive-md" />
        </div>
      ))}
    </div>
  )
}

function ItemizedSection({ data, labels }) {
  const categories = Object.entries(labels)
    .map(([key, label]) => ({ key, label, items: data[key] || [] }))
    .filter(c => c.items.length > 0)

  if (categories.length === 0) return <div style={{ color: 'var(--text-muted)' }}>—</div>

  return (
    <div className="space-y-2">
      {categories.map(cat => (
        <div key={cat.key}>
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
            {cat.label}
          </div>
          <div className="ml-2 space-y-1">
            {cat.items.map((item, idx) => (
              <ItemizedItem key={idx} item={item} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function ItemizedItem({ item }) {
  const icon = { positive: '✓', negative: '✗', neutral: '○' }[item.sentiment] || '○'
  const color = {
    positive: 'var(--success)',
    negative: 'var(--danger)',
    neutral: 'var(--text-muted)',
  }[item.sentiment] || 'var(--text-muted)'

  return (
    <div className="flex items-start gap-2 text-xs">
      <span style={{ color, flexShrink: 0 }}>{icon}</span>
      <MarkdownContent content={item.finding} className="deep-dive-md" inline />
    </div>
  )
}
