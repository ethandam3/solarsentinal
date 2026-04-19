/**
 * useWebSocket.js
 * Wrapper around react-use-websocket that:
 *   - Auto-reconnects on disconnect
 *   - Parses incoming JSON frames
 *   - Exposes connection state + message history
 */

import { useCallback, useState } from 'react'
import useWS, { ReadyState } from 'react-use-websocket'
import { WS_URL } from '../config.js'

const STATUS_LABELS = {
  [ReadyState.CONNECTING]:  'Connecting…',
  [ReadyState.OPEN]:        'Live',
  [ReadyState.CLOSING]:     'Closing…',
  [ReadyState.CLOSED]:      'Disconnected',
  [ReadyState.UNINSTANTIATED]: 'Not started',
}

export function useSolarWebSocket(onMessage) {
  const [messages, setMessages] = useState([])

  const handleMessage = useCallback((event) => {
    try {
      const parsed = JSON.parse(event.data)
      setMessages(prev => [parsed, ...prev].slice(0, 100))  // keep last 100
      if (onMessage) onMessage(parsed)
    } catch (e) {
      console.warn('WS parse error', e)
    }
  }, [onMessage])

  const { readyState } = useWS(WS_URL, {
    onMessage: handleMessage,
    shouldReconnect: () => true,
    reconnectAttempts: 20,
    reconnectInterval: 2000,
  })

  return {
    readyState,
    statusLabel: STATUS_LABELS[readyState],
    isLive: readyState === ReadyState.OPEN,
    messages,
  }
}
