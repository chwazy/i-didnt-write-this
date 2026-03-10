export function connectTaskLogs(taskId, onMessage, onClose) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const ws = new WebSocket(`${protocol}//${host}/ws/tasks/${taskId}/logs`)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onMessage(data)
  }

  ws.onclose = () => {
    if (onClose) onClose()
  }

  ws.onerror = (err) => {
    console.error('WebSocket error:', err)
  }

  return () => ws.close()
}
