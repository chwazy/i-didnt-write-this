import { useEffect, useState, useRef } from 'react'
import { connectTaskLogs } from '@/lib/websocket'
import { api } from '@/lib/api'
import StatusBadge from './StatusBadge'
import { getModelDisplayName } from '@/lib/utils'
import { X, GitBranch } from 'lucide-react'

const MERGE_LABELS = {
  pull_request: 'Pull Request',
  auto_squash_merge: 'Auto Squash Merge',
}

export default function LogDrawer({ task, onClose }) {
  const [logs, setLogs] = useState([])
  const [connected, setConnected] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    // Load existing logs first
    api.getTaskLogs(task.id).then((existingLogs) => {
      setLogs(existingLogs)
    })

    // Then connect WebSocket for live updates
    if (task.status === 'running' || task.status === 'queued') {
      const disconnect = connectTaskLogs(
        task.id,
        (data) => {
          if (data.type === 'done') {
            setConnected(false)
            return
          }
          setLogs((prev) => {
            if (prev.some((l) => l.id === data.id)) return prev
            return [...prev, data]
          })
        },
        () => setConnected(false),
      )
      setConnected(true)
      return disconnect
    }
  }, [task.id, task.status])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  const displayTitle = task.title || `Task #${task.id}`
  const mergeLabel = MERGE_LABELS[task.merge_option]

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full sm:max-w-2xl bg-background border-l border-border flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">{displayTitle}</h2>
            <StatusBadge status={task.status} />
            {connected && (
              <span className="flex items-center gap-1 text-xs text-green-400">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                Live
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-1 hover:bg-accent rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Task details */}
        <div className="px-4 py-3 border-b border-border space-y-2">
          <p className="text-sm text-foreground">{task.task_description}</p>
          <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
            <span>{task.project_name || `Project #${task.project_id}`}</span>
            <span className="inline-flex items-center gap-1 truncate max-w-[200px]">
              <GitBranch className="w-3 h-3 shrink-0" />
              <span className="truncate">{task.branch_name}</span>
            </span>
            {mergeLabel && (
              <span className="text-indigo-400">{mergeLabel}</span>
            )}
            {task.model && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground border border-border">
                {getModelDisplayName(task.model, 'short')}
              </span>
            )}
          </div>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 font-mono text-xs">
          {logs.length === 0 ? (
            <p className="text-muted-foreground">No logs yet...</p>
          ) : (
            logs.map((log, i) => (
              <div key={log.id || i} className="py-0.5 text-foreground whitespace-pre-wrap break-all">
                <span className="text-muted-foreground mr-2 select-none">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                {log.line}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
