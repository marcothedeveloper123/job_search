/**
 * Resizable two-panel layout with draggable divider.
 */
import { useRef, useCallback, useEffect } from 'react'

export function ResizableLayout({ leftWidth, onWidthChange, onReset, left, right }) {
  const containerRef = useRef(null)
  const isDragging = useRef(false)

  const handleMouseDown = (e) => {
    e.preventDefault()
    isDragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  const handleMouseMove = useCallback((e) => {
    if (!isDragging.current || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const newWidth = ((e.clientX - rect.left) / rect.width) * 100
    const clampedWidth = Math.min(Math.max(newWidth, 20), 60)
    onWidthChange(clampedWidth)
  }, [onWidthChange])

  const handleMouseUp = useCallback(() => {
    isDragging.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [])

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [handleMouseMove, handleMouseUp])

  return (
    <div ref={containerRef} className="flex-1 flex overflow-hidden" style={{ height: 'calc(100vh - 60px)' }}>
      <div className="overflow-y-auto shrink-0" style={{ width: 'fit-content', maxWidth: `${leftWidth}%`, minWidth: 200, height: '100%' }}>
        {left}
      </div>
      <div
        onMouseDown={handleMouseDown}
        onDoubleClick={onReset}
        className="w-1 cursor-col-resize hover:bg-blue-400 transition-colors"
        style={{ backgroundColor: 'var(--border)' }}
      />
      <div className="flex-1 overflow-y-auto">
        {right}
      </div>
    </div>
  )
}
