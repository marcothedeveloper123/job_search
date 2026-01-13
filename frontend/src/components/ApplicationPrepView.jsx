/**
 * Right panel showing full application prep materials.
 */
import { useState } from 'react'
import { MarkdownContent } from './MarkdownContent'
import { CollapsibleSection } from './application/CollapsibleSection'
import { SectionStatusRow } from './application/SectionStatusRow'
import { GapAnalysisContent } from './application/GapAnalysisContent'
import { InterviewPrepContent } from './application/InterviewPrepContent'
import { SalaryResearchContent } from './application/SalaryResearchContent'
import { ReferralSearchContent } from './application/ReferralSearchContent'
import { FollowUpContent } from './application/FollowUpContent'

const NOT_GENERATED = <div style={{ color: 'var(--text-muted)' }}>Not yet generated</div>

export function ApplicationPrepView({ application }) {
  if (!application) {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: 'var(--text-muted)' }}>
        Select an application to view materials
      </div>
    )
  }

  const isError = application.status === 'error'

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            {application.job?.company} — {application.job?.title}
          </h1>
          <div className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            {application.job?.location || 'Remote'} • {application.job?.posted || 'Unknown date'}
          </div>
        </div>
        <a
          href={application.job?.url}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 rounded text-sm font-medium"
          style={{
            backgroundColor: 'var(--bg-inverse)',
            color: 'var(--white)',
          }}
        >
          Open Job
        </a>
      </div>

      {isError && <ErrorState error={application.error} />}

      <SectionStatusRow application={application} />

      <CollapsibleSection title="JOB DESCRIPTION" hasContent={!!application.jd} defaultOpen={!!application.jd}>
        <MarkdownContent content={application.jd} className="jd" fallback={NOT_GENERATED} />
      </CollapsibleSection>

      <CollapsibleSection title="GAP ANALYSIS" hasContent={!!application.gap_analysis} defaultOpen={true}>
        <GapAnalysisContent analysis={application.gap_analysis} />
      </CollapsibleSection>

      <CollapsibleSection title="REFERRAL SEARCH" hasContent={!!application.referral_search} defaultOpen={!!application.referral_search}>
        <ReferralSearchContent search={application.referral_search} />
      </CollapsibleSection>

      <CollapsibleSection
        title="TAILORED CV"
        hasContent={!!application.cv_tailored}
        defaultOpen={!!application.cv_tailored}
        action={application.cv_tailored && <ExportButton applicationId={application.application_id} docType="cv" />}
      >
        <MarkdownContent content={application.cv_tailored} className="cv" fallback={NOT_GENERATED} />
      </CollapsibleSection>

      <CollapsibleSection
        title="COVER LETTER"
        hasContent={!!application.cover_letter}
        defaultOpen={!!application.cover_letter}
        action={application.cover_letter && <ExportButton applicationId={application.application_id} docType="cover" />}
      >
        <MarkdownContent content={application.cover_letter} fallback={NOT_GENERATED} />
      </CollapsibleSection>

      <CollapsibleSection title="SALARY RESEARCH" hasContent={!!application.salary_research} defaultOpen={!!application.salary_research}>
        <SalaryResearchContent research={application.salary_research} />
      </CollapsibleSection>

      <CollapsibleSection title="INTERVIEW PREP" hasContent={!!application.interview_prep} defaultOpen={true}>
        <InterviewPrepContent prep={application.interview_prep} />
      </CollapsibleSection>

      <CollapsibleSection title="FOLLOW-UP PLAN" hasContent={!!application.follow_up} defaultOpen={!!application.follow_up}>
        <FollowUpContent followUp={application.follow_up} />
      </CollapsibleSection>
    </div>
  )
}

function ErrorState({ error }) {
  return (
    <div
      className="text-center py-12"
      style={{ color: 'var(--skip-text)' }}
    >
      <div className="text-4xl mb-4">⚠️</div>
      <div className="font-medium mb-2">Something went wrong</div>
      <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
        {error || 'Unknown error occurred'}
      </div>
    </div>
  )
}

function ExportButton({ applicationId, docType }) {
  const [exporting, setExporting] = useState(false)

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await fetch(`/api/applications/${applicationId}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_type: docType, format: 'docx' }),
      })
      const data = await res.json()

      if (data.status === 'ok' && data.filename) {
        window.open(`/api/applications/${applicationId}/download/${data.filename}`, '_blank')
      } else {
        console.error('Export failed:', data.error)
      }
    } catch (err) {
      console.error('Export error:', err)
    } finally {
      setExporting(false)
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={exporting}
      className="p-2 rounded"
      style={{
        backgroundColor: exporting ? 'var(--bg-secondary)' : 'transparent',
        color: exporting ? 'var(--text-muted)' : 'var(--text-secondary)',
        cursor: exporting ? 'wait' : 'pointer',
      }}
      title="Export DOCX"
    >
      {exporting ? '...' : '↗'}
    </button>
  )
}
