/**
 * Status overview row showing completion of application sections.
 */
const STATUS_COMPLETE = '#788c5d'
const STATUS_MISSING = '#d97757'

export function SectionStatusRow({ application }) {
  const sections = [
    { key: 'jd', label: 'JD', has: !!application.jd },
    { key: 'gap', label: 'Gap', has: !!application.gap_analysis },
    { key: 'cv', label: 'CV', has: !!application.cv_tailored },
    { key: 'cover', label: 'Cover', has: !!application.cover_letter },
    { key: 'prep', label: 'Prep', has: !!application.interview_prep },
  ]

  const complete = sections.filter(s => s.has).length
  const total = sections.length

  return (
    <div
      className="mb-4 p-3 rounded-lg flex items-center gap-4"
      style={{ backgroundColor: 'var(--bg-secondary)' }}
    >
      <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
        {complete}/{total}
      </span>
      <div className="flex gap-3">
        {sections.map(s => (
          <div key={s.key} className="flex items-center gap-1">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: s.has ? STATUS_COMPLETE : STATUS_MISSING }}
            />
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {s.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
