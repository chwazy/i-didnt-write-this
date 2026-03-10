import { useEffect, useState, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useStore from '../store/useStore'
import TaskCard from '../components/TaskCard'
import { RefreshCw, ChevronDown, ChevronUp, Inbox, X, PlusCircle, FolderGit2, ClipboardList } from 'lucide-react'
import { isNotificationSupported, requestNotificationPermission, sendNotification } from '@/lib/notifications'
import {
  Drawer,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerClose,
} from '../components/ui/Drawer'

const STATUS_ORDER = ['queued', 'running', 'done', 'failed']
const DEFAULT_VISIBLE = 3

export default function Dashboard() {
  const navigate = useNavigate()
  const tasks = useStore((s) => s.tasks)
  const projects = useStore((s) => s.projects)
  const settings = useStore((s) => s.settings)
  const fetchTasks = useStore((s) => s.fetchTasks)
  const fetchSettings = useStore((s) => s.fetchSettings)
  const fetchProjects = useStore((s) => s.fetchProjects)
  const [expandedCategories, setExpandedCategories] = useState({})
  const prevStatusRef = useRef(null)

  // Request notification permission on mount
  useEffect(() => {
    fetchSettings()
    fetchProjects()
  }, [fetchSettings, fetchProjects])

  useEffect(() => {
    if (settings?.notifications_enabled && isNotificationSupported()) {
      requestNotificationPermission()
    }
  }, [settings?.notifications_enabled])

  // Track task status transitions and fire notifications
  useEffect(() => {
    if (!tasks.length && prevStatusRef.current === null) return

    const prevStatuses = prevStatusRef.current
    // Initialize on first load — don't fire notifications
    if (prevStatuses === null) {
      prevStatusRef.current = Object.fromEntries(tasks.map((t) => [t.id, t.status]))
      return
    }

    for (const task of tasks) {
      const prev = prevStatuses[task.id]
      if ((task.status === 'done' || task.status === 'failed') && prev !== task.status) {
        // Resolve notification preference: project override > global setting
        const project = projects.find((p) => p.id === task.project_id)
        const enabled = project?.notifications_enabled != null
          ? project.notifications_enabled
          : settings?.notifications_enabled ?? true

        if (enabled) {
          const label = task.status === 'done' ? 'Completed' : 'Failed'
          const title = `Task ${label}: ${task.title || task.task_description}`
          sendNotification(title, {
            body: project ? `Project: ${project.name}` : undefined,
            tag: `task-${task.id}`,
          })
        }
      }
    }

    prevStatusRef.current = Object.fromEntries(tasks.map((t) => [t.id, t.status]))
  }, [tasks, projects, settings])

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 5000)
    return () => clearInterval(interval)
  }, [fetchTasks])

  const grouped = useMemo(() => {
    return STATUS_ORDER.reduce((acc, status) => {
      const filtered = tasks.filter((t) => t.status === status)
      // Sort: running/queued by created_at desc; done/failed by finished_at desc (fallback created_at)
      filtered.sort((a, b) => {
        if (status === 'done' || status === 'failed') {
          const aDate = a.finished_at || a.created_at
          const bDate = b.finished_at || b.created_at
          return new Date(bDate) - new Date(aDate)
        }
        return new Date(b.created_at) - new Date(a.created_at)
      })
      acc[status] = filtered
      return acc
    }, {})
  }, [tasks])

  const toggleCategory = (status) => {
    setExpandedCategories((prev) => ({ ...prev, [status]: !prev[status] }))
  }

  const queuedTasks = grouped['queued'] || []
  const queuedExpanded = !!expandedCategories['queued']
  const queuedVisible = queuedExpanded ? queuedTasks : queuedTasks.slice(0, DEFAULT_VISIBLE)
  const queuedHasMore = queuedTasks.length > DEFAULT_VISIBLE
  const queuedRemaining = queuedTasks.length - DEFAULT_VISIBLE

  return (
    <Drawer direction="left">
      <div>
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <div className="flex items-center gap-1">
            <DrawerTrigger asChild>
              <button
                className="flex items-center gap-1.5 p-2 text-muted-foreground hover:text-accent-foreground hover:bg-accent rounded-md"
              >
                <Inbox className="w-4 h-4" />
                {queuedTasks.length > 0 && (
                  <span className="text-xs font-medium bg-muted text-foreground rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
                    {queuedTasks.length}
                  </span>
                )}
              </button>
            </DrawerTrigger>
            <button
              onClick={fetchTasks}
              className="p-2 text-muted-foreground hover:text-accent-foreground hover:bg-accent rounded-md"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        <DrawerContent className="w-full sm:w-80 md:w-96">
          <DrawerHeader className="flex-row items-center justify-between border-b border-border">
            <DrawerTitle>Queued Tasks ({queuedTasks.length})</DrawerTitle>
            <DrawerClose asChild>
              <button className="p-1 hover:bg-accent rounded">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </DrawerClose>
          </DrawerHeader>
          <div className="flex-1 overflow-y-auto p-4">
            {queuedTasks.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No queued tasks</p>
            ) : (
              <>
                <div className="space-y-3">
                  {queuedVisible.map((task) => (
                    <TaskCard key={task.id} task={task} />
                  ))}
                </div>
                {queuedHasMore && (
                  <button
                    onClick={() => toggleCategory('queued')}
                    className="mt-3 flex items-center gap-1 text-sm text-muted-foreground hover:text-accent-foreground transition-colors"
                  >
                    {queuedExpanded ? (
                      <>
                        <ChevronUp className="w-4 h-4" />
                        Show less
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4" />
                        Show {queuedRemaining} more
                      </>
                    )}
                  </button>
                )}
              </>
            )}
          </div>
        </DrawerContent>

        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <ClipboardList className="w-12 h-12 text-gray-600 mb-4" />
            <h2 className="text-xl font-semibold text-gray-300 mb-2">No tasks yet</h2>
            <p className="text-sm text-gray-500 mb-8 max-w-sm">
              Create a task to spin up an agent, or add a project first if you haven't already.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/tasks/new')}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm text-primary-foreground bg-primary rounded-md hover:bg-primary-hover"
              >
                <PlusCircle className="w-4 h-4" />
                New Task
              </button>
              <button
                onClick={() => navigate('/projects')}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm font-medium transition-colors border border-gray-600"
              >
                <FolderGit2 className="w-4 h-4" />
                Add Project
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {STATUS_ORDER.filter((s) => s !== 'queued').map((status) => {
            const all = grouped[status]
            const isExpanded = !!expandedCategories[status]
            const hasMore = all.length > DEFAULT_VISIBLE
            const visible = isExpanded ? all : all.slice(0, DEFAULT_VISIBLE)
            const remaining = all.length - DEFAULT_VISIBLE

            return (
              <div key={status}>
                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                  {status} ({all.length})
                </h2>
                <div className="space-y-3">
                  {visible.map((task) => (
                    <TaskCard key={task.id} task={task} />
                  ))}
                </div>
                {hasMore && (
                  <button
                    onClick={() => toggleCategory(status)}
                    className="mt-3 flex items-center gap-1 text-sm text-muted-foreground hover:text-accent-foreground transition-colors"
                  >
                    {isExpanded ? (
                      <>
                        <ChevronUp className="w-4 h-4" />
                        Show less
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4" />
                        Show {remaining} more
                      </>
                    )}
                  </button>
                )}
              </div>
            )
          })}
          </div>
        )}
      </div>
    </Drawer>
  )
}
