/**
 * WebSocket hook for real-time updates from the server.
 */
import { useEffect, useRef } from 'react'

export function useWebSocket(onMessage) {
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const onMessageRef = useRef(onMessage)

  // Keep ref updated with latest callback
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    const connect = () => {
      // Use relative URL - Vite proxy will handle it in dev
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws`

      try {
        wsRef.current = new WebSocket(wsUrl)

        wsRef.current.onopen = () => {
          console.log('WebSocket connected')
        }

        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            onMessageRef.current(data)
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err)
          }
        }

        wsRef.current.onclose = () => {
          console.log('WebSocket disconnected, reconnecting in 3s...')
          reconnectTimeoutRef.current = setTimeout(connect, 3000)
        }

        wsRef.current.onerror = (err) => {
          console.error('WebSocket error:', err)
          wsRef.current?.close()
        }
      } catch (err) {
        console.error('Failed to connect WebSocket:', err)
        reconnectTimeoutRef.current = setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return wsRef.current
}
