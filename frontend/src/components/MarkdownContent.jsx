/**
 * Shared markdown rendering component.
 */
import { marked } from 'marked'

// Fix common markdown spacing issues from HTML-to-markdown conversion
function preprocessMarkdown(content) {
  return content
    // Add space after closing ** or * when followed by word char
    .replace(/\*\*([^*]+)\*\*([a-zA-Z0-9])/g, '**$1** $2')
    .replace(/\*([^*]+)\*([a-zA-Z0-9])/g, '*$1* $2')
    // Fix concatenated bold blocks like **Requirements****Must-haves**
    .replace(/\*\*\*\*/g, '** **')
}

export function MarkdownContent({ content, className, inline = false, fallback = null }) {
  if (!content) {
    return fallback
  }

  // Configure marked for safe output
  marked.setOptions({
    breaks: true,
    gfm: true,
  })

  const processed = preprocessMarkdown(content)
  // Use parseInline for inline content (avoids wrapping in <p> tags)
  const html = inline ? marked.parseInline(processed) : marked.parse(processed)

  return (
    <span
      className={className}
      style={{ color: 'var(--text-secondary)' }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
