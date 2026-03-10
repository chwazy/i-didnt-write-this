import { useState } from 'react'
import StatusBadge from './StatusBadge'
import LogDrawer from './LogDrawer'
import useStore from '@/store/useStore'
import { relativeTime, formatDuration, getModelDisplayName } from '@/lib/utils'
import { Square, ExternalLink, Clock, Trash2, RotateCw, GitBranch, AlertTriangle } from 'lucide-react'

const MERGE_LABELS = {
  pull_request: 'PR',
  auto_squash_merge: 'Auto-merge',
}

export default function TaskCard({ task }) {
  const [showLogs, setShowLogs] = useState(false)
  const killTask = useStore((s) => s.killTask)
  const deleteTask = useStore((s) => s.deleteTask)
  const retryTask = useStore((s) => s.retryTask)

  const displayTitle = task.title || (
    task.task_description.length > 50
      ? task.task_description.slice(0, 50) + '...'
      : task.task_description
  )

  const mergeLabel = MERGE_LABELS[task.merge_option]

  return (
    <>
      <div
        className="bg-card border border-border rounded-lg p-4 hover:border-input transition-colors cursor-pointer"
        onClick={() => setShowLogs(true)}
      >
        {/* Title */}
        <h3 className="text-sm font-semibold text-foreground mb-1 line-clamp-1" title={displayTitle}>
          {displayTitle}
        </h3>

        {/* Project subtitle */}
        <p className="text-xs text-muted-foreground mb-2">
          {task.project_name || `Project #${task.project_id}`}
        </p>

        {/* Metadata row */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <GitBranch className="w-3 h-3" />
            <span className="text-foreground max-w-[120px] truncate" title={task.branch_name}>{task.branch_name}</span>
          </span>
          {mergeLabel && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30">
              {mergeLabel}
            </span>
          )}
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-500/30">
            {getModelDisplayName(task.model || 'claude-sonnet-4-6', 'short')}
          </span>
          <StatusBadge status={task.status} />
          {task.warning && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/30" title={task.warning}>
              <AlertTriangle className="w-3 h-3" />
              {task.warning}
            </span>
          )}
        </div>

        {/* Task description */}
        <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
          {task.task_description}
        </p>

        {/* Footer: timing + actions */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span title={new Date(task.finished_at || task.created_at).toLocaleString()}>
              {task.finished_at
                ? `Finished ${relativeTime(task.finished_at)}`
                : `Created ${relativeTime(task.created_at)}`}
            </span>
            {(task.status === 'running' || task.finished_at) && (
              <span className="inline-flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatDuration(task.created_at, task.finished_at)}
              </span>
            )}
          </div>

          <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
            {task.pr_url && (
              <a
                href={task.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/30 hover:bg-blue-200 dark:hover:bg-blue-500/30"
              >
                <ExternalLink className="w-3 h-3" /> View PR
              </a>
            )}
            {task.status === 'running' && (
              <button
                onClick={() => killTask(task.id)}
                className="inline-flex items-center gap-1 text-xs text-red-400 hover:text-red-300"
              >
                <Square className="w-3 h-3" /> Kill
              </button>
            )}
            {(task.status === 'failed' || (task.status === 'done' && task.warning)) && (
              <button
                onClick={() => retryTask(task.id)}
                className="inline-flex items-center gap-1 text-xs text-yellow-400 hover:text-yellow-300"
              >
                <RotateCw className="w-3 h-3" /> Retry
              </button>
            )}
            {(task.status === 'done' || task.status === 'failed') && (
              <button
                onClick={() => deleteTask(task.id)}
                className="inline-flex items-center gap-1 text-xs text-red-400 hover:text-red-300"
              >
                <Trash2 className="w-3 h-3" /> Delete
              </button>
            )}
          </div>
        </div>
      </div>

      {showLogs && (
        <LogDrawer task={task} onClose={() => setShowLogs(false)} />
      )}
    </>
  )
}
