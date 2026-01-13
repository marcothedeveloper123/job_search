import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { StepNav } from './components/StepNav'
import { Filters } from './components/Filters'
import { JobList } from './components/JobList'
import { DeepDiveList } from './components/DeepDiveList'
import { DeepDiveDetail } from './components/DeepDiveDetail'
import { ApplicationList } from './components/ApplicationList'
import { ApplicationPrepView } from './components/ApplicationPrepView'
import { ResizableLayout } from './components/ResizableLayout'
import { useWebSocket } from './hooks/useWebSocket'

const DEFAULT_FILTERS = {
  levels: ['staff', 'principal', 'senior', 'lead', 'leadership', 'other'],
  search: '',
  aiFocus: false,
  showArchived: false,
  showSelectedOnly: false,
}

function formatSource(source) {
  if (!source) return ''
  if (source === 'linkedin') return 'LI'
  if (source === 'jobs.cz') return 'JO'
  if (source === 'startupjobs.cz') return 'SJ'
  return source.slice(0, 2).toUpperCase()
}

const DEFAULT_LEFT_WIDTH = 40 // percentage

function App() {
  // Navigation
  const [step, setStep] = useState(1)

  // Data
  const [jobs, setJobs] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [deepDives, setDeepDives] = useState([])
  const [deepDivesLoaded, setDeepDivesLoaded] = useState(false)
  const [applications, setApplications] = useState([])

  // Filters
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  // Deep dive view
  const [selectedDiveJobId, setSelectedDiveJobId] = useState(null)

  // Application view
  const [selectedAppId, setSelectedAppId] = useState(null)
  const [currentApplication, setCurrentApplication] = useState(null)

  // Archive toggles for steps 2 & 3
  const [showArchivedDives, setShowArchivedDives] = useState(false)
  const [showArchivedApps, setShowArchivedApps] = useState(false)

  // Resizable panel
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH)

  // Fetch functions - always fetch all jobs for lookup by other views
  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/jobs?include_archived=true')
      const data = await res.json()
      setJobs(data.jobs || [])
    } catch (err) {
      console.error('Failed to fetch jobs:', err)
    }
  }, [])

  const fetchSelections = useCallback(async () => {
    try {
      const res = await fetch('/api/selections')
      const data = await res.json()
      setSelectedIds(data.selected_ids || [])
    } catch (err) {
      console.error('Failed to fetch selections:', err)
    }
  }, [])

  const fetchDeepDives = useCallback(async () => {
    try {
      const url = showArchivedDives ? '/api/deep-dives?include_archived=true' : '/api/deep-dives'
      const res = await fetch(url)
      const data = await res.json()
      setDeepDives(data.deep_dives || [])
      setDeepDivesLoaded(true)
    } catch (err) {
      console.error('Failed to fetch deep dives:', err)
      setDeepDivesLoaded(true)  // Mark as loaded even on error
    }
  }, [showArchivedDives])

  const fetchApplications = useCallback(async () => {
    try {
      const url = showArchivedApps ? '/api/applications?include_archived=true' : '/api/applications'
      const res = await fetch(url)
      const data = await res.json()
      setApplications(data.applications || [])
    } catch (err) {
      console.error('Failed to fetch applications:', err)
    }
  }, [showArchivedApps])

  // Save selections
  const saveSelections = useCallback(async (ids) => {
    setSelectedIds(ids)
    try {
      await fetch('/api/selections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_ids: ids }),
      })
    } catch (err) {
      console.error('Failed to save selections:', err)
    }
  }, [])

  // Restore handlers for archived items
  const restoreJob = useCallback(async (jobId) => {
    try {
      await fetch('/api/jobs/unarchive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_ids: [jobId] }),
      })
    } catch (err) {
      console.error('Failed to restore job:', err)
    }
  }, [])

  const reorderJobs = useCallback(async (jobIds) => {
    try {
      await fetch('/api/jobs/reorder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_ids: jobIds }),
      })
      // WebSocket will trigger refresh
    } catch (err) {
      console.error('Failed to reorder jobs:', err)
    }
  }, [])

  const restoreDeepDive = useCallback(async (jobId) => {
    try {
      await fetch('/api/deep-dives/unarchive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_ids: [jobId] }),
      })
    } catch (err) {
      console.error('Failed to restore deep dive:', err)
    }
  }, [])

  const restoreApplication = useCallback(async (appId) => {
    try {
      await fetch('/api/applications/unarchive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ application_ids: [appId] }),
      })
    } catch (err) {
      console.error('Failed to restore application:', err)
    }
  }, [])

  const archiveDeepDive = useCallback(async (jobId) => {
    try {
      await fetch('/api/deep-dives/archive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_ids: [jobId] }),
      })
    } catch (err) {
      console.error('Failed to archive deep dive:', err)
    }
  }, [])

  const archiveApplication = useCallback(async (appId) => {
    try {
      await fetch('/api/applications/archive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ application_ids: [appId] }),
      })
    } catch (err) {
      console.error('Failed to archive application:', err)
    }
  }, [])

  // Fetch current application detail (must be defined before WebSocket handler)
  const fetchCurrentApplication = useCallback(() => {
    if (selectedAppId) {
      fetch(`/api/applications/${selectedAppId}`)
        .then(res => res.json())
        .then(data => setCurrentApplication(data))
        .catch(err => console.error('Failed to fetch application:', err))
    } else {
      setCurrentApplication(null)
    }
  }, [selectedAppId])

  // Initial fetch
  useEffect(() => {
    fetchJobs()
    fetchSelections()
    fetchDeepDives()
    fetchApplications()
  }, [fetchJobs, fetchSelections, fetchDeepDives, fetchApplications])

  // View mapping for WebSocket commands
  const VIEW_MAP = { select: 1, deep_dive: 2, deep_dives: 2, application: 3, applications: 3 }

  // WebSocket handler
  const handleWsMessage = useCallback((msg) => {
    if (msg.event === 'jobs_updated') {
      // Refetch all dependent state when jobs change
      // (selections and deep dives may reference stale job IDs)
      fetchJobs()
      fetchSelections()
      fetchDeepDives()
    } else if (msg.event === 'deep_dive_updated') {
      fetchDeepDives()
      // Auto-select the updated deep dive
      if (msg.data?.job_id) {
        setSelectedDiveJobId(msg.data.job_id)
        setStep(2)
      }
    } else if (msg.event === 'deep_dives_changed') {
      // List changed (delete/archive) - refetch and clear selection if needed
      fetchDeepDives()
    } else if (msg.event === 'application_updated') {
      fetchApplications()
      // Auto-select the updated application and navigate to step 3
      if (msg.data?.application_id) {
        setSelectedAppId(msg.data.application_id)
        setStep(3)
        fetchCurrentApplication()
      }
    } else if (msg.event === 'applications_changed') {
      // List changed (delete/archive) - refetch and clear selection if deleted
      fetchApplications()
      setCurrentApplication(null)
      setSelectedAppId(null)
    } else if (msg.event === 'view_changed') {
      // Claude requested view change
      const newStep = VIEW_MAP[msg.data?.view]
      if (newStep) setStep(newStep)
    }
  }, [fetchJobs, fetchSelections, fetchDeepDives, fetchApplications, selectedAppId, fetchCurrentApplication])

  useWebSocket(handleWsMessage)

  // Filter jobs for Step 1
  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      // Archived filter
      if (!filters.showArchived && job.archived) return false

      // Level filter
      if (!filters.levels.includes(job.level || 'other')) return false

      // Free text search
      if (filters.search) {
        const q = filters.search.toLowerCase()
        const sourceCode = formatSource(job.source)
        const searchable = [job.title, job.company, job.location, sourceCode]
          .map(s => (s || '').toLowerCase())
          .join(' ')
        if (!searchable.includes(q)) return false
      }

      // AI focus filter
      if (filters.aiFocus && !job.ai_focus) return false

      // Selected only filter
      if (filters.showSelectedOnly && !selectedIds.includes(job.job_id)) return false

      return true
    })
  }, [jobs, filters, selectedIds])

  // Filter deep dives by archived status only
  const filteredDeepDives = useMemo(() => {
    if (showArchivedDives) return deepDives
    return deepDives.filter(d => !d.archived)
  }, [deepDives, showArchivedDives])

  // Get current deep dive
  const currentDive = useMemo(() => {
    return deepDives.find((d) => d.job_id === selectedDiveJobId)
  }, [deepDives, selectedDiveJobId])

  const currentDiveJob = useMemo(() => {
    return jobs.find((j) => j.job_id === selectedDiveJobId)
  }, [jobs, selectedDiveJobId])

  // Fetch current application when selection changes
  useEffect(() => {
    fetchCurrentApplication()
  }, [fetchCurrentApplication])

  // Auto-select first deep dive when entering step 2
  useEffect(() => {
    if (step === 2 && !selectedDiveJobId && filteredDeepDives.length > 0) {
      setSelectedDiveJobId(filteredDeepDives[0].job_id)
    }
  }, [step, selectedDiveJobId, filteredDeepDives])

  // Auto-select first application in applications view
  useEffect(() => {
    if (step === 3 && !selectedAppId && applications.length > 0) {
      setSelectedAppId(applications[0].application_id)
    }
  }, [step, selectedAppId, applications])

  // Track previous step for skip detection
  const prevStepRef = useRef(step)
  const [isSkipTransition, setIsSkipTransition] = useState(false)

  useEffect(() => {
    const diff = Math.abs(step - prevStepRef.current)
    setIsSkipTransition(diff > 1)
    prevStepRef.current = step
  }, [step])

  // Calculate carousel offset
  const carouselOffset = (step - 1) * -100

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <StepNav
        currentStep={step}
        onStepChange={setStep}
        jobCount={filteredJobs.length}
        deepDiveCount={filteredDeepDives.length}
        applicationCount={applications.length}
      />

      <div className="flex-1 overflow-hidden">
        <div
          className={`view-carousel ${isSkipTransition ? 'skip-transition' : ''}`}
          style={{
            transform: `translateX(${carouselOffset}%)`,
            height: '100%',
          }}
        >
          {/* Panel 1: Select */}
          <div className="view-panel flex flex-col">
            <Filters
              filters={filters}
              onFiltersChange={setFilters}
              selectedCount={selectedIds.length}
              totalCount={filteredJobs.length}
            />
            <main className="flex-1 overflow-y-auto">
              <JobList
                jobs={filteredJobs}
                selectedIds={selectedIds}
                onSelectionChange={saveSelections}
                onRestore={restoreJob}
                onReorder={reorderJobs}
              />
            </main>
          </div>

          {/* Panel 2: Deep Dives */}
          <div className="view-panel">
            <ResizableLayout
              leftWidth={leftWidth}
              onWidthChange={setLeftWidth}
              onReset={() => setLeftWidth(DEFAULT_LEFT_WIDTH)}
              left={
                <DeepDiveList
                  jobs={jobs}
                  deepDives={filteredDeepDives}
                  selectedJobId={selectedDiveJobId}
                  onSelect={setSelectedDiveJobId}
                  showArchived={showArchivedDives}
                  onToggleArchived={() => setShowArchivedDives(!showArchivedDives)}
                  onRestore={restoreDeepDive}
                  onArchive={archiveDeepDive}
                />
              }
              right={
                <DeepDiveDetail
                  job={currentDiveJob}
                  deepDive={currentDive}
                  isLoading={!deepDivesLoaded}
                />
              }
            />
          </div>

          {/* Panel 3: Applications */}
          <div className="view-panel">
            <ResizableLayout
              leftWidth={leftWidth}
              onWidthChange={setLeftWidth}
              onReset={() => setLeftWidth(DEFAULT_LEFT_WIDTH)}
              left={
                <ApplicationList
                  applications={applications}
                  selectedId={selectedAppId}
                  onSelect={setSelectedAppId}
                  showArchived={showArchivedApps}
                  onToggleArchived={() => setShowArchivedApps(!showArchivedApps)}
                  onRestore={restoreApplication}
                  onArchive={archiveApplication}
                />
              }
              right={
                <ApplicationPrepView
                  application={currentApplication}
                />
              }
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
