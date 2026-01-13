/**
 * Step navigation bar showing Select, Deep Dives, and Applications steps.
 */
export function StepNav({ currentStep, onStepChange, jobCount, deepDiveCount, applicationCount }) {
  return (
    <nav
      className="flex gap-4 px-6 py-4 border-b"
      style={{ borderColor: 'var(--border)' }}
    >
      <StepButton
        active={currentStep === 1}
        onClick={() => onStepChange(1)}
        label="1. Select"
        count={jobCount}
      />
      <StepButton
        active={currentStep === 2}
        onClick={() => onStepChange(2)}
        label="2. Deep Dives"
        count={deepDiveCount}
      />
      <StepButton
        active={currentStep === 3}
        onClick={() => onStepChange(3)}
        label="3. Applications"
        count={applicationCount}
      />
    </nav>
  )
}

function StepButton({ active, onClick, label, count }) {
  return (
    <button
      onClick={onClick}
      className="px-4 py-2 rounded-full font-medium text-sm"
      style={{
        backgroundColor: active ? 'var(--bg-secondary)' : 'transparent',
        color: active ? 'var(--text-primary)' : 'var(--text-muted)',
      }}
    >
      {label}
      {count > 0 && (
        <span
          className="ml-2 px-2 py-0.5 rounded-full text-xs"
          style={{
            backgroundColor: active ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
          }}
        >
          {count}
        </span>
      )}
    </button>
  )
}
