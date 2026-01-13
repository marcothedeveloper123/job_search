/**
 * Right panel showing full deep dive research for selected job.
 */
import { Section } from './deep-dive/Section'
import { JDContent } from './deep-dive/JDContent'
import { ResearchContent } from './deep-dive/ResearchContent'
import { InsightsContent, EnhancedInsightsContent } from './deep-dive/InsightsContent'
import { ConclusionsContent } from './deep-dive/ConclusionsContent'
import { RecommendationsContent } from './deep-dive/RecommendationsContent'

export function DeepDiveDetail({ job, deepDive, isLoading }) {
  if (!job) {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: 'var(--text-muted)' }}>
        Select a job to view details
      </div>
    )
  }

  const isComplete = deepDive?.status === 'complete'
  const showLoading = isLoading && !deepDive

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            {job.company} — {job.title}
          </h1>
          <div className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            {job.location || 'Remote'} • {job.source}
          </div>
        </div>
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 rounded text-sm font-medium"
          style={{
            backgroundColor: 'var(--bg-inverse)',
            color: 'var(--white)',
          }}
        >
          Open Link
        </a>
      </div>

      {showLoading ? (
        <LoadingState />
      ) : !isComplete ? (
        <PendingState />
      ) : (
        <>
          {deepDive.jd && (
            <Section title="JOB DESCRIPTION">
              <JDContent jd={deepDive.jd} />
            </Section>
          )}

          <Section title="RESEARCH">
            <ResearchContent research={deepDive.research} researchNotes={deepDive.research_notes} />
          </Section>

          {deepDive.enhanced_insights ? (
            <Section title="FIT ANALYSIS">
              <EnhancedInsightsContent insights={deepDive.enhanced_insights} />
            </Section>
          ) : (
            <Section title="INSIGHTS">
              <InsightsContent insights={deepDive.insights} />
            </Section>
          )}

          <Section title="CONCLUSIONS">
            <ConclusionsContent conclusions={deepDive.conclusions} />
          </Section>

          <Section title="RECOMMENDATIONS">
            <RecommendationsContent recommendations={deepDive.recommendations} />
          </Section>
        </>
      )}
    </div>
  )
}

function LoadingState() {
  return (
    <div
      className="text-center py-12"
      style={{ color: 'var(--text-muted)' }}
    >
      <div className="text-4xl mb-4">⋯</div>
      <div className="font-medium">Loading...</div>
    </div>
  )
}

function PendingState() {
  return (
    <div
      className="text-center py-12"
      style={{ color: 'var(--text-muted)' }}
    >
      <div className="text-4xl mb-4">⏳</div>
      <div className="font-medium mb-2">Research pending</div>
      <div className="text-sm">
        Claude will analyze this role when you're ready.
        <br />
        Return to chat and say "deep dive my selections"
      </div>
    </div>
  )
}
